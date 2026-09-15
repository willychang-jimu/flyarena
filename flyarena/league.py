"""每日模擬聯賽（紙上交易，不連任何券商帳戶）。

建立聯賽時存下：參賽果蠅「出生當下」的大腦、設定檔副本、賽制與開賽日。
每天收盤後：更新資料 → 從開賽日確定性重播到最新交易日 → 存當日快照 → 產出戰報。
重播讓結果完全可重現，也不必保存掛單、未結算獎懲等中間狀態。
賽制：每 season_days 個交易日結算一季，累積成績最後 eliminate 名淘汰（停止交易、保留紀錄），
直到剩 min_survivors 隻。對照組（隨機、買進持有、動能）一起跑但不參加淘汰。
限制：若資料源修正了過去的價格，重播出的歷史名次可能改變；快照裡記錄資料指紋供比對。
"""

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from . import backtest, data, metrics, store, tournament
from .brains import ACTION_NAMES

ROOT = Path(__file__).resolve().parent.parent
LEAGUES = ROOT / "leagues"


def create(name, cfg, entries, start, season_days=20, eliminate=1, min_survivors=4, controls=True):
    folder = LEAGUES / name
    if folder.exists():
        raise FileExistsError(f"聯賽 {name} 已存在")
    store.save_brains(folder, entries)
    (folder / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    rules = {
        "name": name,
        "start": start,
        "season_days": season_days,
        "eliminate": eliminate,
        "min_survivors": min_survivors,
        "controls": controls,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (folder / "league.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    return folder


def _seed(name):
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "little")


def replay(name, refresh=True):
    folder = LEAGUES / name
    cfg = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((folder / "league.json").read_text(encoding="utf-8"))
    frames = data.load_all(cfg, refresh)
    market = backtest.Market(frames, cfg)
    traders = [backtest.Trader(n, b, cfg, _seed(n), m) for n, b, m in store.load_brains(folder)]
    if rules["controls"]:
        traders += tournament.controls(market, cfg, _seed(name))
    days = market.days(rules["start"])
    if not days:
        raise RuntimeError("開賽日之後還沒有交易日資料")
    size = rules["season_days"]
    seasons = [days[i : i + size] for i in range(0, len(days), size)]
    active, eliminated = list(traders), []
    kind = cfg["tournament"]["score"]
    for i, chunk in enumerate(seasons, 1):
        backtest.run(active, market, cfg, chunk[0], chunk[-1])
        flies = [t for t in active if not t.meta.get("control")]
        if len(chunk) < size or len(flies) - rules["eliminate"] < rules["min_survivors"]:
            continue
        ranked = sorted(flies, key=lambda t: tournament.row(t, market, cfg, kind)["score"])
        for t in ranked[: rules["eliminate"]]:
            active.remove(t)
            eliminated.append({"name": t.name, "season": i, "date": str(chunk[-1].date())})
    fingerprint = hashlib.sha256(
        b"".join(frames[s].to_csv().encode() for s in sorted(frames))
    ).hexdigest()[:16]
    return {
        "cfg": cfg, "rules": rules, "market": market, "traders": traders,
        "active": {t.name for t in active}, "eliminated": eliminated,
        "days": days, "seasons": len(seasons), "fingerprint": fingerprint,
    }


def snapshot(result):
    """整理「今天」的戰果，並存成 leagues/<名>/days/<日期>.json。"""
    cfg, market, days = result["cfg"], result["market"], result["days"]
    today = days[-1]
    yesterday = days[-2] if len(days) > 1 else None
    kind = cfg["tournament"]["score"]
    rows = []
    for t in result["traders"]:
        r = tournament.row(t, market, cfg, kind)
        curve = dict(t.curve)
        prev = curve.get(yesterday, cfg["broker"]["capital"])
        r.update(
            active=t.name in result["active"],
            today_change=(curve[today] / prev - 1) if today in curve else None,
            decisions=[
                {"symbol": e["symbol"], "action": ACTION_NAMES[e["action"]], "mbon": e.get("mbon")}
                for e in t.journal if e["date"] == today
            ],
            fills=[f.__dict__ for f in t.broker.fills if f.date == str(today.date())],
            dopamine=[
                {"value": v, "symbol": s} for d, v, s in t.reward_log if d == today
            ],
            positions={s: n for s, n in t.broker.positions.items() if n},
            curve=[(str(d.date()), round(e)) for d, e in t.curve],
        )
        rows.append(r)
    # 存活果蠅依成績 → 對照組 → 已淘汰
    rows.sort(key=lambda r: (
        not r["active"],
        bool((r.get("meta") or {}).get("control")),
        -r["score"] if np.isfinite(r["score"]) else 0,
    ))
    snap = {
        "league": result["rules"]["name"],
        "date": str(today.date()),
        "season": result["seasons"],
        "trading_days": len(days),
        "benchmark_total": metrics.benchmark_return(market, days[0], today),
        "benchmark_today": metrics.benchmark_return(market, yesterday, today) if yesterday else 0.0,
        "eliminated": result["eliminated"],
        "fingerprint": result["fingerprint"],
        "rules": result["rules"],
        "rows": rows,
    }
    out = LEAGUES / snap["league"] / "days"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{snap['date']}.json").write_text(
        json.dumps(snap, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return snap


def history(name):
    """歷次快照的資料指紋，用來發現資料源是否改寫了歷史。"""
    folder = LEAGUES / name / "days"
    items = []
    for p in sorted(folder.glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        items.append({"date": s["date"], "fingerprint": s["fingerprint"]})
    return items
