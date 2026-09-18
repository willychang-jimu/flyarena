"""指令介面。用法：python -m flyarena <指令> --help"""

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

from . import backtest, dashboard, data, league, probe, profiles, report, senses, store, tournament
from .brains import make_brain

ROOT = Path(__file__).resolve().parent.parent
SEASONS = ROOT / "leagues" / "seasons.json"


def load_config(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_fetch(a, cfg):
    for s, df in data.load_all(cfg, refresh=True).items():
        print(f"{s:10s} {len(df):5d} 筆  {df.index[0].date()} ~ {df.index[-1].date()}")


def cmd_probe(a, cfg):
    market = backtest.Market(data.load_all(cfg), cfg)
    runs, tunings = {}, {}
    for label, frozen in (("會學習的果蠅", False), ("凍結的果蠅", True)):
        brain = make_brain("mushroom", market.n_pn, dict(cfg["brain"], frozen=frozen), a.seed)
        runs[label] = probe.conditioning(brain, market.names, seed=a.seed)
        # 反應曲線在「只學原始規則」的大腦上量測，凍結者當雜訊底線
        fresh = make_brain("mushroom", market.n_pn, dict(cfg["brain"], frozen=frozen), a.seed)
        probe.conditioning(fresh, market.names, seed=a.seed, reversal_blocks=0)
        tunings[label] = probe.sensitivity(probe.tuning(fresh, market.names, seed=a.seed + 1))
    path = report.probe_page(runs, tunings, ROOT / "reports" / f"probe-seed{a.seed}.html")
    for label, curve in runs.items():
        print(label, " → ".join(f"{acc['平均']:.0%}" for _, acc in curve[::4]))
    print("報告：", path)


def cmd_tournament(a, cfg):
    if a.seed is not None:
        cfg["tournament"]["seed"] = a.seed
    name = a.name or f"tournament-seed{cfg['tournament']['seed']}"
    out = ROOT / "runs" / name
    market = backtest.Market(data.load_all(cfg), cfg)
    res = tournament.run(cfg, market)
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"rounds": res["rounds"], "final": res["final"], "champion": res["champion"].name}
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")
    store.save_brains(out / "survivors", [(t.name, t.brain, t.meta) for t in res["population"]])
    path = report.tournament_page(report.load_json(out / "result.json"), cfg, ROOT / "reports" / f"{name}.html")
    print("存活果蠅：", out / "survivors")
    print("報告：", path)


def cmd_league_create(a, cfg):
    if a.source:
        entries = store.load_brains(ROOT / a.source)
    else:
        entries = [
            (f"fly-{i:03d}", make_brain("mushroom", _n_pn(), cfg["brain"], 1000 + i),
             {"generation": 0, "parent": None})
            for i in range(a.new)
        ]
    folder = league.create(a.name, cfg, entries, a.start, a.season_days, a.eliminate, a.min_survivors)
    print(f"聯賽建立於 {folder}，參賽 {len(entries)} 隻，開賽日 {a.start}")


def _n_pn():
    """感覺輸入數量（特徵數 × 每個特徵的 PN 數），不需要下載資料就能算。"""
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    dummy = pd.DataFrame({c: 1.0 for c in ("open", "high", "low", "close", "volume")}, index=idx)
    return senses.features(dummy, dummy).shape[1] * len(senses.CENTERS)


def cmd_season_create(a, cfg):
    from . import universe

    rows, as_of = universe.top(a.top)
    season = json.loads(json.dumps(cfg))
    season["symbols"] = [r["symbol"] for r in rows]
    season["symbol_names"] = {r["symbol"]: r["name"] for r in rows}
    season["universe"] = {
        "rule": f"上市市值前 {a.top} 大（排除 ETF、特別股、存託憑證、創新板），整季固定",
        "as_of": as_of,
        "industries": {r["symbol"]: r["industry"] for r in rows},
    }
    season["data_start"] = a.data_start
    season["broker"].update(order_value=a.order_value, max_position_value=a.max_position,
                            max_buys_per_day=a.max_buys)
    n_pn = _n_pn()
    rookies = [
        (f"fly-{a.first_id + i:03d}", make_brain("mushroom", n_pn, cfg["brain"], a.seed + i),
         {"generation": 0, "parent": None, "rookie": True})
        for i in range(a.field_size)  # 多存幾隻，實際只補到 field_size
    ]
    extra = {"title": a.title, "field_size": a.field_size}
    if a.veterans_from:
        extra["veterans_from"] = a.veterans_from
    folder = league.create(a.name, season, rookies, a.start, a.season_days, a.eliminate, a.min_survivors, **extra)
    if a.veterans_from:  # 老將沿用上一屆的暱稱、個性與你改過的內容
        shutil.copyfile(league.LEAGUES / a.veterans_from / "profiles.json", folder / "profiles.json")
    index = json.loads(SEASONS.read_text(encoding="utf-8"))
    if a.name not in index["seasons"]:
        index["seasons"].append(a.name)
        SEASONS.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{a.title} 建立於 {folder}")
    print(f"選股：{len(rows)} 檔（市值資料日 {as_of}），第 1 名 {rows[0]['name']}、最後一名 {rows[-1]['name']}")
    print(f"開賽 {a.start}，參賽 {a.field_size} 隻" + (f"（{a.veterans_from} 的存活者＋新秀補滿）" if a.veterans_from else ""))


