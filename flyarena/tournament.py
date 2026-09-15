"""淘汰賽：一群果蠅在訓練期分回合比賽，每回合淘汰最後幾名，由前幾名繁殖（突變）補位。
記憶會跟著同一隻果蠅進入下一回合；子代繼承接線與參數，但記憶從零開始。

注意：訓練期選出的冠軍可能只是運氣好（過度配適）。所以最後一定要在「沒比過的測試期」
和以下對照組一起驗證，名次才有研究意義：
- 冠軍（測試期繼續學習）
- 冠軍・凍結        ：保留記憶但不再學習
- 冠軍・失憶        ：同樣的接線與參數，記憶清空且凍結 → 若和「凍結」差不多，代表記憶沒用
- 冠軍・亂獎懲雙胞胎：同樣基因從零開始，訓練期用打亂的獎懲 → 若一樣好，代表學到的不是因果
- 隨機、買進持有、動能規則
"""

import numpy as np
import pandas as pd

from . import backtest, metrics
from .brains import make_brain
from .brains.mushroom import MUTABLE

SCORES = ("sharpe", "return", "hit_rate", "calmar")


def score(perf, sig, kind):
    if not perf:
        return float("-inf")
    if kind == "calmar":
        return perf["cagr"] / max(abs(perf["max_drawdown"]), 0.01)
    if kind == "hit_rate":
        v = sig["hit_rate"]
        return v if np.isfinite(v) else 0.0
    return perf[kind]


def row(trader, market, cfg, kind):
    perf = metrics.performance(trader, cfg["broker"]["capital"])
    sig = metrics.signal_quality(trader, market)
    return {
        "name": trader.name,
        "kind": trader.brain.kind,
        "meta": trader.meta,
        "score": score(perf, sig, kind),
        **perf,
        **sig,
        "rewards": trader.reward_count["reward"],
        "punishments": trader.reward_count["punish"],
        "memory": getattr(trader.brain, "memory_change", lambda: 0.0)(),
        "params": getattr(trader.brain, "params", {}),
    }


def controls(market, cfg, seed):
    return [
        backtest.Trader(k, make_brain(k, market.n_pn, None, seed), cfg, seed, {"control": True})
        for k in ("random", "buyhold", "momentum")
    ]


def spawn(cfg, market, rng):
    T, base = cfg["tournament"], dict(cfg["brain"])
    flies = []
    for i in range(T["population"]):
        seed = int(rng.integers(1 << 31))
        brain = make_brain("mushroom", market.n_pn, base, seed)
        if i:  # 第 0 隻用設定檔原始參數，其餘在附近隨機分布，增加族群多樣性
            for name, (lo, hi) in MUTABLE.items():
                brain.params[name] = float(
                    np.clip(brain.params[name] * np.exp(rng.normal(0, T["mutation"] * 2)), lo, hi)
                )
        meta = {"generation": 0, "parent": None, "born_round": 0}
        flies.append(backtest.Trader(f"fly-{i:03d}", brain, cfg, seed, meta))
    return flies


def split(days, n):
    chunks = np.array_split(np.arange(len(days)), n)
    return [(days[c[0]], days[c[-1]]) for c in chunks if len(c)]


def run(cfg, market, progress=print):
    T, P = cfg["tournament"], cfg["periods"]
    kind = T["score"]
    if kind not in SCORES:
        raise ValueError(f"score 必須是 {SCORES}")
    rng = np.random.default_rng(T["seed"])
    pop = spawn(cfg, market, rng)
    next_id = len(pop)
    rounds = []
    periods = split(market.days(P["train_start"], P["train_end"]), T["rounds"])
    for r, (start, end) in enumerate(periods, 1):
        for t in pop:
            t.reset_account(cfg)
        ctrl = controls(market, cfg, T["seed"] + r)
        backtest.run(pop + ctrl, market, cfg, start, end)
        rows = sorted((row(t, market, cfg, kind) for t in pop), key=lambda x: -x["score"])
        record = {
            "round": r,
            "start": str(start.date()),
            "end": str(end.date()),
            "benchmark": metrics.benchmark_return(market, start, end),
            "flies": rows,
            "controls": [row(t, market, cfg, kind) for t in ctrl],
            "eliminated": [],
            "born": [],
        }
        if r < len(periods) and T["eliminate"]:
            by_name = {t.name: t for t in pop}
            losers = {x["name"] for x in rows[-T["eliminate"]:]}
            parents = [by_name[x["name"]] for x in rows[: T["eliminate"]]]
            pop = [t for t in pop if t.name not in losers]
            for p in parents:
                child = backtest.Trader(
                    f"fly-{next_id:03d}",
                    p.brain.mutate(rng, T["mutation"]),
                    cfg,
                    int(rng.integers(1 << 31)),
                    {"generation": p.meta["generation"] + 1, "parent": p.name, "born_round": r},
                )
                next_id += 1
                pop.append(child)
                record["born"].append({"name": child.name, "parent": p.name})
            record["eliminated"] = sorted(losers)
        rounds.append(record)
        progress(f"第 {r} 回合 {record['start']}~{record['end']} 冠軍 {rows[0]['name']} "
                 f"{kind}={rows[0]['score']:+.2f}，淘汰 {len(record['eliminated'])} 隻")
    champion = next(t for t in pop if t.name == rounds[-1]["flies"][0]["name"])
    return {"rounds": rounds, "population": pop, "champion": champion,
            "final": validate(champion, cfg, market, progress)}


def validate(champion, cfg, market, progress=print):
    P, T = cfg["periods"], cfg["tournament"]
    seed = T["seed"] + 999
    kind = T["score"]

    frozen = champion.brain.clone()
    frozen.frozen = True
    amnesia = champion.brain.clone()
    amnesia.W[:] = 1.0
    amnesia.frozen = True

    twin_brain = champion.brain.clone()
    twin_brain.W[:] = 1.0
    shuffled_cfg = dict(cfg, reward=dict(cfg["reward"], mode="shuffled"))
    twin = backtest.Trader("冠軍・亂獎懲雙胞胎", twin_brain, shuffled_cfg, seed)
    progress("最終驗證：先讓亂獎懲雙胞胎走完訓練期…")
    backtest.run([twin], market, shuffled_cfg, P["train_start"], P["train_end"])
    twin.reset_account(shuffled_cfg)

    champ = champion.brain.clone()
    test = [
        backtest.Trader("冠軍", champ, cfg, seed, champion.meta),
        backtest.Trader("冠軍・凍結", frozen, cfg, seed, champion.meta),
        backtest.Trader("冠軍・失憶", amnesia, cfg, seed, champion.meta),
        twin,
    ] + controls(market, cfg, seed)
    progress("最終驗證：測試期…")
    backtest.run(test, market, cfg, P["test_start"], None)
    start, end = pd.Timestamp(P["test_start"]), market.calendar[-1]
    return {
        "start": P["test_start"],
        "end": str(end.date()),
        "benchmark": metrics.benchmark_return(market, start, end),
        "rows": [row(t, market, cfg, kind) for t in test],
        "curves": {t.name: [(str(d.date()), round(e)) for d, e in t.curve] for t in test},
    }
