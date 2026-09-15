"""季賽報告（Markdown）：賽況總覽、各季排名、前三名總結、淘汰果蠅失敗報告、研究觀察。

python -m flyarena season-report 聯賽名稱 [--offline]
→ notes/season-reports/<聯賽>_<資料日期>.md
"""

import math
from pathlib import Path

import numpy as np

from . import analysis, league, profiles, store
from .analysis import FEATURE_ZH

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notes" / "season-reports"
SHORT = ("ret_1", "ret_3", "ret_5", "ret_10", "range_20", "ma_20")
LONG = ("ret_20", "ret_60", "range_60", "ma_60")
MARKET = ("mkt_1", "mkt_5", "mkt_20")


def pct(x, d=1, sign=True):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:+.{d}%}" if sign else f"{x:.{d}%}"


def num(x, d=2):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{d}f}"


def style(prefs, floor):
    """把超過雜訊門檻的訊號偏好翻成白話的交易風格。"""
    if not prefs:
        return "（沒有可分析的學習結構）"
    def group(keys, label, up, down):
        sig = [(k, prefs[k]) for k in keys if k in prefs and abs(prefs[k]) > floor]
        pos = sum(v for _, v in sig if v > 0)
        neg = -sum(v for _, v in sig if v < 0)
        if not sig:
            return None
        if pos and neg and min(pos, neg) > 0.5 * max(pos, neg):  # 同一組訊號方向相反，不硬下結論
            ups = "、".join(FEATURE_ZH[k] for k, v in sig if v > 0)
            downs = "、".join(FEATURE_ZH[k] for k, v in sig if v < 0)
            return f"{label}方向不一致（{ups}越高越想買，{downs}越高越想賣）"
        return up if pos > neg else down

    parts = [
        group(SHORT, "短線訊號", "短線強勢（近幾天上漲、位在 20 日高檔）時想買", "短線轉弱時想買（短線逢低）"),
        group(LONG, "長線訊號", "長期漲多時仍想買（長線追漲）", "長期已經漲多時傾向賣出（長線獲利了結）"),
        group(MARKET, "大盤訊號", "大盤越強越想買", "大盤越弱反而越想買"),
        group(("rel_20",), "", "偏好比大盤強的股票", "偏好比大盤弱的股票"),
        group(("vol_20",), "", "波動越大越積極", "波動越大越想賣出"),
        group(("volume_ratio",), "", "放量時想買", "量縮時想買"),
    ]
    return "；".join(p for p in parts if p) or "還看不出穩定的訊號偏好（都在雜訊範圍內）"


def signal_list(prefs, floor, positive, top=3):
    items = sorted(prefs.items(), key=lambda kv: -kv[1] if positive else kv[1])
    chosen = [(k, v) for k, v in items if (v > floor if positive else v < -floor)][:top]
    return "、".join(f"{FEATURE_ZH.get(k, k)}（{v:+.3f}）" for k, v in chosen) or "無（都在雜訊範圍內）"


def who(name, prof):
    x = prof[name]
    return f"{x['emoji']} {x['nickname']}（{name}，{x['title']}，第 {x['family']['generation']} 代）"


def metrics_table(p):
    perf, risk, sig = p["perf"], p["risk"], p["signal"]
    rows = [
        ("累積報酬", pct(perf["return"])), ("同期大盤", pct(p["bench_return"])),
        ("Sharpe", num(perf["sharpe"])), ("最大回撤", pct(perf["max_drawdown"], 1, False)),
        ("平均持股比例", pct(p["exposure"], 0, False)), ("Beta（跟大盤連動程度）", num(risk["beta"])),
        ("年化 Alpha（扣掉大盤連動後的超額報酬）", pct(risk["alpha"])),
        ("判斷命中率", pct(sig["hit_rate"], 1, False)), ("IC（判斷與後續報酬的相關）", num(sig["ic"], 3)),
        ("成交次數", f"{perf['trades']:,}"), ("交易成本（手續費＋稅）", f"{perf['costs']:,.0f} 元"),
        ("多巴胺 獎勵／懲罰", f"{p['rewards']['reward']} / {p['rewards']['punish']}"),
        ("記憶變化", num(p["memory"], 3)),
    ]
    return "| 指標 | 數值 |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)


