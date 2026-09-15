"""輕量蘑菇體模型（果蠅學習與記憶的核心迴路的簡化版）。

PN（感覺輸入）→ KC（Kenyon 細胞，大量、稀疏）→ MBON（輸出神經元）
- 每顆 KC 隨機接少數幾顆 PN（真實果蠅約 6~7 顆）。這組接線是這隻果蠅的「基因」。
- APL 側抑制讓每天只有少數 KC 活化（稀疏編碼），不同市場狀態會啟動不同的 KC 組合。
- 三顆 MBON 分別代表 BUY / HOLD / SELL，輸出最大者勝出（加少量探索雜訊）。
- 多巴胺只改 KC→MBON 權重，比照果蠅「活化的 KC 遇到多巴胺 → 突觸被壓低」：
    懲罰（類 PPL1）：壓低「剛做的動作」那顆 MBON 對這批 KC 的權重 → 下次較不會這樣做
    獎勵（類 PAM） ：壓低「其他動作」MBON 對這批 KC 的權重     → 相對偏好剛做的動作
這是抽象化的計算模型，不是果蠅生理的精確重現。
"""

import numpy as np

from .base import BUY, HOLD, SELL, Brain

ACTIONS = (BUY, HOLD, SELL)

# 淘汰賽突變時可以變動的參數與範圍
MUTABLE = {
    "learning_rate": (1e-4, 0.5),
    "trace_decay": (0.0, 0.95),
    "kc_sparsity": (0.01, 0.2),
    "exploration": (0.0, 0.3),
    "weight_recovery": (0.0, 0.05),
}


class MushroomBrain(Brain):
    kind = "mushroom"
    learns = True

    def __init__(
        self,
        n_pn,
        n_kc=2000,
        pn_per_kc=7,
        kc_sparsity=0.05,
        learning_rate=0.05,
        trace_decay=0.6,
        weight_recovery=0.002,
        exploration=0.05,
        frozen=False,
        seed=0,
    ):
        rng = np.random.default_rng(seed)
        self.n_pn, self.n_kc, self.pn_per_kc = n_pn, n_kc, pn_per_kc
        self.params = {
            "kc_sparsity": kc_sparsity,
            "learning_rate": learning_rate,
            "trace_decay": trace_decay,
            "weight_recovery": weight_recovery,
            "exploration": exploration,
        }
        self.frozen = frozen
        self.seed = seed
        self.wiring = np.stack(
            [rng.choice(n_pn, pn_per_kc, replace=False) for _ in range(n_kc)]
        )
        self.W = np.ones((3, n_kc))
        self.trace = np.zeros((3, n_kc))

    def kc_response(self, pn):
        drive = np.asarray(pn)[self.wiring].sum(axis=1)
        k = max(1, int(round(self.params["kc_sparsity"] * self.n_kc)))
        return np.argpartition(drive, -k)[-k:]  # APL 抑制後仍活化的 KC

    def decide(self, obs, rng):
        active = self.kc_response(getattr(obs, "pn", obs))
        p = self.params
        if p["weight_recovery"]:
            self.W += p["weight_recovery"] * (1.0 - self.W)  # 記憶緩慢回到基準
        mbon = self.W[:, active].mean(axis=1)
        i = int(np.argmax(mbon + rng.normal(0, p["exploration"], 3)))
        self.trace *= p["trace_decay"]
        self.trace[i, active] += 1.0
        info = {
            "mbon": [round(float(x), 4) for x in mbon],
            "kc_active": int(len(active)),
            "tag": (i, active),
        }
        return ACTIONS[i], info

    def reinforce(self, value, tag=None):
        """tag=None 用資格痕跡（最近幾天的動作）；給 tag 則只作用在那一次決策。"""
        if self.frozen or not value:
            return
        v = float(np.clip(value, -1.0, 1.0))
        if tag is None:
            elig = self.trace
        else:
            i, active = tag
            elig = np.zeros_like(self.W)
            elig[i, active] = 1.0
        lr = self.params["learning_rate"]
        if v < 0:
            self.W -= lr * -v * elig
        else:
            self.W -= lr * v * (elig.sum(axis=0, keepdims=True) - elig)
        np.clip(self.W, 0.0, 2.0, out=self.W)

    def new_episode(self):
        self.trace[:] = 0.0

    def memory_change(self):
        """權重偏離出生時基準的程度，用來觀察學到多少。"""
        return float(np.abs(self.W - 1.0).mean())

    def state(self):
        return {
            "kind": self.kind,
            "n_pn": self.n_pn,
            "n_kc": self.n_kc,
            "pn_per_kc": self.pn_per_kc,
            "params": dict(self.params),
            "frozen": self.frozen,
            "seed": self.seed,
            "wiring": self.wiring,
            "W": self.W,
        }

    def load_state(self, s):
        self.n_pn, self.n_kc, self.pn_per_kc = s["n_pn"], s["n_kc"], s["pn_per_kc"]
        self.params = dict(s["params"])
        self.frozen, self.seed = s["frozen"], s["seed"]
        self.wiring = np.asarray(s["wiring"])
        self.W = np.asarray(s["W"], dtype=np.float64).copy()
        self.trace = np.zeros_like(self.W)

    def mutate(self, rng, scale):
        """子代：參數小幅突變、少量 KC 重新接線；記憶（W）不遺傳，出生時歸零。"""
        child = self.clone()
        for name, (lo, hi) in MUTABLE.items():
            x = child.params[name] * np.exp(rng.normal(0, scale))
            x += rng.normal(0, scale * 0.01 * (hi - lo))
            child.params[name] = float(np.clip(x, lo, hi))
        rewire = rng.choice(self.n_kc, int(scale * 0.1 * self.n_kc), replace=False)
        for k in rewire:
            child.wiring[k] = rng.choice(self.n_pn, self.pn_per_kc, replace=False)
        child.W = np.ones_like(self.W)
        child.trace = np.zeros_like(self.W)
        child.seed = int(rng.integers(1 << 31))
        return child
