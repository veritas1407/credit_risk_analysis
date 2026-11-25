import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calc
import store
import ui

ctx = store.load_state(store.current_state())
S = ctx.s
A = dict(zip(ctx.assumptions.key, ctx.assumptions.value))

st.title("Opportunity & test")
st.write("Every assumption is a control. Defaults are deliberately conservative: only part of a gap is closed, and a funded loan is worth a modest share of its amount.")

with st.container(border=True, key="card-sliders"):
    c1, c2, c3 = st.columns([1, 1, 1])
    share = c1.slider("Share of the gap the intervention closes", 0, 100, 25, 5, format="%d%%",
                      help="Brokers' applicants are self-selected, so closing 100% of the direct-vs-broker gap is unrealistic.") / 100
    bps = c2.slider("Revenue per funded loan (basis points of loan amount)", 25, 300, 100, 25, help="Gross lender revenue per funded loan as a share of the loan. 100 bps = 1%.")
    scope = c3.radio("Scope", [f"{ctx.name} only", "All six states"], horizontal=False)

if scope == "All six states":
    parts = []
    for s_ in store.STATES:
        c_ = store.load_state(s_)
        parts.append(calc.opportunity_direct_refi(c_.leak, c_.assumptions, share, bps))
    opp = pd.concat(parts)
    lender_scen = [calc.opportunity_lender_gap(store.load_state(s_).lenders, store.load_state(s_).assumptions, share, bps) for s_ in store.STATES]
    B = {k: sum(d[k] for d in lender_scen) for k in lender_scen[0]}
    where = "six states"
else:
    opp = calc.opportunity_direct_refi(ctx.leak, ctx.assumptions, share, bps)
    B = calc.opportunity_lender_gap(ctx.lenders, ctx.assumptions, share, bps)
    where = ctx.name

st.subheader("Scenario A: fix incomplete files in direct refinances")
ui.kpis([
    dict(label=f"Funded loans recovered ({where}, one year)", value=opp.funded_loans.sum(), decimals=0, color=store.TEAL, sub=f"{opp.recovered_files.sum():,.0f} files recovered × {A['approval_given_stay']:.0%} funded"),
    dict(label="Origination volume", value=opp.volume.sum() / 1e6, decimals=0, prefix="$", unit="M", color="#6EA8FF", sub="at each state's median originated loan"),
    dict(label=f"Revenue at {bps} bps", value=opp.revenue.sum() / 1e6, decimals=1, prefix="$", unit="M", color=store.VIOLET, sub="gross, before the cost of the intervention"),
])
c1, c2 = st.columns([1, 1])
with c1:
    stages = [("Closed incomplete (direct refis)", float(sum((r.direct_incomplete_pct / 100) * r.direct_apps for r in opp.itertuples()))),
              ("Excess over the broker rate (the gap)", float(opp.gap_files.sum())),
              (f"Recovered at {share:.0%}", float(opp.recovered_files.sum())), ("Funded after a decision", float(opp.funded_loans.sum()))]
    fig = go.Figure(go.Funnel(y=[s[0] for s in stages], x=[s[1] for s in stages], textinfo="value+percent initial", texttemplate="%{value:,.0f}",
                              marker=dict(color=[store.ORANGE, store.AMBER, store.VIOLET, store.TEAL]), connector=dict(line=dict(color="#27304A"))))
    st.plotly_chart(ui.style(fig, 330, legend=False), width="stretch", config={"displayModeBar": False}, key="opp_funnel", alt="Funnel from incomplete files to recovered funded loans")
with c2:
    shares = np.arange(5, 55, 5)
    bpss = np.arange(25, 325, 50)
    z = np.array([[sum(calc.opportunity_direct_refi(ctx.leak, ctx.assumptions, sh / 100, b).revenue) / 1e6 for b in bpss] for sh in shares]) if scope != "All six states" else \
        np.array([[sum(calc.opportunity_direct_refi(store.load_state(s_).leak, store.load_state(s_).assumptions, sh / 100, b).revenue.sum() for s_ in store.STATES) / 1e6 for b in bpss] for sh in shares])
    fig = go.Figure(go.Heatmap(z=z, x=[f"{b} bps" for b in bpss], y=[f"{s}%" for s in shares], colorscale="Purples", texttemplate="$%{z:.1f}M", textfont=dict(size=11),
                               colorbar=dict(thickness=10, title=dict(text="$M", side="right")), hovertemplate="Gap closed %{y}, %{x}<br>Revenue $%{z:.2f}M<extra></extra>"))
    fig.update_xaxes(title="Revenue per funded loan"); fig.update_yaxes(title="Share of the gap closed", autorange="reversed")
    st.plotly_chart(ui.style(fig, 330, legend=False), width="stretch", config={"displayModeBar": False}, key="opp_heat", alt="Sensitivity of revenue to gap closed and revenue per loan")
st.dataframe(opp.assign(purpose=opp.purpose.map(store.PURPOSE))[["purpose", "direct_apps", "direct_incomplete_pct", "indirect_incomplete_pct", "gap_files", "funded_loans"]].rename(columns={
    "purpose": "Purpose", "direct_apps": "Direct applications", "direct_incomplete_pct": "Direct incomplete %", "indirect_incomplete_pct": "Broker incomplete %",
    "gap_files": "Gap (files)", "funded_loans": "Funded loans"}).round(1), hide_index=True, width="stretch")

