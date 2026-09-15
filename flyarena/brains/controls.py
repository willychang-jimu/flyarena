"""對照組大腦。果蠅要贏過這些，才算有東西可以研究。"""

import numpy as np

from .base import BUY, HOLD, SELL, Brain


class RandomBrain(Brain):
    """每天隨機買、賣或不動：檢查成績是不是運氣。"""

    kind = "random"

    def __init__(self, p_buy=1 / 3, p_sell=1 / 3, seed=0):
        self.p = (p_buy, 1 - p_buy - p_sell, p_sell)
        self.seed = seed

    def decide(self, obs, rng):
        return (BUY, HOLD, SELL)[rng.choice(3, p=self.p)], {}

    def state(self):
        return {"kind": self.kind, "p": list(self.p), "seed": self.seed}


class BuyHoldBrain(Brain):
    """一直買到部位上限後持有：大盤上漲時任何「偏多」的交易員都會像高手。"""

    kind = "buyhold"

    def decide(self, obs, rng):
        return BUY, {}

    def state(self):
        return {"kind": self.kind}


class MomentumBrain(Brain):
    """簡單動能規則：20 日報酬與均線乖離都偏強就買，都偏弱就賣。"""

    kind = "momentum"

    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def decide(self, obs, rng):
        z = dict(zip(obs.names, obs.z))
        score = (z["ret_20"] + z["ma_20"]) / 2
        if score > self.threshold:
            return BUY, {"score": round(float(score), 3)}
        if score < -self.threshold:
            return SELL, {"score": round(float(score), 3)}
        return HOLD, {"score": round(float(score), 3)}

    def state(self):
        return {"kind": self.kind, "threshold": self.threshold}
