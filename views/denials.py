import numpy as np
import plotly.graph_objects as go
import streamlit as st

import store
import ui

ctx = store.load_state(store.current_state())
S = ctx.s

SHORT = {"Debt-to-income ratio": "DTI", "Credit history": "Credit", "Credit application incomplete": "Incomplete", "Insufficient cash": "Cash",
         "Unverifiable information": "Unverified", "Employment history": "Employment", "Not reported": "n/r", "Mortgage insurance denied": "MI denied"}
st.title("Denials")
st.write("Denials are the number most teams watch. Why do they happen, and where does the line fall?")

# ---------------------------------------------------------------- reasons
dp = ctx.den_purpose.copy()
dp["purpose"] = dp.purpose_label.map(store.PURPOSE)
dp["share"] = 100 * dp.denials / dp.groupby("purpose_label").denials.transform("sum")
order = dp.groupby("reason").denials.sum().sort_values(ascending=False).index.tolist()
colors = {r: store.DENIAL_REASON_COLORS[i % len(store.DENIAL_REASON_COLORS)] for i, r in enumerate(order)}
st.subheader("Reasons, by loan purpose")
fig = go.Figure()
for reason in order:
    d = dp[dp.reason == reason].set_index("purpose").reindex(list(store.PURPOSE.values()))
    fig.add_bar(y=list(store.PURPOSE.values()), x=d.share.fillna(0), orientation="h", name=reason, marker_color=colors[reason],
                text=[f"{v:.0f}%" if v >= 6 else "" for v in d.share.fillna(0)], textposition="inside", textfont=dict(color="#0B1020", size=12),
                customdata=d.denials.fillna(0), hovertemplate="%{y}<br>" + reason + ": %{x:.1f}% (%{customdata:,.0f} denials)<extra></extra>")
fig.update_layout(barmode="stack", bargap=0.3)
fig.update_xaxes(range=[0, 100], ticksuffix="%", title="Share of the purpose's denials"); fig.update_yaxes(autorange="reversed", title=None)
st.plotly_chart(ui.style(fig, 300), width="stretch", config={"displayModeBar": False}, key="den_reasons", alt="Stacked bars of denial reasons by loan purpose")

top = {p: dp[dp.purpose_label == p].sort_values("denials", ascending=False).iloc[0] for p in store.PURPOSE if (dp.purpose_label == p).any()}
ui.callout("<b>Top reason by purpose:</b> " + "; ".join(f"{store.PURPOSE[p]} → {r.reason.lower()} ({r.share:.0f}%)" for p, r in top.items()) + ". "
           f"<b>'Credit application incomplete' is itself a denial reason:</b> {S.get('den_incomplete_share_cash_out_refi', float('nan')):.0f}% of cash-out and "
           f"{S.get('den_incomplete_share_refinance', float('nan')):.0f}% of refinance denials, against {S.get('den_incomplete_share_purchase', float('nan')):.0f}% of purchase denials. "
           "It is the same document-completion failure that shows up in stalled files, here recorded as a formal denial.", "warn")

# ---------------------------------------------------------------- DTI
c1, c2 = st.columns([1.2, 1])
with c1:
    st.subheader("The debt-to-income cliff")
    dti = ctx.dti.copy()
    dti["label"] = dti.dti_band.str.split(": ").str[1].str.replace("-", "–")
    cliff = dti.dti_band.str.startswith("6")
    fig = go.Figure(go.Bar(x=dti.label, y=dti.denial_rate_pct, marker_color=np.where(dti.denial_rate_pct > 20, store.ROSE, "#6EA8FF"),
                           text=[f"{v:.0f}%" for v in dti.denial_rate_pct], textposition="outside", customdata=dti.decided,
                           hovertemplate="DTI %{x}%<br>Denial rate %{y:.1f}% of %{customdata:,} decided files<extra></extra>"))
    fig.add_vline(x=4.5, line=dict(color=store.AMBER, dash="dash", width=1.5), annotation_text="50% DTI", annotation_font_color=store.AMBER, annotation_position="top left")
    fig.update_xaxes(title="Debt-to-income band (%)"); fig.update_yaxes(title="Denial rate", ticksuffix="%", range=[0, 105])
    st.plotly_chart(ui.style(fig, 360, legend=False), width="stretch", config={"displayModeBar": False}, key="den_dti", alt="Denial rate by debt-to-income band, with a cliff at 50 percent")
    st.caption(f"Among files that were funded or denied with a recorded DTI. Flat near {S.dti_43_49:.0f}% up to 49%, then {S.dti_50_60:.0f}% at 50–60% and {S.dti_60p:.0f}% above 60%. "
               "The jump at 50% looks like a policy line; DTI is blank for withdrawn files, so this describes only files that reached a decision.")
with c2:
    st.subheader("Reasons by loan type")
    dl = ctx.den_loantype.copy()
    dl["loan_type"] = dl.loan_type.map(store.LOAN_TYPE)
    dl["share"] = 100 * dl.denials / dl.groupby("loan_type").denials.transform("sum")
    pv = dl.pivot_table(index="loan_type", columns="reason", values="share", fill_value=0).reindex(columns=order)
    fig = go.Figure(go.Heatmap(z=pv.values, x=[SHORT.get(c, c) for c in pv.columns], y=pv.index, colorscale="Magma", zmin=0, reversescale=False,
                               text=np.round(pv.values, 0).astype(int).astype(str), texttemplate="%{text}%", textfont=dict(size=11), showscale=False,
                               hovertemplate="%{y} · %{x}<br>%{z:.1f}% of its denials<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title=None); fig.update_xaxes(tickangle=-40, tickfont=dict(size=11))
    st.plotly_chart(ui.style(fig, 360, legend=False, margin=dict(l=8, r=8, t=10, b=8)), width="stretch", config={"displayModeBar": False}, key="den_lt", alt="Heat map of denial reasons by loan type")
    st.caption("Reasons are as reported; up to four may be listed per denial and only the first is kept.")
