"""
Approval-Abandonment Frontier: Maryland mortgage applications, HMDA 2024.

Reads the small CSV tables in data/ (built by build_data.py from the cleaned HMDA parquet).
Run locally:  streamlit run app.py
"""

import altair as alt
import pandas as pd
import streamlit as st

import calc

st.set_page_config(page_title="Approval-Abandonment Frontier", page_icon="🏠", layout="wide")

# ----------------------------------------------------------------------------- data
@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(f"data/{name}.csv")


lenders = load("lenders")
by_purpose = load("outcomes_by_purpose")
segments = load("segments")
leak = load("leak_by_segment")
availability = load("info_availability")
income = load("income_bands")
size_channel = load("size_channel")
price_groups = load("pricing_groups")
price_corr = load("pricing_corr")
price_loantype = load("pricing_by_loan_type")
den_purpose = load("denial_reasons_purpose")
den_loantype = load("denial_reasons_loantype")
dti = load("dti_denial")
counties = load("counties")
assumptions = load("assumptions")
quality = load("data_quality")
attrition = pd.read_csv("attrition.csv")

PURPOSE = {"purchase": "Purchase", "refinance": "Refinance", "cash_out_refi": "Cash-out refi"}
OUTCOME_ORDER = ["originated", "lender_denied", "customer_withdrew", "stalled_incomplete", "customer_declined"]
OUTCOME = {
    "originated": "Originated", "lender_denied": "Lender denied", "customer_withdrew": "Customer withdrew",
    "stalled_incomplete": "Incomplete / stalled", "customer_declined": "Customer declined offer",
}
OUTCOME_COLORS = ["#2f6fb0", "#c0392b", "#d9731a", "#e8b04b", "#9aa5b1"]
BLUE, ORANGE, RED, GREY = "#2f6fb0", "#d9731a", "#c0392b", "#9aa5b1"

total = int(by_purpose["apps"].sum())
by_outcome = by_purpose.groupby("outcome")["apps"].sum()
walked = int(by_outcome[["customer_withdrew", "stalled_incomplete", "customer_declined"]].sum())
denied = int(by_outcome["lender_denied"])
orig = int(by_outcome["originated"])
A = dict(zip(assumptions["key"], assumptions["value"]))

# direct vs indirect refinance leak, used across tabs
refi = leak[leak.purpose_label.isin(["refinance", "cash_out_refi"])]
dir_refi = refi[refi.channel_label == "direct"]
ind_refi = refi[refi.channel_label == "indirect"]
dir_refi_apps = int(dir_refi.apps.sum())
dir_refi_incomplete = int(dir_refi.incomplete.sum())
dir_refi_inc_rate = dir_refi_incomplete / dir_refi_apps
ind_refi_inc_rate = ind_refi.incomplete.sum() / ind_refi.apps.sum()
dir_refi_funded_rate = dir_refi.originated.sum() / dir_refi_apps
all_incomplete = int(by_outcome["stalled_incomplete"])

n_adj = int(lenders.on_adj_frontier.sum())
n_both = int((lenders.on_raw_frontier & lenders.on_adj_frontier).sum())
n_inc_keep = int((lenders.on_adj_frontier & lenders.on_inc_frontier).sum())
n_500_keep = int((lenders.on_adj_frontier & lenders.on_500_frontier).sum())
n_sig_worse = int((lenders.wa_z > 1.96).sum())
n_sig_better = int((lenders.wa_z < -1.96).sum())

DEFAULT_SHARE, DEFAULT_BPS = 0.25, 100
_c = counties[~counties.noisy]
cty_lo, cty_hi = _c.wa_oe.min(), _c.wa_oe.max()


