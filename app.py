"""
Approval-Abandonment Frontier: Maryland mortgage applications, HMDA 2024.

Reads the small CSV tables in data/ (built by build_data.py from the cleaned HMDA parquet).
Run locally:  streamlit run app.py
"""

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Approval-Abandonment Frontier", page_icon="🏠", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(f"data/{name}.csv")


lenders = load("lenders")
by_purpose = load("outcomes_by_purpose")
segments = load("segments")
availability = load("info_availability")
income = load("income_bands")

PURPOSE_LABELS = {"purchase": "Purchase", "refinance": "Refinance", "cash_out_refi": "Cash-out refi"}
OUTCOME_ORDER = ["originated", "lender_denied", "customer_withdrew", "stalled_incomplete", "customer_declined"]
OUTCOME_LABELS = {
    "originated": "Originated",
    "lender_denied": "Lender denied",
    "customer_withdrew": "Customer withdrew",
    "stalled_incomplete": "Incomplete / stalled",
    "customer_declined": "Customer declined offer",
}
BLUE, ORANGE, GREY = "#2f6fb0", "#d9731a", "#9aa5b1"

total = int(by_purpose["apps"].sum())
by_outcome = by_purpose.groupby("outcome")["apps"].sum()
walked = by_outcome[["customer_withdrew", "stalled_incomplete", "customer_declined"]].sum()