def _site(a, result, snap):
    out = a.out or ROOT / ("docs" if a.publish else "preview") / snap["league"]
    path = dashboard.build(result, snap, out, save_profiles=a.publish)
    print("公開網站：" if a.publish else "本機預覽（不影響公開網站）：", path)


def cmd_daily(a, cfg):
    try:
        result = league.replay(a.name, refresh=not a.offline)
    except league.NotStarted as e:
        print(e)
        return
    snap = league.snapshot(result)
    folder = league.LEAGUES / a.name
    dates = sorted(p.stem for p in (folder / "days").glob("*.json"))
    capital = result["cfg"]["broker"]["capital"]
    path = report.daily_page(snap, folder / "reports" / f"{snap['date']}.html", capital, dates)
    report.daily_page(snap, folder / "reports" / "latest.html", capital, dates)
    print(f"{snap['date']} 第 {snap['season']} 季，大盤今日 {snap['benchmark_today']:+.2%}")
    for r in [r for r in snap["rows"] if r["active"]][:8]:
        tag = "對照" if (r.get("meta") or {}).get("control") else "    "
        today = r["today_change"] if r["today_change"] is not None else 0.0
        print(f"  {tag} {r['name']:10s} 今日 {today:+.2%}  累積 {r['return']:+.1%}  Sharpe {r['sharpe']:+.2f}")
    print("戰報：", path)
    if not a.no_site:
        _site(a, result, snap)


def cmd_site(a, cfg):
    try:
        result = league.replay(a.name, refresh=not a.offline)
    except league.NotStarted as e:
        print(e)
        return
    snap = league.snapshot(result)
    _site(a, result, snap)
    print("角色檔（可修改暱稱、個性、頭像）：", league.LEAGUES / a.name / "profiles.json")


def cmd_season_report(a, cfg):
    from . import season_report

    try:
        print("季賽報告：", season_report.build(a.name, refresh=not a.offline))
    except league.NotStarted as e:
        print(e)


def cmd_prompts(a, cfg):
    """為還沒有角色圖的果蠅產生提示詞，貼到影像生成工具就能畫出風格一致的圖。"""
    from . import cards

    try:
        result = league.replay(a.name, refresh=False)
    except league.NotStarted as e:
        print(f"{e}；等開賽、果蠅拿到暱稱之後再產生提示詞")
        return
    snap = league.snapshot(result)
    profs = profiles.build(league.LEAGUES / a.name, snap["rows"], save=False)
    todo = [(n, p) for n, p in profs.items() if a.all or not p.get("avatar")]
    if not todo:
        print("每隻果蠅都有角色圖了。想全部重做請加 --all")
        return
    out = ROOT / "notes" / "prompts"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{a.name}.md"
    body = [f"# {a.name} 角色圖提示詞", "",
            "把下面每一段貼到影像生成工具，生成 1:1 圖片後放進 `avatars/`，",
            "再到 `leagues/<賽季>/profiles.json` 把該果蠅的 `avatar` 填成檔名即可。", ""]
    for name, p in todo:
        body += [f"## {p['nickname']}（{name}・{p['title']}）", "", "```", cards.prompt(name, p, a.extra), "```", ""]
    path.write_text("\n".join(body), encoding="utf-8")
    print(f"{len(todo)} 隻的提示詞 → {path}")


def cmd_publish(a, cfg):
    """發布清單上的所有賽季：各自的 dashboard、季賽報告，以及賽季總覽首頁。"""
    from . import season_report

    base = ROOT / ("preview" if a.preview else "docs")
    cards, honours = [], {}  # honours：累積各屆冠軍次數，決定卡片稀有度
    for name in json.loads(SEASONS.read_text(encoding="utf-8"))["seasons"]:
        _, rules = league.load_rules(name)
        card = {"name": name, "title": rules.get("title", name), "start": rules["start"], "end": rules.get("end")}
        try:
            result = league.replay(name, refresh=not a.offline)
        except league.NotStarted as e:
            print(e)
            cards.append(dict(card, status="upcoming"))
            continue
        snap = league.snapshot(result)
        dashboard.build(result, snap, base / name, save_profiles=not a.preview, honours=honours)
        winner = dashboard.champion(snap, rules)
        if winner:
            honours[winner] = honours.get(winner, 0) + 1
        report_dir = base / "reports" if a.preview else None
        season_report.build(name, result=result, out=report_dir)
        prof = profiles.build(league.LEAGUES / name, snap["rows"], save=False)
        leader = next((r for r in snap["rows"] if r["active"] and not (r.get("meta") or {}).get("control")), None)
        ended = bool(rules.get("end")) and dt.date.today().isoformat() > rules["end"]
        card.update(status="ended" if ended else "live", date=snap["date"], season=snap["season"],
                    days=snap["trading_days"], benchmark=snap["benchmark_total"],
                    alive=sum(1 for r in snap["rows"] if r["active"] and not (r.get("meta") or {}).get("control")),
                    leader=None if leader is None else {
                        "name": leader["name"], "nickname": prof[leader["name"]]["nickname"],
                        "emoji": prof[leader["name"]]["emoji"], "return": leader["return"]})
        cards.append(card)
        print(f"{card['title']}：{snap['date']}，存活 {card['alive']} 隻")
    shutil.rmtree(base / "avatars", ignore_errors=True)  # 舊版單一賽季網站留下的頭像
    print("賽季總覽：", dashboard.build_index(cards, base))


