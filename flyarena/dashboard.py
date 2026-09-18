"""聯賽 Dashboard：產生可直接放上 GitHub Pages 的靜態網站（預設輸出到 docs/）。

網頁是單一 index.html（資料內嵌，不需要伺服器），加上 avatars/ 頭像。
只放模擬成績、報酬率曲線與決策紀錄，不放原始股價。
"""

import html
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


def payload(result, snap, out_dir, save_profiles=False):
    cfg, market = result["cfg"], result["market"]
    capital = cfg["broker"]["capital"]
    names = {**SYMBOL_NAMES, **cfg.get("symbol_names", {})}
    dates = [str(d.date()) for d in result["days"]]
    bench = market.bench.reindex(result["days"]).ffill()
    rows = {r["name"]: r for r in snap["rows"]}
    profs = profiles.build(league.LEAGUES / snap["league"], snap["rows"], save=save_profiles)
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
        journal = [e for e in t.journal if e["date"] in recent_days and e["action"] != HOLD and e.get("selected", True)][-40:]
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
            "positions": [{"symbol": s, "name": names.get(s, s), "shares": n}
                          for s, n in r["positions"].items()],
            "today": {
                # 只放買賣決策（150 檔時「不動」會讓網頁暴增）
                "decisions": [{"symbol": d["symbol"], "action": d["action"], "selected": d.get("selected", True),
                               "name": names.get(d["symbol"], d["symbol"])}
                              for d in r["decisions"] if d["action"] != "HOLD"],
                "fills": [{"side": f["side"], "symbol": f["symbol"], "name": names.get(f["symbol"], f["symbol"]),
                           "shares": f["shares"], "fee": round(f["fee"]), "tax": round(f["tax"])} for f in r["fills"]],
                "reward": sum(1 for x in r["dopamine"] if x["value"] > 0),
                "punish": sum(1 for x in r["dopamine"] if x["value"] < 0),
            },
            "recent": [{"date": str(e["date"].date()), "symbol": e["symbol"],
                        "name": names.get(e["symbol"], e["symbol"]),
                        "action": ACTION_NAMES[e["action"]], "filled": e.get("filled"),
                        "note": e.get("note", "等待開盤")} for e in reversed(journal)],
        })
    rules = snap["rules"]
    return {
        "league": {
            "name": snap["league"], "title": rules.get("title", snap["league"]),
            "date": snap["date"], "season": snap["season"],
            "trading_days": snap["trading_days"], "start": rules["start"],
            "season_days": rules["season_days"], "eliminate": rules["eliminate"],
            "min_survivors": rules["min_survivors"],
            "benchmark_total": _num(snap["benchmark_total"]), "benchmark_today": _num(snap["benchmark_today"]),
            "fingerprint": snap["fingerprint"], "reward_mode": cfg["reward"]["mode"],
            "capital": capital, "order_value": cfg["broker"]["order_value"],
            # 不放產生時間：資料沒變時網頁內容完全相同，每日腳本就不會推送多餘的 commit
            "trade_every_days": cfg["broker"]["trade_every_days"],
        },
        "dates": dates,
        "benchmark": [_num(v / bench.iloc[0] - 1) for v in bench],
        "eliminations": result["eliminated"],
        "traders": traders,
    }


def build(result, snap, out_dir=None, save_profiles=False):
    """公開網站（docs/）由雲端用 save_profiles=True 產生；本機預覽輸出到 preview/ 且不改寫角色檔。"""
    out_dir = Path(out_dir) if out_dir else ROOT / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = payload(result, snap, out_dir, save_profiles)
    # 網站 logo：Windows 10 沒有 🪰 字型，改用自動生成的卡通果蠅
    (out_dir / "avatars" / "logo.svg").write_text(avatars.fly_svg("flyarena", {"title": "均衡"}), encoding="utf-8")
    keep = {Path(t["avatar"]).name for t in data["traders"]} | {"logo.svg"}
    for stale in (out_dir / "avatars").iterdir():  # 換過頭像後，舊檔案不要留在網站上
        if stale.name not in keep:
            stale.unlink()
    html = (TEMPLATE / "dashboard.html").read_text(encoding="utf-8")
    css = (TEMPLATE / "dashboard.css").read_text(encoding="utf-8")
    js = (TEMPLATE / "dashboard.js").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (html.replace("/*__CSS__*/", css).replace("/*__JS__*/", js)
            .replace("__DATA__", blob).replace("__TITLE__", f"果蠅交易聯賽｜{data['league']['title']}"))
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"