st.subheader("Scenario B: lenders significantly worse than their loan mix")
ui.kpis([
    dict(label=f"Funded loans recovered ({where})", value=B["funded_loans"], decimals=0, color=store.TEAL, sub=f"{B['lenders']:.0f} lenders, {B['excess_walkaways']:,.0f} excess walk-aways"),
    dict(label="Origination volume", value=B["volume"] / 1e6, decimals=0, prefix="$", unit="M", color="#6EA8FF", sub="at the median originated loan"),
    dict(label=f"Revenue at {bps} bps", value=B["revenue"] / 1e6, decimals=1, prefix="$", unit="M", color=store.VIOLET, sub="if each closes the same share of its excess"),
])
ui.callout("<b>Treat these as order-of-magnitude estimates.</b> They assume recovered files behave like average files that stay to a decision, ignore the cost of the intervention, "
           "and use one year of public data. Scenarios A and B overlap and must not be added.", "warn")

# ---------------------------------------------------------------- experiment
st.subheader("Experiment design: file-completion assistant")
e1, e2 = st.columns(2)
with e1.container(key="card-exp1"):
    st.markdown("""
**Hypothesis.** For direct-channel refinance applicants, a live document checklist plus automated nudges and a human call after 48 hours of inactivity
reduces the share of files closed incomplete, *without changing credit decisions*.

**Population and assignment.** New direct refinance and cash-out applications; randomise 50/50 at the application level, stratified by purpose and loan type.
Exclude files already in underwriting.
""")
with e2.container(key="card-exp2"):
    st.markdown("""
**Metrics.** *Primary:* share of files closed incomplete. *Secondary:* withdrawal rate, files reaching a decision, funded rate, time to decision.
*Guardrails:* denial-rate **mix** (denials may rise mechanically as more files reach underwriting), cost per file, complaints, treatment parity.

**Ship if** the incomplete rate falls ≥ 2 points, funded rate does not fall, and guardrails hold. **Stop if** cost per recovered loan exceeds contribution per loan.
""")

st.markdown("**Sample-size calculator**")
m1, m2, m3, m4 = st.columns(4)
metric = m1.selectbox("Primary metric", ["Files closed incomplete", "Funded rate"])
base = ctx.dir_refi_inc_rate if metric == "Files closed incomplete" else ctx.dir_refi_funded_rate
mde = m2.slider("Effect to detect (points)", 0.5, 10.0, 3.0 if metric == "Files closed incomplete" else 2.5, 0.5)
weekly = m3.number_input("Eligible applications / week", 50, 5000, max(100, int(round(ctx.dir_refi_apps / 52 / 50) * 50)), 50)
power = m4.select_slider("Power", [0.7, 0.8, 0.9], value=0.8)
sign = -1 if metric == "Files closed incomplete" else 1
p2 = base + sign * mde / 100
n_arm = calc.sample_size_per_arm(base, p2, power=power)
ui.kpis([
    dict(label=f"Baseline ({ctx.state} direct refis)", value=100 * base, unit="%", color=store.ORANGE, sub="2024 HMDA"),
    dict(label="Target", value=100 * p2, unit="%", color=store.TEAL, sub=f"{'−' if sign < 0 else '+'}{mde:.1f} points"),
    dict(label=f"Files per arm (α = 5%, power {power:.0%})", value=n_arm / 1000, decimals=2, unit="K", color="#6EA8FF", sub=f"{n_arm:,} per arm, {2 * n_arm:,} total"),
    dict(label="Weeks to run", value=2 * n_arm / weekly, decimals=1, color=store.VIOLET, sub=f"at {weekly:,} eligible applications a week"),
])
grid = np.arange(0.5, 10.5, 0.5)
fig = go.Figure(go.Scatter(x=grid, y=[calc.sample_size_per_arm(base, base + sign * g / 100, power=power) for g in grid], mode="lines", line=dict(color=store.AMBER, width=3),
                           hovertemplate="Detect %{x:.1f} pts → %{y:,} per arm<extra></extra>"))
fig.add_trace(go.Scatter(x=[mde], y=[n_arm], mode="markers", marker=dict(size=14, color=store.TEAL, line=dict(width=2, color="#fff")), hoverinfo="skip"))
fig.update_xaxes(title="Smallest effect to detect (points)"); fig.update_yaxes(title="Files per arm", type="log", tickvals=[100, 300, 1000, 3000, 10000, 30000], ticktext=["100", "300", "1K", "3K", "10K", "30K"])
st.plotly_chart(ui.style(fig, 300, legend=False), width="stretch", config={"displayModeBar": False}, key="opp_power", alt="Sample size per arm against the effect to detect")
st.caption("Halving the detectable effect roughly quadruples the sample. Incomplete files are a proximal metric and need far fewer files than the funded rate; "
           "power the test on the proximal metric and pre-register the funded rate as a secondary readout.")