st.title("The Approval–Abandonment Frontier")
st.caption(
    "Maryland first-lien, owner-occupied home loan applications, HMDA 2024 · "
    "which lenders lose the fewest applicants **and** deny the fewest, after adjusting for the loans they handle."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Applications", f"{total:,}")
c2.metric("Originated", f"{by_outcome['originated'] / total:.1%}")
c3.metric("Applicant walked away", f"{walked / total:.1%}", help="Withdrew + incomplete + declined the offer")
c4.metric("Lender denied", f"{by_outcome['lender_denied'] / total:.1%}")

tab_funnel, tab_frontier, tab_method = st.tabs(["1 · The funnel", "2 · Lender frontier", "3 · Method & caveats"])

# ------------------------------------------------------------------ funnel
with tab_funnel:
    st.subheader("More applicants walk away than lenders turn down")
    st.write(
        f"**{walked / total:.1%}** of applications end because the *applicant* leaves, against "
        f"**{by_outcome['lender_denied'] / total:.1%}** denied by the lender. Refinances leak the most."
    )

    p = by_purpose.copy()
    p["purpose"] = p["purpose_label"].map(PURPOSE_LABELS)
    p["share"] = p["apps"] / p.groupby("purpose_label")["apps"].transform("sum")
    p["outcome_label"] = p["outcome"].map(OUTCOME_LABELS)
    chart = (
        alt.Chart(p)
        .mark_bar()
        .encode(
            y=alt.Y("purpose:N", title=None, sort=["Purchase", "Refinance", "Cash-out refi"]),
            x=alt.X("share:Q", title="Share of applications", axis=alt.Axis(format="%")),
            color=alt.Color(
                "outcome_label:N",
                title="Outcome",
                sort=[OUTCOME_LABELS[o] for o in OUTCOME_ORDER],
                scale=alt.Scale(
                    domain=[OUTCOME_LABELS[o] for o in OUTCOME_ORDER],
                    range=[BLUE, "#c0392b", ORANGE, "#e8b04b", GREY],
                ),
            ),
            order=alt.Order("outcome_order:Q"),
            tooltip=["purpose", "outcome_label", alt.Tooltip("apps:Q", format=","), alt.Tooltip("share:Q", format=".1%")],
        )
        .transform_calculate(
            outcome_order="indexof(['originated','lender_denied','customer_withdrew','stalled_incomplete','customer_declined'], datum.outcome)"
        )
        .properties(height=190)
    )
    st.altair_chart(chart, width="stretch")

    left, right = st.columns(2)
    with left:
        st.markdown("**Walk-away rate by loan type × channel** (segments with ≥ 500 applications)")
        seg = segments.copy()
        seg["loan_type_label"] = seg["loan_type"].map({1: "Conventional", 2: "FHA", 3: "VA", 4: "USDA"})
        seg["segment"] = seg["loan_type_label"] + " · " + seg["channel_label"]
        state_rate = walked / total * 100
        bars = (
            alt.Chart(seg)
            .mark_bar(color=ORANGE)
            .encode(
                y=alt.Y("segment:N", sort="-x", title=None),
                x=alt.X("walkaway_pct:Q", title="Walk-away rate (%)"),
                tooltip=["segment", alt.Tooltip("apps:Q", format=","), "walkaway_pct", "denial_pct"],
            )
        )
        rule = alt.Chart(pd.DataFrame({"x": [state_rate]})).mark_rule(strokeDash=[4, 4], color="#555").encode(x="x:Q")
        st.altair_chart(bars + rule, width="stretch")
        st.caption("Dashed line = Maryland average. Direct-channel applicants walk away far more than broker (indirect) ones.")
    with right:
        st.markdown("**Income: denials fall as income rises, walk-aways don't**")
        inc = income.melt(id_vars=["band"], value_vars=["walkaway_pct", "denial_pct"], var_name="metric", value_name="pct")
        inc["metric"] = inc["metric"].map({"walkaway_pct": "Walk-away", "denial_pct": "Denial"})
        inc["Income band (low → high)"] = inc["band"]
        line = (
            alt.Chart(inc)
            .mark_line(point=True)
            .encode(
                x=alt.X("band:O", title="Income quintile (1 = lowest)", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("pct:Q", title="Rate (%)", scale=alt.Scale(zero=True)),
                color=alt.Color("metric:N", title=None, scale=alt.Scale(domain=["Walk-away", "Denial"], range=[ORANGE, "#c0392b"])),
                tooltip=["band", "metric", "pct"],
            )
        )
        st.altair_chart(line, width="stretch")
        st.caption("Income quintiles of equal size (about 22,000 applications each). Higher income does not make applicants stay.")

    st.markdown("**What is recorded, by outcome** (share of applications with the field filled in)")
    av = availability.copy()
    av["outcome"] = av["outcome"].map(OUTCOME_LABELS)
    av = av.rename(
        columns={
            "apps": "Applications", "income_pct": "Income %", "cltv_pct": "CLTV %", "dti_pct": "DTI %",
            "rate_pct": "Interest rate %", "costs_pct": "Loan costs %", "outcome": "Outcome",
        }
    )
    st.dataframe(av, hide_index=True, width="stretch")
    st.caption(
        "Withdrawn and incomplete applications have no DTI by HMDA reporting rules. Missing DTI is a proxy for "
        "'did not reach underwriting', not a directly observed event."
    )

# ---------------------------------------------------------------- frontier
with tab_frontier:
    st.subheader("Which lenders do well on both measures?")
    st.write(
        "A lender is **on the frontier** if no other lender has both a lower walk-away rate *and* a lower denial rate. "
        "Lenders on the frontier set the best achievable performance; everyone else can be compared to them."
    )
    mode = st.radio(
        "Compare lenders on",
        ["Mix-adjusted (observed ÷ expected)", "Raw rates"],
        horizontal=True,
        help="Adjusted: each lender is compared to what its own mix of loan purpose × loan type predicts.",
    )
    adjusted = mode.startswith("Mix")

    d = lenders.copy()
    if adjusted:
        x, y, frontier_col = "den_oe", "wa_oe", "on_adj_frontier"
        xt, yt = "Denial O/E (1.0 = as expected for its loan mix)", "Walk-away O/E (1.0 = as expected for its loan mix)"
    else:
        x, y, frontier_col = "denial_pct", "walkaway_pct", "on_raw_frontier"
        xt, yt = "Denial rate (%)", "Walk-away rate (%)"
    d["frontier"] = d[frontier_col].map({True: "On frontier", False: "Other lenders"})
    d["purchase_share_lbl"] = d["purchase_share"].round(0).astype(int).astype(str) + "% purchase"

    tip = [
        alt.Tooltip("name:N", title="Lender"),
        alt.Tooltip("apps:Q", title="Applications", format=","),
        alt.Tooltip("walkaway_pct:Q", title="Walk-away %"),
        alt.Tooltip("denial_pct:Q", title="Denial %"),
        alt.Tooltip("wa_oe:Q", title="Walk-away O/E"),
        alt.Tooltip("den_oe:Q", title="Denial O/E"),
        alt.Tooltip("purchase_share:Q", title="Purchase share %"),
    ]
    base = alt.Chart(d).encode(
        x=alt.X(f"{x}:Q", title=xt, scale=alt.Scale(zero=True)),
        y=alt.Y(f"{y}:Q", title=yt, scale=alt.Scale(zero=True)),
    )
    points = base.mark_circle(opacity=0.8).encode(
        size=alt.Size("apps:Q", title="Applications", scale=alt.Scale(range=[40, 900])),
        color=alt.Color("frontier:N", title=None, scale=alt.Scale(domain=["On frontier", "Other lenders"], range=[ORANGE, GREY])),
        tooltip=tip,
    )
    fr = d[d[frontier_col]].sort_values(x)
    line = alt.Chart(fr).mark_line(color=ORANGE, strokeDash=[5, 4]).encode(x=f"{x}:Q", y=f"{y}:Q")
    labels = (
        alt.Chart(fr)
        .mark_text(align="left", dx=9, dy=-6, fontSize=11, color="#333")
        .encode(x=f"{x}:Q", y=f"{y}:Q", text="name:N")
    )
    layers = [points, line, labels]
    if adjusted:
        layers.append(alt.Chart(pd.DataFrame({"v": [1]})).mark_rule(color="#888", strokeWidth=0.8).encode(x="v:Q"))
        layers.append(alt.Chart(pd.DataFrame({"v": [1]})).mark_rule(color="#888", strokeWidth=0.8).encode(y="v:Q"))
    st.altair_chart(alt.layer(*layers).properties(height=520).interactive(), width="stretch")
    st.caption(
        "Bottom-left is best. Bubble size = applications. "
        + ("Lines at 1.0 mark 'as expected for its loan mix'." if adjusted else "Raw rates ignore that refinance-heavy lenders naturally lose more applicants.")
    )

    st.markdown(f"**Frontier lenders ({int(d[frontier_col].sum())})**")
    show = fr[
        ["name", "apps", "walkaway_pct", "denial_pct", "purchase_share", "wa_oe", "den_oe"]
    ].rename(
        columns={
            "name": "Lender", "apps": "Applications", "walkaway_pct": "Walk-away %", "denial_pct": "Denial %",
            "purchase_share": "Purchase share %", "wa_oe": "Walk-away O/E", "den_oe": "Denial O/E",
        }
    )
    st.dataframe(show, hide_index=True, width="stretch")

    both = int((lenders["on_raw_frontier"] & lenders["on_adj_frontier"]).sum())
    st.info(
        f"**Adjusting for loan mix changes who looks best.** {both} lenders sit on both frontiers; the rest of each "
        "frontier is different. Largest lenders: switch the toggle and watch Rocket Mortgage move onto the frontier "
        "once its mix is taken into account."
    )

    st.markdown("**Where the lost applicants are** · excess walk-aways = applications × (actual − expected rate)")
    ex = lenders.sort_values("excess_walkaways", ascending=False).head(10)[
        ["name", "apps", "wa_actual", "wa_expected", "wa_oe", "excess_walkaways"]
    ].rename(
        columns={
            "name": "Lender", "apps": "Applications", "wa_actual": "Walk-away % (actual)",
            "wa_expected": "Walk-away % (expected for mix)", "wa_oe": "O/E", "excess_walkaways": "Excess walk-aways",
        }
    )
    st.dataframe(ex, hide_index=True, width="stretch")
    st.caption("Applicants lost beyond what each lender's own loan mix predicts: the biggest recoverable volume.")

    with st.expander("All 111 lenders (≥ 200 applications)"):
        st.dataframe(
            lenders[["name", "apps", "walkaway_pct", "denial_pct", "purchase_share", "wa_oe", "den_oe", "on_raw_frontier", "on_adj_frontier"]],
            hide_index=True,
            width="stretch",
        )

# ------------------------------------------------------------------ method
with tab_method:
    st.subheader("How the numbers are built")
    st.markdown(
        """
**Population.** HMDA 2024 Maryland LAR → applications with an action of originated, approved-not-accepted, denied,
withdrawn, or closed-incomplete; first-lien, owner-occupied, site-built 1–4 unit; purpose = purchase / refinance /
cash-out refi. 206,077 → **118,431** rows (the filter attrition is in `attrition.csv`).

**Walk-away** = customer withdrew + file closed for incompleteness + customer declined an approved offer.
**Denial** = lender denied.

**Mix adjustment (indirect standardization).** For every application, look up the statewide walk-away (and denial) rate
of applications with the same *loan purpose × loan type*. Averaging those per lender gives the rate the lender
would have *if it were average at every loan type it handles*. **O/E = observed ÷ expected**; 1.0 is as expected,
below 1.0 is better than its mix predicts.

**Frontier.** Lender B *dominates* lender A if B is at least as good on both measures and strictly better on one.
The frontier is the set of lenders nobody dominates (a `NOT EXISTS` correlated subquery).
        """
    )
    st.subheader("Limitations")
    st.markdown(
        """
- **Only purpose × loan type are adjusted.** Income, loan size, county and borrower credit also affect abandonment.
  HMDA has no credit score, and DTI/CLTV are blank for withdrawals, so a high O/E is a flag to investigate, not proof of a poor process.
- **Channel is deliberately not adjusted** because it is the lender's own business-model choice.
- **Small lenders are noisy.** Lenders need 200+ applications; a lender with a few hundred applications and a handful
  of denials (e.g. denial rate near 0%) can reach the frontier by luck.
- **Walk-away mixes distinct events.** Withdrawal timing is unknown, so it is not all confirmed rejection of an offer.
- **Each lender is compared with a baseline that includes itself;** the largest lender (~6% of applications) pulls the baseline slightly toward its own rate.
- **Pricing is not analysed here:** pricing fields exist only for originated loans, which would add survivorship bias.
        """
    )
    st.caption("Source: FFIEC HMDA Data Browser, Maryland 2024 LAR · Lender names from the public GLEIF registry · Built with DuckDB + Streamlit.")