def timing_lines(p, horizon):
    q = p["quality"]
    lines = [f"買進判斷 {q['BUY']['n']:,} 次，之後 {horizon} 天平均 {pct(q['BUY']['mean'], 2)}，方向命中 {pct(q['BUY']['hit'], 1, False)}",
             f"賣出判斷 {q['SELL']['n']:,} 次，之後 {horizon} 天平均 {pct(q['SELL']['mean'], 2)}，方向命中 {pct(q['SELL']['hit'], 1, False)}",
             f"不動 {q['HOLD']['n']:,} 次，之後 {horizon} 天平均 {pct(q['HOLD']['mean'], 2)}"]
    b, h, s = q["BUY"]["mean"], q["HOLD"]["mean"], q["SELL"]["mean"]
    if math.isfinite(b) and math.isfinite(h):
        lines.append(f"⚠️ 買進後的平均報酬（{pct(b, 2)}）比不動的日子（{pct(h, 2)}）還低：挑的買點沒有比隨便一天好"
                     if b < h else f"買進後的平均報酬（{pct(b, 2)}）高於不動的日子（{pct(h, 2)}），買點可能有一點選擇能力，仍需更多樣本確認")
    if math.isfinite(s) and s > 0:
        lines.append(f"賣出後股價平均還漲 {pct(s, 2)}：多數賣出發生在上漲途中")
    return lines


def top_section(rank, p, prof, cfg):
    horizon = cfg["reward"].get("horizon_days", 5)
    attr = p["attribution"]
    lines = [f"### 第 {rank} 名：{who(p['name'], prof)}", "", metrics_table(p), "",
             "**投資對了什麼（與做錯什麼）**", ""]
    winners = [(s, a) for s, a in attr.items() if a["pnl"] > 0][:3]
    losers = [(s, a) for s, a in reversed(list(attr.items())) if a["pnl"] < 0][:2]
    for label, group in (("賺錢", winners), ("賠錢", losers)):
        for s, a in group:
            win = f"，賣出獲利 {a['wins']}/{a['sells']} 次" if a["sells"] else ""
            hold = f"，目前還持有 {a['shares']:,} 股" if a["shares"] else ""
            lines.append(f"- {label}：{a['name']} {a['pnl']:+,.0f} 元（買 {a['buys']} 次、賣 {a['sells']} 次{win}{hold}）")
    beta, alpha = p["risk"]["beta"], p["risk"]["alpha"]
    source = ("報酬主要來自跟著大盤上漲，而不是選股或擇時。" if not math.isfinite(alpha) or alpha <= 0.02
              else "扣除大盤影響後仍有正的超額報酬，但一季的結果仍可能是運氣。")
    lines.append(f"- 報酬拆解：Beta {num(beta)}，代表大盤每漲 1%，牠平均跟著漲約 {num(beta)}%；"
                 f"扣掉這部分後的年化 Alpha 是 {pct(alpha)}。{source}")
    lines += [f"- {x}" for x in timing_lines(p, horizon)]
    floor = p["prefs_floor"]
    lines += ["", "**學習準則分析**", "",
              f"- 交易風格：{style(p['prefs_now'], floor)}",
              f"- 最想買的訊號：{signal_list(p['prefs_now'], floor, True)}",
              f"- 最想賣的訊號：{signal_list(p['prefs_now'], floor, False)}"]
    if p["prefs_change"]:
        lines += [f"- 開賽以來新學到、變得更想買的訊號：{signal_list(p['prefs_change'], floor, True)}",
                  f"- 開賽以來變得更想賣的訊號：{signal_list(p['prefs_change'], floor, False)}"]
    lines.append(f"- 數值是訊號從偏低（−2σ）變成偏高（+2σ）時，「買進輸出神經元 − 賣出輸出神經元」的變化，正值＝訊號越高越想買；"
                 f"雜訊門檻 ±{floor:.3f}，低於門檻的不列入。")
    return "\n".join(lines)


