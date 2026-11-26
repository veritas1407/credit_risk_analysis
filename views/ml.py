import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import store
import ui

ctx = store.load_state(store.current_state())
ML, S = ctx.ml, ctx.s
mm = ctx.ml_metrics.set_index("model")
FEATURE = {"purpose": "Loan purpose", "loan_type": "Loan type", "log_income": "Income", "log_loan_amount": "Loan amount",
           "loan_to_income": "Loan-to-income", "loan_term": "Loan term", "total_units": "Units", "conforming": "Conforming-limit status",
           "open_end": "Open-end line", "reverse_mortgage": "Reverse mortgage", "tract_income_pct": "Tract income level",
           "county": "County", "preapproval": "Pre-approval requested", "channel": "Channel (direct / broker)"}

st.title("Case-mix model")
st.write("The lender comparison adjusts only for loan purpose × loan type. Is that too crude? Here a gradient-boosted model of *who walks away* "
         "and *who is denied* replaces that adjustment, using 13 facts known when the application arrives. Every application is scored by a model that "
         "**never saw that lender** (5-fold cross-validation grouped by lender), so a lender cannot be flattered by its own data.")
ui.callout("<b>This is not a credit model or a risk score.</b> It is a measurement tool: it answers whether richer case-mix changes the lender story. "
           "It uses no DTI, CLTV, AUS or pricing fields (blank by rule for withdrawn files, so they would leak the answer), no lender identity, and no "
           "protected characteristics.", "info")

ui.kpis([
    dict(label="Walk-away: AUC of the model", value=ML.auc_ml_wa, decimals=2, color=store.ORANGE, sub=f"simple segment baseline {ML.auc_segment_wa:.2f}; 0.50 = coin flip"),
    dict(label="Denial: AUC of the model", value=ML.auc_ml_den, decimals=2, color=store.ROSE, sub=f"segment baseline {ML.auc_segment_den:.2f}"),
    dict(label="True lender spread (τ), segment → ML", value=ML.tau_ml, decimals=2, color=store.VIOLET, sub=f"was {ML.tau_segment:.2f} with the simple adjustment"),
    dict(label="Frontier lenders that survive", value=int(ML.f_ml_and_adj), decimals=0, color=store.TEAL, sub=f"of {int(ML.f_adj)} on the mix-adjusted frontier"),
])

# ---------------------------------------------------------------- AUC + importance
c1, c2 = st.columns([1, 1.25])
with c1:
    st.subheader("How predictable is it?")
    fig = go.Figure()
    groups = [("Walk-away", "Walk-away"), ("Denial", "Denial")]
    fig.add_bar(x=["Walk-away", "Denial"], y=[mm.loc["Walk-away", "auc_segment"], mm.loc["Denial", "auc_segment"]], name="Segment baseline",
                marker_color="#5A6B94", text=[f"{mm.loc[k, 'auc_segment']:.3f}" for k, _ in groups], textposition="outside")
    fig.add_bar(x=["Walk-away", "Denial"], y=[mm.loc["Walk-away", "auc_model"], mm.loc["Denial", "auc_model"]], name="13-feature model",
                marker_color=[store.ORANGE, store.ROSE], text=[f"{mm.loc[k, 'auc_model']:.3f}" for k, _ in groups], textposition="outside")
    fig.add_bar(x=["Walk-away"], y=[mm.loc["Walk-away + channel", "auc_model"]], name="+ channel", marker_color=store.AMBER,
                text=[f"{mm.loc['Walk-away + channel', 'auc_model']:.3f}"], textposition="outside")
    fig.add_hline(y=0.5, line=dict(color="rgba(255,255,255,.3)", dash="dot"), annotation_text="coin flip", annotation_font_color="#8FA0C2")
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_yaxes(range=[0.45, 0.85], title="AUC (out-of-lender)")
    st.plotly_chart(ui.style(fig, 360), width="stretch", config={"displayModeBar": False}, key="ml_auc", alt="AUC of walk-away and denial models against the segment baseline")
