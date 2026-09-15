"""台股模擬券商。只做模擬，不連任何券商帳戶。

- 第 t 天收盤後決策，第 t+1 天開盤價成交（不偷看未來）。
- 手續費 = 成交金額 × 費率 × 折扣，有最低手續費；賣出另收證交稅（ETF 0.1%）。
- 不融資、不放空，現金不足或無庫存時該筆委託被拒絕。
- 使用還原股價，股數與最低手續費是近似值；未模擬漲跌停鎖死買不到、流動性與滑價。
"""

import math
from dataclasses import asdict, dataclass

from .brains import BUY, SELL


@dataclass
class Fill:
    date: str
    symbol: str
    side: str
    shares: int
    price: float
    value: float
    fee: float
    tax: float


class Broker:
    def __init__(self, cfg):
        self.c = cfg
        self.cash = float(cfg["capital"])
        self.positions = {}
        self.fills = []
        self.costs = 0.0

    def _fee(self, value, shares):
        odd = shares % 1000 != 0
        minimum = self.c["min_fee_odd_lot"] if odd else self.c["min_fee"]
        return max(value * self.c["fee_rate"] * self.c["fee_discount"], minimum)

    def _tax_rate(self, symbol):
        return self.c["etf_tax_rate"] if symbol.startswith("00") else self.c["tax_rate"]

    def _round(self, shares):
        lot = 1 if self.c["odd_lot"] else 1000
        return int(math.floor(shares / lot) * lot)

    def execute(self, date, symbol, action, price):
        """回傳 (Fill 或 None, 說明)。"""
        held = self.positions.get(symbol, 0)
        if action == BUY:
            room = self.c["max_position_value"] - held * price
            budget = min(self.c["order_value"], room, self.cash)
            shares = self._round(budget / price)
            while shares > 0:
                value = shares * price
                fee = self._fee(value, shares)
                if value + fee <= self.cash:
                    break
                shares = self._round(shares - (1 if self.c["odd_lot"] else 1000))
            if shares <= 0:
                return None, "現金不足或已達部位上限"
            self.cash -= value + fee
            self.positions[symbol] = held + shares
            fill = Fill(str(date), symbol, "BUY", shares, price, value, fee, 0.0)
        elif action == SELL:
            shares = min(held, self._round(self.c["order_value"] / price) or held)
            shares = shares if self.c["odd_lot"] or shares == held else self._round(shares)
            if shares <= 0:
                return None, "沒有庫存"
            value = shares * price
            fee = self._fee(value, shares)
            tax = value * self._tax_rate(symbol)
            self.cash += value - fee - tax
            self.positions[symbol] = held - shares
            fill = Fill(str(date), symbol, "SELL", shares, price, value, fee, tax)
        else:
            return None, "HOLD"
        self.costs += fill.fee + fill.tax
        self.fills.append(fill)
        return fill, "成交"

    def equity(self, prices):
        return self.cash + sum(
            n * prices[s] for s, n in self.positions.items() if n and s in prices
        )

    def state(self):
        return {
            "cash": self.cash,
            "positions": dict(self.positions),
            "costs": self.costs,
            "fills": [asdict(f) for f in self.fills],
        }

    def load_state(self, s):
        self.cash = s["cash"]
        self.positions = dict(s["positions"])
        self.costs = s["costs"]
        self.fills = [Fill(**f) for f in s["fills"]]
