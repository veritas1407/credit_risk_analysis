import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import store
import ui

ctx = store.load_state(store.current_state())
L, S, ML = ctx.lenders.copy(), ctx.s, ctx.ml

st.title("Lender frontier")
st.write("A lender is **on the frontier** if no other lender has both a lower walk-away rate *and* a lower denial rate. "
         "Low walk-aways can be bought by denying more, so both are read together. Rates are compared with what each lender's own mix of "
         "applications would predict (**O/E = observed ÷ expected**, 1.0 = as expected).")

VIEWS = {
    "Mix-adjusted": ("den_oe", "wa_oe", "on_adj_frontier", True, "Purpose × loan type"),
    "ML-adjusted": ("den_oe_ml", "wa_oe_ml", "on_ml_frontier", True, "13-feature gradient-boosted model, scored out-of-lender"),
    "Mix + income": ("den_oe_inc", "wa_oe_inc", "on_inc_frontier", True, "Purpose × loan type × income fifth"),
    "Raw rates": ("denial_pct", "walkaway_pct", "on_raw_frontier", False, "No adjustment"),
}
view = st.segmented_control("Compare lenders on", list(VIEWS), default="Mix-adjusted", required=True, key="len_view")
xcol, ycol, fcol, adjusted, how = VIEWS[view]
L["tier"] = np.where(L[fcol], "On the frontier", np.where(L.wa_z > 1.96, "Significantly more walk-aways than mix predicts", "Other lenders"))
L["short"] = L.name.str.replace(r",? (L\.?L\.?C\.?|LLC|INC\.?|Inc\.?|CORP\.?|N\.A\.|NA|LP|L\.P\.)$", "", regex=True).str.slice(0, 26)

c_left, c_right = st.columns([1.7, 1])
with c_left:
    fig = go.Figure()
    for tier, color, opacity in [("Other lenders", "#5A6B94", 0.55), ("Significantly more walk-aways than mix predicts", store.ORANGE, 0.8), ("On the frontier", store.TEAL, 0.95)]:
        d = L[L.tier == tier]
        fig.add_trace(go.Scatter(
            x=d[xcol], y=d[ycol], mode="markers", name=tier, customdata=np.c_[d.lei, d.name, d.apps, d.walkaway_pct, d.denial_pct, d.wa_oe, d.den_oe],
            marker=dict(size=np.sqrt(d.apps) / 3.2 + 6, color=color, opacity=opacity, line=dict(width=1.5 if tier == "On the frontier" else 0.5, color="#E8ECF5" if tier == "On the frontier" else "#0B1020")),
            hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[2]:,} applications<br>Walk-away %{customdata[3]:.1f}% (O/E %{customdata[5]:.2f})"
                          "<br>Denial %{customdata[4]:.1f}% (O/E %{customdata[6]:.2f})<extra></extra>"))
    fr = L[L[fcol]].sort_values(xcol)
    fig.add_trace(go.Scatter(x=fr[xcol], y=fr[ycol], mode="lines+text", line=dict(color=store.TEAL, dash="dot", width=1.5, shape="hv"), text=fr.short,
                             textposition="top right", textfont=dict(size=10.5, color="#BFEFE6"), hoverinfo="skip", showlegend=False))
    if adjusted:
        fig.add_hline(y=1, line=dict(color="rgba(255,255,255,.25)", width=1)); fig.add_vline(x=1, line=dict(color="rgba(255,255,255,.25)", width=1))
    fig.update_xaxes(title=("Denial O/E (1.0 = as expected for its mix)" if adjusted else "Denial rate (%)"), rangemode="tozero")
    fig.update_yaxes(title=("Walk-away O/E (1.0 = as expected)" if adjusted else "Walk-away rate (%)"), rangemode="tozero")
    ev = st.plotly_chart(ui.style(fig, 560), width="stretch", on_select="rerun", selection_mode="points", key=f"len_scatter_{view}",
                         config={"displayModeBar": False}, alt="Scatter of lenders by denial and walk-away measure with the frontier highlighted")
    st.caption(f"Adjustment: **{how}**. Bottom-left is best. Bubble size = applications. Click a bubble to inspect that lender.")
