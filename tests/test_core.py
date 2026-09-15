"""核心正確性測試：全部使用合成資料，不需要網路。"""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flyarena import backtest, data, league, probe
from flyarena.brains import BUY, HOLD, SELL, Brain, make_brain
from flyarena.market import Broker
from flyarena.rewards import RewardSystem

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "arena.json").read_text(encoding="utf-8"))


def config():
    cfg = copy.deepcopy(CFG)
    cfg["symbols"] = ["1111.TW", "0099.TW"]
    cfg["benchmark"] = "^TEST"
    return cfg


def frames(n=420, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.DatetimeIndex(pd.bdate_range("2020-01-01", periods=n), name="date")
    out = {}
    for s in ["1111.TW", "0099.TW", "^TEST"]:
        close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
        open_ = close * np.exp(rng.normal(0, 0.003, n))
        out[s] = pd.DataFrame(
            {"open": open_, "high": np.maximum(open_, close) * 1.004,
             "low": np.minimum(open_, close) * 0.996, "close": close, "volume": 1e6},
            index=dates,
        )
    return out


def test_clean_stitches_impossible_jump():
    df = frames()["1111.TW"]
    df.loc[df.index[200]:, ["open", "high", "low", "close"]] *= 4
    fixed = data.clean(df)
    assert fixed.close.pct_change().abs().max() < 0.105
    assert fixed.attrs["breaks"] == 1


def test_broker_fees_tax_and_inventory():
    b = Broker(CFG["broker"])
    buy, _ = b.execute("d", "2330.TW", BUY, 100.0)
    assert buy.shares == 1000
    assert buy.fee == pytest.approx(100000 * 0.001425 * 0.6)
    sell, _ = b.execute("d", "2330.TW", SELL, 110.0)
    assert sell.shares == 909  # 單筆上限 10 萬
    assert sell.tax == pytest.approx(sell.value * 0.003)
    assert b.execute("d", "2330.TW", SELL, 110.0)[0].shares == 91
    assert b.execute("d", "2330.TW", SELL, 110.0)[0] is None  # 不能放空

    etf = Broker(CFG["broker"])
    etf.execute("d", "0050.TW", BUY, 100.0)
    assert etf.execute("d", "0050.TW", SELL, 100.0)[0].tax == pytest.approx(100000 * 0.001)


class OnceBuyer(Brain):
    kind = "once"

    def __init__(self):
        self.done = False

    def decide(self, obs, rng):
        if self.done or obs.symbol != "1111.TW":
            return HOLD, {}
        self.done = True
        return BUY, {}


def test_orders_fill_at_next_open():
    cfg, fr = config(), frames()
    m = backtest.Market(fr, cfg)
    days = m.days()
    first = next(d for d in days if d in m.rows["1111.TW"])
    i = days.index(first)
    t = backtest.Trader("t", OnceBuyer(), cfg)
    backtest.run([t], m, cfg, first, days[i + 3])
    fill = t.broker.fills[0]
    assert fill.date == str(days[i + 1].date())
    assert fill.price == pytest.approx(fr["1111.TW"].open[days[i + 1]])


def test_action_contingent_reward_timing():
    r = RewardSystem({"mode": "action_contingent", "horizon_days": 2, "cost": 0.004, "scale": 0.03})
    assert r.outcome(BUY, 100, 105) > 0 > r.outcome(SELL, 100, 105)
    assert r.outcome(HOLD, 100, 100.1) > 0 > r.outcome(HOLD, 100, 110)
    r.on_decision(0, "X", BUY, 100.0, "tag")
    assert r.on_day(1, {"X": 110.0}, 1, 1) == []
    ((value, (symbol, tag)),) = r.on_day(2, {"X": 110.0}, 1, 1)
    assert value > 0 and symbol == "X" and tag == "tag"


def test_learning_brain_beats_frozen_in_conditioning():
    names = backtest.Market(frames(), config()).names
    n_pn = len(names) * 5
    learned = make_brain("mushroom", n_pn, CFG["brain"], 1)
    frozen = make_brain("mushroom", n_pn, dict(CFG["brain"], frozen=True), 1)
    a = probe.conditioning(learned, names, seed=0, reversal_blocks=0)[-1][1]["平均"]
    b = probe.conditioning(frozen, names, seed=0, reversal_blocks=0)[-1][1]["平均"]
    assert a > 0.9 and b < 0.5
    assert max(probe.sensitivity(probe.tuning(frozen, names, trials=5)).values()) == 0


def test_league_replay_is_deterministic(tmp_path, monkeypatch):
    cfg, fr = config(), frames()
    monkeypatch.setattr(league, "LEAGUES", tmp_path)
    monkeypatch.setattr(league.data, "load_all", lambda c, refresh=False: fr)
    m = backtest.Market(fr, cfg)
    entries = [(f"fly-{i}", make_brain("mushroom", m.n_pn, cfg["brain"], i), {"generation": 0})
               for i in range(5)]
    league.create("t", cfg, entries, str(m.calendar[300].date()), 20, 1, 3)
    a = league.snapshot(league.replay("t"))
    b = league.snapshot(league.replay("t"))
    assert [(r["name"], r["equity"]) for r in a["rows"]] == [(r["name"], r["equity"]) for r in b["rows"]]
    assert len(a["eliminated"]) == 2
