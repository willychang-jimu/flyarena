"""績效與訊號準確度。"""

import math

import numpy as np

from .brains import BUY, HOLD, SELL


def performance(trader, capital):
    if len(trader.curve) < 2:
        return {}
    eq = np.array([e for _, e in trader.curve], dtype=float)
    r = np.diff(np.log(eq))
    years = len(r) / 252
    peak = np.maximum.accumulate(eq)
    fills = trader.broker.fills
    return {
        "return": eq[-1] / capital - 1,
        "cagr": (eq[-1] / capital) ** (1 / years) - 1 if years > 0 else 0.0,
        "vol": float(r.std() * math.sqrt(252)),
        "sharpe": float(r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else 0.0,
        "max_drawdown": float((eq / peak - 1).min()),
        "trades": len(fills),
        "costs": trader.broker.costs,
        "equity": float(eq[-1]),
    }


def signal_quality(trader, market):
    """每個 BUY/SELL 判斷，事後看 horizon 天的方向對不對（和有沒有成交無關）。"""
    hits, total, pairs = 0, 0, []
    counts = {BUY: 0, HOLD: 0, SELL: 0}
    for e in trader.journal:
        counts[e["action"]] += 1
        fwd = market.fwd[e["symbol"]].get(e["date"])
        if fwd is None or not np.isfinite(fwd):
            continue
        pairs.append((e["action"], fwd))
        if e["action"] != HOLD:
            total += 1
            hits += int(np.sign(fwd) == e["action"])
    ic = 0.0
    if len(pairs) > 10:
        a, f = np.array(pairs).T
        if a.std() > 0 and f.std() > 0:
            ic = float(np.corrcoef(a, f)[0, 1])
    n = sum(counts.values()) or 1
    return {
        "hit_rate": hits / total if total else float("nan"),
        "calls": total,
        "ic": ic,
        "buy_share": counts[BUY] / n,
        "hold_share": counts[HOLD] / n,
        "sell_share": counts[SELL] / n,
    }


def benchmark_return(market, start, end):
    b = market.bench[(market.bench.index >= start) & (market.bench.index <= end)]
    return float(b.iloc[-1] / b.iloc[0] - 1) if len(b) > 1 else float("nan")
