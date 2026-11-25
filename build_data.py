"""
build_data.py: hmda_clean.parquet -> small CSV tables that the Streamlit app and memo read.

Sections
    1. Funnel            outcomes, leak components by segment, income bands, loan size x channel
    2. Lenders           scorecard, mix-adjusted O/E (+ z-scores), income-adjusted O/E, Pareto frontiers
    3. Pricing           originated conventional purchase loans, lender medians, frontier vs rest
    4. Denials           reasons by purpose / loan type, DTI vs denial rate
    5. Geography         county rates, county mix-adjusted O/E, top lender per county
    6. Opportunity       assumptions derived from the data
    7. Data quality      checks and what they imply
    8. Verification      independent re-computation of key numbers (the script fails if they disagree)

Run:  python build_data.py        (needs data/lender_names.csv from fetch_lender_names.py)
"""

import os

import duckdb
import numpy as np
import pandas as pd

os.makedirs("data", exist_ok=True)
con = duckdb.connect()
con.execute("CREATE VIEW lar AS SELECT * FROM read_parquet('hmda_clean.parquet')")


def save(df: pd.DataFrame, name: str) -> pd.DataFrame:
    df.to_csv(f"data/{name}.csv", index=False)
    return df


def q(sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


TOTAL = int(q("SELECT COUNT(*) n FROM lar").n[0])

# ================================================================== 1. FUNNEL
save(
    q("SELECT purpose_label, outcome, COUNT(*) AS apps FROM lar GROUP BY ALL ORDER BY 1, 3 DESC"),
    "outcomes_by_purpose",
)

save(
    q("""
    SELECT loan_type, channel_label, COUNT(*) AS apps,
           ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct
    FROM lar GROUP BY ALL HAVING COUNT(*) >= 500 ORDER BY walkaway_pct DESC
    """),
    "segments",
)

# where applicants leak, by purpose x channel (the heart of the product story)
leak = save(
    q("""
    SELECT purpose_label, channel_label, COUNT(*) AS apps,
           COUNT(*) FILTER (WHERE outcome = 'originated')         AS originated,
           COUNT(*) FILTER (WHERE outcome = 'lender_denied')      AS denied,
           COUNT(*) FILTER (WHERE outcome = 'customer_withdrew')  AS withdrew,
           COUNT(*) FILTER (WHERE outcome = 'stalled_incomplete') AS incomplete,
           COUNT(*) FILTER (WHERE outcome = 'customer_declined')  AS declined
    FROM lar WHERE channel_label IN ('direct', 'indirect')
    GROUP BY ALL ORDER BY 1, 2
    """),
    "leak_by_segment",
)

save(
    q("""
    SELECT outcome, COUNT(*) AS apps,
           ROUND(100.0 * COUNT(income) / COUNT(*), 1)           AS income_pct,
           ROUND(100.0 * COUNT(property_value) / COUNT(*), 1)   AS property_value_pct,
           ROUND(100.0 * COUNT(cltv) / COUNT(*), 1)             AS cltv_pct,
           ROUND(100.0 * COUNT(dti_num) / COUNT(*), 1)          AS dti_pct,
           ROUND(100.0 * COUNT(interest_rate) / COUNT(*), 1)    AS rate_pct,
           ROUND(100.0 * COUNT(total_loan_costs) / COUNT(*), 1) AS costs_pct
    FROM lar GROUP BY outcome ORDER BY apps DESC
    """),
    "info_availability",
)

save(
    q("""
    SELECT band, MIN(income) AS min_income_k, MAX(income) AS max_income_k, COUNT(*) AS apps,
           ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct
    FROM (SELECT *, NTILE(5) OVER (ORDER BY income) AS band FROM lar WHERE income > 0)
    GROUP BY band ORDER BY band
    """),
    "income_bands",
)

save(
    q("""
    WITH b AS (
        SELECT *, NTILE(4) OVER (PARTITION BY purpose_label ORDER BY loan_amount) AS size_quartile
        FROM lar WHERE channel_label IN ('direct', 'indirect') AND loan_amount IS NOT NULL
    )
    SELECT purpose_label, size_quartile, channel_label, COUNT(*) AS apps,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'originated') / COUNT(*), 1) AS originated_pct,
           ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct
    FROM b GROUP BY ALL ORDER BY 1, 2, 3
    """),
    "size_channel",
)

# ================================================================== 2. LENDERS
con.execute("""
CREATE VIEW lender_scorecard AS
WITH lender_stats AS (
    SELECT lei, COUNT(*) AS apps,
           ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE purpose_label = 'purchase') / COUNT(*), 1) AS purchase_share
    FROM lar GROUP BY lei HAVING COUNT(*) >= 200
),
state AS (
    SELECT ROUND(100.0 * AVG(walked_away), 1) AS state_wa_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS state_den_pct
    FROM lar
)
SELECT l.lei, l.apps, l.walkaway_pct, l.denial_pct, l.purchase_share,
       ROUND(l.walkaway_pct - s.state_wa_pct, 1) AS wa_gap_pp,
       ROUND(l.denial_pct - s.state_den_pct, 1)  AS den_gap_pp
FROM lender_stats l CROSS JOIN state s
""")

# income band for every application: 0 = unknown / non-positive, 1-5 = quintile of positive income
con.execute("""
CREATE VIEW lar_inc AS
SELECT *,
       CASE WHEN income > 0
            THEN NTILE(5) OVER (PARTITION BY COALESCE(income > 0, FALSE) ORDER BY income)
            ELSE 0 END AS inc_band
FROM lar
""")


def oe_view(name: str, seg_cols: str, source: str) -> None:
    """Indirect standardization: expected rate = mean of the statewide rate for each application's segment."""
    on = " AND ".join(f"a.{c.strip()} = s.{c.strip()}" for c in seg_cols.split(","))
    con.execute(f"""
    CREATE VIEW {name} AS
    WITH seg_rate AS (
        SELECT {seg_cols},
               AVG(walked_away) AS seg_wa,
               AVG(CASE WHEN outcome = 'lender_denied' THEN 1 ELSE 0 END) AS seg_den
        FROM {source} GROUP BY {seg_cols}
    ),
    app_expected AS (
        SELECT a.lei, a.walked_away,
               CASE WHEN a.outcome = 'lender_denied' THEN 1 ELSE 0 END AS is_denied,
               s.seg_wa, s.seg_den
        FROM {source} a JOIN seg_rate s ON {on}
    )
    SELECT lei, COUNT(*) AS apps,
           ROUND(100.0 * AVG(walked_away), 1) AS wa_actual,
           ROUND(100.0 * AVG(seg_wa), 1)      AS wa_expected,
           ROUND(AVG(walked_away) / AVG(seg_wa), 2) AS wa_oe,
           ROUND(100.0 * AVG(is_denied), 1)   AS den_actual,
           ROUND(100.0 * AVG(seg_den), 1)     AS den_expected,
           ROUND(AVG(is_denied) / AVG(seg_den), 2) AS den_oe,
           SUM(walked_away)                   AS wa_obs,
           SUM(seg_wa)                        AS wa_exp,
           SUM(seg_wa * (1 - seg_wa))         AS wa_var,
           SUM(is_denied)                     AS den_obs,
           SUM(seg_den)                       AS den_exp,
           SUM(seg_den * (1 - seg_den))       AS den_var
    FROM app_expected GROUP BY lei HAVING COUNT(*) >= 200
    """)


oe_view("lender_oe", "purpose_label, loan_type", "lar")
oe_view("lender_oe_inc", "purpose_label, loan_type, inc_band", "lar_inc")


def frontier(source: str, x: str, y: str) -> set:
    """Lenders that no other lender dominates: nobody is <= on both measures and < on at least one."""
    sql = f"""
    WITH t AS ({source})
    SELECT a.lei FROM t a
    WHERE NOT EXISTS (
        SELECT 1 FROM t b
        WHERE b.{x} <= a.{x} AND b.{y} <= a.{y} AND (b.{x} < a.{x} OR b.{y} < a.{y})
    )"""
    return set(q(sql).lei)


f_raw = frontier("SELECT * FROM lender_scorecard", "walkaway_pct", "denial_pct")
f_adj = frontier("SELECT * FROM lender_oe", "wa_oe", "den_oe")
f_inc = frontier("SELECT * FROM lender_oe_inc", "wa_oe", "den_oe")
f_500 = frontier("SELECT * FROM lender_oe WHERE apps >= 500", "wa_oe", "den_oe")

names = pd.read_csv("data/lender_names.csv")
den_reason = q("""
    SELECT lei, COUNT(*) AS denials,
           ROUND(100.0 * COUNT(*) FILTER (WHERE denial_reason = '7') / COUNT(*), 1) AS den_incomplete_share
    FROM lar WHERE outcome = 'lender_denied' GROUP BY lei
""")

lenders = q("""
    SELECT s.lei, s.apps, s.walkaway_pct, s.denial_pct, s.purchase_share, s.wa_gap_pp, s.den_gap_pp,
           o.wa_actual, o.wa_expected, o.wa_oe, o.den_actual, o.den_expected, o.den_oe,
           o.wa_obs, o.wa_exp, o.wa_var, o.den_obs, o.den_exp, o.den_var,
           i.wa_oe AS wa_oe_inc, i.den_oe AS den_oe_inc
    FROM lender_scorecard s
    JOIN lender_oe o USING (lei)
    JOIN lender_oe_inc i USING (lei)
    ORDER BY s.apps DESC
""")
lenders = lenders.merge(names, on="lei", how="left").merge(den_reason, on="lei", how="left")
lenders["name"] = lenders["name"].fillna(lenders["lei"])
lenders["excess_walkaways"] = (lenders.wa_obs - lenders.wa_exp).round()
lenders["wa_z"] = ((lenders.wa_obs - lenders.wa_exp) / np.sqrt(lenders.wa_var)).round(2)
lenders["den_z"] = ((lenders.den_obs - lenders.den_exp) / np.sqrt(lenders.den_var)).round(2)
lenders["on_raw_frontier"] = lenders.lei.isin(f_raw)
lenders["on_adj_frontier"] = lenders.lei.isin(f_adj)
lenders["on_inc_frontier"] = lenders.lei.isin(f_inc)
lenders["on_500_frontier"] = lenders.lei.isin(f_500)
lenders["robust_frontier"] = lenders.on_adj_frontier & lenders.on_inc_frontier
lenders = lenders.drop(columns=["wa_var", "den_var", "wa_obs", "wa_exp", "den_obs", "den_exp"])

# ================================================================== 3. PRICING
# Pricing fields exist only for originated loans -> hold the segment fixed (conventional purchase)
price_loans = q("""
    SELECT lei, rate_spread, total_loan_costs, discount_points, interest_rate
    FROM lar WHERE outcome = 'originated' AND loan_type = '1' AND purpose_label = 'purchase'
""")
price_lender = (
    price_loans.groupby("lei")
    .agg(
        price_loans=("lei", "size"),
        med_spread=("rate_spread", "median"),
        med_costs=("total_loan_costs", "median"),
        med_points=("discount_points", "median"),
        med_rate=("interest_rate", "median"),
    )
    .reset_index()
)
price_lender = price_lender[price_lender.price_loans >= 100]
lenders = lenders.merge(price_lender, on="lei", how="left")
save(lenders.round(3), "lenders")

pl = price_loans.merge(lenders[["lei", "robust_frontier", "on_adj_frontier"]], on="lei", how="inner")
pl = pl[pl.lei.isin(price_lender.lei)]


def group_label(row):
    if row.robust_frontier:
        return "Robust frontier (adjusted and income-adjusted)"
    if row.on_adj_frontier:
        return "Adjusted frontier only"
    return "All other lenders"


pl["grp"] = pl.apply(group_label, axis=1)
price_groups = (
    pl.groupby("grp")
    .agg(
        lenders=("lei", "nunique"), loans=("lei", "size"),
        med_spread=("rate_spread", "median"), med_costs=("total_loan_costs", "median"),
        med_points=("discount_points", "median"), med_rate=("interest_rate", "median"),
    )
    .reset_index()
    .round(2)
)
save(price_groups, "pricing_groups")

pc = lenders.dropna(subset=["med_spread"])
rows = []
for xcol, xlab in [("wa_oe", "Walk-away O/E"), ("den_oe", "Denial O/E")]:
    for ycol, ylab in [("med_spread", "Median rate spread"), ("med_costs", "Median loan costs"),
                       ("med_points", "Median discount points"), ("med_rate", "Median interest rate")]:
        rows.append({"measure": xlab, "price": ylab, "spearman": round(pc[xcol].rank().corr(pc[ycol].rank()), 2),
                     "lenders": len(pc)})
save(pd.DataFrame(rows), "pricing_corr")

save(
    q("""
    SELECT loan_type, COUNT(*) AS loans, ROUND(MEDIAN(rate_spread), 2) AS med_spread,
           ROUND(MEDIAN(total_loan_costs)) AS med_costs, ROUND(MEDIAN(interest_rate), 2) AS med_rate
    FROM lar WHERE outcome = 'originated' AND purpose_label = 'purchase' GROUP BY 1 ORDER BY 1
    """),
    "pricing_by_loan_type",
)

# ================================================================== 4. DENIALS
REASONS = {"1": "Debt-to-income ratio", "2": "Employment history", "3": "Credit history", "4": "Collateral",
           "5": "Insufficient cash", "6": "Unverifiable information", "7": "Credit application incomplete",
           "8": "Mortgage insurance denied", "9": "Other"}
dr = q("""
    SELECT purpose_label, loan_type, COALESCE(denial_reason, 'NA') AS code, COUNT(*) AS denials
    FROM lar WHERE outcome = 'lender_denied' GROUP BY ALL
""")
dr["reason"] = dr.code.map(REASONS).fillna("Not reported")
save(dr.groupby(["purpose_label", "code", "reason"], as_index=False).denials.sum(), "denial_reasons_purpose")
save(dr.groupby(["loan_type", "code", "reason"], as_index=False).denials.sum(), "denial_reasons_loantype")

# among applications that reached a decision (originated or denied) with a recorded DTI
save(
    q("""
    WITH d AS (
        SELECT CASE WHEN dti_num < 20 THEN '1: <20'  WHEN dti_num < 30 THEN '2: 20-29'
                    WHEN dti_num < 36 THEN '3: 30-35' WHEN dti_num < 43 THEN '4: 36-42'
                    WHEN dti_num < 50 THEN '5: 43-49' WHEN dti_num <= 60 THEN '6: 50-60'
                    ELSE '7: >60' END AS dti_band,
               outcome, loan_type
        FROM lar WHERE dti_num IS NOT NULL AND outcome IN ('originated', 'lender_denied')
    )
    SELECT dti_band, COUNT(*) AS decided,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_rate_pct
    FROM d GROUP BY 1 ORDER BY 1
    """),
    "dti_denial",
)

# ================================================================== 5. GEOGRAPHY
COUNTIES = {
    "24001": "Allegany", "24003": "Anne Arundel", "24005": "Baltimore County", "24009": "Calvert",
    "24011": "Caroline", "24013": "Carroll", "24015": "Cecil", "24017": "Charles", "24019": "Dorchester",
    "24021": "Frederick", "24023": "Garrett", "24025": "Harford", "24027": "Howard", "24029": "Kent",
    "24031": "Montgomery", "24033": "Prince George's", "24035": "Queen Anne's", "24037": "St. Mary's",
    "24039": "Somerset", "24041": "Talbot", "24043": "Washington", "24045": "Wicomico", "24047": "Worcester",
    "24510": "Baltimore City",
}
county = q("""
    WITH seg AS (
        SELECT purpose_label, loan_type, AVG(walked_away) AS seg_wa,
               AVG(CASE WHEN outcome = 'lender_denied' THEN 1 ELSE 0 END) AS seg_den
        FROM lar GROUP BY ALL
    )
    SELECT l.county_code, COUNT(*) AS apps,
           ROUND(100.0 * AVG(l.walked_away), 1) AS walkaway_pct,
           ROUND(100.0 * AVG(CASE WHEN l.outcome = 'lender_denied' THEN 1 ELSE 0 END), 1) AS denial_pct,
           ROUND(100.0 * AVG(s.seg_wa), 1) AS wa_expected,
           ROUND(100.0 * AVG(s.seg_den), 1) AS den_expected,
           ROUND(AVG(l.walked_away) / AVG(s.seg_wa), 2) AS wa_oe,
           ROUND(AVG(CASE WHEN l.outcome = 'lender_denied' THEN 1 ELSE 0 END) / AVG(s.seg_den), 2) AS den_oe,
           ROUND(100.0 * COUNT(*) FILTER (WHERE l.purpose_label = 'purchase') / COUNT(*), 1) AS purchase_share
    FROM lar l JOIN seg s USING (purpose_label, loan_type)
    GROUP BY l.county_code ORDER BY apps DESC
""")
top = q("""
    WITH cl AS (SELECT county_code, lei, COUNT(*) AS n FROM lar GROUP BY ALL),
         ct AS (SELECT county_code, SUM(n) AS tot FROM cl GROUP BY 1)
    SELECT cl.county_code, cl.lei AS top_lei, cl.n AS top_apps, ROUND(100.0 * cl.n / ct.tot, 1) AS top_share_pct
    FROM cl JOIN ct USING (county_code)
    WHERE cl.n = (SELECT MAX(n) FROM cl c2 WHERE c2.county_code = cl.county_code)
""").drop_duplicates("county_code")
county = county.merge(top, on="county_code", how="left").merge(
    names.rename(columns={"lei": "top_lei", "name": "top_lender"}), on="top_lei", how="left")
county["county"] = county.county_code.map(COUNTIES).fillna("County not reported")
county["noisy"] = county.apps < 1000
save(county, "counties")

# ================================================================== 6. OPPORTUNITY INPUTS
by_outcome = q("SELECT outcome, COUNT(*) AS n FROM lar GROUP BY 1").set_index("outcome").n
approval_given_stay = by_outcome["originated"] / (by_outcome["originated"] + by_outcome["lender_denied"])
costs = q("""
    SELECT purpose_label, ROUND(MEDIAN(total_loan_costs)) AS med_costs, ROUND(MEDIAN(loan_amount)) AS med_loan
    FROM lar WHERE outcome = 'originated' GROUP BY 1
""")
assump = [("approval_given_stay", round(float(approval_given_stay), 4),
           "originated / (originated + denied): share of files that stay to a decision and are funded")]
for _, r in costs.iterrows():
    assump.append((f"med_costs_{r.purpose_label}", float(r.med_costs), "median borrower-paid total loan costs, originated loans"))
    assump.append((f"med_loan_{r.purpose_label}", float(r.med_loan), "median loan amount, originated loans"))
assump.append(("med_loan_all", float(q("SELECT MEDIAN(loan_amount) m FROM lar WHERE outcome = 'originated'").m[0]),
               "median loan amount, all originated loans"))
assumptions_df = save(pd.DataFrame(assump, columns=["key", "value", "note"]), "assumptions")

# ================================================================== 7. DATA QUALITY
dq = []
def add(check, result, implication):
    dq.append({"check": check, "result": result, "implication": implication})

n_apps = TOTAL
add("Scope", f"{n_apps:,} applications after filtering 235,625 raw rows (attrition.csv)",
    "First-lien, owner-occupied, site-built 1-4 unit; purchase / refinance / cash-out refi only.")
inc_bad = q("SELECT COUNT(*) FILTER (WHERE income IS NULL) n, COUNT(*) FILTER (WHERE income <= 0) z, COUNT(*) FILTER (WHERE income > 2000) hi FROM lar").iloc[0]
add("Income missing / non-positive / above $2M", f"{inc_bad.n:,} / {inc_bad.z:,} / {inc_bad.hi:,}",
    "Excluded from income bands (and set to band 0 in the income-adjusted check). Income is in $000s.")
miss = q("""SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE dti_num IS NULL) / COUNT(*), 1) AS dti_na
            FROM lar WHERE outcome IN ('customer_withdrew', 'stalled_incomplete')""").iloc[0, 0]
add("DTI, CLTV, property value for withdrawn / incomplete files", f"DTI missing for {miss}% (also 100% for CLTV and property value)",
    "HMDA blank-by-rule: a 'reached_underwriting' flag built from these fields is circular, so it is not used.")
aus6 = q("""SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE aus = '6') / COUNT(*), 1) FROM lar WHERE outcome = 'customer_withdrew'""").iloc[0, 0]
add("Automated underwriting system = 'not applicable'", f"{aus6}% of withdrawn files; 43% walk-away rate for that group",
    "AUS code is a result of the funnel stage, not a cause of abandonment: not used as a driver.")
pre = q("""SELECT COUNT(*) FILTER (WHERE preapproval = '1') n,
                  COUNT(*) FILTER (WHERE preapproval = '1' AND outcome = 'lender_denied') d FROM lar""").iloc[0]
add("Pre-approval requested", f"{pre.n:,} files, {pre.d} lender denials",
    "Denied pre-approval requests are a separate HMDA action outside the scope, so pre-approved files look unrealistically good: not used.")
dup = q("""SELECT COUNT(*) - COUNT(DISTINCT (lei, county_code, loan_amount, income, property_value, action_taken, interest_rate)) FROM lar""").iloc[0, 0]
add("Possible duplicate rows (same lender, county, amount, income, value, action, rate)", f"{dup:,}",
    "HMDA has no application ID, so these cannot be separated from genuine near-identical applications. Kept.")
cov = lenders.apps.sum() / TOTAL
add("Lenders with 200+ applications", f"{len(lenders)} of 615 lenders cover {cov:.1%} of applications",
    "Smaller lenders are excluded from lender comparisons (their rates are too noisy).")
add("Pricing fields", "Present only for originated loans (rate also for approved-not-accepted)",
    "Pricing comparisons use one fixed segment (conventional purchase) and carry survivorship bias.")
add("Unit of analysis", "Application, not borrower", "HMDA has no applicant id, so repeat applicants cannot be linked.")
save(pd.DataFrame(dq), "data_quality")

# ================================================================== 8. VERIFICATION
oc = pd.read_csv("data/outcomes_by_purpose.csv")
assert oc.apps.sum() == TOTAL == 118431, "outcome table does not add up to 118,431"
assert len(lenders) == 111, f"expected 111 lenders, got {len(lenders)}"
all_oe = q("""
    WITH seg AS (SELECT purpose_label, loan_type, AVG(walked_away) AS r FROM lar GROUP BY ALL)
    SELECT SUM(walked_away) / SUM(r) AS ratio FROM lar JOIN seg USING (purpose_label, loan_type)
""").ratio[0]
assert abs(all_oe - 1) < 1e-9, "state-wide walk-away O/E must be exactly 1"


def brute_frontier(df, x, y):
    out = set()
    for _, a in df.iterrows():
        dominated = ((df[x] <= a[x]) & (df[y] <= a[y]) & ((df[x] < a[x]) | (df[y] < a[y]))).any()
        if not dominated:
            out.add(a.lei)
    return out

assert brute_frontier(lenders, "walkaway_pct", "denial_pct") == f_raw, "raw frontier mismatch"
assert brute_frontier(lenders, "wa_oe", "den_oe") == f_adj, "adjusted frontier mismatch"
assert brute_frontier(lenders, "wa_oe_inc", "den_oe_inc") == f_inc, "income-adjusted frontier mismatch"
assert len(set(oc.purpose_label)) == 3
assert county.apps.sum() == TOTAL
import calc
calc.selfcheck(leak, assumptions_df, lenders)

# ================================================================== SUMMARY
print(f"applications {TOTAL:,} | lenders {len(lenders)}")
print(f"frontiers: raw {len(f_raw)}, adjusted {len(f_adj)}, income-adjusted {len(f_inc)}, adjusted min-500 {len(f_500)}")
print(f"adjusted frontier members still on income-adjusted frontier: {len(f_adj & f_inc)} of {len(f_adj)}")
print(f"adjusted & raw overlap: {len(f_adj & f_raw)}; adjusted & min-500 overlap: {len(f_adj & f_500)}")
print("all assertions passed")