def failure_section(p, window, peers, rank, prof, cfg, elim, season_days):
    q = p["quality"]
    n = sum(q[k]["n"] for k in q) or 1
    lines = [f"### 第 {elim['season']} 季淘汰（{elim['date']}）：{who(p['name'], prof)}", "",
             f"存活 {p['days_alive']} 個交易日，淘汰時排名 {rank} / {len(peers)}，報酬 {pct(p['perf']['return'])}（同期大盤 {pct(p['bench_return'])}），"
             f"平均持股比例 {pct(p['exposure'], 0, False)}，成交 {p['perf']['trades']} 次。", "",
             "**可能的失敗原因（和同一段期間還在比賽的果蠅比較）**", ""]
    lines += [f"- {r}" for r in analysis.failure_reasons(p, window, peers, cfg, season_days)]
    lines += ["", f"- 決策比例：買 {q['BUY']['n'] / n:.0%}、不動 {q['HOLD']['n'] / n:.0%}、賣 {q['SELL']['n'] / n:.0%}",
              f"- 被淘汰時的交易風格：{style(p['prefs_now'], p['prefs_floor'])}"]
    return "\n".join(lines)


def observations(alive, dead, controls, bench):
    mean = lambda xs: float(np.mean(xs)) if xs else float("nan")
    worse = sum(1 for p in alive if p["quality"]["BUY"]["mean"] < p["quality"]["HOLD"]["mean"])
    lines = ["## 研究觀察與限制", "",
             f"- 存活果蠅平均 Beta {num(mean([p['risk']['beta'] for p in alive]))}、平均年化 Alpha "
             f"{pct(mean([p['risk']['alpha'] for p in alive]))}：報酬大多可以用「跟著大盤漲」解釋。",
             f"- 存活果蠅平均命中率 {pct(mean([p['signal']['hit_rate'] for p in alive]), 1, False)}、平均 IC "
             f"{num(mean([p['signal']['ic'] for p in alive]), 3)}；命中率低於 50%、IC 為負，代表還沒有方向判斷能力的證據。",
             f"- {worse} / {len(alive)} 隻存活果蠅，買進後的平均報酬低於「不動」的日子：挑選買點的能力還沒有出現。"]
    if dead:
        lines.append(f"- 淘汰果蠅平均持股比例 {pct(mean([p['exposure'] for p in dead]), 0, False)}，存活果蠅 "
                     f"{pct(mean([p['exposure'] for p in alive]), 0, False)}：多頭行情中，持股比例較高的果蠅名次普遍較好。")
    bh = next((p for p in controls if p["name"] == "buyhold"), None)
    if bh:
        lines.append(f"- 存股阿伯（買進持有）{pct(bh['perf']['return'])}，同期大盤 {pct(bench)}。"
                     "果蠅要在盤整或下跌行情也贏過牠，才能說學到了有用的東西。")
    lines += ["- 這是單一聯賽、單一隨機種子、一段多頭行情的結果；換 seed、換行情重跑之前，不宜下結論。",
              "- 淘汰規則依 Sharpe，會獎勵「波動小、跟著大盤漲」的果蠅，不一定是判斷最準的果蠅。",
              "- 訊號偏好是用人工刺激量測大腦的反應，代表「牠傾向怎麼反應」，不代表這些訊號真的能預測股價。"]
    return lines