with c2:
    st.subheader("What drives each prediction?")
    imp = ctx.ml_importance
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Walk-away", "Denial"), horizontal_spacing=0.28)
    for i, (m, color) in enumerate([("Walk-away + channel", store.ORANGE), ("Denial", store.ROSE)], start=1):
        d = imp[imp.model == m].sort_values("importance").tail(8)
        fig.add_bar(y=[FEATURE[f] for f in d.feature], x=d.importance, orientation="h", marker_color=color, row=1, col=i,
                    error_x=dict(type="data", array=d.importance_sd, color="rgba(255,255,255,.35)"),
                    hovertemplate="%{y}<br>AUC drop when shuffled: %{x:.4f}<extra></extra>", showlegend=False)
    fig.update_xaxes(title="AUC lost if shuffled")
    fig.update_annotations(font=dict(color="#C9D3EA", size=13))
    st.plotly_chart(ui.style(fig, 360, legend=False), width="stretch", config={"displayModeBar": False}, key="ml_imp", alt="Permutation importance of model features")

d_auc = ML.auc_ml_wa - ML.auc_segment_wa
ui.callout(f"<b>Walk-away in general is hard to predict.</b> From everything HMDA records at application time, the model reaches AUC {ML.auc_ml_wa:.2f} "
           f"(+{d_auc:.2f} over just knowing loan purpose and type; adding the channel gives {ML.auc_ml_wa_channel:.2f}). Denial is far more predictable "
           f"(AUC {ML.auc_ml_den:.2f}), with loan purpose and loan-to-income the main inputs. <b>What this means:</b> these fields say little about who will leave, and nothing about why. "
           "Unfinished files, which the proposed assistant targets, are a separate and more predictable outcome (see <i>Six-state check</i>).", "warn")

# ---------------------------------------------------------------- calibration + O/E agreement
c3, c4 = st.columns(2)
with c3:
    st.subheader("Is it calibrated?")
    cal = ctx.ml_calibration
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="rgba(255,255,255,.3)", dash="dot"), name="Perfect", hoverinfo="skip"))
    for m, color in [("Walk-away", store.ORANGE), ("Denial", store.ROSE)]:
        d = cal[cal.model == m]
        fig.add_trace(go.Scatter(x=d.pred * 100, y=d.obs * 100, mode="lines+markers", name=m, line=dict(color=color, width=2.5), marker=dict(size=8),
                                 hovertemplate="Predicted %{x:.1f}%<br>Observed %{y:.1f}%<extra>" + m + "</extra>"))
    fig.data[0].x, fig.data[0].y = [0, max(cal.obs.max(), cal.pred.max()) * 100], [0, max(cal.obs.max(), cal.pred.max()) * 100]
    fig.update_xaxes(title="Predicted probability (decile average)", ticksuffix="%"); fig.update_yaxes(title="Observed rate", ticksuffix="%")
    st.plotly_chart(ui.style(fig, 340), width="stretch", config={"displayModeBar": False}, key="ml_cal", alt="Calibration of predicted versus observed rates by decile")
    st.caption(f"Total predicted ÷ observed: walk-away {ML.calib_wa:.3f}, denial {ML.calib_den:.3f} (1.000 = perfect). Points on the dotted line are well calibrated.")
