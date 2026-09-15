"""獎懲機制：決定什麼時候、用多強的訊號去刺激多巴胺。

模式
- equity_binary       ：比照 stonkfly，每天總資產漲就獎勵、跌就懲罰，強度固定。
- equity_proportional ：同上，但強度依漲跌幅大小。
- action_contingent   ：只針對「那一次決策」結算：horizon 天後看方向對不對、扣掉交易成本。
                        HOLD 在波動小於成本時算對，錯過大行情算錯。
- shuffled            ：和 action_contingent 同樣的強度分布，但正負號隨機 → 破壞因果的對照組。
- none                ：完全不給獎懲。
SELL 在沒有庫存時雖然不會成交，仍當作「看空」的判斷來結算，衡量的是訊號本身。
"""

import numpy as np

from .brains import BUY, HOLD, SELL

MODES = ("equity_binary", "equity_proportional", "action_contingent", "shuffled", "none")


class RewardSystem:
    def __init__(self, cfg, seed=0):
        self.mode = cfg.get("mode", "action_contingent")
        if self.mode not in MODES:
            raise ValueError(f"未知的獎懲模式：{self.mode}")
        self.horizon = int(cfg.get("horizon_days", 5))
        self.deadband = float(cfg.get("deadband", 0.002))
        self.scale = float(cfg.get("scale", 0.03))  # 3% 的結果 = 最強刺激
        self.cost = float(cfg.get("cost", 0.004))  # 來回交易成本的近似
        self.rng = np.random.default_rng(seed)
        self.pending = []

    def on_decision(self, day, symbol, action, entry_price, tag):
        if self.mode in ("action_contingent", "shuffled"):
            self.pending.append((day + self.horizon, symbol, action, entry_price, tag))

    def _contingent(self, action, ret):
        if action == HOLD:
            edge = self.cost - abs(ret)
        else:
            edge = action * ret - self.cost
        if abs(edge) < self.deadband:
            return 0.0
        return float(np.clip(edge / self.scale, -1, 1))

    def on_day(self, day, closes, equity_before, equity_now):
        """每天收盤後呼叫。回傳 [(強度, tag), ...]；tag=None 代表作用在資格痕跡上。"""
        if self.mode == "none":
            return []
        if self.mode.startswith("equity"):
            if not equity_before:
                return []
            change = equity_now / equity_before - 1
            if abs(change) < self.deadband / 10:
                return []
            if self.mode == "equity_binary":
                return [(float(np.sign(change)), None)]
            return [(float(np.clip(change / (self.scale / 10), -1, 1)), None)]
        due = [p for p in self.pending if p[0] <= day and p[1] in closes]
        self.pending = [p for p in self.pending if p not in due]
        out = []
        for _, symbol, action, entry, tag in due:
            value = self._contingent(action, float(np.log(closes[symbol] / entry)))
            if self.mode == "shuffled":
                value *= self.rng.choice((-1.0, 1.0))
            if value:
                out.append((value, (symbol, tag)))
        return out

    def outcome(self, action, entry, exit_price):
        """給分析用：這次判斷事後看對不對（不含隨機化）。"""
        return self._contingent(action, float(np.log(exit_price / entry)))
