import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import charts
import store
import ui

ctx = store.load_state(store.current_state())
S = store.states_table().set_index("state")
M = store.ml_summary().set_index("state")
order = list(store.STATES)

st.title("Six-state check")
st.write("One state can be a coincidence. The same analysis was re-run, unchanged, on Maryland and all five neighbours "
         f"(Virginia, Pennsylvania, Delaware, D.C., West Virginia): {int(S.apps.sum()):,} applications in total. Which findings replicate?")

st.subheader("The direct-refinance leak")
st.plotly_chart(charts.dumbbell(S.reset_index(), ctx.state, height=360), width="stretch", config={"displayModeBar": False}, key="st_dumb",
                alt="Dumbbell chart of direct versus broker refinance incomplete rates in six states")
ui.callout(f"In every state, direct refinances close incomplete at <b>{S.dir_refi_inc_pct.min():.1f}–{S.dir_refi_inc_pct.max():.1f}%</b>, against {S.dir_purch_inc_pct.min():.1f}–{S.dir_purch_inc_pct.max():.1f}% "
           f"for direct purchases and {S.ind_refi_inc_pct.min():.1f}–{S.ind_refi_inc_pct.max():.1f}% for brokered refinances. They make up "
           f"{S.share_of_stalled_dir_refi.min():.0f}–{S.share_of_stalled_dir_refi.max():.0f}% of all stalled files. "
           f"(West Virginia has only {int(S.loc['WV', 'ind_refi_apps'])} brokered refinances, so its broker rate is thin.)", "good")

# ---------------------------------------------------------------- scoreboard
st.subheader("Replication scoreboard")


def grade(ok, part=None):
    if ok is None or (isinstance(ok, float) and np.isnan(ok)):
        return "na"
    return "ok" if ok else ("part" if part else "no")


claims = []
ratio = S.dir_refi_inc_pct / S.ind_refi_inc_pct
claims.append(("Applicants walk away more often than lenders deny", "walk-away % > denial %", {s: grade(S.loc[s, "walk_pct"] > S.loc[s, "den_pct"]) for s in order}))
claims.append(("Direct refinances close incomplete ≥ 2× the broker rate", "ratio ≥ 2 (✓), ≥ 1.5 (partial)", {s: grade(ratio[s] >= 2, ratio[s] >= 1.5) for s in order}))
claims.append(("Direct refinances are ≥ 60% of stalled files", "share ≥ 60%", {s: grade(S.loc[s, "share_of_stalled_dir_refi"] >= 60) for s in order}))
claims.append(("Income lowers denials but not walk-aways", "top-fifth denial ≤ ½ of bottom; walk-away range ≤ 5 pts",
               {s: grade(S.loc[s, "den_q5"] <= S.loc[s, "den_q1"] / 2 and S.loc[s, "wa_band_range"] <= 5) for s in order}))
claims.append(("Denial rate jumps at 50% DTI", "50–60% rate ≥ 2× the 43–49% rate", {s: grade(S.loc[s, "dti_50_60"] >= 2 * S.loc[s, "dti_43_49"]) for s in order}))
claims.append(("Lenders differ by more than chance", "true spread τ ≥ 0.25", {s: grade(S.loc[s, "tau"] >= 0.25) for s in order}))
claims.append(("An ML case-mix model does not shrink that spread", "τ changes by ≤ 0.10", {s: grade(abs(M.loc[s, "tau_ml"] - M.loc[s, "tau_segment"]) <= 0.10) for s in order}))
claims.append(("The frontier survives the ML adjustment", "≥ 80% of members kept", {s: grade(M.loc[s, "f_ml_and_adj"] >= 0.8 * M.loc[s, "f_adj"], M.loc[s, "f_ml_and_adj"] >= 0.6 * M.loc[s, "f_adj"]) for s in order}))
claims.append(("Raw rankings mislead (frontier changes once mix is removed)", "< 75% of adjusted frontier also on raw frontier",
               {s: grade(S.loc[s, "f_adj_and_raw"] < 0.75 * S.loc[s, "f_adj"], S.loc[s, "f_adj_and_raw"] < S.loc[s, "f_adj"]) for s in order}))