def main(argv=None):
    p = argparse.ArgumentParser(prog="flyarena", description="果蠅交易員研究平台（模擬交易）")
    p.add_argument("--config", default=str(ROOT / "arena.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="更新台股日線資料")
    s = sub.add_parser("probe", help="訊號反應測試（制約實驗＋反應曲線）")
    s.add_argument("--seed", type=int, default=0)
    s = sub.add_parser("tournament", help="淘汰賽＋測試期最終驗證")
    s.add_argument("--seed", type=int)
    s.add_argument("--name")

    s = sub.add_parser("league-create", help="建立每日模擬聯賽")
    s.add_argument("name")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--from", dest="source", help="存活果蠅資料夾，例如 runs/tournament-seed7/survivors")
    g.add_argument("--new", type=int, help="改用 N 隻新生果蠅")
    s.add_argument("--start", default=dt.date.today().isoformat())
    s.add_argument("--season-days", type=int, default=20)
    s.add_argument("--eliminate", type=int, default=1)
    s.add_argument("--min-survivors", type=int, default=4)

    s = sub.add_parser("season-create", help="建立新一屆聯賽：依市值排名選股，可帶上一屆的存活果蠅")
    s.add_argument("name")
    s.add_argument("--title", required=True)
    s.add_argument("--start", required=True)
    s.add_argument("--top", type=int, default=150, help="選市值前幾大")
    s.add_argument("--veterans-from", help="上一屆的聯賽名稱（存活果蠅帶記憶參賽）")
    s.add_argument("--field-size", type=int, default=16, help="參賽果蠅總數，新秀補滿")
    s.add_argument("--first-id", type=int, default=100, help="新秀編號起點")
    s.add_argument("--seed", type=int, default=20261000)
    s.add_argument("--order-value", type=int, default=50000)
    s.add_argument("--max-position", type=int, default=100000)
    s.add_argument("--max-buys", type=int, default=3, help="每日最多新買幾檔")
    s.add_argument("--data-start", default="2024-06-01", help="下載資料的起始日")
    s.add_argument("--season-days", type=int, default=20)
    s.add_argument("--eliminate", type=int, default=1)
    s.add_argument("--min-survivors", type=int, default=4)

    daily_parser = s = sub.add_parser("daily", help="每日收盤後：重播聯賽並產生戰報")
    s.add_argument("name")
    s.add_argument("--offline", action="store_true", help="不更新資料，用本機快取")
    s.add_argument("--no-site", action="store_true", help="不產生 dashboard")
    s = sub.add_parser("site", help="只重建 dashboard（改完 profiles.json 或頭像後預覽）")
    s.add_argument("name")
    s.add_argument("--offline", action="store_true", help="不更新資料，用本機快取")
    for s in (daily_parser, s):
        s.add_argument("--publish", action="store_true",
                       help="寫入公開網站 docs/<賽季>/ 並更新 profiles.json（預設只輸出本機預覽 preview/）")
        s.add_argument("--out", help="自訂 dashboard 輸出資料夾")

    s = sub.add_parser("season-report", help="產生季賽報告（Markdown）：前三名總結、淘汰果蠅失敗報告")
    s.add_argument("name")
    s.add_argument("--offline", action="store_true", help="不更新資料，用本機快取")

    s = sub.add_parser("prompts", help="產生角色圖提示詞（給還沒有圖的果蠅），輸出到 notes/prompts/")
    s.add_argument("name")
    s.add_argument("--all", action="store_true", help="連已經有圖的果蠅也產生")
    s.add_argument("--extra", default="", help="追加描述，例如：手裡捏著一張虧損對帳單")

    s = sub.add_parser("publish", help="發布所有賽季（雲端每日執行）：dashboard、季賽報告、賽季總覽首頁")
    s.add_argument("--preview", action="store_true", help="只輸出本機預覽 preview/，不改公開網站與角色檔")
    s.add_argument("--offline", action="store_true", help="不更新資料，用本機快取")

    a = p.parse_args(argv)
    cfg = load_config(a.config)
    {"fetch": cmd_fetch, "probe": cmd_probe, "tournament": cmd_tournament,
     "league-create": cmd_league_create, "season-create": cmd_season_create,
     "daily": cmd_daily, "site": cmd_site, "season-report": cmd_season_report,
     "prompts": cmd_prompts, "publish": cmd_publish}[a.cmd](a, cfg)


if __name__ == "__main__":
    sys.exit(main())
