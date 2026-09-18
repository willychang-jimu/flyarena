(() => {
  const D = JSON.parse(document.getElementById("data").textContent);
  const L = D.league;
  const byId = Object.fromEntries(D.traders.map((t) => [t.id, t]));
  const flies = D.traders.filter((t) => !t.control);
  const state = { filter: "all", q: "", selected: null };
  const $ = (s) => document.querySelector(s);
  const SVGNS = "http://www.w3.org/2000/svg";

  // DOM 小工具：文字一律走 textContent（資料可能被使用者編輯，不當成 HTML）
  function el(tag, attrs = {}, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k != null) e.append(k instanceof Node ? k : document.createTextNode(k));
    return e;
  }
  function sv(tag, attrs = {}, style = {}) {
    const e = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    Object.assign(e.style, style);
    return e;
  }
  const pct = (x, d = 1, sign = true) => (x == null ? "—" : (sign && x > 0 ? "+" : "") + (x * 100).toFixed(d) + "%");
  const fmt = (x, d = 2) => (x == null ? "—" : x.toLocaleString("zh-TW", { minimumFractionDigits: d, maximumFractionDigits: d }));
  function delta(x, d = 1) {
    if (x == null) return el("span", { class: "muted", text: "—" });
    const cls = x > 0 ? "up" : x < 0 ? "down" : "";
    const arrow = x > 0 ? "▲ " : x < 0 ? "▼ " : "";
    return el("span", { class: `${cls} num`, text: arrow + pct(Math.abs(x), d, false) });
  }
  const avatar = (t, size = "") => el("img", { class: `av ${size}`, src: t.avatar, alt: "", loading: "lazy" });
  const label = (t) => `${t.emoji || ""} ${t.nickname}`.trim();
  function status(t) {
    if (t.control) return el("span", { class: "tag", text: "對照組" });
    if (t.eliminated) return el("span", { class: "tag out", text: `第 ${t.eliminated.season} 季淘汰` });
    return el("span", { class: "tag", text: "存活" });
  }

  // 排名：存活果蠅依 Sharpe → 對照組 → 已淘汰（越晚淘汰越前面）
  const sharpe = (t) => (t.stats.sharpe == null ? -Infinity : t.stats.sharpe);
  const ordered = [
    ...flies.filter((t) => t.active).sort((a, b) => sharpe(b) - sharpe(a)),
    ...D.traders.filter((t) => t.control),
    ...flies.filter((t) => !t.active).sort((a, b) => (b.eliminated?.season || 0) - (a.eliminated?.season || 0)),
  ];
  const rank = {};
  ordered.filter((t) => t.active && !t.control).forEach((t, i) => (rank[t.id] = i + 1));
  const leader = ordered[0];
  const buyhold = byId.buyhold;
  state.selected = leader ? leader.id : D.traders[0].id;

  function visible(t) {
    const f = state.filter;
    if (f === "active" && !(t.active && !t.control)) return false;
    if (f === "out" && (t.active || t.control)) return false;
    if (f === "control" && !t.control) return false;
    if (!state.q) return true;
    const hay = [t.id, t.nickname, t.title, t.gene].join(" ").toLowerCase();
    return hay.includes(state.q.toLowerCase());
  }

  // ---- 標題與摘要 ----
  function renderHeader() {
    document.getElementById("title").textContent = `果蠅交易聯賽｜${L.title || L.name}`;
    $("#subtitle").textContent =
      `${L.date} 收盤・第 ${L.season} 季・開賽第 ${L.trading_days} 個交易日・` +
      `每 ${L.season_days} 個交易日淘汰 ${L.eliminate} 隻（剩 ${L.min_survivors} 隻為止）・依 Sharpe 排名`;
    const alive = flies.filter((t) => t.active);
    const beatBench = alive.filter((t) => (t.stats.return ?? -1) > L.benchmark_total).length;
    const beatBH = buyhold ? alive.filter((t) => (t.stats.return ?? -1) > (buyhold.stats.return ?? 0)).length : null;
    const kpi = (lab, value, hint, cls = "") =>
      el("div", { class: `kpi ${cls}` }, el("div", { class: "label", text: lab }), el("div", { class: "value" }, value), hint ? el("div", { class: "hint", text: hint }) : null);
    $("#kpis").replaceChildren(
      leader ? kpi("目前領先", [avatar(leader), label(leader)], `累積 ${pct(leader.stats.return)}`, "hero") : null,
      kpi("大盤今日", delta(L.benchmark_today, 2), "加權指數，不含息"),
      kpi("大盤開賽以來", delta(L.benchmark_total), `自 ${L.start}`),
      kpi("存活果蠅", `${alive.length} / ${flies.length}`),
      kpi("贏過大盤", `${beatBench} 隻`, "存活果蠅中"),
      beatBH == null ? null : kpi("贏過存股阿伯", `${beatBH} 隻`, `買進持有 ${pct(buyhold.stats.return)}`),
    );
  }

  // ---- 資產曲線 ----
  function niceTicks(lo, hi, n = 5) {
    const raw = (hi - lo || 0.01) / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const out = [];
    for (let v = Math.floor(lo / step) * step; v <= hi + step * 0.5; v += step) out.push(+v.toFixed(10));
    return out;
  }
  function linePath(vals, X, Y) {
    let d = "", pen = false;
    vals.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += (pen ? "L" : "M") + X(i).toFixed(1) + "," + Y(v).toFixed(1);
      pen = true;
    });
    return d;
  }
  function chartSeries() {
    const t = byId[state.selected];
    const list = [{ name: `${t.nickname}（${t.id}）`, vals: t.curve, color: "var(--s1)" }];
    if (buyhold && t.id !== "buyhold") list.push({ name: "存股阿伯（買進持有）", vals: buyhold.curve, color: "var(--s2)" });
    list.push({ name: "大盤（加權指數）", vals: D.benchmark, color: "var(--s3)" });
    return list;
  }
  function renderChart() {
    const W = 720, H = 300, ML = 48, MR = 104, MT = 12, MB = 28;
    const n = D.dates.length;
    const series = chartSeries();
    const context = D.traders.filter((t) => visible(t) && t.id !== state.selected && t.id !== "buyhold");
    const all = [...series.flatMap((s) => s.vals), ...context.flatMap((t) => t.curve)].filter((v) => v != null);
    const ticks = niceTicks(Math.min(0, ...all), Math.max(0, ...all));
    const lo = ticks[0], hi = ticks[ticks.length - 1];
    const X = (i) => ML + ((W - ML - MR) * i) / Math.max(1, n - 1);
    const Y = (v) => MT + (H - MT - MB) * (1 - (v - lo) / (hi - lo || 1));
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "資產曲線圖，數值請見表格檢視" });
    for (const v of ticks) {
      svg.append(sv("line", { class: v === 0 ? "zero" : "gridline", x1: ML, x2: W - MR, y1: Y(v), y2: Y(v) }));
      const tx = sv("text", { x: ML - 6, y: Y(v) + 4, "text-anchor": "end" });
      tx.textContent = `${Math.round(v * 100)}%`;
      svg.append(tx);
    }
    let lastMonth = "";
    const months = [];
    D.dates.forEach((d, i) => { const m = d.slice(0, 7); if (m !== lastMonth) { months.push(i); lastMonth = m; } });
    const every = Math.ceil(months.length / 8);
    months.filter((_, j) => j % every === 0).forEach((i) => {
      const tx = sv("text", { x: X(i), y: H - 8, "text-anchor": i === 0 ? "start" : "middle" });
      tx.textContent = `${+D.dates[i].slice(5, 7)}月`;
      svg.append(tx);
    });
    for (const t of context) svg.append(sv("path", { class: "ctx", d: linePath(t.curve, X, Y) }));
    for (const s of [...series].reverse()) svg.append(sv("path", { class: "series", d: linePath(s.vals, X, Y) }, { stroke: s.color }));

    // 線尾標籤：太靠近就省略次要的那條（圖例仍然有）
    const ends = [];
    for (const s of series) {
      let i = s.vals.length - 1;
      while (i >= 0 && s.vals[i] == null) i--;
      if (i < 0) continue;
      const y = Y(s.vals[i]);
      if (ends.some((e) => Math.abs(e - y) < 13)) continue;
      ends.push(y);
      svg.append(sv("circle", { class: "dot", cx: X(i), cy: y, r: 4 }, { fill: s.color }));
      const tx = sv("text", { x: X(i) + 8, y: y + 4 }, { fill: "var(--ink-2)" });
      tx.textContent = `${s.name.split("（")[0]} ${pct(s.vals[i], 0)}`;
      svg.append(tx);
    }

    // 十字游標與提示
    const cross = sv("line", { class: "cross", y1: MT, y2: H - MB, visibility: "hidden" });
    const dots = series.map((s) => sv("circle", { class: "dot", r: 4, visibility: "hidden" }, { fill: s.color }));
    const hit = sv("rect", { x: ML, y: MT, width: W - ML - MR, height: H - MT - MB, fill: "transparent", tabindex: 0 });
    svg.append(cross, ...dots, hit);
    const tip = $("#tip");
    let cursor = n - 1;
    function show(i, clientX, clientY) {
      cursor = Math.max(0, Math.min(n - 1, i));
      cross.setAttribute("x1", X(cursor)); cross.setAttribute("x2", X(cursor));
      cross.setAttribute("visibility", "visible");
      const rows = [el("div", { class: "muted", text: D.dates[cursor] })];
      series.forEach((s, j) => {
        const v = s.vals[cursor];
        dots[j].setAttribute("visibility", v == null ? "hidden" : "visible");
        if (v != null) { dots[j].setAttribute("cx", X(cursor)); dots[j].setAttribute("cy", Y(v)); }
        rows.push(el("div", { class: "row" },
          el("span", { class: "name" }, el("i", { class: "key", style: `background:${s.color}` }), s.name),
          el("b", { text: pct(v) })));
      });
      tip.replaceChildren(...rows);
      tip.hidden = false;
      const box = svg.getBoundingClientRect();
      const px = clientX ?? box.left + (X(cursor) / W) * box.width;
      const py = clientY ?? box.top + box.height / 3;
      const left = Math.min(px + 14, innerWidth - tip.offsetWidth - 8);
      tip.style.left = `${Math.max(8, left)}px`;
      tip.style.top = `${Math.max(8, py - tip.offsetHeight - 12)}px`;
    }
    function hide() { cross.setAttribute("visibility", "hidden"); dots.forEach((d) => d.setAttribute("visibility", "hidden")); tip.hidden = true; }
    hit.addEventListener("pointermove", (e) => {
      const box = svg.getBoundingClientRect();
      const x = ((e.clientX - box.left) / box.width) * W;
      show(Math.round(((x - ML) / (W - ML - MR)) * (n - 1)), e.clientX, e.clientY);
    });
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("blur", hide);
    hit.addEventListener("focus", () => show(cursor));
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); show(cursor + (e.key === "ArrowLeft" ? -1 : 1)); }
    });
    $("#chart").replaceChildren(svg);
    $("#legend").replaceChildren(...series.map((s) => el("span", {}, el("i", { class: "key", style: `background:${s.color}` }), s.name)),
      el("span", {}, el("i", { class: "key", style: "background:var(--context)" }), "其他交易員"));
    const table = el("table", {}, el("tr", {}, el("th", { class: "l", text: "日期" }), ...series.map((s) => el("th", { text: s.name }))),
      ...D.dates.map((d, i) => el("tr", {}, el("td", { class: "l", text: d }), ...series.map((s) => el("td", { text: pct(s.vals[i]) })))).reverse());
    $("#chart-table").replaceChildren(table);
  }

  // ---- 詳情面板 ----
  function traitBlock(t) {
    if (!t.traits) return null;
    const rows = [];
    for (const k of ["學習速度", "記性", "冒險心", "專注", "積極"]) {
      const v = t.traits[k] ?? 0;
      rows.push(el("span", { text: k }), el("div", { class: "meter", title: `${Math.round(v * 100)} 分（族群百分位）` }, el("i", { style: `width:${Math.round(v * 100)}%` })));
    }
    const lean = t.traits["多空傾向"] ?? 0;
    const w = Math.min(50, Math.abs(lean) * 50);
    rows.push(el("span", { text: "多空" }), el("div", { class: "lean", title: `買進比例減賣出比例：${pct(lean, 0)}` },
      el("i", { style: lean >= 0 ? `left:50%;width:${w}%;background:var(--buy)` : `right:50%;width:${w}%;background:var(--sell)` })));
    return el("div", { class: "traits" }, rows);
  }
  function nodeButton(id) {
    const t = byId[id];
    if (!t) return el("span", { class: "ghostnode", text: `${id}（淘汰賽中出局）` });
    return el("button", { class: "node", type: "button", onclick: () => select(id) }, avatar(t), `${t.nickname}（${t.id}）`);
  }
  function renderDetail() {
    const t = byId[state.selected];
    const s = t.stats;
    const stat = (k, v) => [el("span", { text: k }), el("b", { class: "num" }, v)];
    const today = t.today;
    const decisions = today.decisions.filter((d) => d.action !== "HOLD" && d.selected !== false);
    const skipped = today.decisions.filter((d) => d.action === "BUY" && d.selected === false).length;
    $("#detail").replaceChildren(
      el("div", { class: "hero" }, avatar(t, "xl"),
        el("div", {}, el("h3", { text: label(t) }), el("div", { class: "muted small", text: t.control ? "對照組" : `${t.id}・第 ${t.generation} 代` }),
          el("div", {}, el("span", { class: "tag", text: t.title }), " ", status(t)))),
      el("p", { class: "ink2 small", text: t.bio }),
      el("div", { class: "section" }, el("h4", { text: "成績" }), el("div", { class: "grid" },
        stat("累積報酬", delta(s.return)), stat("今日", delta(s.today_change, 2)),
        stat("Sharpe", fmt(s.sharpe)), stat("最大回撤", pct(s.max_drawdown, 1, false)),
        stat("命中率", pct(s.hit_rate, 1, false)), stat("IC", fmt(s.ic, 3)),
        stat("成交次數", fmt(s.trades, 0)), stat("交易成本", fmt(s.costs, 0)),
        stat("獎勵 / 懲罰", `${fmt(s.rewards, 0)} / ${fmt(s.punishments, 0)}`), stat("記憶變化", fmt(s.memory, 3)))),
      t.traits ? el("div", { class: "section" }, el("h4", { text: "個性特質（和族群比較）" }), traitBlock(t)) : null,
      el("div", { class: "section" }, el("h4", { text: `今天（${L.date}）` }),
        el("div", {}, decisions.length ? decisions.map((d) => el("span", { class: `chip ${d.action}`, text: `${d.name} ${d.action === "BUY" ? "買" : "賣"}` })) : el("span", { class: "muted small", text: "收盤後沒有買賣決策" })),
        skipped ? el("div", { class: "small muted", text: `另有 ${skipped} 檔想買但沒入選（每日買進上限）` }) : null,
        el("div", { class: "small ink2", text: today.fills.length ? "開盤成交：" + today.fills.map((f) => `${f.side === "BUY" ? "買" : "賣"} ${f.name} ${f.shares.toLocaleString()} 股`).join("、") : "今天開盤沒有成交" }),
        el("div", { class: "small ink2", text: `多巴胺：獎勵 ${today.reward} 次、懲罰 ${today.punish} 次` }),
        el("div", { class: "small muted", text: "庫存：" + (t.positions.length ? t.positions.map((p) => `${p.name} ${p.shares.toLocaleString()} 股`).join("、") : "空手") })),
      t.control ? null : el("div", { class: "section" }, el("h4", { text: "家族" }),
        el("div", { class: "small" }, "父親：", t.parent ? nodeButton(t.parent) : el("span", { class: "muted", text: "初代果蠅" })),
        el("div", { class: "small" }, "子代：", t.children.length ? t.children.map(nodeButton) : el("span", { class: "muted", text: "無" }))),
      el("div", { class: "section" }, el("h4", { text: "最近 10 個交易日的買賣決策" }),
        t.recent.length ? el("div", { class: "scroll" }, el("table", {},
          el("tr", {}, el("th", { class: "l", text: "日期" }), el("th", { class: "l", text: "標的" }), el("th", { text: "決策" }), el("th", { text: "結果" })),
          t.recent.map((r) => el("tr", {}, el("td", { class: "l", text: r.date.slice(5) }), el("td", { class: "l", text: r.name }),
            el("td", {}, el("span", { class: `chip ${r.action}`, text: r.action === "BUY" ? "買" : "賣" })), el("td", { class: "small", text: r.note }))))) :
          el("span", { class: "muted small", text: "沒有買賣決策" })),
    );
  }

  // ---- 排行榜 ----
  function sparkline(vals) {
    const pts = vals.filter((v) => v != null);
    const svg = sv("svg", { viewBox: "0 0 80 24", width: 80, height: 24, "aria-hidden": "true" });
    if (pts.length < 2) return svg;
    const lo = Math.min(...pts), hi = Math.max(...pts);
    const X = (i) => (78 * i) / (pts.length - 1) + 1;
    const Y = (v) => 22 - (20 * (v - lo)) / (hi - lo || 1);
    svg.append(sv("path", { d: linePath(pts, X, Y), fill: "none", "stroke-width": 1.5 }, { stroke: "var(--muted)" }));
    svg.append(sv("circle", { cx: X(pts.length - 1), cy: Y(pts[pts.length - 1]), r: 2.5 }, { fill: "var(--s1)" }));
    return svg;
  }
  function renderBoard() {
    const head = el("thead", {}, el("tr", {}, ["名次", "交易員", "個性", "今日", "累積報酬", "Sharpe", "最大回撤", "命中率", "成交", "走勢"]
      .map((h, i) => el("th", { class: i === 1 || i === 2 ? "l" : "", text: h }))));
    const body = el("tbody");
    for (const t of ordered.filter(visible)) {
      const s = t.stats;
      body.append(el("tr", {
        class: [t.active || t.control ? "" : "out", t.id === state.selected ? "selected" : ""].join(" "),
        tabindex: 0, "aria-selected": String(t.id === state.selected),
        onclick: () => select(t.id), onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(t.id); } },
      },
        el("td", { text: t.control ? "—" : t.active ? String(rank[t.id]) : "淘汰" }),
        el("td", { class: "l" }, el("div", { class: "who" }, avatar(t), el("div", {}, label(t), el("br"), el("small", { text: t.id })))),
        el("td", { class: "l" }, el("span", { class: "tag", text: t.title })),
        el("td", {}, delta(s.today_change, 2)), el("td", {}, delta(s.return)),
        el("td", { text: fmt(s.sharpe) }), el("td", { text: pct(s.max_drawdown, 1, false) }),
        el("td", { text: pct(s.hit_rate, 1, false) }), el("td", { text: fmt(s.trades, 0) }),
        el("td", {}, sparkline(t.curve))));
    }
    $("#board").replaceChildren(head, body);
  }

  // ---- 角色卡 ----
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function holoTracking(card) {
    // 亮面反光與彩光跟著指標移動；卡片同時微微傾斜，像拿在手上看
    const move = (e) => {
      const b = card.getBoundingClientRect();
      const x = ((e.clientX - b.left) / b.width) * 100;
      const y = ((e.clientY - b.top) / b.height) * 100;
      card.style.setProperty("--mx", `${x.toFixed(1)}%`);
      card.style.setProperty("--my", `${y.toFixed(1)}%`);
      card.style.setProperty("--angle", ((x + y) * 1.8).toFixed(0));
      if (!REDUCED) card.style.transform = `perspective(900px) rotateY(${(x - 50) / 8}deg) rotateX(${(50 - y) / 9}deg) translateY(-2px)`;
    };
    const reset = () => {
      card.style.transform = "";
      card.style.setProperty("--mx", "50%");
      card.style.setProperty("--my", "50%");
    };
    card.addEventListener("pointermove", move);
    card.addEventListener("pointerleave", reset);
    card.addEventListener("blur", reset);
  }

  function renderCards() {
    $("#cards").replaceChildren(...ordered.filter(visible).map((t) => {
      const c = t.card;
      const ttl = t.titles;
      const badge = t.control ? "對照組" : t.active ? `#${String(rank[t.id]).padStart(2, "0")}` : `第 ${t.eliminated.season} 季淘汰`;
      const badges = [];
      if (ttl.league) badges.push(el("span", { text: `🏆 屆冠軍 ×${ttl.league}` }));
      if (ttl.season) badges.push(el("span", { text: `🥇 季冠軍 ×${ttl.season}` }));
      const stat = (label, value) => el("div", {}, el("b", { text: value }), el("span", { text: label }));
      const card = el("button", {
        type: "button",
        class: ["fly", ttl.tier, t.active || t.control ? "" : "out", t.id === state.selected ? "selected" : ""].join(" "),
        style: `--from:${c.from};--to:${c.to};--pill:${c.pill}`,
        "aria-pressed": String(t.id === state.selected), title: t.bio, onclick: () => select(t.id),
      },
        el("div", { class: "card-top" }, el("span", { text: badge }),
          el("span", { class: "tier", text: t.control ? c.code : `${c.code}・${ttl.tier_name}` })),
        el("div", { class: "card-art" }, el("img", { src: t.avatar, alt: "", loading: "lazy" })),
        badges.length ? el("div", { class: "card-badges" }, badges) : null,
        el("div", { class: "card-name", text: t.nickname }),
        el("div", { class: "card-stats" },
          stat("累積報酬", pct(t.stats.return, 0)),
          stat("Sharpe", fmt(t.stats.sharpe, 1)),
          stat("命中率", pct(t.stats.hit_rate, 0, false))),
        el("div", { class: "card-foot" }, el("span", { text: t.title }), delta(t.stats.today_change, 2)));
      holoTracking(card);
      return card;
    }));
  }

  // ---- 家族樹、淘汰紀錄、說明 ----
  function renderTree() {
    const kids = {};
    for (const t of flies) (kids[t.parent || ""] ||= []).push(t.id);
    const branch = (id) => {
      const children = (kids[id] || []).sort();
      return el("li", {}, nodeButton(id), byId[id]?.eliminated ? el("span", { class: "tag out", text: `第 ${byId[id].eliminated.season} 季淘汰` }) : null,
        children.length ? el("ul", {}, children.map(branch)) : null);
    };
    const roots = [...(kids[""] || []), ...Object.keys(kids).filter((p) => p && !byId[p])].sort();
    $("#tree").replaceChildren(el("ul", {}, roots.map(branch)));
  }
  function renderTimeline() {
    const items = [...D.eliminations].sort((a, b) => a.season - b.season);
    $("#timeline").replaceChildren(...(items.length ? items.map((e) => {
      const t = byId[e.name];
      return el("li", {}, el("span", { class: "when", text: `第 ${e.season} 季・${e.date.slice(5)}` }),
        t ? avatar(t) : null, el("span", {}, t ? `${label(t)}（${t.id}）` : e.name),
        t ? el("span", { class: "muted small" }, "累積 ", delta(t.stats.return)) : null);
    }) : [el("li", { class: "muted", text: "還沒有果蠅被淘汰" })]));
  }
  function renderAbout() {
    const modes = { action_contingent: "依決策結果結算（幾天後看方向對不對，扣掉交易成本）", equity_binary: "每日資產漲跌（固定強度）",
      equity_proportional: "每日資產漲跌（依幅度）", shuffled: "打亂的獎懲（對照實驗）", none: "不給獎懲" };
    const p = (text) => el("p", { text });
    $("#about").replaceChildren(
      p("每隻果蠅是一個簡化的果蠅蘑菇體模型（果蠅學習與記憶的腦區）。每天收盤後，行情被編碼成一種「氣味」輸入大腦，輸出神經元決定買、賣或不動，隔天開盤以模擬價格成交。"),
      p(`獎懲方式：${modes[L.reward_mode] || L.reward_mode}。做對了刺激獎勵型多巴胺、做錯了刺激懲罰型多巴胺，改變牠的連結強度，這就是學習。`),
      p(`每隻果蠅模擬本金 ${L.capital.toLocaleString()} 元，單筆 ${L.order_value.toLocaleString()} 元，每 ${L.trade_every_days} 個交易日決策一次，含手續費與證交稅。`),
      p("對照組：骰子（隨機交易）、存股阿伯（買進持有）、追高哥（簡單動能規則）。果蠅要穩定贏過牠們，才代表學到了東西；在大盤上漲時贏過骰子，並不稀奇。"),
      p("暱稱取自真實的果蠅突變基因，個性由每隻果蠅的大腦參數和交易行為自動推算。"),
      p("角色卡的稀有度依戰績決定：拿過季冠軍（某一季結算時排第 1）是閃卡，奪下一屆冠軍是金卡，"
        + "兩屆以上冠軍是彩虹卡；卡面顯示名次、累積報酬、Sharpe 與命中率，冠軍次數會跟著果蠅帶到下一屆。"),
    );
    $("#footer").textContent = `資料日期 ${L.date}・資料指紋 ${L.fingerprint}・網頁只含模擬成績，不含原始股價・非投資建議`;
  }

  function select(id) {
    state.selected = id;
    renderBoard(); renderCards(); renderChart(); renderDetail();
    if (innerWidth < 900) $("#detail").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function refresh() { renderBoard(); renderCards(); renderChart(); }

  document.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    state.filter = b.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    refresh();
  }));
  $("#search").addEventListener("input", (e) => { state.q = e.target.value.trim(); refresh(); });

  const modes = [null, "dark", "light"];
  let theme = null;
  try { theme = localStorage.getItem("flyarena-theme"); } catch (e) { theme = null; }
  function applyTheme() {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
    else document.documentElement.removeAttribute("data-theme");
    $("#theme").title = theme === "dark" ? "目前：深色" : theme === "light" ? "目前：淺色" : "目前：跟隨系統";
  }
  $("#theme").addEventListener("click", () => {
    theme = modes[(modes.indexOf(theme) + 1) % modes.length];
    applyTheme();
    try { theme ? localStorage.setItem("flyarena-theme", theme) : localStorage.removeItem("flyarena-theme"); } catch (e) { /* 無痕模式 */ }
  });
  applyTheme();

  renderHeader(); renderBoard(); renderCards(); renderChart(); renderDetail(); renderTree(); renderTimeline(); renderAbout();
})();
