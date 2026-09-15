"""季賽分析：成績歸因、持股比例、和大盤的連動、判斷品質、學到的訊號偏好、淘汰原因。
只使用聯賽重播結果與本機快取資料，不需要網路。"""

import math

import numpy as np
import pandas as pd

from . import metrics, probe
from .brains import BUY, HOLD, SELL

SYMBOL_NAMES = {
    "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "2308.TW": "台達電",
    "0050.TW": "元大台灣50", "006208.TW": "富邦台50", "00878.TW": "國泰永續高股息",
}
FEATURE_ZH = {
    "ret_1": "1日報酬", "ret_3": "3日報酬", "ret_5": "5日報酬", "ret_10": "10日報酬",
    "ret_20": "20日報酬", "ret_60": "60日報酬", "vol_20": "20日波動度",
    "range_20": "20日區間位置", "ma_20": "20日均線乖離", "range_60": "60日區間位置",
    "ma_60": "60日均線乖離", "volume_ratio": "量比（5日/20日）", "gap": "開盤跳空",
    "mkt_1": "大盤1日報酬", "mkt_5": "大盤5日報酬", "mkt_20": "大盤20日報酬", "rel_20": "20日相對大盤強弱",
}


def book(trader, market, days, capital):
    """依成交紀錄重建每日現金、持股市值與總資產。淘汰後的日子不列入。"""
    by_date = {}
    for f in trader.broker.fills:
        by_date.setdefault(f.date, []).append(f)
    curve = dict(trader.curve)
    cash, pos, last, rows = float(capital), {}, {}, []
    for d in days:
        if d not in curve:
            break
        for f in by_date.get(str(d.date()), []):
            if f.side == "BUY":
                cash -= f.value + f.fee
                pos[f.symbol] = pos.get(f.symbol, 0) + f.shares
            else:
                cash += f.value - f.fee - f.tax
                pos[f.symbol] = pos.get(f.symbol, 0) - f.shares
        for s in market.symbols:
            if d in market.close[s]:
                last[s] = market.close[s][d]
        held = sum(n * last[s] for s, n in pos.items() if n and s in last)
        rows.append((d, cash, held, cash + held))
    return pd.DataFrame(rows, columns=["date", "cash", "held", "equity"]).set_index("date")


def attribution(trader, market, last_day, names=None):
    """每檔股票的損益（已實現＋未實現，扣除手續費與稅）與賣出勝率（平均成本法）。"""
    names = names or SYMBOL_NAMES
    out = {}
    for f in trader.broker.fills:
        a = out.setdefault(f.symbol, {"buy": 0.0, "sell": 0.0, "costs": 0.0, "shares": 0,
                                      "avg": 0.0, "wins": 0, "sells": 0, "buys": 0})
        if f.side == "BUY":
            total = a["avg"] * a["shares"] + f.value + f.fee
            a["shares"] += f.shares
            a["avg"] = total / a["shares"]
            a["buy"] += f.value
            a["buys"] += 1
        else:
            realized = (f.price - a["avg"]) * f.shares - f.fee - f.tax
            a["wins"] += int(realized > 0)
            a["sells"] += 1
            a["shares"] -= f.shares
            a["sell"] += f.value
        a["costs"] += f.fee + f.tax
    for s, a in out.items():
        close = market.close[s]
        price = close.get(last_day) or close[max(d for d in close if d <= last_day)]
        a["open_value"] = a["shares"] * price
        a["pnl"] = a["sell"] + a["open_value"] - a["buy"] - a["costs"]
        a["name"] = names.get(s, s)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["pnl"]))


def beta_alpha(equity, bench):
    r = np.log(equity).diff().dropna()
    b = np.log(bench.reindex(equity.index).ffill()).diff().reindex(r.index).fillna(0)
    if len(r) < 10 or b.var() == 0:
        return {"beta": float("nan"), "alpha": float("nan"), "r2": float("nan")}
    if r.var() == 0:  # 從未進場：和大盤沒有連動
        return {"beta": 0.0, "alpha": 0.0, "r2": float("nan")}
    beta = float(np.cov(r, b)[0, 1] / b.var())
    alpha = float((r.mean() - beta * b.mean()) * 252)
    r2 = float(np.corrcoef(r, b)[0, 1] ** 2)
    return {"beta": beta, "alpha": alpha, "r2": r2}


def decision_quality(trader, market, end=None):
    """每種決策之後 horizon 天的平均報酬與命中率（和有沒有成交無關）。"""
    stats = {BUY: [], HOLD: [], SELL: []}
    for e in trader.journal:
        if end is not None and e["date"] > end:
            continue
        fwd = market.fwd[e["symbol"]].get(e["date"])
        if fwd is not None and np.isfinite(fwd):
            stats[e["action"]].append(fwd)
    out = {}
    for a, name in ((BUY, "BUY"), (HOLD, "HOLD"), (SELL, "SELL")):
        v = np.array(stats[a])
        hit = float(np.mean(np.sign(v) == a)) if len(v) and a != HOLD else float("nan")
        out[name] = {"n": len(v), "mean": float(v.mean()) if len(v) else float("nan"), "hit": hit}
    return out


def preferences(brain, names, seed=0, trials=40):
    """每個訊號由偏低（-2σ）到偏高（+2σ）時，BUY 輸出減 SELL 輸出的變化；正值＝訊號越高越想買。
    同時估計雜訊門檻：訊號完全不變（兩次都是 0σ）時量到的最大差異。低於門檻的偏好不採信。"""
    if not hasattr(brain, "W"):
        return {}, 0.0
    rows = probe.tuning(brain, names, seed=seed, values=np.array([-2.0, 2.0]), trials=trials)
    null = probe.tuning(brain, names, seed=seed + 1, values=np.array([0.0, 0.0]), trials=trials)
    floor = max(abs(v[1][4] - v[0][4]) for v in null.values())
    return {k: v[1][4] - v[0][4] for k, v in rows.items()}, float(floor)


