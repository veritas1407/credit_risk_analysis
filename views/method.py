import streamlit as st

import store
import ui

ctx = store.load_state(store.current_state())

st.title("Method & data")

st.subheader("How the numbers are built")
a, b = st.columns(2)
with a.container(key="card-m1"):
    st.markdown(f"""
**Population.** HMDA 2024 loan/application register for {ctx.name} → applications with an action of originated, approved-not-accepted, denied, withdrawn
or closed-incomplete; first-lien, owner-occupied, site-built 1–4 unit; purpose = purchase, refinance or cash-out refinance.

**Outcomes.** *Walk-away* = applicant withdrew + file closed for incompleteness + applicant declined an approved offer. *Denial* = lender denied.

**Mix adjustment (indirect standardisation).** For each application, take the statewide walk-away (and denial) rate of applications with the same
loan purpose × loan type. The average over a lender's applications is the rate it would have *if it were average at every loan type it handles*.
**O/E = observed ÷ expected.** z = (observed − expected) ÷ √Σp(1−p) says whether a gap exceeds chance.
""")
with b.container(key="card-m2"):
    st.markdown("""
**Frontier.** Lender B *dominates* A if B is at least as good on both measures and strictly better on one. The frontier is everyone nobody dominates
(SQL `NOT EXISTS`). It is recomputed under four adjustments and verified against a brute-force check in `build_data.py`.

**Shrinkage.** A DerSimonian–Laird empirical-Bayes step estimates the *true* spread of lender O/E (τ) and pulls noisy small lenders toward the average.

**ML case-mix model.** Gradient-boosted trees on 13 application-time fields, scored out-of-lender (see *Case-mix model*).

**Opportunity and test.** Scenario maths lives in `calc.py` with built-in checks. Sample sizes use the standard two-proportion z-test.
""")

st.subheader("Limitations")
st.markdown("""
- **Adjustment is partial.** Purpose × loan type (optionally income, or 13 ML features) are controlled. HMDA has no credit score and DTI/CLTV are blank for
  withdrawals, so a high O/E is a flag to investigate, not proof of a weaker process.
- **Channel is deliberately not adjusted** in the main comparison: it is the lender's own business-model choice. The direct-vs-broker gap is an association;
  brokers pre-screen and coach applicants, so not all of it is recoverable.
- **Blank fields are not random.** Income is blank much more often on incomplete and declined-offer files. The transfer test drops income fields for this reason;
  the income-adjusted frontier groups unknown income into its own band, which may favour lenders with many such files.
- **Small lenders are noisy.** Lenders need 200+ applications; frontiers of 2–7 lenders move when one lender moves.
- **Walk-away mixes distinct events.** Withdrawal timing is unknown, so it is not all confirmed rejection of an offer.
- **Each lender is compared with a baseline that includes itself.** The largest lender pulls the baseline toward its own rate.
- **One year, applications not borrowers.** HMDA has no applicant id and no timestamps. Replication across six states is evidence of a pattern, not proof of causation.
- **No demographic analysis.** Fair-lending analysis requires protected-class data and a compliance process; none was attempted, and no model here uses protected characteristics.
""")

st.subheader(f"Data quality: {ctx.name}")
st.dataframe(ctx.quality.rename(columns={"check": "Check", "result": "Result", "implication": "Implication"}), hide_index=True, width="stretch")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Filter attrition** (raw file → analysis population)")
    at = store.attrition()
    at = at[at.state == ctx.state][["step", "rows"]].rename(columns={"step": "Step", "rows": "Rows"})
    st.dataframe(at, hide_index=True, width="stretch", column_config={"Rows": st.column_config.NumberColumn(format="%d")})
with c2:
    st.markdown("**What is recorded, by outcome** (% of applications with the field filled in)")
    av = ctx.availability.copy()
    av["outcome"] = av.outcome.map(store.OUTCOME_LABEL)
    st.dataframe(av.rename(columns={"outcome": "Outcome", "apps": "Applications", "income_pct": "Income", "property_value_pct": "Property value", "cltv_pct": "CLTV",
                                    "dti_pct": "DTI", "rate_pct": "Rate", "costs_pct": "Costs"}), hide_index=True, width="stretch")
    st.caption("Blank-by-rule fields for withdrawn and incomplete files are why DTI, CLTV and AUS are not used to explain walk-aways.")

st.subheader("Reproduce it")
st.code("""pip install -r requirements-build.txt
python clean.py            # raw HMDA CSVs (raw_data/<ST>_2024.csv) -> hmda_clean.parquet
python fetch_lender_names.py   # LEI -> legal name via the public GLEIF registry
python prep_geo.py         # county names + map shapes
python build_data.py       # per-state tables + assertions (fails if any check disagrees)
python build_ml.py         # out-of-lender gradient-boosted case-mix model
python build_transfer.py   # train on Maryland, test on the other five states
streamlit run app.py""", language="bash")
st.caption("Source: FFIEC HMDA Data Browser, 2024 LAR. Lender names: GLEIF. Built with DuckDB, scikit-learn, Plotly and Streamlit. "
           "Descriptive analysis only; no claim about any lender's practices.")