claims.append(("Price does not buy retention", "|ρ| ≤ 0.2 (✓), ≤ 0.35 (partial); n/a under 10 lenders",
               {s: ("na" if S.loc[s, "price_lenders"] < 10 else grade(S.loc[s, "price_rho_wa_max_abs"] <= 0.2, S.loc[s, "price_rho_wa_max_abs"] <= 0.35)) for s in order}))
sym = {"ok": ui.tag("ok", "✓"), "part": ui.tag("part", "~"), "no": ui.tag("no", "✗"), "na": '<span class="dim">n/a</span>'}
head = "".join(f"<th style='padding:8px 10px;text-align:center;{'color:#fff;border-bottom:2px solid #6D4DFF' if s == ctx.state else 'color:#8FA0C2'}'>{s}</th>" for s in order)
rows = ""
for name, rule, res in claims:
    k = sum(v == "ok" for v in res.values())
    cells = "".join(f"<td style='text-align:center;padding:8px 6px'>{sym[res[s]]}</td>" for s in order)
    rows += (f"<tr style='border-top:1px solid #27304A'><td style='padding:9px 10px'><b style='color:#E8ECF5'>{name}</b><br><span class='dim' style='font-size:.78rem'>{rule}</span></td>"
             f"{cells}<td style='text-align:center;font-weight:700;color:#E8ECF5'>{k}/6</td></tr>")
st.html(f"<table style='width:100%;border-collapse:collapse;font-size:.92rem;background:rgba(19,26,46,.6);border:1px solid #27304A;border-radius:12px'>"
        f"<tr><th style='text-align:left;padding:8px 10px;color:#8FA0C2'>Finding</th>{head}<th style='color:#8FA0C2'>Holds</th></tr>{rows}</table>")
st.caption("✓ holds, ~ partly holds, ✗ does not hold. Thresholds are stated under each finding and are rules of thumb, not formal tests. "
           "The weakest findings: the raw-vs-adjusted frontier (in West Virginia and D.C. nearly every adjusted-frontier lender is also on the raw one), "
           "and price (West Virginia has only 19 lenders with enough pricing data, and D.C. has too few).")

# ---------------------------------------------------------------- income small multiples
st.subheader("Income lowers denials, not walk-aways, in every state")
fig = make_subplots(rows=1, cols=6, shared_yaxes=True, subplot_titles=[s for s in order], horizontal_spacing=0.015)
for i, s in enumerate(order, start=1):
    inc = store._csv(f"data/{s}/income_bands.csv")
    fig.add_trace(go.Scatter(x=inc.band, y=inc.walkaway_pct, mode="lines+markers", name="Walk-away", line=dict(color=store.ORANGE, width=3), marker=dict(size=7), showlegend=(i == 1),
                             hovertemplate=f"{s} income fifth %{{x}}<br>Walk-away %{{y:.1f}}%<extra></extra>"), row=1, col=i)
    fig.add_trace(go.Scatter(x=inc.band, y=inc.denial_pct, mode="lines+markers", name="Denial", line=dict(color=store.ROSE, width=3), marker=dict(size=7), showlegend=(i == 1),
                             hovertemplate=f"{s} income fifth %{{x}}<br>Denial %{{y:.1f}}%<extra></extra>"), row=1, col=i)
fig.update_yaxes(range=[0, 32], ticksuffix="%", row=1, col=1)
fig.update_xaxes(dtick=1, title=None)
fig.update_annotations(font=dict(color="#C9D3EA", size=13))
fig.update_layout(legend=dict(y=1.22))
st.plotly_chart(ui.style(fig, 300), width="stretch", config={"displayModeBar": False}, key="st_inc", alt="Walk-away and denial rate by income fifth in six states")
st.caption("Income fifth 1 = lowest. Five equal-sized groups per state.")

# ---------------------------------------------------------------- frontier stability
st.subheader("How stable is the lender frontier?")
fig = go.Figure()
for col, name, color in [("f_adj_and_raw", "Also on raw frontier", "#5A6B94"), ("f_adj_and_inc", "Survives adding income", store.AMBER),
                         ("f_adj_and_500", "Survives 500+ application cut", store.VIOLET)]:
    fig.add_bar(x=order, y=[100 * S.loc[s, col] / S.loc[s, "f_adj"] for s in order], name=name, marker_color=color,
                customdata=[[S.loc[s, col], S.loc[s, "f_adj"]] for s in order], hovertemplate="%{x}: %{customdata[0]:.0f} of %{customdata[1]:.0f}<extra>" + name + "</extra>")
