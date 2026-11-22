/* Breakout Screener front end. No dependencies: data comes from data/*.json written by the
   daily GitHub Action; charts are drawn on <canvas> by the small Chart class below. */
(() => {
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = (x, d = 2) => x == null || isNaN(x) ? "–" : Number(x).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d});
const sgn = (x, d = 1) => x == null || isNaN(x) ? "–" : (x > 0 ? "+" : "") + fmt(x, d) + "%";
const cls = x => x > 0 ? "pos" : x < 0 ? "neg" : "";
const vol = v => v >= 1e9 ? fmt(v / 1e9, 2) + "B" : v >= 1e6 ? fmt(v / 1e6, 2) + "M" : v >= 1e3 ? fmt(v / 1e3, 0) + "K" : String(v);
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const prettyDate = s => { const [y, m, d] = s.split("-").map(Number); return `${MONTHS[m - 1]} ${d}, ${y}`; };

const S = { latest: null, history: [], pattern: "all", status: "all", q: "", sort: "score",
            open: new Set(), charts: new Map(), hist: "all", frame: "D" };
try { if (localStorage.getItem("frame") === "W") S.frame = "W"; } catch (e) {}
const MA_LABELS = {D: ["50", "150", "200"], W: ["10w", "30w", "40w"]};
const maLegend = f => MA_LABELS[f].map((t, i) => `<span style="color:var(${["--ma50", "--ma150", "--ma200"][i]})">${t}</span>`).join("");

/* ------------------------------------------------------------------ boot */
async function load() {
  try {
    const bust = "?t=" + Math.floor(Date.now() / 300000);
    const [l, h] = await Promise.all([
      fetch("data/latest.json" + bust).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch("data/history.json" + bust).then(r => r.ok ? r.json() : []).catch(() => []),
    ]);
    S.latest = l; S.history = h || [];
  } catch (e) {
    $("#asof").textContent = "No data yet";
    $("#list").innerHTML = `<div class="empty">Couldn't load today's results (${esc(e.message)}).<br>
      If you just set this up, run the workflow once from the Actions tab.</div>`;
    return;
  }
  const L = S.latest;
  $("#asof").textContent = `US close ${prettyDate(L.data_date)} · updated ${L.generated_hkt} HKT`;
  $("#demo-note").hidden = !L.demo;
  const ageDays = (Date.now() - new Date(L.data_date + "T21:00:00Z")) / 864e5;
  if (ageDays > 4 && !L.demo) {
    const n = $("#stale-note"); n.hidden = false;
    n.textContent = `Data is ${Math.floor(ageDays)} days old. Check the Actions tab on GitHub for a failed run.`;
  }
  renderMarket(); renderChips(); renderList(); renderHistory(); renderRules();
  bind(); route();
}

function bind() {
  $$("#status-seg button").forEach(b => b.onclick = () => {
    S.status = b.dataset.status; $$("#status-seg button").forEach(x => x.classList.toggle("on", x === b)); renderList();
  });
  $("#search").oninput = e => { S.q = e.target.value.trim().toLowerCase(); renderList(); };
  $("#sort").onchange = e => { S.sort = e.target.value; renderList(); };
  $$("#hist-seg button").forEach(b => b.onclick = () => {
    S.hist = b.dataset.h; $$("#hist-seg button").forEach(x => x.classList.toggle("on", x === b)); renderHistoryTable();
  });
  window.addEventListener("hashchange", route);
}

function route() {
  const tab = (location.hash || "#today").slice(1);
  const known = ["today", "history", "rules"].includes(tab) ? tab : "today";
  $$(".view").forEach(v => v.hidden = v.id !== "view-" + known);
  $$(".tabs a").forEach(a => a.classList.toggle("on", a.dataset.tab === known));
  if (known === "today") S.charts.forEach(c => c.resize());
}