with c4:
    st.subheader("Does the lender ranking change?")
    L = ctx.lenders
    fig = go.Figure()
    top = max(L.wa_oe.max(), L.wa_oe_ml.max()) * 1.05
    fig.add_trace(go.Scatter(x=[0, top], y=[0, top], mode="lines", line=dict(color="rgba(255,255,255,.3)", dash="dot"), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=L.wa_oe, y=L.wa_oe_ml, mode="markers", marker=dict(size=np.sqrt(L.apps) / 5 + 5, color=np.where(L.on_ml_frontier, store.TEAL, "#6EA8FF"),
                  opacity=0.8, line=dict(width=0.5, color="#0B1020")), customdata=np.c_[L.name, L.apps],
                  hovertemplate="<b>%{customdata[0]}</b><br>segment O/E %{x:.2f}<br>ML O/E %{y:.2f}<extra></extra>", showlegend=False))
    fig.update_xaxes(title="Walk-away O/E, purpose × loan type"); fig.update_yaxes(title="Walk-away O/E, ML model")
    st.plotly_chart(ui.style(fig, 340, legend=False), width="stretch", config={"displayModeBar": False}, key="ml_oe", alt="Scatter of lender O/E under the segment adjustment versus the ML adjustment")
    st.caption(f"Rank correlation {ML.rho_seg_vs_ml:.2f}. Teal = on the ML frontier. Lenders sit on the diagonal: the richer model leaves the ranking almost unchanged.")

# ---------------------------------------------------------------- tau across states
st.subheader("Does a richer adjustment shrink the real lender-to-lender spread?")
ms = store.ml_summary().copy()
fig = go.Figure()
for col, name, color in [("tau_segment", "Purpose × loan type", "#5A6B94"), ("tau_ml", "13-feature ML model", store.ORANGE), ("tau_channel", "ML + channel", store.AMBER)]:
    fig.add_bar(x=ms.state, y=ms[col], name=name, marker_color=color, text=[f"{v:.2f}" for v in ms[col]], textposition="outside")
fig.update_layout(barmode="group", bargap=0.3)
fig.update_yaxes(title="τ: true spread of lender walk-away O/E", range=[0, 0.6])
st.plotly_chart(ui.style(fig, 340), width="stretch", config={"displayModeBar": False}, key="ml_tau", alt="True between-lender spread under three adjustments in each state")
ui.callout(f"<b>It does not.</b> τ stays around 0.4 in every state however much case-mix is controlled. Lenders still differ by roughly ±40% in how many applicants they lose, "
           f"and the frontier mostly survives ({int(ML.f_ml_and_adj)} of {int(ML.f_adj)} here). The 13 fields used here do not explain the lender gap. "
           "<b>Caveat:</b> HMDA cannot see credit score, rate shopping or why a file stalled, so these are flags to investigate, not verdicts.", "good")

with st.expander("Model card"):
    st.markdown(f"""
**Targets.** Walked away (withdrew, closed incomplete, declined an approved offer) and denied by the lender.

**Algorithm.** `HistGradientBoostingClassifier` (200 iterations, learning rate 0.08, 24 leaves, L2 = 1), scikit-learn.

**Features (13).** {", ".join(FEATURE[f] for f in list(FEATURE)[:13])}. A second walk-away variant adds the application channel.

**Deliberately excluded.** DTI, CLTV, property value, AUS result, interest rate, costs (blank by rule for withdrawn files: leakage); lender identity;
race, ethnicity, sex, age and tract minority share (fair-lending).

**Validation.** 5-fold `GroupKFold` by lender: predictions for a lender come from models trained without that lender. Metrics: AUC, calibration by decile,
total predicted ÷ observed (asserted within 3% for states with 50,000+ applications). Importance is permutation importance on a held-out fold.

**How O/E is built.** Expected walk-aways for a lender = Σ predicted probabilities over its applications; O/E = observed ÷ expected; z = (obs − exp) ÷ √Σp(1−p).
τ is the DerSimonian–Laird estimate of the between-lender standard deviation of true O/E.

**Missing income.** Income is blank more often on incomplete and declined-offer files, so a blank carries information about the outcome. In the
Maryland-trained transfer test, removing both income fields changes walk-away AUC by less than 0.005. That test leaves them out.

**Limits.** Out-of-lender scoring is harsh in small states (a single large lender can move the totals); {ctx.name} has {int(ML.lenders)} lenders in the comparison.
""")
