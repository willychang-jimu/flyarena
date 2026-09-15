"""聯賽 Dashboard：產生可直接放上 GitHub Pages 的靜態網站（預設輸出到 docs/）。

網頁是單一 index.html（資料內嵌，不需要伺服器），加上 avatars/ 頭像。
只放模擬成績、報酬率曲線與決策紀錄，不放原始股價。
"""

import datetime as dt
import json
from pathlib import Path

from . import avatars, league, profiles
from .brains import ACTION_NAMES, HOLD

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).with_name("site")

SYMBOL_NAMES = {
    "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "2308.TW": "台達電",
    "0050.TW": "元大台灣50", "006208.TW": "富邦台50", "00878.TW": "國泰永續高股息",
}
STAT_KEYS = ("return", "sharpe", "max_drawdown", "hit_rate", "calls", "ic", "trades", "costs",
             "rewards", "punishments", "memory", "today_change", "buy_share", "hold_share", "sell_share")


def _num(x, digits=5):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, digits) if x == x and abs(x) != float("inf") else None


def payload(result, snap, out_dir):
    cfg, market = result["cfg"], result["market"]
    capital = cfg["broker"]["capital"]
    dates = [str(d.date()) for d in result["days"]]
    bench = market.bench.reindex(result["days"]).ffill()
    rows = {r["name"]: r for r in snap["rows"]}
    profs = profiles.build(league.LEAGUES / snap["league"], snap["rows"])
    eliminated = {e["name"]: e for e in result["eliminated"]}
    children = {}
    for name, p in profs.items():
        parent = (p.get("family") or {}).get("parent")
        if parent:
            children.setdefault(parent, []).append(name)
    recent_days = set(result["days"][-10:])
    traders = []
    for t in result["traders"]:
        r, p = rows[t.name], profs[t.name]
        curve = dict(t.curve)
        journal = [e for e in t.journal if e["date"] in recent_days and e["action"] != HOLD][-40:]
        traders.append({
            "id": t.name,
            "nickname": p["nickname"], "title": p["title"], "emoji": p["emoji"], "bio": p["bio"],
            "gene": p.get("gene"), "gene_note": p.get("gene_note"),
            "avatar": avatars.resolve(t.name, p, out_dir),
            "control": p["control"], "active": r["active"],
            "eliminated": eliminated.get(t.name),
            "generation": p["family"]["generation"], "parent": p["family"]["parent"],
            "children": sorted(children.get(t.name, [])),
            "traits": {k: _num(v, 3) for k, v in (p.get("traits") or {}).items()} or None,
            "stats": {k: _num(r.get(k)) for k in STAT_KEYS},
            "curve": [_num(curve[d] / capital - 1) if d in curve else None for d in result["days"]],
            "positions": [{"symbol": s, "name": SYMBOL_NAMES.get(s, s), "shares": n}
                          for s, n in r["positions"].items()],
            "today": {
                "decisions": [dict(d, name=SYMBOL_NAMES.get(d["symbol"], d["symbol"])) for d in r["decisions"]],
                "fills": [{"side": f["side"], "symbol": f["symbol"], "name": SYMBOL_NAMES.get(f["symbol"], f["symbol"]),
                           "shares": f["shares"], "fee": round(f["fee"]), "tax": round(f["tax"])} for f in r["fills"]],
                "reward": sum(1 for x in r["dopamine"] if x["value"] > 0),
                "punish": sum(1 for x in r["dopamine"] if x["value"] < 0),
            },
            "recent": [{"date": str(e["date"].date()), "symbol": e["symbol"],
                        "name": SYMBOL_NAMES.get(e["symbol"], e["symbol"]),
                        "action": ACTION_NAMES[e["action"]], "filled": e.get("filled"),
                        "note": e.get("note", "等待開盤")} for e in reversed(journal)],
        })
    rules = snap["rules"]
    return {
        "league": {
            "name": snap["league"], "date": snap["date"], "season": snap["season"],
            "trading_days": snap["trading_days"], "start": rules["start"],
            "season_days": rules["season_days"], "eliminate": rules["eliminate"],
            "min_survivors": rules["min_survivors"],
            "benchmark_total": _num(snap["benchmark_total"]), "benchmark_today": _num(snap["benchmark_today"]),
            "fingerprint": snap["fingerprint"], "reward_mode": cfg["reward"]["mode"],
            "capital": capital, "order_value": cfg["broker"]["order_value"],
            "trade_every_days": cfg["broker"]["trade_every_days"],
            "generated": dt.datetime.now().isoformat(timespec="minutes"),
        },
        "dates": dates,
        "benchmark": [_num(v / bench.iloc[0] - 1) for v in bench],
        "eliminations": result["eliminated"],
        "traders": traders,
    }


def build(result, snap, out_dir=None):
    out_dir = Path(out_dir) if out_dir else ROOT / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = payload(result, snap, out_dir)
    # 網站 logo：Windows 10 沒有 🪰 字型，改用像素果蠅
    (out_dir / "avatars" / "logo.svg").write_text(avatars.fly_svg("flyarena", {"title": "均衡"}), encoding="utf-8")
    html = (TEMPLATE / "dashboard.html").read_text(encoding="utf-8")
    css = (TEMPLATE / "dashboard.css").read_text(encoding="utf-8")
    js = (TEMPLATE / "dashboard.js").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (html.replace("/*__CSS__*/", css).replace("/*__JS__*/", js)
            .replace("__DATA__", blob).replace("__TITLE__", f"果蠅交易聯賽｜{data['league']['name']}"))
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"
