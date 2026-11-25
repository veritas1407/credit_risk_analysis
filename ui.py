"""
ui.py: the design system. Global CSS, hero / KPI / callout components, the animated funnel, and the Plotly house style.

Custom CSS is used on purpose (the project asked for a distinctive front end); colours and fonts still come from
.streamlit/config.toml, and CSS only targets stable `data-testid` hooks and `st-key-*` container keys.
"""

import json

import streamlit as st

CSS = r"""
<style>
:root{--bg:#0B1020;--card:#131A2E;--card2:#172039;--line:#27304A;--muted:#8FA0C2;--text:#E8ECF5;
--teal:#2EE6C5;--rose:#FF5C7A;--amber:#FFC857;--orange:#FF7F32;--violet:#B79CFF;--brand:#6D4DFF;}
/* the syntax string is written with CSS escapes (\00003C = "<"): the HTML sanitizer drops any style block containing a literal "<" */
@property --w{syntax:'\00003Cinteger\00003E';initial-value:0;inherits:true}
@property --f{syntax:'\00003Cinteger\00003E';initial-value:0;inherits:true}

[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1100px 560px at 8% -8%, rgba(109,77,255,.20), transparent 60%),
    radial-gradient(900px 520px at 100% 2%, rgba(46,230,197,.10), transparent 55%),
    radial-gradient(800px 600px at 50% 120%, rgba(255,92,122,.07), transparent 60%),
    #0B1020;
}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{border-right:1px solid var(--line)}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a{border-radius:10px}
h1,h2,h3{letter-spacing:-.02em}
h2{margin-top:.4rem}
.stPlotlyChart, [data-testid="stPlotlyChart"]{border-radius:14px}
[data-testid="stMetric"]{background:linear-gradient(180deg,var(--card),#10172A);border:1px solid var(--line);
  border-radius:14px;padding:14px 16px}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:12px;overflow:hidden}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:12px;background:rgba(19,26,46,.6)}
div[class*="st-key-card"]{background:linear-gradient(180deg,rgba(23,32,57,.85),rgba(16,23,42,.85));
  border:1px solid var(--line);border-radius:16px;padding:18px 20px;
  transition:border-color .25s, transform .25s, box-shadow .25s}
div[class*="st-key-card"]:hover{border-color:#3C4A74;box-shadow:0 10px 40px -18px rgba(109,77,255,.55)}

/* ------------------------------------------------------------------ hero */
.hero{padding:6px 0 4px}
.hero .kicker{font-size:.78rem;letter-spacing:.16em;text-transform:uppercase;color:var(--teal);font-weight:600}
.hero h1{font-size:clamp(2.2rem,5.2vw,3.7rem);line-height:1.04;margin:.25rem 0 .6rem;font-weight:700;padding:0}
.hero h1 .grad{background:linear-gradient(92deg,#2EE6C5 0%,#6EA8FF 42%,#B79CFF 72%,#FF7F32 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{max-width:60rem;color:#B6C1DA;font-size:1.06rem;line-height:1.55;margin:0}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.chip{border:1px solid var(--line);background:rgba(19,26,46,.7);color:#C9D3EA;border-radius:999px;
  padding:4px 12px;font-size:.78rem;font-weight:500}
.chip b{color:var(--text)}

/* ------------------------------------------------------------------ KPI cards */
.kgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:14px;margin:6px 0 4px}
.kcard{position:relative;overflow:hidden;background:linear-gradient(160deg,#172039 0%,#10172A 100%);
  border:1px solid var(--line);border-radius:16px;padding:16px 18px 14px;animation:rise .7s both}
.kcard::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--accent,#6D4DFF)}
.kcard::after{content:"";position:absolute;right:-30px;top:-30px;width:110px;height:110px;border-radius:50%;
  background:var(--accent,#6D4DFF);opacity:.12;filter:blur(22px)}
.kcard .lab{font-size:.74rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:600}
.kcard .val{font-family:'Space Grotesk',Inter,sans-serif;font-size:2.35rem;font-weight:700;line-height:1.15;margin-top:4px;
  color:var(--text);font-variant-numeric:tabular-nums}
.kcard .val .u{font-size:1.3rem;color:var(--accent,#C9D3EA);margin-left:2px;font-weight:600}
.kcard .sub{font-size:.8rem;color:#9AA8C6;margin-top:2px;line-height:1.35}
.kcard .num::after{counter-reset:w var(--w) f var(--f)}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

/* ------------------------------------------------------------------ callouts, steps, stat rows */
.callout{border-left:3px solid var(--accent,#6D4DFF);background:rgba(19,26,46,.75);border-radius:0 12px 12px 0;
  padding:12px 16px;margin:8px 0;color:#CBD5EC;font-size:.96rem;line-height:1.55}
.callout b{color:#fff}
.callout.good{--accent:#2EE6C5}.callout.warn{--accent:#FFC857}.callout.bad{--accent:#FF5C7A}.callout.info{--accent:#6EA8FF}
.eyebrow{font-size:.74rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600;margin:.2rem 0 -.2rem}
.big{font-family:'Space Grotesk',Inter,sans-serif;font-weight:700;font-size:2.8rem;line-height:1.05;letter-spacing:-.03em}
.dim{color:var(--muted)}
.finding{display:flex;gap:14px;align-items:flex-start}
.finding .n{flex:none;width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-weight:700;
  background:rgba(109,77,255,.2);color:#C9BDFF;font-family:'Space Grotesk',sans-serif}
.finding p{margin:0;color:#CBD5EC;line-height:1.55}
.finding p b{color:#fff}
.tag{display:inline-block;border-radius:6px;padding:1px 8px;font-size:.74rem;font-weight:600;margin-right:6px}
.tag.ok{background:rgba(46,230,197,.14);color:#2EE6C5}.tag.part{background:rgba(255,200,87,.14);color:#FFC857}
.tag.no{background:rgba(255,92,122,.14);color:#FF5C7A}
.brand{display:flex;gap:10px;align-items:center;margin:2px 0 6px}
.brand .logo{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#6D4DFF,#2EE6C5);
  display:grid;place-items:center;font-weight:800;color:#0B1020;font-family:'Space Grotesk',sans-serif}
.brand .t{font-family:'Space Grotesk',sans-serif;font-weight:700;line-height:1.1;font-size:1.02rem}
.brand .s{font-size:.72rem;color:var(--muted);letter-spacing:.04em}
@media (prefers-reduced-motion:reduce){.kcard{animation:none}}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def hero(kicker: str, title: str, subtitle: str, chips: list[str] | None = None) -> None:
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in (chips or []))
    st.html(f'<div class="hero"><div class="kicker">{kicker}</div><h1>{title}</h1><p>{subtitle}</p>'
            f'<div class="chips">{chip_html}</div></div>')


_KPI_CALLS = 0


def kpis(items: list[dict]) -> None:
    """Animated KPI cards. item = {label, value, decimals, prefix, suffix, unit, color, sub}. The number counts up (CSS only)."""
    global _KPI_CALLS
    _KPI_CALLS += 1
    uid = f"{_KPI_CALLS}"
    css, cards = [], []
    for i, it in enumerate(items):
        i = f"{uid}_{i}"
        v, d = float(it["value"]), int(it.get("decimals", 1))
        whole, frac = divmod(int(round(v * 10**d)), 10**d)
        css.append(f"@keyframes k{i}{{from{{--w:0;--f:0}}to{{--w:{whole};--f:{frac}}}}}"
                   f".kc{i} .num{{animation:k{i} 1.5s cubic-bezier(.16,.8,.24,1) both .1s}}")
        counter = "counter(w) '.' counter(f)" if d == 1 else ("counter(w) '.' counter(f, decimal-leading-zero)" if d == 2 else "counter(w)")
        css.append(f".kc{i} .num::after{{content:{counter}}}")
        label = f'{it.get("prefix", "")}{v:.{d}f}{it.get("unit", "")}'
        cards.append(
            f'<div class="kcard kc{i}" style="--accent:{it.get("color", "#6D4DFF")};animation-delay:{int(i.split("_")[1]) * 0.08:.2f}s" aria-label="{it["label"]}: {label}">'
            f'<div class="lab">{it["label"]}</div>'
            f'<div class="val">{it.get("prefix", "")}<span class="num"></span><span class="u">{it.get("unit", "")}</span></div>'
            f'<div class="sub">{it.get("sub", "")}</div></div>')
    st.html(f"<style>{''.join(css)}</style><div class='kgrid'>{''.join(cards)}</div>")


def callout(text: str, tone: str = "info") -> None:
    st.html(f'<div class="callout {tone}">{text}</div>')


def finding(n: int, text: str) -> None:
    st.html(f'<div class="finding"><div class="n">{n}</div><p>{text}</p></div>')


def tag(kind: str, text: str) -> str:
    return f'<span class="tag {kind}">{text}</span>'


def eyebrow(text: str) -> None:
    st.html(f'<div class="eyebrow">{text}</div>')


# ---------------------------------------------------------------------------------------------- Plotly house style
def style(fig, height: int = 380, legend: bool = True, margin: dict | None = None):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#C9D3EA", size=13),
        margin=margin or dict(l=8, r=8, t=28, b=8),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        hoverlabel=dict(bgcolor="#1A2340", bordercolor="#3A4668", font=dict(family="Inter, sans-serif", size=13, color="#E8ECF5")),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#5F6E94", activecolor="#9DB4FF"),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.06)", zerolinecolor="rgba(255,255,255,.14)", linecolor="rgba(255,255,255,.14)",
                     tickfont=dict(size=12), title_font=dict(size=12, color="#8FA0C2"))
    fig.update_yaxes(gridcolor="rgba(255,255,255,.06)", zerolinecolor="rgba(255,255,255,.14)", linecolor="rgba(255,255,255,.14)",
                     tickfont=dict(size=12), title_font=dict(size=12, color="#8FA0C2"))
    return fig


# ---------------------------------------------------------------------------------------------- animated funnel
FUNNEL_HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>html,body{margin:0;height:100%;background:transparent;overflow:hidden;font-family:Inter,system-ui,sans-serif}
canvas{width:100%;height:100%;display:block}</style></head><body><canvas id="c"></canvas>
<script>
(function(){
const D = __DATA__;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
let W, H, DPR, slices = [], parts = [], hover = -1, xs, xd, bw = 12;
const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n>>16},${(n>>8)&255},${n&255},${a})`; };
const smooth = t => t*t*(3-2*t);

function layout(){
  DPR = window.devicePixelRatio || 1; W = cv.clientWidth; H = cv.clientHeight;
  cv.width = W*DPR; cv.height = H*DPR; ctx.setTransform(DPR,0,0,DPR,0,0);
  const padT = 34, padB = 18, gap = 9, innerH = H - padT - padB;
  const labelW = Math.min(250, W*0.36);
  xs = 26; xd = W - labelW - 16;
  const dh = innerH - gap*(D.rows.length-1);
  let sy = padT, dy = padT; slices = [];
  D.rows.forEach((r, i) => {
    const sh = innerH * r.share, h = Math.max(5, dh * r.share);
    slices.push(Object.assign({}, r, {sy0: sy, sy1: sy + sh, dy0: dy, dy1: dy + h, i}));
    sy += sh; dy += h + gap;
  });
  // label positions: centre of each destination slice, pushed apart so text never overlaps
  let last = -1e9;
  slices.forEach(s => { s.ly = Math.max((s.dy0 + s.dy1)/2, last + 24); last = s.ly; });
  const over = last - (H - 14); if (over > 0) slices.forEach(s => s.ly -= over);
}

function band(s, alpha){
  const x0 = xs + bw, x1 = xd, mx = (x0 + x1)/2;
  ctx.beginPath();
  ctx.moveTo(x0, s.sy0);
  ctx.bezierCurveTo(mx, s.sy0, mx, s.dy0, x1, s.dy0);
  ctx.lineTo(x1, s.dy1);
  ctx.bezierCurveTo(mx, s.dy1, mx, s.sy1, x0, s.sy1);
  ctx.closePath();
  const g = ctx.createLinearGradient(x0, 0, x1, 0);
  g.addColorStop(0, rgba(s.color, alpha*0.45)); g.addColorStop(1, rgba(s.color, alpha));
  ctx.fillStyle = g; ctx.fill();
}

function spawn(){
  let r = Math.random(), acc = 0, s = slices[slices.length-1];
  for (const c of slices){ acc += c.share; if (r <= acc){ s = c; break; } }
  parts.push({s, t: 0, sp: 0.0035 + Math.random()*0.004,
              ys: s.sy0 + Math.random()*(s.sy1 - s.sy0), ye: s.dy0 + Math.random()*(s.dy1 - s.dy0), r: 1.3 + Math.random()*1.6});
}

function draw(){
  ctx.clearRect(0, 0, W, H);
  slices.forEach(s => band(s, hover === s.i ? 0.34 : (hover >= 0 ? 0.07 : 0.16)));
  // source bar
  const g = ctx.createLinearGradient(0, 34, 0, H-18);
  g.addColorStop(0, '#6EA8FF'); g.addColorStop(1, '#B79CFF');
  ctx.fillStyle = g; ctx.beginPath(); ctx.roundRect(xs, 34, bw, H - 52, 6); ctx.fill();
  ctx.fillStyle = '#E8ECF5'; ctx.font = '600 13px Inter, sans-serif'; ctx.textBaseline = 'alphabetic';
  ctx.fillText(D.title, xs, 20);
  ctx.fillStyle = '#8FA0C2'; ctx.font = '500 12px Inter, sans-serif';
  ctx.fillText(D.subtitle, xs + ctx.measureText(D.title).width + 12 + 0, 20);
  // particles
  ctx.globalCompositeOperation = 'lighter';
  for (const p of parts){
    const e = smooth(p.t), x = xs + bw + (xd - xs - bw)*p.t, y = p.ys + (p.ye - p.ys)*e;
    const a = Math.min(1, p.t*10) * Math.min(1, (1 - p.t)*8) * (hover >= 0 && hover !== p.s.i ? 0.25 : 0.95);
    ctx.fillStyle = rgba(p.s.color, a); ctx.beginPath(); ctx.arc(x, y, p.r, 0, 6.2832); ctx.fill();
    ctx.fillStyle = rgba(p.s.color, a*0.18); ctx.beginPath(); ctx.arc(x, y, p.r*3, 0, 6.2832); ctx.fill();
  }
  ctx.globalCompositeOperation = 'source-over';
  // destination bars + labels
  slices.forEach(s => {
    ctx.fillStyle = s.color; ctx.beginPath(); ctx.roundRect(xd, s.dy0, bw, s.dy1 - s.dy0, 4); ctx.fill();
    const lx = xd + bw + 12, dim = hover >= 0 && hover !== s.i;
    ctx.globalAlpha = dim ? 0.35 : 1;
    ctx.fillStyle = s.color; ctx.font = '700 22px "Space Grotesk", Inter, sans-serif'; ctx.textBaseline = 'middle';
    const pct = (s.share*100).toFixed(1) + '%';
    ctx.fillText(pct, lx, s.ly);
    const pw = ctx.measureText(pct).width;
    ctx.fillStyle = '#B6C1DA'; ctx.font = '500 12.5px Inter, sans-serif';
    ctx.fillText(hover === s.i ? s.n.toLocaleString() + ' applications' : s.label, lx + pw + 8, s.ly + 1);
    ctx.globalAlpha = 1;
    if (Math.abs(s.ly - (s.dy0 + s.dy1)/2) > 4){
      ctx.strokeStyle = rgba(s.color, 0.5); ctx.lineWidth = 1; ctx.beginPath();
      ctx.moveTo(xd + bw, (s.dy0 + s.dy1)/2); ctx.lineTo(lx - 4, s.ly); ctx.stroke();
    }
  });
}

function tick(){
  if (parts.length < 230) { spawn(); spawn(); }
  for (const p of parts) p.t += p.sp;
  parts = parts.filter(p => p.t < 1);
  draw(); requestAnimationFrame(tick);
}

cv.addEventListener('mousemove', ev => {
  const r = cv.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
  let h = -1;
  slices.forEach(s => { if (x > xd - 6 && Math.abs(y - s.ly) < 13) h = s.i; });
  if (h < 0 && x > xs && x < xd) slices.forEach(s => { const t = (x - xs)/(xd - xs), yy = s.sy0 + (s.dy0 - s.sy0)*smooth(t), y2 = s.sy1 + (s.dy1 - s.sy1)*smooth(t); if (y >= yy && y <= y2) h = s.i; });
  hover = h; if (reduce) draw();
});
cv.addEventListener('mouseleave', () => { hover = -1; if (reduce) draw(); });
window.addEventListener('resize', () => { layout(); if (reduce) draw(); });
layout();
if (reduce){ draw(); } else { for (let i = 0; i < 160; i++){ spawn(); parts[i].t = Math.random(); } requestAnimationFrame(tick); }
})();
</script></body></html>"""


def funnel_canvas(title: str, subtitle: str, rows: list[dict], height: int = 360) -> None:
    """Animated flow of applications into their outcomes. rows = [{label, share, n, color}] with shares summing to 1."""
    html = FUNNEL_HTML.replace("__DATA__", json.dumps({"title": title, "subtitle": subtitle, "rows": rows}))
    st.iframe(html, height=height)
