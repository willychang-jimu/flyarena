"""回測引擎：一群果蠅交易員在同一段行情上逐日交易。

每個交易日的順序（避免偷看未來）：
  1. 開盤：執行前一個交易日收盤後下的委託，成交價 = 當天開盤價
  2. 收盤：以收盤價計算資產，發放到期的獎懲（刺激多巴胺）
  3. 收盤後：每隔 trade_every_days 天，對每檔股票做決策，委託留到下個交易日開盤
"""

import numpy as np
import pandas as pd

from . import senses
from .brains import BUY, HOLD, SELL, Observation
from .market import Broker
from .rewards import RewardSystem


class Market:
    """整理好的行情與感覺輸入，所有交易員共用。"""

    def __init__(self, frames, cfg):
        bench = frames[cfg["benchmark"]]
        self.symbols = list(cfg["symbols"])
        self.horizon = int(cfg["reward"].get("horizon_days", 5))
        self.open, self.close, self.rows, self.pn, self.z, self.fwd = {}, {}, {}, {}, {}, {}
        calendar = set()
        for s in self.symbols:
            df = frames[s]
            z, pn = senses.sensory_frame(df, bench)
            self.names = list(z.columns)
            self.rows[s] = {d: i for i, d in enumerate(z.index)}
            self.z[s], self.pn[s] = z.to_numpy(), pn
            self.open[s] = df.open.to_dict()
            self.close[s] = df.close.to_dict()
            # 決策日 t 的前瞻報酬：t+1 開盤買進，t+horizon 收盤結算
            fwd = np.log(df.close.shift(-self.horizon) / df.open.shift(-1))
            self.fwd[s] = fwd.to_dict()
            calendar.update(df.index)
        self.calendar = sorted(calendar)
        # 全域交易日編號：分段執行（聯賽每季一段）時，獎懲到期日與交易頻率仍然一致
        self.day_index = {d: i for i, d in enumerate(self.calendar)}
        self.bench = bench.close
        self.n_pn = pn.shape[1]

    def days(self, start=None, end=None):
        start = pd.Timestamp(start) if start else self.calendar[0]
        end = pd.Timestamp(end) if end else self.calendar[-1]
        return [d for d in self.calendar if start <= d <= end]


class Trader:
    def __init__(self, name, brain, cfg, seed=0, meta=None):
        self.name = name
        self.brain = brain
        self.broker = Broker(cfg["broker"])
        self.rewards = RewardSystem(cfg["reward"], seed)
        self.rng = np.random.default_rng(seed)
        self.meta = dict(meta or {})
        self.orders = []
        self.marks = {}
        self.curve = []
        self.journal = []
        self.last_equity = self.broker.cash
        self.reward_count = {"reward": 0, "punish": 0}
        self.reward_log = []

    def reset_account(self, cfg):
        """換一段新行情（例如淘汰賽下一回合）：帳戶重置，大腦記憶保留。"""
        self.broker = Broker(cfg["broker"])
        self.rewards.pending = []
        self.orders, self.marks, self.curve, self.journal = [], {}, [], []
        self.last_equity = self.broker.cash
        self.reward_count = {"reward": 0, "punish": 0}
        self.reward_log = []
        self.brain.new_episode()


def select_orders(trader, orders, max_buys):
    """每日買進上限：只執行「最想買」（conviction 最高）的前 max_buys 檔 BUY；
    SELL 只有持股時才算入選。沒入選的判斷不下單，但仍會結算獎懲，果蠅照樣從中學習。
    已達單檔部位上限或現金不足的股票買不下去，不佔名額，改由下一檔遞補。"""
    broker = trader.broker

    def can_buy(symbol):
        held = broker.positions.get(symbol, 0) * trader.marks.get(symbol, 0.0)
        return broker.cash >= 1000 and held < broker.c["max_position_value"] * 0.98

    buys = [o for o in orders if o[1] == BUY]
    for o in buys:
        o[3]["selected"] = False
    eligible = [o for o in buys if can_buy(o[0])]
    score = {id(o): o[3]["conviction"] if "conviction" in o[3] else trader.rng.random() for o in eligible}
    for o in sorted(eligible, key=lambda o: -score[id(o)])[:max_buys]:
        o[3]["selected"] = True
    for o in orders:
        if o[1] == SELL:
            o[3]["selected"] = trader.broker.positions.get(o[0], 0) > 0


def run(traders, market, cfg, start=None, end=None, learn=True):
    days = market.days(start, end)
    every = max(1, int(cfg["broker"]["trade_every_days"]))
    max_buys = cfg["broker"].get("max_buys_per_day")
    for d in days:
        k = market.day_index[d]
        opens = {s: market.open[s][d] for s in market.symbols if d in market.open[s]}
        closes = {s: market.close[s][d] for s in market.symbols if d in market.close[s]}
        for t in traders:
            waiting = []
            for s, action, tag, entry in t.orders:
                if s not in opens:
                    waiting.append((s, action, tag, entry))  # 該檔今天沒開盤，順延
                    continue
                if entry.get("selected", True):
                    fill, note = t.broker.execute(d.date(), s, action, opens[s])
                else:
                    fill, note = None, "未入選（超過每日買進上限或沒有庫存）"
                t.rewards.on_decision(k, s, action, opens[s], tag)
                entry.update(filled=fill is not None, note=note, price=round(opens[s], 4))
            t.orders = waiting

            t.marks.update(closes)
            equity = t.broker.equity(t.marks)
            for value, tag in t.rewards.on_day(k, closes, t.last_equity, equity):
                if learn:
                    t.brain.reinforce(value, tag=None if tag is None else tag[1])
                t.reward_count["reward" if value > 0 else "punish"] += 1
                t.reward_log.append((d, round(value, 3), None if tag is None else tag[0]))
            t.curve.append((d, equity))
            t.last_equity = equity

            if k % every:
                continue
            new_orders = []
            for s in market.symbols:
                row = market.rows[s].get(d)
                if row is None:
                    continue
                obs = Observation(d, s, market.pn[s][row], market.z[s][row], market.names)
                action, info = t.brain.decide(obs, t.rng)
                tag = info.pop("tag", None)
                entry = {"date": d, "symbol": s, "action": action, **info}
                t.journal.append(entry)
                if action != HOLD:
                    new_orders.append((s, action, tag, entry))
            if max_buys is not None:
                select_orders(t, new_orders, int(max_buys))
            t.orders.extend(new_orders)
    return traders
