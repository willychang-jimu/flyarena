"""產生靜態 HTML 戰報（單一檔案、無外部資源，瀏覽器直接開）。
台股慣例：紅色 = 上漲，綠色 = 下跌。"""

import html
import json
import math
from pathlib import Path

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--up:#d0342c;--down:#16875a;
--s0:#2f6fdf;--s1:#d0342c;--s2:#e08a00;--s3:#7a4fd6;--s4:#0f9aa8;--s5:#b0467a;--grey:#b9b9bd}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1d1d20;--fg:#ececee;--muted:#9a9aa0;--line:#2e2e33;
--up:#ff6b61;--down:#3ccf8e;--s0:#6f9cff;--s1:#ff6b61;--s2:#ffb340;--s3:#a98bff;--s4:#39c6d4;--s5:#e27aad;--grey:#55555c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.55 system-ui,"Microsoft JhengHei","PingFang TC",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 10px}
.sub{color:var(--muted);margin-bottom:18px}
.kpis{display:flex;flex-wrap:wrap;gap:10px}.kpi{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:10px 14px;min-width:140px}.kpi b{display:block;font-size:20px}
.kpi span{color:var(--muted);font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:10px 0}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:12px}th:first-child,td:first-child,td.l,th.l{text-align:left}
tr.out td{color:var(--muted)}tr.ctrl td{font-style:italic}
.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}
.chip{display:inline-block;border-radius:6px;padding:1px 7px;margin:2px;font-size:12px;border:1px solid var(--line)}
.chip.BUY{background:color-mix(in srgb,var(--up) 14%,transparent)}
.chip.SELL{background:color-mix(in srgb,var(--down) 14%,transparent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.bar{height:10px;border-radius:5px;background:var(--s0)}.bar.floor{background:var(--grey)}
.check{margin:4px 0}.note{color:var(--muted);font-size:13px}
svg text{fill:var(--muted);font-size:11px}svg .grid{stroke:var(--line)}
a{color:var(--s0)}
"""
PALETTE = ["var(--s0)", "var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)"]


def esc(x):
    return html.escape(str(x))


def pct(x, digits=1, color=True, sign=True):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return '<span class="muted">—</span>'
    cls = "up" if x > 0 else "down" if x < 0 else ""
    text = f"{x:+.{digits}%}" if sign else f"{x:.{digits}%}"
    return f'<span class="{cls}">{text}</span>' if color else text


def num(x, digits=2):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{digits}f}"


def page(title, body):
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def write(path, title, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page(title, body), encoding="utf-8")
    return path


def line_chart(series, styles=None, order=None, fmt=lambda v: f"{v:+.0%}", height=280):
    """series：{名稱: [(x, y), ...]}；x 預設為可排序的日期字串，order 可指定順序。"""
    styles = styles or {}
    xs = order or sorted({x for s in series.values() for x, _ in s})
    if len(xs) < 2:
        return ""
    xi = {x: i for i, x in enumerate(xs)}
    ys = [y for s in series.values() for _, y in s]
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    W, H, L, R, T, B = 900, height, 58, 130, 12, 26
    X = lambda i: L + (W - L - R) * i / (len(xs) - 1)
    Y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    parts = []
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        parts.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                     f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{esc(fmt(v))}</text>')
    for i in (0, len(xs) // 2, len(xs) - 1):
        anchor = "start" if i == 0 else "end" if i == len(xs) - 1 else "middle"
        parts.append(f'<text x="{X(i):.1f}" y="{H - 6}" text-anchor="{anchor}">{esc(xs[i])}</text>')
    step = max(1, len(xs) // 500)
    labels = []
    for name, pts in series.items():
        st = styles.get(name, {})
        pts = [p for j, p in enumerate(pts) if j % step == 0 or j == len(pts) - 1]
        d = " ".join(f"{'M' if j == 0 else 'L'}{X(xi[x]):.1f},{Y(y):.1f}" for j, (x, y) in enumerate(pts))
        dash = ' stroke-dasharray="5 4"' if st.get("dash") else ""
        parts.append(f'<path d="{d}" fill="none" stroke="{st.get("color", "var(--grey)")}" '
                     f'stroke-width="{st.get("width", 1.2)}"{dash}><title>{esc(name)}</title></path>')
        if st.get("label") and pts:
            labels.append([Y(pts[-1][1]), X(xi[pts[-1][0]]), name, st.get("color", "var(--grey)")])
    labels.sort()
    for j in range(1, len(labels)):  # 標籤避免重疊
        labels[j][0] = max(labels[j][0], labels[j - 1][0] + 13)
    for y, x, name, color in labels:
        parts.append(f'<text x="{x + 6:.1f}" y="{y + 4:.1f}" style="fill:{color}">{esc(name)}</text>')
    return f'<div class="scroll"><svg viewBox="0 0 {W} {H}" width="100%" role="img">{"".join(parts)}</svg></div>'


def ranking_table(rows, today=False):
    head = ["名次", "名字", "類型"] + (["今日"] if today else []) + [
        "累積報酬", "Sharpe", "最大回撤", "命中率", "判斷數", "IC", "成交", "成本", "獎/懲", "記憶變化"]
    out = ["<div class='scroll'><table><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>"]
    rank = 0
    for r in rows:
        control = (r.get("meta") or {}).get("control")
        active = r.get("active", True)
        if active and not control:
            rank += 1
        cls = "ctrl" if control else "" if active else "out"
        kind = "對照組" if control else f"第{(r.get('meta') or {}).get('generation', 0)}代"
        cells = [str(rank) if active and not control else ("—" if control else "淘汰"),
                 esc(r["name"]), kind]
        if today:
            cells.append(pct(r.get("today_change"), 2))
        cells += [pct(r.get("return")), num(r.get("sharpe")), pct(r.get("max_drawdown"), 1, False, False),
                  pct(r.get("hit_rate"), 1, False, False), str(r.get("calls", 0)), num(r.get("ic"), 3),
                  str(r.get("trades", 0)), num(r.get("costs"), 0),
                  f"{r.get('rewards', 0)}/{r.get('punishments', 0)}", num(r.get("memory"), 3)]
        out.append(f"<tr class='{cls}'>" + "".join(
            f"<td class='l'>{c}</td>" if i in (1, 2) else f"<td>{c}</td>" for i, c in enumerate(cells)) + "</tr>")
    return "".join(out) + "</table></div>"


def equity_series(rows, capital, highlight=3):
    series, styles, color = {}, {}, 0
    for r in rows:
        if not r.get("curve"):
            continue
        control = (r.get("meta") or {}).get("control")
        series[r["name"]] = [(d, e / capital - 1) for d, e in r["curve"]]
        if control:
            styles[r["name"]] = {"color": "var(--muted)", "dash": True, "label": True}
        elif color < highlight and r.get("active", True):
            styles[r["name"]] = {"color": PALETTE[color], "width": 2.2, "label": True}
            color += 1
    return series, styles


def daily_page(snap, path, capital, past_dates=()):
    active = [r for r in snap["rows"] if r["active"] and not (r.get("meta") or {}).get("control")]
    leader = active[0] if active else None
    body = [f"<h1>果蠅交易聯賽｜{esc(snap['league'])}</h1>",
            f"<div class='sub'>{esc(snap['date'])} 收盤後戰報・第 {snap['season']} 季・開賽第 {snap['trading_days']} 個交易日・"
            f"模擬交易，非投資建議</div><div class='kpis'>",
            f"<div class='kpi'><span>大盤今日</span><b>{pct(snap['benchmark_today'], 2)}</b></div>",
            f"<div class='kpi'><span>大盤開賽以來</span><b>{pct(snap['benchmark_total'])}</b></div>",
            f"<div class='kpi'><span>存活果蠅</span><b>{len(active)}</b></div>"]
    if leader:
        body.append(f"<div class='kpi'><span>目前領先</span><b>{esc(leader['name'])}</b>{pct(leader['return'])}</div>")
    body.append("</div><h2>排行榜</h2>" + ranking_table(snap["rows"], today=True))
    series, styles = equity_series(snap["rows"], capital)
    body.append("<h2>資產曲線（開賽以來報酬）</h2><div class='card'>" + line_chart(series, styles) +
                "<div class='note'>彩色：前三名；虛線：對照組；灰色：其他果蠅</div></div>")
    body.append("<h2>今天每隻果蠅做了什麼</h2><div class='grid'>")
    for r in snap["rows"]:
        if not r["active"]:
            continue
        chips = "".join(f"<span class='chip {esc(d['action'])}'>{esc(d['symbol'].replace('.TW', ''))} {esc(d['action'])}</span>"
                        for d in r["decisions"]) or "<span class='muted'>今天沒有決策</span>"
        fills = "".join(f"<div>{esc(f['side'])} {esc(f['symbol'])} {f['shares']:,} 股 @ {f['price']:.2f}"
                        f"（費 {f['fee']:.0f}、稅 {f['tax']:.0f}）</div>" for f in r["fills"]) or "<span class='muted'>無成交</span>"
        dop = r["dopamine"]
        good = sum(1 for x in dop if x["value"] > 0)
        dopamine = f"獎勵 {good} 次、懲罰 {len(dop) - good} 次" if dop else "無"
        pos = "、".join(f"{esc(s.replace('.TW', ''))} {n:,}" for s, n in r["positions"].items()) or "空手"
        body.append(f"<div class='card'><b>{esc(r['name'])}</b> {pct(r.get('today_change'), 2)}"
                    f"<div>收盤後決策（明天開盤執行）：{chips}</div><div>今天開盤成交：{fills}</div>"
                    f"<div>多巴胺：{dopamine}</div><div class='note'>庫存：{pos}</div></div>")
    body.append("</div>")
    if snap["eliminated"]:
        body.append("<h2>淘汰紀錄</h2><div class='card'>" + "".join(
            f"<div>第 {e['season']} 季（{esc(e['date'])}）淘汰 <b>{esc(e['name'])}</b></div>" for e in snap["eliminated"]) + "</div>")
    if past_dates:
        body.append("<h2>歷史戰報</h2><div class='card'>" + " ".join(
            f"<a href='{esc(d)}.html'>{esc(d)}</a>" for d in past_dates) + "</div>")
    body.append(f"<p class='note'>資料指紋 {esc(snap['fingerprint'])}：若和前幾天不同，代表資料源改寫了歷史價格，"
                "重播後的過去名次可能改變。</p>")
    return write(path, f"果蠅聯賽 {snap['date']}", "".join(body))


def verdict(final):
    rows = {r["name"]: r for r in final["rows"]}
    get = lambda n, k: rows.get(n, {}).get(k, float("nan"))
    checks = [
        ("冠軍的 Sharpe 高於買進持有", get("冠軍", "sharpe"), get("buyhold", "sharpe")),
        ("冠軍的 Sharpe 高於隨機交易員", get("冠軍", "sharpe"), get("random", "sharpe")),
        ("保留記憶（凍結）勝過清空記憶（失憶）→ 記憶有用", get("冠軍・凍結", "sharpe"), get("冠軍・失憶", "sharpe")),
        ("正確獎懲勝過亂獎懲雙胞胎 → 學到的是因果", get("冠軍", "sharpe"), get("冠軍・亂獎懲雙胞胎", "sharpe")),
        ("判斷命中率高於 52%", get("冠軍", "hit_rate"), 0.52),
    ]
    out = []
    for text, a, b in checks:
        ok = math.isfinite(a) and math.isfinite(b) and a > b
        out.append(f"<div class='check'>{'✅' if ok else '❌'} {esc(text)}"
                   f"<span class='muted'>（{num(a, 3)} vs {num(b, 3)}）</span></div>")
    return "".join(out)


def tournament_page(result, cfg, path):
    rounds, final = result["rounds"], result["final"]
    capital = cfg["broker"]["capital"]
    body = [f"<h1>🏆 果蠅淘汰賽報告</h1><div class='sub'>族群 {cfg['tournament']['population']} 隻・"
            f"{len(rounds)} 回合・評分 {esc(cfg['tournament']['score'])}・獎懲 {esc(cfg['reward']['mode'])}</div>",
            "<h2>各回合</h2><div class='scroll'><table><tr><th>回合</th><th class='l'>期間</th><th>大盤</th>"
            "<th class='l'>冠軍</th><th>冠軍報酬</th><th>冠軍 Sharpe</th><th>買進持有</th><th class='l'>淘汰</th><th class='l'>新生</th></tr>"]
    for r in rounds:
        c = r["flies"][0]
        bh = next((x for x in r["controls"] if x["name"] == "buyhold"), {})
        born = "、".join(f"{b['name']}←{b['parent']}" for b in r["born"])
        body.append(f"<tr><td>{r['round']}</td><td class='l'>{esc(r['start'])}~{esc(r['end'])}</td><td>{pct(r['benchmark'])}</td>"
                    f"<td class='l'>{esc(c['name'])}</td><td>{pct(c['return'])}</td><td>{num(c['sharpe'])}</td>"
                    f"<td>{pct(bh.get('return'))}</td><td class='l'>{esc('、'.join(r['eliminated']))}</td><td class='l'>{esc(born)}</td></tr>")
    body.append("</table></div>")
    body.append(f"<h2>最終驗證：沒比過的測試期 {esc(final['start'])} ~ {esc(final['end'])}</h2>"
                f"<div class='kpis'><div class='kpi'><span>大盤</span><b>{pct(final['benchmark'])}</b></div></div>")
    rows = [dict(r, curve=final["curves"].get(r["name"]),
                 meta=dict(r.get("meta") or {}, control=r["kind"] != "mushroom")) for r in final["rows"]]
    body.append(ranking_table(rows))
    series, styles = equity_series(rows, capital, highlight=4)
    body.append("<div class='card'>" + line_chart(series, styles) + "</div>")
    body.append("<h2>自動檢核</h2><div class='card'>" + verdict(final) +
                "<p class='note'>這只是一個隨機種子、一段測試期的結果。要下結論，請換不同 seed 重跑多次，"
                "看這些 ✅ 是否穩定出現；只出現一次很可能是運氣。</p></div>")
    return write(path, "果蠅淘汰賽報告", "".join(body))


def probe_page(runs, tunings, path):
    """runs：{標籤: conditioning 曲線}；tunings：{標籤: sensitivity dict}"""
    stages = [s for s, _ in next(iter(runs.values()))]
    series = {label: [(s, acc["平均"]) for s, acc in curve] for label, curve in runs.items()}
    styles = {label: {"color": PALETTE[i], "width": 2.2, "label": True} for i, label in enumerate(runs)}
    series["隨機水準"] = [(s, 1 / 3) for s in stages]
    styles["隨機水準"] = {"color": "var(--muted)", "dash": True, "label": True}
    body = ["<h1>🧪 訊號反應測試</h1><div class='sub'>比照果蠅「氣味＋電擊」制約實驗：多頭→BUY、空頭→SELL、盤整→HOLD，之後規則反轉</div>",
            "<h2>學習曲線（平均正確率）</h2><div class='card'>" +
            line_chart(series, styles, order=stages, fmt=lambda v: f"{v:.0%}") + "</div>"]
    body.append("<h2>各階段正確率</h2><div class='scroll'><table><tr><th class='l'>階段</th>" +
                "".join(f"<th>{esc(l)}・{p}</th>" for l in runs for p in ("多頭", "空頭", "盤整")) + "</tr>")
    for i, s in enumerate(stages):
        body.append(f"<tr><td class='l'>{esc(s)}</td>" + "".join(
            f"<td>{runs[l][i][1][p]:.0%}</td>" for l in runs for p in ("多頭", "空頭", "盤整")) + "</tr>")
    body.append("</table></div>")
    if tunings:
        labels = list(tunings)
        floor = tunings[labels[-1]]
        top = max([*tunings[labels[0]].values(), *floor.values(), 1e-9])
        body.append(f"<h2>對各訊號的反應強度</h2><p class='note'>藍色 = {esc(labels[0])}，灰色 = {esc(labels[-1])}（對照）。"
                    "數值是「BUY 輸出減 SELL 輸出」隨該訊號變化的幅度；藍色明顯長過灰色，才是真的學到有反應。"
                    "訓練用的多頭／空頭圖樣由 ret_5、ret_20、ma_20、range_20 組成。</p><div class='card scroll'><table>")
        for name, v in tunings[labels[0]].items():
            f = floor.get(name, 0)
            body.append(f"<tr><td class='l'>{esc(name)}</td><td style='width:70%'>"
                        f"<div class='bar' style='width:{v / top * 100:.0f}%'></div>"
                        f"<div class='bar floor' style='width:{f / top * 100:.0f}%;margin-top:3px'></div></td>"
                        f"<td>{v:.3f} / {f:.3f}</td></tr>")
        body.append("</table></div>")
    return write(path, "訊號反應測試", "".join(body))


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