fig.add_bar(x=order, y=[100 * M.loc[s, "f_ml_and_adj"] / M.loc[s, "f_adj"] for s in order], name="Survives ML adjustment", marker_color=store.TEAL,
            customdata=[[M.loc[s, "f_ml_and_adj"], M.loc[s, "f_adj"]] for s in order], hovertemplate="%{x}: %{customdata[0]:.0f} of %{customdata[1]:.0f}<extra>ML</extra>")
fig.update_layout(barmode="group", bargap=0.25)
fig.update_yaxes(title="% of the mix-adjusted frontier kept", ticksuffix="%", range=[0, 112])
st.plotly_chart(ui.style(fig, 340), width="stretch", config={"displayModeBar": False}, key="st_front", alt="Share of adjusted frontier lenders kept under four robustness checks")
st.caption("Frontiers are small (2–7 lenders in most states) so one lender moving changes the percentage a lot; read the hover counts. "
           "The frontier is robust to adding income and to the ML adjustment, much less to the raw-rate view.")

# ---------------------------------------------------------------- transfer to unseen states
st.subheader("Does a model carry over to states it has never seen?")
st.write("A model trained on **Maryland only** scores the other five states. The baseline is a lookup table of Maryland's rate for each purpose × channel. "
         "County is left out (it cannot carry over), and so are the income fields: income is blank far more often on unfinished files, so the blank itself can give the answer away.")
TR = store._csv("data/transfer_metrics.csv")
PER = store._csv("data/lender_persistence.csv")
target = st.segmented_control("Predicting", ["Closed incomplete", "Any walk-away", "Denial"], default="Closed incomplete", required=True, key="st_target")
t = TR[TR.target == target]
t1, t2 = st.columns([1.35, 1])
with t1:
    fig = go.Figure()
    fig.add_bar(x=t.test_state, y=t.auc_table, name="Lookup table", marker_color="#5A6B94", text=[f"{v:.2f}" for v in t.auc_table], textposition="outside")
    fig.add_bar(x=t.test_state, y=t.auc_model, name="Model", marker_color=store.TEAL, text=[f"{v:.2f}" for v in t.auc_model], textposition="outside")
    fig.add_hline(y=0.5, line=dict(color="rgba(255,255,255,.3)", dash="dot"), annotation_text="coin flip", annotation_position="bottom left", annotation_font_color="#8FA0C2")
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_yaxes(range=[0.45, 0.86], title="AUC on the unseen state")
    fig.update_xaxes(title="Test state (never used in training)")
    st.plotly_chart(ui.style(fig, 340), width="stretch", config={"displayModeBar": False}, key="st_transfer",
                    alt="AUC of the Maryland-trained model and lookup table in five unseen states")
with t2:
    st.markdown("**If you could act on only 20% of files, what share of the cases would you reach?**")
    st.dataframe(pd.DataFrame({"State": t.test_state, "Lookup table %": 100 * t.top20_table, "Model %": 100 * t.top20_model,
                               "Predicted ÷ observed": t.pred_over_obs}), hide_index=True, width="stretch",
                 column_config={"Lookup table %": st.column_config.NumberColumn(format="%.0f"), "Model %": st.column_config.NumberColumn(format="%.0f"),
                                "Predicted ÷ observed": st.column_config.NumberColumn(format="%.2f")})
    st.caption("Picking at random would reach about 20%. Predicted ÷ observed far from 1.00 means totals need recalibrating on the new data.")

wins = int((t.top20_model > t.top20_table).sum())
meaning = {"Closed incomplete": "Unfinished files are <b>moderately predictable</b> on unseen states, with much of that coming from purpose and channel alone.",
           "Any walk-away": "Walk-away in general is <b>weakly predictable</b>: these fields say little about who will leave, and nothing about why.",
           "Denial": f"Denial ranking carries over. Adding the income fields raises AUC to {t.auc_all_inputs.min():.2f}–{t.auc_all_inputs.max():.2f}, and it stays that high when only files reporting income are used."}[target]
ui.callout(f"{meaning} Model AUC {t.auc_model.min():.2f}–{t.auc_model.max():.2f} against {t.auc_table.min():.2f}–{t.auc_table.max():.2f} for the table; "
           f"on the top-20% test the model reaches more cases than the table in {wins} of {len(t)} states. "
           f"Predicted totals run from {t.pred_over_obs.min():.2f}× to {t.pred_over_obs.max():.2f}× the real count, so <b>recalibrate before using the numbers</b>.", "info")
