import numpy as np
import plotly.graph_objects as go
import streamlit as st

import store
import ui

ctx = store.load_state(store.current_state())
L, S = ctx.lenders, ctx.s

st.title("Pricing")
st.write("Do the best-performing lenders keep applicants by charging more? Pricing fields exist only for *originated* loans, so comparing lenders on all loans "
         "would be biased. This page holds one segment fixed: **originated conventional purchase loans**, lenders with 100+ such loans.")

pg = ctx.price_groups
PRICE = {"med_spread": "Median rate spread (pts)", "med_costs": "Median loan costs ($)", "med_points": "Median discount points ($)", "med_rate": "Median interest rate (%)"}
if pg.empty or int(S.price_lenders) < 5:
    st.warning(f"Only {int(S.price_lenders)} lenders in {ctx.name} have 100+ originated conventional purchase loans, too few for a pricing comparison. Pick a larger state.")
    st.stop()

rb = pg[pg.grp.str.startswith("Robust")]
ot = pg[pg.grp.str.startswith("All other")]
if not rb.empty and not ot.empty:
    rb, ot = rb.iloc[0], ot.iloc[0]
    ui.kpis([
        dict(label="Rate spread, robust-frontier lenders", value=rb.med_spread, decimals=2, color=store.TEAL, sub=f"{int(rb.lenders)} lenders, {int(rb.loans):,} loans"),
        dict(label="Rate spread, all other lenders", value=ot.med_spread, decimals=2, color="#6EA8FF", sub=f"{int(ot.lenders)} lenders, {int(ot.loans):,} loans"),
        dict(label="Loan costs, robust frontier", value=rb.med_costs / 1000, decimals=2, prefix="$", unit="K", color=store.TEAL, sub="median, borrower-paid"),
        dict(label="Loan costs, all others", value=ot.med_costs / 1000, decimals=2, prefix="$", unit="K", color="#6EA8FF", sub="median, borrower-paid"),
    ])
    gap = rb.med_costs - ot.med_costs
    ui.callout(f"<b>Finding.</b> Robust-frontier lenders price {'in line with' if abs(gap) < 0.06 * ot.med_costs else ('above' if gap > 0 else 'below')} everyone else: median rate spread "
               f"{rb.med_spread:.2f} vs {ot.med_spread:.2f} points, median loan costs ${rb.med_costs:,.0f} vs ${ot.med_costs:,.0f}. "
               "Keeping applicants does not appear to be bought with higher prices.", "good")
else:
    ui.callout(f"No {ctx.name} lender is on both the mix-adjusted and income-adjusted frontier with enough conventional purchase loans, so there is no robust-frontier group to compare. "
               "The across-lender view below still applies.", "info")
st.dataframe(pg.rename(columns={"grp": "Lender group", "lenders": "Lenders", "loans": "Loans", **{k: v for k, v in PRICE.items()}}), hide_index=True, width="stretch")

st.subheader("Across lenders: does walk-away move with price?")
c1, c2 = st.columns([1.5, 1])
with c1:
    ycol = st.segmented_control("Price measure", list(PRICE), default="med_spread", format_func=PRICE.get, required=True, key="price_measure")
    xcol = st.segmented_control("Compare with", ["wa_oe", "den_oe"], default="wa_oe", required=True, key="price_x",
                                format_func=lambda v: {"wa_oe": "Walk-away O/E", "den_oe": "Denial O/E"}[v])
    d = L.dropna(subset=["med_spread"]).copy()
    d["tier"] = np.where(d.robust_frontier, "Robust frontier", "Other lenders")
    fig = go.Figure()
    for tier, color in [("Other lenders", "#5A6B94"), ("Robust frontier", store.TEAL)]:
        t = d[d.tier == tier]
        fig.add_trace(go.Scatter(x=t[xcol], y=t[ycol], mode="markers", name=tier, marker=dict(size=np.sqrt(t.price_loans) / 1.6 + 5, color=color, opacity=0.8, line=dict(width=0.5, color="#0B1020")),
                                 customdata=np.c_[t.name, t.price_loans], hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:,} loans<br>O/E %{x:.2f}, price %{y:,.2f}<extra></extra>"))
    if len(d) > 3:
        m, b = np.polyfit(d[xcol], d[ycol], 1)
        xs = np.linspace(d[xcol].min(), d[xcol].max(), 20)
        fig.add_trace(go.Scatter(x=xs, y=m * xs + b, mode="lines", line=dict(color="rgba(255,255,255,.4)", dash="dot"), name="Linear fit", hoverinfo="skip"))
    fig.update_xaxes(title={"wa_oe": "Walk-away O/E (mix-adjusted)", "den_oe": "Denial O/E (mix-adjusted)"}[xcol]); fig.update_yaxes(title=PRICE[ycol])
    st.plotly_chart(ui.style(fig, 400), width="stretch", config={"displayModeBar": False}, key="price_scatter", alt="Scatter of lender price measures against walk-away or denial O/E")
with c2:
    pc = ctx.price_corr.pivot(index="price", columns="measure", values="spearman")
    st.markdown("**Spearman rank correlation**")
    st.dataframe(pc.reset_index().rename(columns={"price": "Price measure"}), hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(c, format="%.2f") for c in pc.columns})
    st.caption(f"{int(S.price_lenders)} lenders. Walk-away O/E is essentially unrelated to price (largest |ρ| = {S.price_rho_wa_max_abs:.2f}). "
               "Lenders that deny more tend to charge slightly less, consistent with strict lenders taking safer borrowers, not with them charging for retention."
               + (" Small state: correlations from under 25 lenders are noisy." if S.price_lenders < 25 else ""))

st.subheader("For context: pricing by loan type")
lt = ctx.price_loantype.copy()
lt["loan_type"] = lt.loan_type.map(store.LOAN_TYPE)
st.dataframe(lt.rename(columns={"loan_type": "Loan type", "loans": "Originated purchase loans", "med_spread": "Median rate spread (pts)", "med_costs": "Median loan costs ($)", "med_rate": "Median rate (%)"}),
             hide_index=True, width="stretch")
st.caption("Limitations: survivorship (only funded loans are priced), no credit score, and few frontier lenders with enough conventional purchase volume.")