# ----------------------------------------------------------------------------- header
st.title("The Approval–Abandonment Frontier")
st.caption(
    "Maryland first-lien, owner-occupied home loan applications, HMDA 2024 · "
    "where applicants leave, which lenders keep them, and what a product team should do about it."
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Applications", f"{total:,}")
c2.metric("Originated", f"{orig / total:.1%}")
c3.metric("Applicant walked away", f"{walked / total:.1%}", help="Withdrew + closed incomplete + declined the offer")
c4.metric("Lender denied", f"{denied / total:.1%}")

tabs = st.tabs(["Summary", "Funnel", "Lenders", "Pricing", "Denials", "Geography", "Opportunity & test", "Method & data"])
(t_sum, t_fun, t_len, t_pri, t_den, t_geo, t_opp, t_met) = tabs

# ============================================================================ SUMMARY
with t_sum:
    d_opp = calc.opportunity_direct_refi(leak, assumptions, DEFAULT_SHARE, DEFAULT_BPS)
    l_opp = calc.opportunity_lender_gap(lenders, assumptions, DEFAULT_SHARE, DEFAULT_BPS)
    share_of_stalled = dir_refi_incomplete / all_incomplete

    st.subheader("Product memo: the leak is in direct-channel refinances")
    st.markdown(
        f"""
**Problem.** {walked / total:.1%} of Maryland mortgage applications end because the *applicant* leaves; only
{denied / total:.1%} are denied. Denials get most of the attention; the larger loss is applicants who leave.

**Where it leaks.** Files closed as *incomplete* are the clearest process failure (the lender could not get what it needed to decide).
**{dir_refi_inc_rate:.1%}** of direct-channel refinance and cash-out applications end that way, against
**{ind_refi_inc_rate:.1%}** through brokers, and 1.7% for direct purchases. Direct refinances are
**{share_of_stalled:.0%}** of all stalled files in the state ({dir_refi_incomplete:,} of {all_incomplete:,}).

**Neither income nor geography explains it.** Income lowers denials (20.5% → 6.9%) but not walk-aways
(about 24–25% in every income band). After adjusting for loan mix, county observed ÷ expected ratios run only from {cty_lo:.2f} to {cty_hi:.2f}.

**Lenders differ a lot once loan mix is removed.** {n_sig_worse} of 111 lenders lose significantly more applicants than
their own mix predicts and {n_sig_better} significantly fewer. Only {n_both} of the {n_adj} lenders on the mix-adjusted
frontier are also on the raw-rate frontier, so raw rankings mislead. The frontier does not cost borrowers more: its lenders
price about the same as everyone else on conventional purchase loans.

**Recommendation.** Build a *file-completion assistant* for direct refinance applicants: a live document checklist,
automated nudges, and a human call when a file stalls for 48 hours. It targets the largest identifiable leak and leaves the
credit decision untouched.

**Size of the prize (Maryland only, one year, assumptions on the *Opportunity & test* tab).** Closing
{DEFAULT_SHARE:.0%} of the direct-vs-broker incomplete-file gap recovers about **{d_opp.funded_loans.sum():,.0f} funded loans**
(~${d_opp.volume.sum() / 1e6:,.0f}M of origination volume). Closing {DEFAULT_SHARE:.0%} of the excess walk-aways at the
{l_opp['lenders']} significantly worse lenders is about {l_opp['funded_loans']:,.0f} loans (~${l_opp['volume'] / 1e6:,.0f}M).

**How we would test it.** A randomised trial on direct refinance applications. Primary metric: share of files closed
incomplete ({dir_refi_inc_rate:.1%} → {dir_refi_inc_rate - 0.03:.1%}); it needs about
{calc.sample_size_per_arm(dir_refi_inc_rate, dir_refi_inc_rate - 0.03):,} files per arm. Guardrails: denial rate,
time to decision, cost per file, complaints, treatment parity.
        """
    )
    st.info(
        "Descriptive analysis of public HMDA data. It makes no claim about any lender's practices, and no demographic "
        "(fair-lending) analysis is attempted. Interventions must never change credit decisions or use protected characteristics."
    )

# ============================================================================ FUNNEL
with t_fun:
    st.subheader("More applicants walk away than lenders turn down")
    p = by_purpose.copy()
    p["purpose"] = p["purpose_label"].map(PURPOSE)
    p["share"] = p["apps"] / p.groupby("purpose_label")["apps"].transform("sum")
    p["outcome_label"] = p["outcome"].map(OUTCOME)
    order_expr = f"indexof({OUTCOME_ORDER}, datum.outcome)"
    chart = (
        alt.Chart(p)
        .mark_bar()
        .encode(
            y=alt.Y("purpose:N", title=None, sort=list(PURPOSE.values())),
            x=alt.X("share:Q", title="Share of applications", axis=alt.Axis(format="%")),
            color=alt.Color(
                "outcome_label:N", title="Outcome", sort=[OUTCOME[o] for o in OUTCOME_ORDER],
                scale=alt.Scale(domain=[OUTCOME[o] for o in OUTCOME_ORDER], range=OUTCOME_COLORS),
            ),
            order=alt.Order("o:Q"),
            tooltip=["purpose", "outcome_label", alt.Tooltip("apps:Q", format=","), alt.Tooltip("share:Q", format=".1%")],
        )
        .transform_calculate(o=order_expr)
        .properties(height=190)
    )
    st.altair_chart(chart, width="stretch")
    st.caption("Refinances lose roughly 35–37% of applications to walk-aways; purchases about 20%.")

    st.subheader("Where files leak: purpose × channel")
    lk = leak.copy()
    lk["segment"] = lk.purpose_label.map(PURPOSE) + " · " + lk.channel_label
    lk = lk.melt(id_vars=["segment", "apps"], value_vars=["originated", "denied", "withdrew", "incomplete", "declined"],
                 var_name="outcome", value_name="n")
    lk["share"] = lk.n / lk.apps
    names = {"originated": "Originated", "denied": "Lender denied", "withdrew": "Customer withdrew",
             "incomplete": "Incomplete / stalled", "declined": "Customer declined offer"}
    lk["outcome_label"] = lk.outcome.map(names)
    lk_order = f"indexof({list(names.keys())}, datum.outcome)"
    lchart = (
        alt.Chart(lk).mark_bar().encode(
            y=alt.Y("segment:N", title=None, sort=alt.SortField("apps", order="descending")),
            x=alt.X("share:Q", title="Share of applications", axis=alt.Axis(format="%")),
            color=alt.Color("outcome_label:N", title="Outcome", sort=list(names.values()),
                            scale=alt.Scale(domain=list(names.values()), range=OUTCOME_COLORS)),
            order=alt.Order("o:Q"),
            tooltip=["segment", "outcome_label", alt.Tooltip("n:Q", format=","), alt.Tooltip("share:Q", format=".1%")],
        ).transform_calculate(o=lk_order).properties(height=260)
    )
    st.altair_chart(lchart, width="stretch")
    st.markdown(
        f"The yellow slice is the story: **{dir_refi_inc_rate:.1%}** of direct refinance applications are closed incomplete, "
        f"versus **{ind_refi_inc_rate:.1%}** through brokers. Direct *purchases* lose only 1.7% this way, so the problem is "
        "specific to refinances that applicants must paper on their own."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Walk-away rate by loan type × channel** (segments with ≥ 500 applications)")
        seg = segments.copy()
        seg["loan_type_label"] = seg["loan_type"].map({1: "Conventional", 2: "FHA", 3: "VA", 4: "USDA"})
        seg["segment"] = seg["loan_type_label"] + " · " + seg["channel_label"]
        bars = alt.Chart(seg).mark_bar(color=ORANGE).encode(
            y=alt.Y("segment:N", sort="-x", title=None), x=alt.X("walkaway_pct:Q", title="Walk-away rate (%)"),
            tooltip=["segment", alt.Tooltip("apps:Q", format=","), "walkaway_pct", "denial_pct"])
        rule = alt.Chart(pd.DataFrame({"x": [walked / total * 100]})).mark_rule(strokeDash=[4, 4], color="#555").encode(x="x:Q")
        st.altair_chart(bars + rule, width="stretch")
        st.caption("Dashed line = Maryland average. Direct applicants walk away far more than broker (indirect) ones for every loan type.")
    with right:
        st.markdown("**Income: denials fall as income rises, walk-aways don't**")
        inc = income.melt(id_vars=["band"], value_vars=["walkaway_pct", "denial_pct"], var_name="metric", value_name="pct")
        inc["metric"] = inc["metric"].map({"walkaway_pct": "Walk-away", "denial_pct": "Denial"})
        line = alt.Chart(inc).mark_line(point=True).encode(
            x=alt.X("band:O", title="Income quintile (1 = lowest)", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("pct:Q", title="Rate (%)", scale=alt.Scale(zero=True)),
            color=alt.Color("metric:N", title=None, scale=alt.Scale(domain=["Walk-away", "Denial"], range=[ORANGE, RED])),
            tooltip=["band", "metric", "pct"])
        st.altair_chart(line, width="stretch")
        st.caption("Five income groups of equal size (about 22,000 applications each).")

    st.markdown("**Loan size and channel** (share of applications that originate, by loan-size quartile within purpose)")
    sc = size_channel.copy()
    sc["purpose"] = sc.purpose_label.map(PURPOSE)
    sch = alt.Chart(sc).mark_line(point=True).encode(
        x=alt.X("size_quartile:O", title="Loan size quartile (1 = smallest)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("originated_pct:Q", title="Originated (%)", scale=alt.Scale(zero=True)),
        color=alt.Color("channel_label:N", title="Channel", scale=alt.Scale(domain=["direct", "indirect"], range=[ORANGE, BLUE])),
        tooltip=["purpose", "size_quartile", "channel_label", alt.Tooltip("apps:Q", format=","), "originated_pct"],
    ).properties(height=220).facet(column=alt.Column("purpose:N", title=None))
    st.altair_chart(sch)
    st.caption("The channel gap is wide in refinances at every loan size; loan size itself matters much less.")

# ============================================================================ LENDERS
with t_len:
    st.subheader("Which lenders do well on both measures?")
    st.write(
        "A lender is **on the frontier** if no other lender has both a lower walk-away rate *and* a lower denial rate. "
        "Low walk-aways can be bought by denying more, so both must be read together."
    )
    mode = st.radio(
        "Compare lenders on",
        ["Mix-adjusted (observed ÷ expected)", "Mix + income adjusted", "Raw rates"],
        horizontal=True,
        help="Adjusted: each lender is compared with what its own mix (loan purpose × loan type, optionally income band) predicts.",
    )
    d = lenders.copy()
    if mode.startswith("Mix-adjusted"):
        x, y, fcol, adjusted = "den_oe", "wa_oe", "on_adj_frontier", True
    elif mode.startswith("Mix +"):
        x, y, fcol, adjusted = "den_oe_inc", "wa_oe_inc", "on_inc_frontier", True
    else:
        x, y, fcol, adjusted = "denial_pct", "walkaway_pct", "on_raw_frontier", False
    xt = "Denial O/E (1.0 = as expected for its mix)" if adjusted else "Denial rate (%)"
    yt = "Walk-away O/E (1.0 = as expected for its mix)" if adjusted else "Walk-away rate (%)"
    d["frontier"] = d[fcol].map({True: "On frontier", False: "Other lenders"})

    tip = [alt.Tooltip("name:N", title="Lender"), alt.Tooltip("apps:Q", title="Applications", format=","),
           alt.Tooltip("walkaway_pct:Q", title="Walk-away %"), alt.Tooltip("denial_pct:Q", title="Denial %"),
           alt.Tooltip("wa_oe:Q", title="Walk-away O/E"), alt.Tooltip("den_oe:Q", title="Denial O/E"),
           alt.Tooltip("purchase_share:Q", title="Purchase share %")]
    base = alt.Chart(d).encode(x=alt.X(f"{x}:Q", title=xt, scale=alt.Scale(zero=True)),
                               y=alt.Y(f"{y}:Q", title=yt, scale=alt.Scale(zero=True)))
    points = base.mark_circle(opacity=0.8).encode(
        size=alt.Size("apps:Q", title="Applications", scale=alt.Scale(range=[40, 900])),
        color=alt.Color("frontier:N", title=None, scale=alt.Scale(domain=["On frontier", "Other lenders"], range=[ORANGE, GREY])),
        tooltip=tip)
    fr = d[d[fcol]].sort_values(x)
    line = alt.Chart(fr).mark_line(color=ORANGE, strokeDash=[5, 4]).encode(x=f"{x}:Q", y=f"{y}:Q")
    labels = alt.Chart(fr).mark_text(align="left", dx=9, dy=-6, fontSize=11, color="#333").encode(x=f"{x}:Q", y=f"{y}:Q", text="name:N")
    layers = [points, line, labels]
    if adjusted:
        one = pd.DataFrame({"v": [1]})
        layers += [alt.Chart(one).mark_rule(color="#888", strokeWidth=0.8).encode(x="v:Q"),
                   alt.Chart(one).mark_rule(color="#888", strokeWidth=0.8).encode(y="v:Q")]
    st.altair_chart(alt.layer(*layers).properties(height=520).interactive(), width="stretch")
    st.caption("Bottom-left is best. Bubble size = applications. "
               + ("Lines at 1.0 mean 'as expected for its loan mix'." if adjusted else
                  "Raw rates ignore that refinance-heavy lenders naturally lose more applicants."))

    st.markdown(f"**Frontier lenders ({int(d[fcol].sum())})**")
    show = fr[["name", "apps", "walkaway_pct", "denial_pct", "purchase_share", "wa_oe", "den_oe", "wa_z", "den_z"]].rename(columns={
        "name": "Lender", "apps": "Applications", "walkaway_pct": "Walk-away %", "denial_pct": "Denial %",
        "purchase_share": "Purchase share %", "wa_oe": "Walk-away O/E", "den_oe": "Denial O/E",
        "wa_z": "Walk-away z", "den_z": "Denial z"})
    st.dataframe(show, hide_index=True, width="stretch")

    st.markdown("**How robust is the frontier?**")
    r1, r2, r3 = st.columns(3)
    r1.metric("On both raw and adjusted frontier", f"{n_both} of {n_adj}",
              help="Adjusting for loan mix changes who looks best")
    r2.metric("Survive adding income to the adjustment", f"{n_inc_keep} of {n_adj}")
    r3.metric("Survive requiring 500+ applications", f"{n_500_keep} of {n_adj}")
    st.caption("Lenders that stay on the frontier under all three views are the most credible. "
               "z = (observed − expected) ÷ standard error; |z| above 1.96 is unlikely by chance for one lender "
               "(with 111 lenders a few false alarms are expected, but the large z-values here are far beyond that).")

    st.markdown(f"**Where the lost applicants are** · {n_sig_worse} lenders are significantly worse than their mix, "
                f"{n_sig_better} significantly better. Excess = observed − expected walk-aways.")
    ex = lenders.sort_values("excess_walkaways", ascending=False).head(10)[
        ["name", "apps", "wa_actual", "wa_expected", "wa_oe", "wa_z", "excess_walkaways"]].rename(columns={
        "name": "Lender", "apps": "Applications", "wa_actual": "Walk-away % (actual)",
        "wa_expected": "Walk-away % (expected for mix)", "wa_oe": "O/E", "wa_z": "z", "excess_walkaways": "Excess walk-aways"})
    st.dataframe(ex, hide_index=True, width="stretch")
    with st.expander("All 111 lenders (≥ 200 applications)"):
        st.dataframe(lenders[["name", "apps", "walkaway_pct", "denial_pct", "purchase_share", "wa_oe", "den_oe",
                              "wa_z", "den_z", "on_raw_frontier", "on_adj_frontier", "robust_frontier"]],
                     hide_index=True, width="stretch")

# ============================================================================ PRICING
with t_pri:
    st.subheader("Do the best-performing lenders charge borrowers more?")
    st.write(
        "Pricing fields exist only for *originated* loans, so comparing lenders on all loans would be biased. "
        "This tab holds one segment fixed: **originated conventional purchase loans**, lenders with 100+ such loans."
    )
    pg = price_groups.rename(columns={
        "grp": "Lender group", "lenders": "Lenders", "loans": "Loans", "med_spread": "Median rate spread (pp)",
        "med_costs": "Median loan costs ($)", "med_points": "Median discount points ($)", "med_rate": "Median interest rate (%)"})
    st.dataframe(pg, hide_index=True, width="stretch")
    rb = price_groups[price_groups.grp.str.startswith("Robust")].iloc[0]
    ot = price_groups[price_groups.grp.str.startswith("All other")].iloc[0]
    st.markdown(
        f"**Finding.** Robust-frontier lenders price in line with everyone else: median rate spread "
        f"{rb.med_spread:.2f} vs {ot.med_spread:.2f} points, median loan costs ${rb.med_costs:,.0f} vs ${ot.med_costs:,.0f}. "
        "Keeping applicants does not appear to be bought with higher prices."
    )
    st.markdown("**Across lenders: does walk-away or denial O/E move with price?** (Spearman rank correlation)")
    pcorr = price_corr.pivot(index="price", columns="measure", values="spearman").reset_index().rename(columns={"price": "Price measure"})
    st.dataframe(pcorr, hide_index=True, width="stretch")
    st.caption(
        "Walk-away O/E is essentially uncorrelated with price (|ρ| ≤ 0.13). Lenders that deny more tend to charge slightly less "
        "(ρ between −0.15 and −0.29), consistent with strict lenders taking safer borrowers, not with them charging for retention."
    )
    c_x = st.selectbox("Scatter: price measure", ["med_spread", "med_costs", "med_points", "med_rate"],
                       format_func=lambda s: {"med_spread": "Median rate spread", "med_costs": "Median loan costs",
                                              "med_points": "Median discount points", "med_rate": "Median interest rate"}[s])
    pdat = lenders.dropna(subset=["med_spread"])
    sp = alt.Chart(pdat).mark_circle(opacity=0.75).encode(
        x=alt.X("wa_oe:Q", title="Walk-away O/E (mix-adjusted)"), y=alt.Y(f"{c_x}:Q", title="Median (conventional purchase, originated)"),
        size=alt.Size("price_loans:Q", title="Loans", scale=alt.Scale(range=[30, 500])),
        color=alt.Color("robust_frontier:N", title="Robust frontier", scale=alt.Scale(domain=[True, False], range=[ORANGE, GREY])),
        tooltip=[alt.Tooltip("name:N", title="Lender"), "price_loans", "wa_oe", "den_oe", c_x]).properties(height=360)
    st.altair_chart(sp, width="stretch")
    st.markdown("**For context: pricing by loan type** (originated purchase loans)")
    lt = price_loantype.copy()
    lt["loan_type"] = lt.loan_type.map({1: "Conventional", 2: "FHA", 3: "VA", 4: "USDA"})
    st.dataframe(lt.rename(columns={"loan_type": "Loan type", "loans": "Loans", "med_spread": "Median rate spread (pp)",
                                    "med_costs": "Median loan costs ($)", "med_rate": "Median rate (%)"}),
                 hide_index=True, width="stretch")
    st.caption("Limitations: survivorship (only funded loans are priced), no credit score, and a small number of robust-frontier lenders with enough conventional purchase volume.")

# ============================================================================ DENIALS
with t_den:
    st.subheader("Why are applications denied?")
    dp = den_purpose.copy()
    dp["purpose"] = dp.purpose_label.map(PURPOSE)
    dp["share"] = dp.denials / dp.groupby("purpose_label").denials.transform("sum")
    dch = alt.Chart(dp).mark_bar().encode(
        y=alt.Y("purpose:N", title=None, sort=list(PURPOSE.values())),
        x=alt.X("share:Q", title="Share of denials", axis=alt.Axis(format="%")),
        color=alt.Color("reason:N", title="Reason"),
        tooltip=["purpose", "reason", alt.Tooltip("denials:Q", format=","), alt.Tooltip("share:Q", format=".1%")],
    ).properties(height=200)
    st.altair_chart(dch, width="stretch")
    inc7 = dp[dp.code.astype(str) == "7"].set_index("purpose_label").denials
    tot_by = dp.groupby("purpose_label").denials.sum()
    st.markdown(
        f"- **Purchases** are denied mainly on **debt-to-income** (37%); **cash-out refinances** on **credit history** (27%) "
        f"and DTI (23%).\n"
        f"- **'Credit application incomplete' is itself a denial reason:** {inc7.get('cash_out_refi', 0) / tot_by['cash_out_refi']:.0%} of cash-out and "
        f"{inc7.get('refinance', 0) / tot_by['refinance']:.0%} of refinance denials, but only {inc7.get('purchase', 0) / tot_by['purchase']:.0%} of purchase denials. "
        "It is the same document-completion failure that shows up in the stalled files, here appearing as a formal denial."
    )
    cdd, cde = st.columns(2)
    with cdd:
        st.markdown("**Denial rate by DTI** (originated or denied files with a recorded DTI)")
        dti_chart = alt.Chart(dti).mark_bar(color=RED).encode(
            x=alt.X("dti_band:N", title="Debt-to-income band (%)", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("denial_rate_pct:Q", title="Denial rate (%)"),
            tooltip=["dti_band", alt.Tooltip("decided:Q", format=","), "denial_rate_pct"]).properties(height=280)
        st.altair_chart(dti_chart, width="stretch")
        st.caption("Flat near 9–10% from 20% to 49% DTI, then a cliff: 26.6% at 50–60% and 89.5% above 60%. "
                   "The jump at 50% looks like a policy line. The elevated rate below 20% is unexplained and may reflect "
                   "thin-income or collateral issues.")
    with cde:
        st.markdown("**Top denial reasons by loan type**")
        dl = den_loantype.copy()
        dl["loan_type"] = dl.loan_type.map({1: "Conventional", 2: "FHA", 3: "VA", 4: "USDA"})
        dl["share"] = dl.denials / dl.groupby("loan_type").denials.transform("sum")
        top3 = dl.sort_values(["loan_type", "denials"], ascending=[True, False]).groupby("loan_type").head(3)
        top3["share"] = (100 * top3.share).round(1)
        st.dataframe(top3[["loan_type", "reason", "denials", "share"]].rename(columns={
            "loan_type": "Loan type", "reason": "Reason", "denials": "Denials", "share": "Share of loan type's denials (%)"}),
            hide_index=True, width="stretch")
        st.caption("Reasons are as reported by the lender; up to four may be listed per denial and only the first is kept here.")

# ============================================================================ GEOGRAPHY
with t_geo:
    st.subheader("Geography matters little once loan mix is removed")
    cg = counties[~counties.noisy].copy()
    cg["label"] = cg["county"]
    lo, hi = cg.wa_oe.min(), cg.wa_oe.max()
    st.write(
        f"Jurisdictions with 1,000+ applications ({len(cg)} of the 23 counties and Baltimore City): raw walk-away runs from "
        f"{cg.walkaway_pct.min():.1f}% to {cg.walkaway_pct.max():.1f}%. After adjusting for each county's loan mix, "
        f"the observed ÷ expected ratio ranges only from {lo:.2f} to {hi:.2f}."
    )
    gb = alt.Chart(cg).mark_bar(color=ORANGE).encode(
        y=alt.Y("label:N", sort="-x", title=None), x=alt.X("walkaway_pct:Q", title="Walk-away rate (%)"),
        tooltip=["county", alt.Tooltip("apps:Q", format=","), "walkaway_pct", "wa_expected", "wa_oe", "denial_pct", "den_oe", "purchase_share"])
    exp_tick = alt.Chart(cg).mark_tick(color="#333", thickness=2, size=14).encode(y=alt.Y("label:N", sort="-x"), x="wa_expected:Q")
    st.altair_chart((gb + exp_tick).properties(height=430), width="stretch")
    st.caption("Bars = actual walk-away rate. Black tick = rate expected from the county's mix of loan purpose × loan type.")
    cols = ["county", "apps", "walkaway_pct", "wa_oe", "denial_pct", "den_oe", "purchase_share", "top_lender", "top_share_pct"]
    st.dataframe(counties[cols].rename(columns={
        "county": "County", "apps": "Applications", "walkaway_pct": "Walk-away %", "wa_oe": "Walk-away O/E",
        "denial_pct": "Denial %", "den_oe": "Denial O/E", "purchase_share": "Purchase share %",
        "top_lender": "Largest lender", "top_share_pct": "Its share %"}), hide_index=True, width="stretch")
    st.caption("Prince George's County and Baltimore City have the highest denial O/E (1.27 and 1.21): more denials than their loan mix predicts. "
               "Rows under 1,000 applications are noisy; 'County not reported' is a data gap, not a place. "
               "The largest lender in most counties holds only 6–8% of applications: Maryland is not concentrated.")

# ============================================================================ OPPORTUNITY & TEST
with t_opp:
    st.subheader("Size of the prize")
    st.write("Every assumption is a slider. Defaults are deliberately conservative: closing only part of a gap, and valuing a funded loan at a modest share of its amount.")
    s1, s2 = st.columns(2)
    share = s1.slider("Share of the gap an intervention closes", 0, 100, int(DEFAULT_SHARE * 100), 5, format="%d%%",
                      help="Brokers' applicants are self-selected, so closing 100% of the direct-vs-broker gap is unrealistic.") / 100
    bps = s2.slider("Revenue per funded loan (basis points of loan amount)", 25, 300, DEFAULT_BPS, 25,
                    help="Gross lender revenue per funded loan, as a share of the loan. 100 bps = 1%.")
    st.caption(f"Fixed from the data: {A['approval_given_stay']:.1%} of files that stay to a decision are funded; median originated loan ${A['med_loan_all']:,.0f}.")

    A1 = calc.opportunity_direct_refi(leak, assumptions, share, bps)
    A2 = calc.opportunity_lender_gap(lenders, assumptions, share, bps)
    ca, cb = st.columns(2)
    with ca:
        st.markdown("**Scenario A: fix incomplete files in direct refinances**")
        st.metric("Funded loans recovered (Maryland, 1 year)", f"{A1.funded_loans.sum():,.0f}")
        st.metric("Origination volume", f"${A1.volume.sum() / 1e6:,.0f}M")
        st.metric("Revenue", f"${A1.revenue.sum() / 1e6:,.1f}M")
        t = A1.copy()
        t["purpose"] = t.purpose.map(PURPOSE)
        st.dataframe(t[["purpose", "direct_apps", "direct_incomplete_pct", "indirect_incomplete_pct", "gap_files", "funded_loans"]].rename(columns={
            "purpose": "Purpose", "direct_apps": "Direct applications", "direct_incomplete_pct": "Direct incomplete %",
            "indirect_incomplete_pct": "Broker incomplete %", "gap_files": "Gap (files)", "funded_loans": "Funded loans"}).round(1),
            hide_index=True, width="stretch")
    with cb:
        st.markdown(f"**Scenario B: {A2['lenders']} lenders significantly worse than their loan mix**")
        st.metric("Funded loans recovered (Maryland, 1 year)", f"{A2['funded_loans']:,.0f}")
        st.metric("Origination volume", f"${A2['volume'] / 1e6:,.0f}M")
        st.metric("Revenue", f"${A2['revenue'] / 1e6:,.1f}M")
        st.caption(f"Excess walk-aways at these lenders: {A2['excess_walkaways']:,.0f} (observed minus expected for their mix).")
    st.warning(
        "Treat these as order-of-magnitude estimates. They assume recovered files behave like average files that stay to a decision, "
        "ignore intervention cost, and are Maryland only (one state, one year). Scenarios A and B overlap and should not be added."
    )

    st.subheader("Experiment design: file-completion assistant")
    st.markdown(
        """
**Hypothesis.** For direct-channel refinance applicants, a live document checklist plus automated nudges and a human call at 48 hours
of inactivity reduces the share of files closed incomplete, without changing credit decisions.

**Population and assignment.** New direct refinance and cash-out applications; randomise at the application level (50/50),
stratified by purpose and loan type. Exclude files already in underwriting.

**Metrics.** *Primary:* share of files closed incomplete (or funded rate, below). *Secondary:* withdrawal rate, files
reaching a decision, time to decision. *Guardrails:* denial rate (it may rise mechanically as more files reach underwriting; watch the
mix, not the level), cost per file, complaint rate, and treatment parity (identical service offered to every applicant).

**Risks.** Novelty effects, contamination if loan officers learn the treatment, and a seasonality break if the test straddles a rate move.
        """
    )
    st.markdown("**Sample-size calculator**")
    m1, m2, m3 = st.columns(3)
    metric = m1.selectbox("Primary metric", ["Files closed incomplete", "Funded rate"])
    base = dir_refi_inc_rate if metric == "Files closed incomplete" else dir_refi_funded_rate
    default_mde = 3.0 if metric == "Files closed incomplete" else 2.5
    mde = m2.slider("Effect to detect (percentage points)", 0.5, 10.0, default_mde, 0.5)
    weekly = m3.number_input("Eligible applications per week", min_value=50, value=400, step=50)
    sign = -1 if metric == "Files closed incomplete" else 1
    p2 = base + sign * mde / 100
    n_arm = calc.sample_size_per_arm(base, p2)
    weeks = 2 * n_arm / weekly
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Baseline (direct refinances, MD 2024)", f"{base:.1%}")
    k2.metric("Target", f"{p2:.1%}")
    k3.metric("Files per arm (80% power, α = 5%)", f"{n_arm:,}")
    k4.metric("Weeks to run", f"{weeks:.1f}")
    st.caption("Incomplete files are a proximal metric and need far fewer files than the funded rate. A sensible plan is to power the test on the "
               "proximal metric and confirm the funded rate as a pre-registered secondary readout.")

# ============================================================================ METHOD & DATA
with t_met:
    st.subheader("How the numbers are built")
    st.markdown(
        """
**Population.** HMDA 2024 Maryland LAR → applications with an action of originated, approved-not-accepted, denied,
withdrawn, or closed-incomplete; first-lien, owner-occupied, site-built 1–4 unit; purpose = purchase / refinance /
cash-out refi.

**Walk-away** = customer withdrew + file closed for incompleteness + customer declined an approved offer.
**Denial** = lender denied.

**Mix adjustment (indirect standardization).** For each application, look up the statewide walk-away (and denial) rate for
applications with the same loan purpose × loan type. The average over a lender's applications is the rate the lender would have
*if it were average at every loan type it handles*. **O/E = observed ÷ expected**: 1.0 is as expected, below 1.0 is better than its
mix predicts. A z-score (observed − expected) ÷ √Σp(1−p) says whether the gap is larger than chance.

**Frontier.** Lender B *dominates* lender A if B is at least as good on both measures and strictly better on one. The frontier is
the set nobody dominates (SQL `NOT EXISTS`). It is recomputed under three adjustments and checked by brute force in `build_data.py`.

**Opportunity and test.** Scenario maths lives in `calc.py` with built-in checks. Sample sizes use the standard two-proportion z-test.
        """
    )
    st.subheader("Limitations")
    st.markdown(
        """
- **Only purpose × loan type (optionally income) are adjusted.** Loan size, county, and borrower credit also affect abandonment.
  HMDA has no credit score, and DTI/CLTV are blank for withdrawals, so a high O/E is a flag to investigate, not proof of a weaker process.
- **Channel is deliberately not adjusted**, because it is the lender's own business-model choice. The direct-vs-broker gap is an
  association: brokers pre-screen and coach borrowers, so not all of it is recoverable.
- **Small lenders are noisy.** Lenders need 200+ applications; lenders with a handful of denials can reach the frontier by luck.
- **Walk-away mixes distinct events.** Withdrawal timing is unknown, so it is not all confirmed rejection of an offer.
- **Each lender is compared with a baseline that includes itself.** The largest lender (about 6% of applications) pulls the baseline toward its own rate.
- **One state, one year, applications not borrowers.** Findings may not generalise to other states or periods.
        """
    )
    st.subheader("Data quality: what was checked and what it implies")
    st.dataframe(quality.rename(columns={"check": "Check", "result": "Result", "implication": "Implication"}),
                 hide_index=True, width="stretch")
    st.markdown("**Filter attrition** (raw file → analysis population)")
    st.dataframe(attrition.rename(columns={"state": "State", "year": "Year", "step": "Step", "rows": "Rows"}),
                 hide_index=True, width="stretch")
    st.markdown("**What is recorded, by outcome** (share of applications with the field filled in)")
    av = availability.copy()
    av["outcome"] = av["outcome"].map(OUTCOME)
    st.dataframe(av.rename(columns={
        "outcome": "Outcome", "apps": "Applications", "income_pct": "Income %", "property_value_pct": "Property value %",
        "cltv_pct": "CLTV %", "dti_pct": "DTI %", "rate_pct": "Interest rate %", "costs_pct": "Loan costs %"}),
        hide_index=True, width="stretch")
    st.caption("Source: FFIEC HMDA Data Browser, Maryland 2024 LAR · Lender names from the public GLEIF registry · Built with DuckDB + Streamlit. "
               "Descriptive analysis only; no claim about any lender's practices.")
