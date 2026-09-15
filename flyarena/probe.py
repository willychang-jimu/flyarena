"""訊號反應測試：果蠅對特定訊號會不會做出「正確」反應。

1. conditioning：比照果蠅「氣味 + 電擊」的經典制約實驗。
   用人工合成的市場狀態當作氣味（多頭、空頭、盤整），規定正確反應，
   前測 → 訓練（對就獎勵、錯就懲罰）→ 每個區塊後測 → 規則反轉（測學習彈性）。
   有學習能力的大腦正確率應該上升、反轉後先下降再回升；凍結的大腦不應該改變。
2. tuning：固定其他特徵，只改變一個特徵，看果蠅選 BUY/HOLD/SELL 的機率怎麼變，
   得到「這隻果蠅對哪些訊號有反應」的反應曲線。
所有量測都在大腦的複製品上做，量測本身不會改變果蠅的記憶。
"""

import numpy as np

from . import senses
from .brains import BUY, HOLD, SELL

PATTERNS = {
    "多頭": {"ret_5": 1.5, "ret_20": 1.5, "ma_20": 1.5, "range_20": 1.2},
    "空頭": {"ret_5": -1.5, "ret_20": -1.5, "ma_20": -1.5, "range_20": -1.2},
    "盤整": {},
}
RULE = {"多頭": BUY, "空頭": SELL, "盤整": HOLD}
REVERSED = {"多頭": SELL, "空頭": BUY, "盤整": HOLD}


def stimulus(names, pattern, rng, noise=0.3):
    z = rng.normal(0, noise, len(names))
    for k, v in pattern.items():
        z[names.index(k)] += v
    return senses.encode(z)


def _measuring_copy(brain):
    """量測用複製品：關掉權重回復，避免上千次量測決策把記憶洗回基準。"""
    probe = brain.clone()
    if hasattr(probe, "params"):
        probe.params = dict(probe.params, weight_recovery=0.0)
    return probe


def accuracy(brain, names, rule, rng, trials=40):
    probe = _measuring_copy(brain)
    result = {}
    for p, correct in rule.items():
        hits = sum(
            probe.decide(stimulus(names, PATTERNS[p], rng), rng)[0] == correct
            for _ in range(trials)
        )
        result[p] = hits / trials
    result["平均"] = float(np.mean(list(result.values())))
    return result


def _train(brain, names, rule, rng, trials):
    patterns = list(rule)
    for _ in range(trials):
        p = patterns[rng.integers(len(patterns))]
        action, info = brain.decide(stimulus(names, PATTERNS[p], rng), rng)
        brain.reinforce(1.0 if action == rule[p] else -1.0, tag=info.get("tag"))


def conditioning(brain, names, seed=0, blocks=8, trials=30, reversal_blocks=8):
    rng = np.random.default_rng(seed)
    curve = [("前測", accuracy(brain, names, RULE, rng))]
    for b in range(blocks):
        _train(brain, names, RULE, rng, trials)
        curve.append((f"訓練 {b + 1}", accuracy(brain, names, RULE, rng)))
    for b in range(reversal_blocks):
        _train(brain, names, REVERSED, rng, trials)
        curve.append((f"反轉 {b + 1}", accuracy(brain, names, REVERSED, rng)))
    return curve


def tuning(brain, names, seed=0, values=np.linspace(-2, 2, 9), trials=30):
    """每列：(特徵值, P(BUY), P(HOLD), P(SELL), 傾向)。
    傾向 = BUY 輸出神經元減 SELL 輸出神經元的平均值（不含探索雜訊）；
    沒有 MBON 的大腦改用 P(BUY) - P(SELL)。"""
    rng = np.random.default_rng(seed)
    probe = _measuring_copy(brain)
    out = {}
    for name in names:
        rows = []
        for v in values:
            counts = {BUY: 0, HOLD: 0, SELL: 0}
            lean = []
            for _ in range(trials):
                action, info = probe.decide(stimulus(names, {name: v}, rng), rng)
                counts[action] += 1
                if "mbon" in info:
                    lean.append(info["mbon"][0] - info["mbon"][2])
            b, h, s = (counts[x] / trials for x in (BUY, HOLD, SELL))
            rows.append((float(v), b, h, s, float(np.mean(lean)) if lean else b - s))
        out[name] = rows
    return out


def sensitivity(tuning_result):
    """每個特徵的反應強度：傾向值在整個掃描範圍內的變化幅度。凍結（未學習）的大腦應接近 0。"""
    score = {}
    for name, rows in tuning_result.items():
        lean = [r[4] for r in rows]
        score[name] = float(max(lean) - min(lean))
    return dict(sorted(score.items(), key=lambda kv: -kv[1]))