if target == "Closed incomplete":
    ui.callout("<b>What this allows, and what it does not.</b> A score like this could later decide who gets the costly human call first. Before that it needs a fair-lending review "
               "and a test showing that high-risk applicants actually benefit: high risk does not mean a call will help. The first A/B test should still include every eligible applicant. "
               "All data is 2024 from neighbouring states that share many lenders, so other years are untested.", "warn")

st.markdown("**Do lenders behave the same way in different states?**")
p1, p2 = st.columns([1.35, 1])
with p2:
    other = st.selectbox("Compare Maryland with", list(PER[PER.state_a == "MD"].state_b), format_func=store.STATES.get, key="st_persist")
    row = PER[(PER.state_a == "MD") & (PER.state_b == other)].iloc[0]
    st.metric("Walk-away O/E rank correlation", f"{row.rho_walkaway:.2f}", help="1.00 = identical ranking of lenders in both states")
    st.caption(f"{int(row.shared_lenders)} lenders have 200+ applications in both. Across all {len(PER)} state pairs with 15+ shared lenders the correlation is "
               f"{PER.rho_walkaway.min():.2f}–{PER.rho_walkaway.max():.2f} for walk-away and {PER.rho_denial.min():.2f}–{PER.rho_denial.max():.2f} for denial "
               "(D.C. has too few shared lenders). This suggests something company-wide. It could be how a lender runs applications or the kind of customer it attracts.")
with p1:
    both = store.load_state("MD").lenders[["lei", "name", "wa_oe"]].merge(store.load_state(other).lenders[["lei", "wa_oe"]], on="lei", suffixes=("_md", "_other"))
    top = float(max(both.wa_oe_md.max(), both.wa_oe_other.max()) * 1.05)
    fig = go.Figure(go.Scatter(x=[0, top], y=[0, top], mode="lines", line=dict(color="rgba(255,255,255,.3)", dash="dot"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=both.wa_oe_md, y=both.wa_oe_other, mode="markers", marker=dict(size=9, color=store.ORANGE, opacity=0.85, line=dict(width=0.5, color="#0B1020")),
                             customdata=both.name, hovertemplate="<b>%{customdata}</b><br>Maryland O/E %{x:.2f}<br>" + other + " O/E %{y:.2f}<extra></extra>"))
    fig.update_xaxes(title="Walk-away O/E in Maryland")
    fig.update_yaxes(title=f"Walk-away O/E in {store.STATES[other]}")
    st.plotly_chart(ui.style(fig, 340, legend=False), width="stretch", config={"displayModeBar": False}, key="st_persist_chart",
                    alt="Each shared lender's walk-away O/E in Maryland against another state")

st.subheader("All numbers")
T = S.join(M[["auc_ml_wa", "auc_ml_den", "tau_ml"]]).reset_index()
cols = {"state": "State", "apps": "Applications", "walk_pct": "Walk-away %", "den_pct": "Denial %", "dir_refi_inc_pct": "Direct refi incomplete %", "ind_refi_inc_pct": "Broker refi incomplete %",
        "dir_purch_inc_pct": "Direct purchase incomplete %", "share_of_stalled_dir_refi": "Direct refi share of stalled %", "lenders": "Lenders", "sig_worse": "Sig. worse", "sig_better": "Sig. better",
        "tau": "τ", "dti_50_60": "Denial at DTI 50–60%", "auc_ml_wa": "ML AUC walk-away", "auc_ml_den": "ML AUC denial"}
st.dataframe(T[list(cols)].rename(columns=cols), hide_index=True, width="stretch",
             column_config={"Applications": st.column_config.NumberColumn(format="%d"), **{c: st.column_config.NumberColumn(format="%.1f") for c in list(cols.values())[2:8] + ["Denial at DTI 50–60%"]},
                            "τ": st.column_config.NumberColumn(format="%.2f"), "ML AUC walk-away": st.column_config.NumberColumn(format="%.3f"), "ML AUC denial": st.column_config.NumberColumn(format="%.3f")})
st.download_button("Download (CSV)", T.to_csv(index=False), file_name="six_state_summary.csv", mime="text/csv")