INDEX_CSS = """
.seasons { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin-top: 20px; }
.season .head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.season h2 { margin: 0; }
.season .stat { display: flex; justify-content: space-between; gap: 8px; margin-top: 8px; font-size: 13px; }
.enter { display: inline-block; margin-top: 14px; color: var(--s1); font-weight: 600; text-decoration: none; }
.enter:hover { text-decoration: underline; }
"""


def _delta(x):
    if x is None:
        return "—"
    cls, arrow = ("up", "▲") if x > 0 else ("down", "▼") if x < 0 else ("", "")
    return f"<span class='{cls}'>{arrow} {abs(x):.1%}</span>"


def build_index(cards, out_dir):
    """賽季總覽首頁：每個賽季的狀態、領先果蠅、大盤同期表現與連結。最新的賽季排最前面。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    e = html.escape
    status = {"live": "進行中", "ended": "已收官", "upcoming": "即將開賽"}
    items = []
    for c in reversed(cards):
        period = f"{c['start']} ～ {c['end']}" if c.get("end") else f"{c['start']} 開賽"
        if c["status"] == "upcoming":
            body, link = f"<p class='ink2'>{e(c['start'])} 開賽，敬請期待。</p>", ""
        else:
            stat = lambda k, v: f"<div class='stat'><span class='ink2'>{k}</span><b>{v}</b></div>"
            leader = c.get("leader")
            body = (stat("資料日期", f"{e(c['date'])}（第 {c['season']} 季・{c['days']} 個交易日）")
                    + stat("存活果蠅", f"{c['alive']} 隻")
                    + (stat("目前領先", f"{e(leader['emoji'])} {e(leader['nickname'])} {_delta(leader['return'])}") if leader else "")
                    + stat("大盤同期", _delta(c["benchmark"])))
            link = f"<a class='enter' href='{e(c['name'])}/'>進入戰況 →</a>"
        items.append(f"<article class='card season'><div class='head'><h2>{e(c['title'])}</h2>"
                     f"<span class='tag'>{status[c['status']]}</span></div>"
                     f"<div class='muted small'>{e(period)}</div>{body}{link}</article>")
    css = (TEMPLATE / "dashboard.css").read_text(encoding="utf-8")
    page = (
        '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>果蠅交易聯賽</title><style>{css}{INDEX_CSS}</style></head><body>"
        '<div class="disclaimer" role="note">⚠️ 這是果蠅神經模型的<strong>模擬交易實驗</strong>：'
        "所有買賣都是虛擬的，股票只是實驗標的，<strong>不構成任何投資建議</strong>。</div><main>"
        '<header class="top"><div><h1 class="brand"><img class="av" src="logo.svg" alt="">'
        "<span>果蠅交易聯賽</span></h1>"
        '<p class="sub">以果蠅蘑菇體神經模型模擬台股交易的研究實驗：每隻果蠅每天收盤後做決策，'
        "做對得到獎勵、做錯受到懲罰，每季淘汰最後一名。</p></div></header>"
        f"<section class='seasons'>{''.join(items)}</section>"
        '<footer class="muted small">網頁只含模擬成績，不含原始股價・非投資建議</footer>'
        "</main></body></html>"
    )
    (out_dir / "logo.svg").write_text(avatars.fly_svg("flyarena", {"title": "均衡"}), encoding="utf-8")
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"