def build(name, refresh=False):
    result = league.replay(name, refresh=refresh)
    cfg, market, rules = result["cfg"], result["market"], result["rules"]
    capital, days = cfg["broker"]["capital"], result["days"]
    snap = league.snapshot(result)
    prof = profiles.build(league.LEAGUES / name, snap["rows"], save=False)
    initial = {n: b for n, b, _ in store.load_brains(league.LEAGUES / name)}
    elim = {e["name"]: e for e in result["eliminated"]}
    data = {t.name: analysis.profile(t, result, cfg, initial) for t in result["traders"]}
    flies = [t for t in result["traders"] if not t.meta.get("control")]
    alive = sorted((data[t.name] for t in flies if t.name not in elim), key=lambda p: -p["perf"]["sharpe"])
    controls = [data[t.name] for t in result["traders"] if t.meta.get("control")]
    bench, season_days = snap["benchmark_total"], rules["season_days"]
    ranks = analysis.season_ranks(result, cfg)
    seasons = max((max(v) for v in ranks.values()), default=0)

    md = [f"# 季賽報告｜{name}（資料截至 {snap['date']}）", "",
          "> 這是果蠅神經模型的模擬交易實驗，所有買賣都是虛擬的，不構成任何投資建議。", "",
          "## 賽況總覽", "",
          f"- 開賽 {rules['start']}，目前第 {snap['season']} 季（每 {season_days} 個交易日一季），共 {snap['trading_days']} 個交易日",
          f"- 大盤（加權指數，不含息）開賽以來 {pct(bench)}",
          f"- 存活果蠅 {len(alive)} / {len(flies)} 隻；贏過大盤 {sum(p['perf']['return'] > bench for p in alive)} 隻",
          "- 對照組：" + "、".join(f"{prof[p['name']]['nickname']} {pct(p['perf']['return'])}（Sharpe {num(p['perf']['sharpe'])}）" for p in controls),
          "", "### 各季排名變化（依截至當季的 Sharpe，1 為最佳）", "",
          "| 果蠅 | " + " | ".join(f"S{i}" for i in range(1, seasons + 1)) + " | 結果 |",
          "|---|" + "---|" * (seasons + 1)]
    for t in sorted(flies, key=lambda t: (t.name in elim, -data[t.name]["perf"]["sharpe"])):
        r = ranks.get(t.name, {})
        end = f"第 {elim[t.name]['season']} 季淘汰" if t.name in elim else "存活"
        md.append(f"| {prof[t.name]['nickname']}（{t.name}） | " + " | ".join(str(r.get(i, "")) for i in range(1, seasons + 1)) + f" | {end} |")

    md += ["", "## 前三名總結", ""]
    for i, p in enumerate(alive[:3], 1):
        md += [top_section(i, p, prof, cfg), ""]

    order = sorted(elim.values(), key=lambda e: e["season"])
    md += ["## 淘汰果蠅失敗報告", "",
           "| 淘汰季 | 果蠅 | 個性 | 存活天數 | 報酬 | 同期大盤 | Sharpe | 持股比例 | 成交 | 成本 |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for e in order:
        p = data[e["name"]]
        md.append(f"| {e['season']} | {prof[e['name']]['nickname']}（{e['name']}） | {prof[e['name']]['title']} | {p['days_alive']} | "
                  f"{pct(p['perf']['return'])} | {pct(p['bench_return'])} | {num(p['perf']['sharpe'])} | "
                  f"{pct(p['exposure'], 0, False)} | {p['perf']['trades']} | {p['perf']['costs']:,.0f} |")
    md.append("")
    for e in order:
        end = data[e["name"]]["last_day"]
        field = [t for t in flies if elim.get(t.name, {"season": 99})["season"] >= e["season"]]
        peers = [analysis.window_stats(t, market, days, capital, end) for t in field]
        window = peers[[t.name for t in field].index(e["name"])]
        md += [failure_section(data[e["name"]], window, peers, ranks[e["name"]][e["season"]],
                               prof, cfg, e, season_days), ""]

    md += observations(alive, [data[e["name"]] for e in order], controls, bench)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}_{snap['date']}.md"
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return path
