import streamlit as st

import calc
import charts
import store
import ui

ctx = store.load_state(store.current_state())
S, ML = ctx.s, ctx.ml
states = store.states_table()
all_apps = int(states.apps.sum())
ratio = S.walk_pct / S.den_pct

ui.hero(
    f"HMDA 2024 · {ctx.name}",
    f'Applicants walk away <span class="grad">{ratio:.1f}×</span> as often as lenders say no',
    f"{ctx.total:,} first-lien, owner-occupied home loan applications in {ctx.name}. Where do applicants leave, which lenders keep them, "
    "and what should a product team build? Switch state in the sidebar: every number re-computes.",
    ["HMDA 2024", f"6 states · {all_apps:,} applications", "SQL · DuckDB", "gradient-boosted case-mix model", "A/B test design"],
)

ui.kpis([
    dict(label="Applications", value=ctx.total / 1000, decimals=1, unit="K", color="#6EA8FF", sub=f"{S.lenders:.0f} lenders with 200+ files"),
    dict(label="Funded", value=S.orig_pct, unit="%", color=store.TEAL, sub="loan originated"),
    dict(label="Applicant walked away", value=S.walk_pct, unit="%", color=store.ORANGE, sub="withdrew, never finished, or declined the offer"),
    dict(label="Denied by lender", value=S.den_pct, unit="%", color=store.ROSE, sub="the number most teams watch"),
    dict(label="Direct refinances closed incomplete", value=S.dir_refi_inc_pct, unit="%", color=store.AMBER,
         sub=f"vs {S.ind_refi_inc_pct:.1f}% through brokers"),
])

st.subheader("Where 100 applications go")
ws = ctx.by_outcome
rows = [dict(label=store.OUTCOME_LABEL[o], share=float(ws[o] / ctx.total), n=int(ws[o]), color=store.COLOR[o]) for o in store.OUTCOMES]
ui.funnel_canvas(f"{ctx.total:,} applications", ctx.name, rows, height=360)
st.caption("Each dot is an application, flowing to its real outcome in proportion to the real data. Hover an outcome to isolate it.")

c1, c2, c3 = st.columns(3)
with c1.container(key="card-f1"):
    ui.finding(1, f"<b>The loss is on the applicant side.</b> {S.walk_pct:.1f}% of applications end because the applicant leaves; "
                  f"{S.den_pct:.1f}% are denied. Income lowers denials ({S.den_q1:.1f}% → {S.den_q5:.1f}% from the lowest to the highest "
                  f"income fifth) but walk-aways barely move ({S.wa_q1:.0f}% → {S.wa_q5:.0f}%).")
with c2.container(key="card-f2"):
    ui.finding(2, f"<b>It concentrates in direct refinances.</b> {S.dir_refi_inc_pct:.1f}% of direct refinance applications end closed incomplete, "
                  f"against {S.ind_refi_inc_pct:.1f}% via brokers and {S.dir_purch_inc_pct:.1f}% for direct purchases. "
                  f"They are <b>{S.share_of_stalled_dir_refi:.0f}%</b> of every stalled file in {ctx.name}.")
with c3.container(key="card-f3"):
    ui.finding(3, f"<b>Lenders differ, and loan mix doesn't explain it.</b> {S.sig_worse:.0f} of {S.lenders:.0f} lenders lose significantly more "
                  f"applicants than their mix predicts. A 13-feature ML model leaves the lender spread at τ = {ML.tau_ml:.2f} "
                  f"(from {ML.tau_segment:.2f}): the gap is process, not who applies.")

left, right = st.columns([1.15, 1])
with left:
    st.subheader("How each segment ends")
    st.plotly_chart(charts.segment_bars(ctx), width="stretch", key="ov_seg", config={"displayModeBar": False},
                    alt="Stacked bars: share of applications by outcome for each loan purpose and channel")
with right:
    st.subheader("It replicates across states")
    st.plotly_chart(charts.dumbbell(states, ctx.state), width="stretch", key="ov_dumb", config={"displayModeBar": False},
                    alt="Dumbbell chart: direct versus broker refinance files closed incomplete in six states")
st.caption("Files closed incomplete: the lender could not get what it needed to decide. Direct refinances sit far above brokered ones and direct purchases in all six states.")

opp = calc.opportunity_direct_refi(ctx.leak, ctx.assumptions, 0.25, 100)
st.subheader("What to do")
ui.callout("<b>Recommendation:</b> test a <b>file-completion assistant</b> on direct-channel refinance applications: a live document checklist, "
           "automated nudges, and a human call when a file stalls for 48 hours. It targets the largest identifiable leak and does not touch the credit "
           "decision. Because walk-away is barely predictable from application data (see <i>Case-mix model</i>), offer it to every eligible applicant "
           "rather than scoring who gets it.", "good")
ui.kpis([
    dict(label=f"Funded loans recovered ({ctx.state}, one year)", value=opp.funded_loans.sum(), decimals=0, color=store.TEAL,
         sub="if the assistant closes 25% of the direct-vs-broker gap"),
    dict(label="Origination volume", value=opp.volume.sum() / 1e6, decimals=0, prefix="$", unit="M", color="#6EA8FF",
         sub=f"at the median originated loan (${S.med_loan_all / 1000:,.0f}K)"),
    dict(label="Revenue at 100 bps", value=opp.revenue.sum() / 1e6, decimals=1, prefix="$", unit="M", color=store.VIOLET,
         sub="order of magnitude; change the assumptions on the Opportunity page"),
])
ui.callout("Descriptive analysis of public HMDA data. It makes no claim about any lender's practices; no demographic (fair-lending) analysis is attempted, "
           "and any intervention must be offered identically to all applicants and must never change credit decisions.", "info")
