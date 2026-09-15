"""指令介面。用法：python -m flyarena <指令> --help"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import backtest, dashboard, data, league, probe, report, store, tournament
from .brains import make_brain

ROOT = Path(__file__).resolve().parent.parent


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
        market = backtest.Market(data.load_all(cfg), cfg)
        entries = [
            (f"fly-{i:03d}", make_brain("mushroom", market.n_pn, cfg["brain"], 1000 + i),
             {"generation": 0, "parent": None})
            for i in range(a.new)
        ]
    folder = league.create(a.name, cfg, entries, a.start, a.season_days, a.eliminate, a.min_survivors)
    print(f"聯賽建立於 {folder}，參賽 {len(entries)} 隻，開賽日 {a.start}")


def cmd_daily(a, cfg):
    result = league.replay(a.name, refresh=not a.offline)
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
        print("Dashboard：", dashboard.build(result, snap, a.out))


def cmd_site(a, cfg):
    result = league.replay(a.name, refresh=not a.offline)
    snap = league.snapshot(result)
    print("Dashboard：", dashboard.build(result, snap, a.out))
    print("角色檔（可修改暱稱、個性、頭像）：", league.LEAGUES / a.name / "profiles.json")


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
    s = sub.add_parser("daily", help="每日收盤後：重播聯賽並產生戰報")
    s.add_argument("name")
    s.add_argument("--offline", action="store_true", help="不更新資料，用本機快取")
    s.add_argument("--no-site", action="store_true", help="不更新 dashboard")
    s.add_argument("--out", default=str(ROOT / "docs"), help="dashboard 輸出資料夾（GitHub Pages 用 docs/）")
    s = sub.add_parser("site", help="只重建 dashboard（改完 profiles.json 或頭像後使用）")
    s.add_argument("name")
    s.add_argument("--offline", action="store_true", help="不更新資料，用本機快取")
    s.add_argument("--out", default=str(ROOT / "docs"), help="dashboard 輸出資料夾")
    a = p.parse_args(argv)
    cfg = load_config(a.config)
    {"fetch": cmd_fetch, "probe": cmd_probe, "tournament": cmd_tournament,
     "league-create": cmd_league_create, "daily": cmd_daily, "site": cmd_site}[a.cmd](a, cfg)


if __name__ == "__main__":
    sys.exit(main())