with c_right:
    ui.kpis([
        dict(label="Lenders on this frontier", value=int(L[fcol].sum()), decimals=0, color=store.TEAL, sub=f"of {len(L)} with 200+ applications"),
        dict(label="Significantly worse than mix", value=int(S.sig_worse), decimals=0, color=store.ORANGE, sub=f"{int(S.sig_better)} significantly better"),
    ])
    st.markdown("**How robust is the frontier?**")
    yr = store._csv("data/temporal_summary.csv").set_index("state").loc[ctx.state]
    rob = pd.DataFrame({
        "Check": ["On raw and mix-adjusted", "Survive adding income", "Survive requiring 500+ applications", "Survive the ML adjustment", "On the 2023 frontier too"],
        "Kept": [f"{int(S.f_adj_and_raw)} of {int(S.f_adj)}", f"{int(S.f_adj_and_inc)} of {int(S.f_adj)}",
                 f"{int(S.f_adj_and_500)} of {int(S.f_adj)}", f"{int(ML.f_ml_and_adj)} of {int(ML.f_adj)}",
                 f"{int(yr.frontier_both)} of {int(yr.frontier_2024)}"]})
    st.dataframe(rob, hide_index=True, width="stretch")
    st.caption("Lenders that stay on the frontier under every view are the most credible. Raw rates mislead because refinance-heavy lenders naturally lose more applicants. "
               "Membership changes a lot between years (see <i>Six-state check</i>), so treat the frontier as a shortlist.", unsafe_allow_html=True)

# ---------------------------------------------------------------- lender card
st.subheader("Inspect a lender")
names = L.sort_values("apps", ascending=False).name.tolist()
clicked = None
pts = (ev.selection.points if ev and getattr(ev, "selection", None) else [])
if pts:
    clicked = pts[0].get("customdata", [None, None])[1]
idx = names.index(clicked) if clicked in names else 0
pick = st.selectbox("Lender", names, index=idx, help="Click a bubble above, or pick from the list (largest first).")
r = L[L.name == pick].iloc[0]
flags = [ui.tag("ok", "Mix-adjusted frontier") if r.on_adj_frontier else "", ui.tag("ok", "Robust frontier") if r.robust_frontier else "",
         ui.tag("part", "ML frontier") if r.on_ml_frontier else "",
         ui.tag("no", "Significantly worse than mix") if r.wa_z > 1.96 else (ui.tag("ok", "Significantly better than mix") if r.wa_z < -1.96 else "")]
ui.callout(f"<b>{r['name']}</b> &nbsp;·&nbsp; {int(r.apps):,} applications in {ctx.name} &nbsp;·&nbsp; {r.purchase_share:.0f}% purchase &nbsp;·&nbsp; "
           f"{r.direct_share:.0f}% direct channel &nbsp;·&nbsp; walk-away O/E {r.wa_oe:.2f}, z = {r.wa_z:.1f}<br>{''.join(f for f in flags if f)}", "info")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Walk-away rate", f"{r.walkaway_pct:.1f}%", f"{r.walkaway_pct - 100 * ctx.walked / ctx.total:+.1f} pts vs state", delta_color="inverse")
k2.metric("Expected for its mix", f"{r.wa_expected:.1f}%", help=f"Walk-away O/E = {r.wa_oe:.2f} (observed ÷ expected)")
k3.metric("Denial rate", f"{r.denial_pct:.1f}%", f"{r.denial_pct - 100 * ctx.denied / ctx.total:+.1f} pts vs state", delta_color="inverse")
k4.metric("Walk-away O/E (shrunk)", f"{r.wa_oe_eb:.2f}",
          help=f"Raw O/E {r.wa_oe:.2f}. Empirical-Bayes estimate: pulls a noisy lender toward the average in proportion to how little data it has ({r.shrink_weight:.0%} weight on its own data).")

lo = ctx.lender_outcomes[ctx.lender_outcomes.lei == r.lei]
rows_y, groups = [], []
for p in store.PURPOSE:
    rows_y += [f"{store.PURPOSE[p]} · this lender", f"{store.PURPOSE[p]} · {ctx.state} average"]
    groups += [(lo, p), (ctx.by_purpose, p)]
fig = go.Figure()
for o in store.OUTCOMES:
    xs_ = []
    for data, p in groups:
        d = data[data.purpose_label == p]
        tot_p = d.apps.sum()
        xs_.append(100 * d[d.outcome == o].apps.sum() / tot_p if tot_p else 0)
    fig.add_bar(y=rows_y, x=xs_, orientation="h", name=store.OUTCOME_LABEL[o], marker_color=store.COLOR[o],
                text=[f"{v:.0f}%" if v >= 5 else "" for v in xs_], textposition="inside", textfont=dict(color="#0B1020", size=11),
                hovertemplate="%{y}<br>" + store.OUTCOME_LABEL[o] + ": %{x:.1f}%<extra></extra>")