def window_stats(trader, market, days, capital, end):
    """截至 end 的表現。淘汰分析用：和同一段期間還在比賽的果蠅公平比較。"""
    b = book(trader, market, [d for d in days if d <= end], capital)
    eq = b.equity.to_numpy()
    r = np.diff(np.log(eq)) if len(eq) > 1 else np.array([0.0])
    q = decision_quality(trader, market, end)
    return {
        "sharpe": float(r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else 0.0,
        "return": float(eq[-1] / capital - 1),
        "exposure": float((b.held / b.equity).mean()),
        "mdd": float((eq / np.maximum.accumulate(eq) - 1).min()),
        "buy_mean": q["BUY"]["mean"],
        "sell_mean": q["SELL"]["mean"],
        "costs": float(sum(f.fee + f.tax for f in trader.broker.fills if f.date <= str(end.date()))),
    }


def season_ranks(result, cfg):
    """每季結束時，依截至當時的 Sharpe 排名（只排當時還在比賽的果蠅）。"""
    days, size = result["days"], result["rules"]["season_days"]
    elim = {e["name"]: e["season"] for e in result["eliminated"]}
    table = {}
    for i in range(0, len(days), size):
        season = i // size + 1
        end = days[min(i + size, len(days)) - 1]
        scores = {}
        for t in result["traders"]:
            if t.meta.get("control") or elim.get(t.name, 99) < season:
                continue
            eq = np.array([e for d, e in t.curve if d <= end], dtype=float)
            r = np.diff(np.log(eq)) if len(eq) > 1 else np.array([0.0])
            scores[t.name] = r.mean() / r.std() * math.sqrt(252) if r.std() > 0 else 0.0
        ranked = sorted(scores, key=lambda n: -scores[n])
        for n in ranked:
            table.setdefault(n, {})[season] = ranked.index(n) + 1
    return table


def profile(trader, result, cfg, initial_brains):
    """單一交易員的完整分析資料。"""
    market, days = result["market"], result["days"]
    capital = cfg["broker"]["capital"]
    b = book(trader, market, days, capital)
    last_day = b.index[-1]
    now, floor = preferences(trader.brain, market.names)
    start = preferences(initial_brains[trader.name], market.names)[0] if trader.name in initial_brains else {}
    bench = market.bench.reindex(b.index).ffill()
    return {
        "name": trader.name, "meta": trader.meta,
        "perf": metrics.performance(trader, capital),
        "signal": metrics.signal_quality(trader, market),
        "last_day": last_day, "days_alive": len(b),
        "bench_return": metrics.benchmark_return(market, days[0], last_day),
        "exposure": float((b.held / b.equity).mean()),
        "exposure_up_days": float((b.held / b.equity)[bench.pct_change() > 0].mean()),
        "risk": beta_alpha(b.equity, market.bench),
        "attribution": attribution(trader, market, last_day, {**SYMBOL_NAMES, **cfg.get("symbol_names", {})}),
        "quality": decision_quality(trader, market),
        "rewards": dict(trader.reward_count),
        "prefs_now": now, "prefs_floor": floor,
        "prefs_change": {k: now[k] - start.get(k, 0.0) for k in now} if start else {},
        "memory": getattr(trader.brain, "memory_change", lambda: 0.0)(),
    }


def failure_reasons(p, window, peers, cfg, season_days):
    """和同一段期間還在比賽的果蠅（peers，含自己）比較，找出落後的地方。"""
    med = lambda k: float(np.nanmedian([x[k] for x in peers]))
    h = cfg["reward"].get("horizon_days", 5)
    w = window
    reasons = [f"截至淘汰日，Sharpe {w['sharpe']:.2f}（同場果蠅中位數 {med('sharpe'):.2f}），"
               f"報酬 {w['return']:+.1%}（中位數 {med('return'):+.1%}）"]
    if p["days_alive"] <= 2 * season_days:
        reasons.append("比賽天數很短就被淘汰，樣本太少，很可能只是運氣不好，不代表能力差")
    if p["perf"]["trades"] == 0:
        reasons.append(f"完全沒有進場，同期大盤 {p['bench_return']:+.1%}，全部錯過")
    elif w["exposure"] < med("exposure") - 0.1:
        reasons.append(f"持股比例 {w['exposure']:.0%}，比同場中位數 {med('exposure'):.0%} 低，大盤上漲時分到的報酬較少")
    if np.isfinite(w["buy_mean"]) and w["buy_mean"] < med("buy_mean") - 0.003:
        reasons.append(f"買進後 {h} 天平均 {w['buy_mean']:+.2%}（同場中位數 {med('buy_mean'):+.2%}），買點比較差")
    if np.isfinite(w["sell_mean"]) and w["sell_mean"] > med("sell_mean") + 0.005:
        reasons.append(f"賣出後股價平均還漲 {w['sell_mean']:+.2%}（同場中位數 {med('sell_mean'):+.2%}），賣得比較早")
    if w["mdd"] < med("mdd") - 0.02:
        reasons.append(f"最大回撤 {w['mdd']:.1%}，比同場中位數 {med('mdd'):.1%} 深")
    if w["costs"] > 5000 and w["costs"] > med("costs") * 1.3:
        reasons.append(f"交易成本 {w['costs']:,.0f} 元，比同場中位數 {med('costs'):,.0f} 元高")
    if len(reasons) == 1 and p["days_alive"] > 2 * season_days:
        reasons.append("各項指標都只比同場果蠅略差一點，差距不大；在淘汰規則下，排最後一名就會出局")
    return reasons
