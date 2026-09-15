"""大腦工廠：依設定或存檔建立大腦。新增大腦種類（例如真實接線版）時只要在這裡註冊。"""

from dataclasses import dataclass

import numpy as np

from .base import ACTION_NAMES, BUY, HOLD, SELL, Brain
from .controls import BuyHoldBrain, MomentumBrain, RandomBrain
from .mushroom import MushroomBrain


@dataclass
class Observation:
    date: object
    symbol: str
    pn: np.ndarray  # 感覺輸入（PN 發放率）
    z: np.ndarray  # 標準化特徵（規則型對照組使用）
    names: list


def make_brain(kind, n_pn, cfg=None, seed=0):
    cfg = dict(cfg or {})
    cfg.pop("kind", None)
    if kind == "mushroom":
        return MushroomBrain(n_pn, seed=seed, **cfg)
    if kind == "random":
        return RandomBrain(seed=seed)
    if kind == "buyhold":
        return BuyHoldBrain()
    if kind == "momentum":
        return MomentumBrain(**cfg)
    raise ValueError(f"未知的大腦種類：{kind}")


def from_state(state):
    kind = state["kind"]
    if kind == "mushroom":
        brain = MushroomBrain(state["n_pn"], n_kc=1, pn_per_kc=1)
        brain.load_state(state)
        return brain
    if kind == "random":
        p = state["p"]
        return RandomBrain(p[0], p[2], state["seed"])
    if kind == "buyhold":
        return BuyHoldBrain()
    if kind == "momentum":
        return MomentumBrain(state["threshold"])
    raise ValueError(f"未知的大腦種類：{kind}")