fig.update_layout(barmode="stack", bargap=0.22)
fig.update_xaxes(range=[0, 100], ticksuffix="%", title=None)
fig.update_yaxes(autorange="reversed", title=None)
st.plotly_chart(ui.style(fig, 360), width="stretch", config={"displayModeBar": False}, key="len_card", alt="Outcome mix of the selected lender versus the state by loan purpose")
if pd.notna(r.med_spread):
    st.caption(f"Pricing on {int(r.price_loans)} originated conventional purchase loans: median rate spread {r.med_spread:.2f} pts, "
               f"median loan costs ${r.med_costs:,.0f}, median interest rate {r.med_rate:.2f}%.")

# ---------------------------------------------------------------- funnel plot
st.subheader("How much of the spread is more than chance?")
rr = float((L.wa_var / L.wa_exp).median())
xs = np.geomspace(max(L.wa_exp.min() * 0.8, 5), L.wa_exp.max() * 1.1, 120)
fig = go.Figure()
for z, name, dash in [(3.09, "99.8% limits", "dot"), (1.96, "95% limits", "dash")]:
    for sign in (1, -1):
        fig.add_trace(go.Scatter(x=xs, y=1 + sign * z * np.sqrt(rr / xs), mode="lines", line=dict(color="rgba(143,160,194,.6)", dash=dash, width=1.2),
                                 name=name, showlegend=(sign == 1), hoverinfo="skip"))
inside = L[(L.wa_oe >= L.wa_lo) & (L.wa_oe <= L.wa_hi)]
above, below = L[L.wa_oe > L.wa_hi], L[L.wa_oe < L.wa_lo]
for d, nm, col in [(inside, "Within chance of expected", "#5A6B94"), (above, "More walk-aways than expected", store.ORANGE), (below, "Fewer walk-aways than expected", store.TEAL)]:
    fig.add_trace(go.Scatter(x=d.wa_exp, y=d.wa_oe, mode="markers", name=nm, marker=dict(size=9, color=col, line=dict(width=0.5, color="#0B1020")),
                             customdata=np.c_[d.name, d.apps, d.wa_z], hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:,} applications<br>O/E %{y:.2f}, z %{customdata[2]:.1f}<extra></extra>"))
fig.add_hline(y=1, line=dict(color="rgba(255,255,255,.3)", width=1))
fig.update_xaxes(type="log", title="Expected walk-aways (lender size, log scale)")
fig.update_yaxes(title="Walk-away O/E")
st.plotly_chart(ui.style(fig, 420), width="stretch", config={"displayModeBar": False}, key="len_funnel",
                alt="Funnel plot of walk-away observed over expected against lender size with control limits")
ui.callout(f"A funnel plot shows what chance alone would produce: small lenders scatter widely, large ones sit near 1.0. In {ctx.name}, "
           f"<b>{len(above)} lenders sit above and {len(below)} below the 95% funnel</b>, far more than the ~{0.025 * len(L):.0f} expected on each side by luck. "
           f"After removing chance, the true lender-to-lender spread in walk-away O/E is <b>τ = {S.tau:.2f}</b> (about ±{100 * S.tau:.0f}% of expected). "
           "That is large: walk-away differs between lenders far more than chance would produce. The data does not show why.", "good")

# ---------------------------------------------------------------- tables
st.subheader("Where the lost applicants are")
ex = L.sort_values("excess_walkaways", ascending=False).head(10)
cfg = {"name": "Lender", "apps": st.column_config.NumberColumn("Applications", format="%d"),
       "wa_actual": st.column_config.NumberColumn("Walk-away %", format="%.1f"), "wa_expected": st.column_config.NumberColumn("Expected %", format="%.1f"),
       "wa_oe": st.column_config.NumberColumn("O/E", format="%.2f"), "wa_z": st.column_config.NumberColumn("z", format="%.1f"),
       "excess_walkaways": st.column_config.ProgressColumn("Excess walk-aways", format="%d", min_value=0, max_value=float(max(ex.excess_walkaways.max(), 1)))}
st.dataframe(ex[list(cfg)], hide_index=True, width="stretch", column_config=cfg)
st.caption(f"Excess = observed − expected walk-aways. {int(S.sig_worse)} lenders are significantly above expectation, together about {S.excess_walkaways_sig_worse:,.0f} excess walk-aways.")
with st.expander(f"All {len(L)} lenders"):
    cols = ["name", "apps", "walkaway_pct", "denial_pct", "purchase_share", "direct_share", "wa_oe", "den_oe", "wa_oe_ml", "wa_z", "den_z", "on_raw_frontier", "on_adj_frontier", "on_ml_frontier", "robust_frontier"]
    st.dataframe(L[cols], hide_index=True, width="stretch")
    st.download_button("Download this table (CSV)", L[cols].to_csv(index=False), file_name=f"lenders_{ctx.state}.csv", mime="text/csv")