/* ------------------------------------------------------------------ market */
function spark(values) {
  if (!values || values.length < 2) return "";
  const lo = Math.min(...values), hi = Math.max(...values), w = 200, h = 34;
  const pts = values.map((v, i) => `${(i / (values.length - 1) * w).toFixed(1)},${(h - 2 - (v - lo) / (hi - lo || 1) * (h - 4)).toFixed(1)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none"
    stroke="var(${up ? "--green" : "--red"})" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
}

function renderMarket() {
  const m = S.latest.market || {};
  const idx = (m.indexes || []).map(i => `
    <div class="idx">
      <div class="idx-head"><b>${esc(i.name)}</b><span>${fmt(i.close)} <span class="${cls(i.chg_pct)}">${sgn(i.chg_pct, 2)}</span></span></div>
      ${spark(i.spark)}
      <div class="checks">
        <span class="${i.above_21ema ? "ok" : "no"}">21-day EMA</span>
        <span class="${i.above_50 ? "ok" : "no"}">50-day</span>
        <span class="${i.above_200 ? "ok" : "no"}">200-day</span>
        <span class="${i.dist_days <= 4 ? "ok" : "no"}" title="${esc((i.dist_dates || []).join(", "))}">${i.dist_days} distribution days</span>
      </div>
    </div>`).join("");
  const b = m.breadth || {};
  $("#market").className = `card market ${m.color || ""}`;
  $("#market").innerHTML = `
    <div class="regime">
      <span class="label">Market condition</span>
      <span class="pill-big"><span class="dot"></span>${esc(m.regime || "Unknown")}</span>
      <p>${esc(m.advice || "")}</p>
    </div>
    <div class="idx-grid">${idx}</div>
    ${b.stocks ? `<div class="breadth">
      <span>Above 50-day: <b>${fmt(b.pct_above_50, 0)}%</b></span>
      <span>Above 200-day: <b>${fmt(b.pct_above_200, 0)}%</b></span>
      <span>New highs / lows: <b class="pos">${b.new_highs}</b> / <b class="neg">${b.new_lows}</b></span>
      <span class="muted">across ${b.stocks.toLocaleString()} liquid stocks</span></div>` : ""}`;
}

/* ------------------------------------------------------------------ candidates */
function renderChips() {
  const c = S.latest.candidates, P = S.latest.patterns;
  const count = k => c.filter(x => k === "all" || x.pattern === k).length;
  const chips = [["all", "All patterns"], ...Object.entries(P)];
  $("#pattern-chips").innerHTML = chips.map(([k, n]) =>
    `<button class="chip ${S.pattern === k ? "on" : ""}" data-p="${k}">${esc(n)}<span class="n">${count(k)}</span></button>`).join("");
  $$("#pattern-chips .chip").forEach(b => b.onclick = () => { S.pattern = b.dataset.p; renderChips(); renderList(); });
}

function filtered() {
  let c = S.latest.candidates.filter(x =>
    (S.pattern === "all" || x.pattern === S.pattern) && (S.status === "all" || x.status === S.status) &&
    (!S.q || x.ticker.toLowerCase().includes(S.q) || (x.name || "").toLowerCase().includes(S.q)));
  const order = {BREAKOUT: 0, SETUP: 1, EXTENDED: 2};
  const by = {
    score: (a, b) => order[a.status] - order[b.status] || b.score - a.score,
    rs: (a, b) => b.rs - a.rs || b.score - a.score,
    pivot: (a, b) => Math.abs(a.vs_pivot_pct) - Math.abs(b.vs_pivot_pct),
    risk: (a, b) => a.risk_pct - b.risk_pct,
    ticker: (a, b) => a.ticker.localeCompare(b.ticker),
  }[S.sort];
  return c.sort(by);
}

const keyOf = c => c.ticker + "|" + c.pattern;
const isNew = c => (S.latest.new_breakouts || []).includes(`${S.latest.data_date}-${c.ticker}-${c.pattern}`);

function renderList() {
  const rows = filtered();
  const st = S.latest.stats || {};
  $("#stats").textContent = st.loaded ? `${st.loaded.toLocaleString()} stocks scanned · ${st.liquid.toLocaleString()} liquid · ` +
    `${st.trend_template.toLocaleString()} pass the Trend Template · ${st.candidates} pattern candidates` : "";
  S.charts.forEach(ch => ch.destroy()); S.charts.clear();
  if (!rows.length) {
    $("#list").innerHTML = `<div class="empty card">${S.latest.candidates.length ? "Nothing matches these filters." :
      "No setups or breakouts today. That's normal in weak markets."}</div>`;
    return;
  }
  const head = `<div class="list-head"><span>Stock</span><span>Signal</span><span class="num">Score</span><span class="num">RS</span>
    <span class="num">Close</span><span class="num">Pivot</span><span class="num">vs pivot</span><span class="num">Stop</span>
    <span class="num">Vol</span><span></span></div>`;
  $("#list").innerHTML = head + rows.map(c => {
    const k = keyOf(c), open = S.open.has(k);
    return `<div class="row ${open ? "open" : ""} ${isNew(c) ? "new" : ""}" data-k="${esc(k)}">
      <div class="row-main" tabindex="0" role="button" aria-expanded="${open}">
        <div class="c-tk tk"><b>${esc(c.ticker)}</b> ${isNew(c) ? '<span class="newtag">NEW</span>' : ""}<span class="nm">${esc(c.name || "")}</span></div>
        <div class="c-badges badges"><span class="st ${c.status}">${c.status}</span><span class="pt">${esc(c.pattern_name)}</span></div>
        <div class="c-score num"><span class="score">${fmt(c.score, 0)}</span><div class="bar"><i style="width:${Math.min(100, c.score)}%"></i></div></div>
        <div class="c-desk num">${c.rs}${c.rs_line_high ? ' <span title="RS line at a new high" class="pos">▲</span>' : ""}</div>
        <div class="c-desk num">${fmt(c.close)}<span class="sub ${cls(c.chg_pct)}">${sgn(c.chg_pct)}</span></div>
        <div class="c-desk num">${fmt(c.pivot)}</div>
        <div class="c-desk num ${cls(c.vs_pivot_pct)}">${sgn(c.vs_pivot_pct)}</div>
        <div class="c-desk num">${fmt(c.stop)}<span class="sub">-${fmt(c.risk_pct, 1)}%</span></div>
        <div class="c-desk num">${c.vol_x != null ? fmt(c.vol_x, 1) + "×" : "–"}</div>
        <div class="caret">›</div>
        <div class="c-nums mobile-nums">
          <div><span class="k">Close</span>${fmt(c.close)}</div>
          <div><span class="k">Pivot</span>${fmt(c.pivot)} <span class="${cls(c.vs_pivot_pct)} small">${sgn(c.vs_pivot_pct)}</span></div>
          <div><span class="k">Stop</span>${fmt(c.stop)} <span class="muted small">-${fmt(c.risk_pct, 1)}%</span></div>
          <div><span class="k">RS · Vol</span>${c.rs} · ${c.vol_x != null ? fmt(c.vol_x, 1) + "×" : "–"}</div>
        </div>
      </div>
      ${open ? detailHTML(c) : ""}
    </div>`;
  }).join("");
  $$("#list .row").forEach(el => {
    const main = $(".row-main", el);
    const toggle = () => {
      const k = el.dataset.k;
      S.open.has(k) ? S.open.delete(k) : S.open.add(k);
      renderList();
    };
    main.onclick = toggle;
    main.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } };
    if (S.open.has(el.dataset.k)) mountChart(el);
  });
}

function detailHTML(c) {
  const tt = c.tt ? Object.entries(c.tt).map(([k, v]) => `<span class="${v ? "ok" : "no"}">${esc(k)}</span>`).join("") : "";
  return `<div class="detail">
    <div class="detail-top">
      <div class="patsel"></div>
      <div class="ctl"><div class="frames"><button data-f="D" class="${S.frame === "D" ? "on" : ""}">Daily</button><button data-f="W" class="${S.frame === "W" ? "on" : ""}">Weekly</button></div>
      <div class="ranges"><button data-r="63">3M</button><button data-r="126">6M</button><button data-r="252" >1Y</button><button data-r="all">All</button></div></div>
    </div>
    <div class="chart-box"><canvas></canvas><div class="legend"></div>
      <div class="legend-ma">${maLegend(S.frame)}</div></div>
    <p class="desc">${esc(c.details)}</p>
    <div class="facts">
      <div class="fact"><div class="k">Buy point</div><div class="v">${fmt(c.entry)}</div></div>
      <div class="fact"><div class="k">Stop</div><div class="v">${fmt(c.stop)} <span class="small muted">-${fmt(c.risk_pct, 1)}%</span></div></div>
      <div class="fact"><div class="k">Base length</div><div class="v">${Math.max(1, Math.round(c.base_days / 5))} wks</div></div>
      <div class="fact"><div class="k">RS rating</div><div class="v">${c.rs}${c.rs_line_high ? ' <span class="small pos">RS line high</span>' : ""}</div></div>
      <div class="fact"><div class="k">Volume today</div><div class="v">${c.vol_x != null ? fmt(c.vol_x, 2) + "× avg" : "–"}</div></div>
    </div>
    <div class="tt">${tt}</div>
    <div class="links"><a href="https://www.tradingview.com/chart/?symbol=${encodeURIComponent(c.ticker)}" target="_blank" rel="noopener">TradingView</a>
      <a href="https://finviz.com/quote.ashx?t=${encodeURIComponent(c.ticker)}" target="_blank" rel="noopener">Finviz</a></div>
  </div>`;
}

async function mountChart(el) {
  const k = el.dataset.k, [ticker, pattern] = k.split("|");
  const canvas = $("canvas", el);
  let data;
  try {
    data = await fetch(`data/charts/${encodeURIComponent(ticker)}.json`).then(r => r.json());
  } catch (e) { $(".legend", el).textContent = "Chart data unavailable"; return; }
  if (!document.body.contains(canvas)) return;
  const ch = new Chart(canvas, $(".legend", el), data, S.frame);
  S.charts.set(k, ch);
  const pats = data.patterns || [];
  let idx = Math.max(0, pats.findIndex(p => p.pattern === pattern));
  const sel = $(".patsel", el);
  sel.innerHTML = pats.map((p, i) => `<button data-i="${i}" class="${i === idx ? "on" : ""}">${esc(p.pattern_name)}</button>`).join("");
  $$("button", sel).forEach(b => b.onclick = () => {
    idx = +b.dataset.i; $$("button", sel).forEach(x => x.classList.toggle("on", x === b)); ch.setPattern(pats[idx]);
  });
  const rbtns = $$(".ranges button", el), fbtns = $$(".frames button", el);
  rbtns.forEach(b => b.onclick = () => { rbtns.forEach(x => x.classList.toggle("on", x === b)); ch.setRange(b.dataset.r); });
  const showFrame = f => {
    fbtns.forEach(x => x.classList.toggle("on", x.dataset.f === f));
    $(".legend-ma", el).innerHTML = maLegend(f);
  };
  if (!data.weekly) { const w = fbtns.find(b => b.dataset.f === "W"); w.disabled = true; w.title = "Weekly data arrives with the next daily run"; showFrame("D"); }
  else showFrame(ch.frame);
  fbtns.forEach(b => b.onclick = () => {
    if (b.disabled || ch.frame === b.dataset.f) return;
    S.frame = b.dataset.f; try { localStorage.setItem("frame", S.frame); } catch (e) {}
    showFrame(S.frame); rbtns.forEach(x => x.classList.remove("on"));
    ch.setFrame(S.frame); ch.fitPattern();
  });
  ch.setPattern(pats[idx]);
  ch.fitPattern();
}

/* ------------------------------------------------------------------ chart */
class Chart {
  constructor(canvas, legend, d, frame = "D") {
    this.cv = canvas; this.ctx = canvas.getContext("2d"); this.legend = legend; this.d = d;
    this.hover = null; this.pat = null; this.pointers = new Map(); this.drag = null;
    this.setFrame(frame, true);
    this.ro = new ResizeObserver(() => this.resize()); this.ro.observe(canvas);
    this.bindEvents(); this.resize();
  }
  /* "D" = daily bars with 50/150/200-day MAs; "W" = weekly bars with 10/30/40-week MAs. */
  setFrame(f, quiet) {
    const d = this.d, w = d.weekly;
    if (f === "W" && !w) f = "D";
    this.frame = f;
    const s = f === "W"
      ? {t: w.t, o: w.o, h: w.h, l: w.l, c: w.c, v: w.v, mas: [w.sma10, w.sma30, w.sma40], volN: 10, pad: 6, view: 78}
      : {t: d.t, o: d.o, h: d.h, l: d.l, c: d.c, v: d.v, mas: [d.sma50, d.sma150, d.sma200], volN: 50, pad: 25, view: 126};
    const N = s.volN;
    s.volAvg = s.v.map((_, i) => i < N - 1 ? null : s.v.slice(i - N + 1, i + 1).reduce((a, b) => a + b, 0) / N);
    this.s = s; this.n = s.t.length;
    const idx = new Map(s.t.map((t, i) => [t, i]));
    // Pattern points are daily dates. On weekly bars, place each one inside its week by weekday.
    this.pos = f === "W" ? t => {
      let lo = 0, hi = this.n - 1;
      if (t > s.t[hi]) return null;
      while (lo < hi) { const m = (lo + hi) >> 1; s.t[m] < t ? lo = m + 1 : hi = m; }
      const dow = new Date(t + "T00:00:00Z").getUTCDay() || 5;
      return lo - 0.5 + (Math.min(5, dow) - 0.5) / 5;
    } : t => idx.get(t) ?? null;
    this.hover = null;
    this.i0 = Math.max(0, this.n - s.view); this.i1 = this.n - 1 + 3;
    if (!quiet) this.draw();
  }
  destroy() { this.ro.disconnect(); }
  colors() {
    const cs = getComputedStyle(document.documentElement), g = n => cs.getPropertyValue(n).trim();
    return {up: g("--up"), down: g("--down"), ma50: g("--ma50"), ma150: g("--ma150"), ma200: g("--ma200"), pat: g("--pat"),
      grid: g("--grid"), text: g("--muted"), fg: g("--text"), card: g("--card"), green: g("--green"), red: g("--red"), line: g("--line")};
  }
  setPattern(p) { this.pat = p; this.draw(); }
  fitPattern() {
    const p = this.pat; let first = this.n - this.s.view;
    if (p) for (const path of p.paths) for (const [t] of path) { const i = this.pos(t); if (i != null) first = Math.min(first, Math.floor(i) - this.s.pad); }
    this.i0 = Math.max(0, first); this.i1 = this.n - 1 + 3; this.draw();
  }
  setRange(r) { const span = r === "all" ? this.n : this.frame === "W" ? Math.round(+r / 252 * 52) : +r; this.i1 = this.n - 1 + 3; this.i0 = Math.max(0, this.i1 - span); this.draw(); }
  resize() {
    const r = this.cv.getBoundingClientRect(); if (!r.width) return;
    const dpr = window.devicePixelRatio || 1;
    this.W = r.width; this.H = r.height;
    this.cv.width = Math.round(r.width * dpr); this.cv.height = Math.round(r.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); this.draw();
  }
  geom() {
    // leave room for the OHLC readout + MA key, which wrap onto extra lines on narrow screens
    const axisW = 62, bottom = 22, top = Math.max(44, (this.legendH || 16) + 30), left = 6, gap = 8;
    const plotW = this.W - axisW - left, total = this.H - bottom - top;
    const priceH = Math.round(total * 0.76), volH = total - priceH - gap;
    const span = this.i1 - this.i0 + 1, bw = plotW / span;
    return {axisW, bottom, top, left, plotW, priceH, volH, volTop: top + priceH + gap, bw};
  }
  x(i, g) { return g.left + (i - this.i0 + 0.5) * g.bw; }
  iAt(px, g) { return Math.round((px - g.left) / g.bw - 0.5 + this.i0); }
  draw() {
    if (!this.W) return;
    const c = this.ctx, d = this.s, g = this.geom(), C = this.colors();
    c.clearRect(0, 0, this.W, this.H);
    const a = Math.max(0, Math.floor(this.i0)), b = Math.min(this.n - 1, Math.ceil(this.i1));
    if (b < a) return;
    let lo = Infinity, hi = -Infinity, vmax = 0;
    for (let i = a; i <= b; i++) { lo = Math.min(lo, d.l[i]); hi = Math.max(hi, d.h[i]); vmax = Math.max(vmax, d.v[i]); }
    if (this.pat) for (const v of [this.pat.pivot, this.pat.stop]) if (v && v > lo * 0.8 && v < hi * 1.25) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
    const pad = (hi - lo) * 0.07 || hi * 0.05; lo -= pad; hi += pad;
    const y = v => g.top + (hi - v) / (hi - lo) * g.priceH;
    const vy = v => g.volTop + g.volH - v / (vmax || 1) * g.volH;
    this.yinv = py => hi - (py - g.top) / g.priceH * (hi - lo);
    const right = g.left + g.plotW;

    // grid + price axis
    c.font = "11px -apple-system, Segoe UI, Roboto, sans-serif"; c.textBaseline = "middle";
    const step = niceStep((hi - lo) / Math.max(3, Math.floor(g.priceH / 55)));
    c.strokeStyle = C.grid; c.fillStyle = C.text; c.lineWidth = 1;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      const yy = Math.round(y(v)) + 0.5; c.beginPath(); c.moveTo(g.left, yy); c.lineTo(right, yy); c.stroke();
      c.fillText(fmtAxis(v, step), right + 8, yy);
    }
    // date axis
    c.textBaseline = "alphabetic"; c.textAlign = "center";
    let lastM = -1, lastX = -999;
    for (let i = a; i <= b; i++) {
      const m = +d.t[i].slice(5, 7);
      if (m !== lastM) {
        const xx = this.x(i, g);
        if (lastM !== -1 && xx - lastX > 42) {
          c.strokeStyle = C.grid; c.beginPath(); c.moveTo(Math.round(xx) + 0.5, g.top); c.lineTo(Math.round(xx) + 0.5, g.volTop + g.volH); c.stroke();
          c.fillStyle = C.text; c.fillText(m === 1 ? d.t[i].slice(0, 4) : MONTHS[m - 1], xx, this.H - 6); lastX = xx;
        }
        lastM = m;
      }
    }
    c.textAlign = "left";

    // clip plot area
    c.save(); c.beginPath(); c.rect(g.left, 0, g.plotW, this.H); c.clip();

    // volume
    const bw = Math.max(1, g.bw * 0.7);
    for (let i = a; i <= b; i++) {
      const up = d.c[i] >= d.o[i]; c.fillStyle = up ? C.up : C.down; c.globalAlpha = 0.45;
      c.fillRect(this.x(i, g) - bw / 2, vy(d.v[i]), bw, g.volTop + g.volH - vy(d.v[i]));
    }
    c.globalAlpha = 1;
    this.line(d.volAvg, a, b, g, vy, C.text, 1);

    // moving averages
    this.line(d.mas[2], a, b, g, y, C.ma200, 1.3);
    this.line(d.mas[1], a, b, g, y, C.ma150, 1.3);
    this.line(d.mas[0], a, b, g, y, C.ma50, 1.3);

    // candles
    for (let i = a; i <= b; i++) {
      const xx = this.x(i, g), up = d.c[i] >= d.o[i], col = up ? C.up : C.down;
      c.strokeStyle = col; c.fillStyle = col; c.lineWidth = 1;
      c.beginPath(); c.moveTo(Math.round(xx) + 0.5, y(d.h[i])); c.lineTo(Math.round(xx) + 0.5, y(d.l[i])); c.stroke();
      const top = y(Math.max(d.o[i], d.c[i])), h = Math.max(1, Math.abs(y(d.o[i]) - y(d.c[i])));
      if (g.bw > 3) { up && g.bw > 5 ? (c.fillStyle = C.card, c.fillRect(xx - bw / 2, top, bw, h), c.strokeRect(xx - bw / 2 + .5, top + .5, bw - 1, h - 1)) : c.fillRect(xx - bw / 2, top, bw, h); }
    }

    // pattern overlay
    const p = this.pat;
    if (p) {
      c.strokeStyle = C.pat; c.lineWidth = 2.2; c.lineJoin = "round";
      for (const path of p.paths) {
        c.beginPath(); let started = false;
        for (const [t, v] of path) { const i = this.pos(t); if (i == null) continue; started ? c.lineTo(this.x(i, g), y(v)) : c.moveTo(this.x(i, g), y(v)); started = true; }
        c.stroke();
        c.fillStyle = C.pat; for (const [t, v] of path) { const i = this.pos(t); if (i == null) continue; c.beginPath(); c.arc(this.x(i, g), y(v), 3, 0, 7); c.fill(); }
      }
      c.font = "600 11px -apple-system, Segoe UI, Roboto, sans-serif";
      for (const [t, v, txt, pos] of p.labels) {
        const i = this.pos(t); if (i == null) continue;
        const xx = this.x(i, g), yy = y(v) + (pos === "above" ? -12 : 14), w = c.measureText(txt).width + 8;
        c.fillStyle = C.card; c.globalAlpha = 0.85; c.fillRect(xx - w / 2, yy - 8, w, 15); c.globalAlpha = 1;
        c.fillStyle = C.pat; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(txt, xx, yy);
      }
      c.textAlign = "left";
    }
    c.restore();

    // pivot / stop lines with axis tags
    if (p) {
      // keep the two price tags from overlapping when pivot and stop are close on screen
      const gapPx = y(p.stop) - y(p.pivot), push = gapPx < 19 ? (19 - gapPx) / 2 : 0;
      this.hline(p.pivot, y, g, C.green, [6, 4], "Pivot", C, -push, false);
      this.hline(p.stop, y, g, C.red, [2, 3], "Stop", C, push, gapPx < 16);
    }

    // crosshair + legend
    const hi_ = this.hover != null ? Math.max(a, Math.min(b, this.hover.i)) : this.n - 1;
    if (this.hover) {
      const xx = Math.round(this.x(hi_, g)) + 0.5;
      c.strokeStyle = C.text; c.setLineDash([3, 3]); c.lineWidth = 1;
      c.beginPath(); c.moveTo(xx, g.top); c.lineTo(xx, g.volTop + g.volH); c.stroke();
      if (this.hover.y > g.top && this.hover.y < g.top + g.priceH) {
        const yy = Math.round(this.hover.y) + 0.5;
        c.beginPath(); c.moveTo(g.left, yy); c.lineTo(right, yy); c.stroke(); c.setLineDash([]);
        this.tag(right, yy, fmt(this.yinv(this.hover.y)), C.fg, C.card);
      }
      c.setLineDash([]);
    }
    const i = hi_, chg = i > 0 ? (d.c[i] / d.c[i - 1] - 1) * 100 : 0;
    this.legend.innerHTML = `<b>${esc(this.d.ticker)}</b><span class="k">${this.frame === "W" ? "Week to " : ""}${prettyDate(d.t[i])}</span>
      <span><span class="k">O</span> ${fmt(d.o[i])}</span><span><span class="k">H</span> ${fmt(d.h[i])}</span>
      <span><span class="k">L</span> ${fmt(d.l[i])}</span><span><span class="k">C</span> ${fmt(d.c[i])} <span class="${cls(chg)}">${sgn(chg, 2)}</span></span>
      <span><span class="k">Vol</span> ${vol(d.v[i])}</span>`;
    const lh = this.legend.offsetHeight;
    if (lh && lh !== this.legendH) {
      this.legendH = lh;
      const ma = this.legend.nextElementSibling; if (ma) ma.style.top = (lh + 10) + "px";
      this.draw();
    }
  }
  line(arr, a, b, g, y, col, w) {
    const c = this.ctx; c.strokeStyle = col; c.lineWidth = w; c.beginPath(); let on = false;
    for (let i = a; i <= b; i++) { const v = arr[i]; if (v == null) { on = false; continue; } const xx = this.x(i, g), yy = y(v); on ? c.lineTo(xx, yy) : c.moveTo(xx, yy); on = true; }
    c.stroke();
  }
  hline(v, y, g, col, dash, text, C, tagShift = 0, labelBelow = false) {
    const c = this.ctx, yy = Math.round(y(v)) + 0.5;
    if (yy < g.top || yy > g.top + g.priceH) return;
    c.strokeStyle = col; c.lineWidth = 1.2; c.setLineDash(dash); c.beginPath(); c.moveTo(g.left, yy); c.lineTo(g.left + g.plotW, yy); c.stroke(); c.setLineDash([]);
    this.tag(g.left + g.plotW, yy + tagShift, fmt(v), "#fff", col);
    c.font = "600 11px -apple-system, Segoe UI, Roboto, sans-serif"; c.fillStyle = col; c.textBaseline = labelBelow ? "top" : "bottom";
    c.fillText(text, g.left + 6, labelBelow ? yy + 3 : yy - 3); c.textBaseline = "middle";
  }
  tag(x, y, text, fg, bg) {
    const c = this.ctx; c.font = "11px -apple-system, Segoe UI, Roboto, sans-serif";
    const w = Math.max(54, c.measureText(text).width + 10);
    c.fillStyle = bg; c.fillRect(x + 2, y - 9, w, 18); c.fillStyle = fg; c.textBaseline = "middle"; c.fillText(text, x + 7, y);
  }
  clampView() {
    const span = this.i1 - this.i0, minSpan = 20, maxSpan = this.n + 5;
    if (span < minSpan) { const m = (this.i0 + this.i1) / 2; this.i0 = m - minSpan / 2; this.i1 = m + minSpan / 2; }
    if (span > maxSpan) { this.i0 = -2; this.i1 = this.n + 3; }
    if (this.i1 > this.n + 8) { const s = this.i1 - this.i0; this.i1 = this.n + 8; this.i0 = this.i1 - s; }
    if (this.i0 < -5) { const s = this.i1 - this.i0; this.i0 = -5; this.i1 = this.i0 + s; }
  }
  zoom(factor, px) {
    const g = this.geom(), at = Math.max(0, Math.min(1, (px - g.left) / g.plotW));
    const span = this.i1 - this.i0, ns = span * factor, pivot = this.i0 + span * at;
    this.i0 = pivot - ns * at; this.i1 = this.i0 + ns; this.clampView(); this.draw();
  }
  bindEvents() {
    const cv = this.cv;
    const pos = e => { const r = cv.getBoundingClientRect(); return {x: e.clientX - r.left, y: e.clientY - r.top}; };
    cv.addEventListener("pointerdown", e => {
      this.pointers.set(e.pointerId, pos(e)); cv.setPointerCapture(e.pointerId);
      if (this.pointers.size === 1) this.drag = {x: pos(e).x, i0: this.i0, i1: this.i1, moved: false};
      if (this.pointers.size === 2) { const [p1, p2] = [...this.pointers.values()]; this.pinch = {d: Math.abs(p1.x - p2.x) || 1, i0: this.i0, i1: this.i1, mid: (p1.x + p2.x) / 2}; this.drag = null; }
    });
    cv.addEventListener("pointermove", e => {
      const p = pos(e), g = this.geom();
      if (this.pointers.has(e.pointerId)) this.pointers.set(e.pointerId, p);
      if (this.pinch && this.pointers.size === 2) {
        const [p1, p2] = [...this.pointers.values()], dnow = Math.abs(p1.x - p2.x) || 1;
        const span0 = this.pinch.i1 - this.pinch.i0, ns = span0 * this.pinch.d / dnow, at = (this.pinch.mid - g.left) / g.plotW;
        const pv = this.pinch.i0 + span0 * at; this.i0 = pv - ns * at; this.i1 = this.i0 + ns; this.clampView(); this.draw(); return;
      }
      if (this.drag && this.pointers.size === 1) {
        const dx = p.x - this.drag.x;
        if (Math.abs(dx) > 3) this.drag.moved = true;
        if (this.drag.moved) { const sh = dx / g.bw; this.i0 = this.drag.i0 - sh; this.i1 = this.drag.i1 - sh; this.clampView(); }
      }
      this.hover = {i: this.iAt(p.x, g), y: p.y}; this.draw();
    });
    const end = e => { this.pointers.delete(e.pointerId); if (this.pointers.size < 2) this.pinch = null; if (!this.pointers.size) this.drag = null; };
    cv.addEventListener("pointerup", end); cv.addEventListener("pointercancel", end);
    cv.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") { this.hover = null; this.draw(); } });
    cv.addEventListener("wheel", e => { e.preventDefault(); this.zoom(Math.exp(e.deltaY * 0.0015), pos(e).x); }, {passive: false});
    cv.addEventListener("dblclick", () => this.fitPattern());
  }
}

function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
}
function fmtAxis(v, step) { const d = step >= 1 ? 0 : step >= 0.1 ? 1 : 2; return fmt(v, d); }

/* ------------------------------------------------------------------ history */
function renderHistory() {
  const H = S.history;
  const done = H.filter(r => r.days >= 1);
  const wins = done.filter(r => r.ret_pct > 0);
  const avg = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;
  const card = (k, v, c = "") => `<div class="card"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`;
  const ar = avg(done.map(r => r.ret_pct)), am = avg(done.map(r => r.max_pct));
  $("#hist-summary").innerHTML = card("Breakouts tracked", H.length) +
    card("Win rate", done.length ? fmt(wins.length / done.length * 100, 0) + "%" : "–") +
    card("Avg return", ar == null ? "–" : sgn(ar), cls(ar)) +
    card("Avg best gain", am == null ? "–" : sgn(am), cls(am)) +
    card("Hit the stop", done.length ? fmt(done.filter(r => r.status === "stopped").length / done.length * 100, 0) + "%" : "–");
  const P = S.latest.patterns || {};
  const rows = Object.entries(P).map(([k, name]) => {
    const g = done.filter(r => r.pattern === k); if (!g.length) return "";
    const a1 = avg(g.map(r => r.ret_pct)), a2 = avg(g.map(r => r.max_pct));
    return `<tr><td>${esc(name)}</td><td class="num">${g.length}</td><td class="num">${fmt(g.filter(r => r.ret_pct > 0).length / g.length * 100, 0)}%</td>
      <td class="num ${cls(a1)}">${sgn(a1)}</td><td class="num ${cls(a2)}">${sgn(a2)}</td>
      <td class="num">${fmt(g.filter(r => r.status === "stopped").length / g.length * 100, 0)}%</td></tr>`;
  }).join("");
  $("#hist-patterns").innerHTML = rows ? `<table><thead><tr><th>Pattern</th><th class="num">Signals</th><th class="num">Win rate</th>
    <th class="num">Avg return</th><th class="num">Avg best</th><th class="num">Stopped</th></tr></thead><tbody>${rows}</tbody></table>`
    : `<span class="muted">Per-pattern results appear once breakouts have at least one day of trading.</span>`;
  renderHistoryTable();
}

function renderHistoryTable() {
  const H = S.history.filter(r => S.hist === "all" || r.status === S.hist)
    .sort((a, b) => b.date.localeCompare(a.date) || b.score - a.score);
  if (!H.length) { $("#hist-list").innerHTML = `<div class="empty">No breakouts recorded yet. New ones are added every morning.</div>`; return; }
  $("#hist-list").innerHTML = `<table><thead><tr><th>Date</th><th>Stock</th><th>Pattern</th><th class="num">Entry</th>
    <th class="num">Stop</th><th class="num">Last / exit</th><th class="num">Return</th><th class="num">Best</th>
    <th class="num">Days</th><th>Status</th></tr></thead><tbody>${H.map(r => `<tr>
      <td>${esc(r.date)}</td><td><b>${esc(r.ticker)}</b> <span class="muted small">${esc(r.name || "")}</span></td>
      <td>${esc(r.pattern_name)}${r.signal === "EXTENDED" ? ' <span class="muted small">(ext)</span>' : ""}</td>
      <td class="num">${fmt(r.entry)}</td><td class="num">${fmt(r.stop)}</td><td class="num">${fmt(r.last)}</td>
      <td class="num ${cls(r.ret_pct)}">${sgn(r.ret_pct)}</td><td class="num ${cls(r.max_pct)}">${sgn(r.max_pct)}</td>
      <td class="num">${r.days}</td><td><span class="st ${r.status}">${r.status}${r.exit_date ? " " + esc(r.exit_date.slice(5)) : ""}</span></td>
    </tr>`).join("")}</tbody></table>`;
}

/* ------------------------------------------------------------------ rules */
function renderRules() {
  $("#rules").innerHTML = `
  <h2>How the daily scan works</h2>
  <ul>
    <li>Runs every weekday at about 7:30am Hong Kong time, after the US close, on all US-listed common stocks (no ETFs, warrants or preferreds).</li>
    <li>Liquidity: price at least $10 and 50-day average dollar volume at least $5M.</li>
    <li><b>RS rating</b>: 12-month performance with the latest quarter double-weighted, ranked 1–99 against every stock scanned. ▲ means the RS line versus the S&amp;P 500 is at or near a new high.</li>
    <li><b>Setup</b>: a valid base with price within a few % of the pivot. Place a buy-stop just above the pivot.</li>
    <li><b>Breakout</b>: yesterday was a valid setup and today closed above the pivot on at least 1.4× average volume, in the upper half of the day's range.</li>
    <li><b>Extended</b>: a breakout that closed more than 5% past the pivot. Don't chase it; wait for a pullback or the next base.</li>
    <li><b>Stop</b>: the low of the final contraction, handle or base, but never more than 8% below the buy point.</li>
    <li><b>Score</b> (0–100): pattern quality (75), RS rating (15) and closeness to the pivot (10).</li>
  </ul>
  <h2>VCP (Minervini)</h2>
  <ul><li>Passes all 8 Trend Template criteria (price above a rising 200-day, 50 &gt; 150 &gt; 200-day, 30%+ off the low, within 25% of the high, RS ≥ 70).</li>
    <li>2–6 contractions from the base high, each with a higher low. First contraction ≤ 40%, final ≤ 10%, and the final at most half the first.</li>
    <li>10-day volume ≤ 0.85× the 50-day average. Pivot = high of the final contraction.</li></ul>
  <h2>Cup with handle (O'Neil)</h2>
  <ul><li>30%+ advance into the left-side high. Above the 200-day; RS ≥ 60.</li>
    <li>Cup 6+ weeks from the left high to the right high, 12–35% deep (50% when the market isn't in a clean uptrend), rounded rather than V-shaped.</li>
    <li>Handle 1–4 weeks long, at most 12% deep, in the upper half of the cup, on below-average volume. Pivot = handle high.</li></ul>
  <h2>High tight flag</h2>
  <ul><li>Price up 90%+ in 8 weeks or less, then a 3–5 week flag no more than 25% deep. Pivot = flag high.</li></ul>
  <h2>Double bottom</h2>
  <ul><li>30%+ prior advance, a W at least 7 weeks long and 12–35% deep. Above the 200-day; RS ≥ 60.</li>
    <li>The second low undercuts the first by 0–8%. The middle peak retraces at least 40% of the first decline. Pivot = middle peak.</li></ul>
  <h2>Flat base</h2>
  <ul><li>Passes the Trend Template. At least 5 weeks moving sideways within 15% of the left-side high, after a 20%+ advance. Pivot = base high.</li></ul>
  <h2>Market condition</h2>
  <ul><li>Each index scores a point for being above its 21-day EMA, above its 50-day, above its 200-day, having a rising 50-day, and having 4 or fewer distribution days in the last 25 sessions. Breadth adjusts the score. ≥ 4 = Uptrend, 2.5–4 = Under pressure, below that = Correction.</li>
    <li>A distribution day is the index falling 0.2% or more on higher volume than the day before. It expires after 25 sessions, or early once the index rises 5% above that day's close.</li></ul>
  <p class="muted small">Prices come from Yahoo Finance and are adjusted for splits and dividends. This is a screen to find ideas, not a trading system. Check every chart, the earnings date and the news before you buy.</p>`;
}

load();
})();
