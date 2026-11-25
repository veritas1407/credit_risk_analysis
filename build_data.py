"""
build_data.py: hmda_clean.parquet -> small CSV tables that the Streamlit app reads.

The SQL for the lender views mirrors diagnostics.py (lender_scorecard, lender_oe).
The frontier queries are NOT EXISTS (Pareto dominance), run on raw and mix-adjusted rates.

Output (data/):
    outcomes_by_purpose.csv   outcome counts per loan purpose
    segments.csv              loan_type x channel funnel
    info_availability.csv     % of fields recorded, by outcome
    income_bands.csv          5 income bands, walk-away / denial
    lenders.csv               one row per lender (>= 200 apps): rates, O/E, frontier flags, name

Run:  python build_data.py
"""

import os

import duckdb

os.makedirs("data", exist_ok=True)
con = duckdb.connect()

con.execute("CREATE VIEW lar AS SELECT * FROM read_parquet('hmda_clean.parquet')")

# ---- lender views (same logic as diagnostics.py) -------------------------------
con.execute("""
CREATE VIEW lender_scorecard AS
WITH lender_stats AS (
    SELECT lei,
           COUNT(*) AS apps,
           ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE purpose_label = 'purchase') / COUNT(*), 1) AS purchase_share
    FROM lar
    GROUP BY lei
    HAVING COUNT(*) >= 200
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

con.execute("""
CREATE VIEW lender_oe AS
WITH seg_rate AS (
    SELECT purpose_label, loan_type,
           AVG(walked_away) AS seg_wa,
           AVG(CASE WHEN outcome = 'lender_denied' THEN 1 ELSE 0 END) AS seg_den
    FROM lar
    GROUP BY purpose_label, loan_type
),
app_expected AS (
    SELECT a.lei, a.walked_away,
           CASE WHEN a.outcome = 'lender_denied' THEN 1 ELSE 0 END AS is_denied,
           s.seg_wa, s.seg_den
    FROM lar a
    JOIN seg_rate s ON a.purpose_label = s.purpose_label AND a.loan_type = s.loan_type
)
SELECT lei,
       COUNT(*) AS apps,
       ROUND(100.0 * AVG(walked_away), 1) AS wa_actual,
       ROUND(100.0 * AVG(seg_wa), 1)      AS wa_expected,
       ROUND(AVG(walked_away) / AVG(seg_wa), 2) AS wa_oe,
       ROUND(100.0 * AVG(is_denied), 1)   AS den_actual,
       ROUND(100.0 * AVG(seg_den), 1)     AS den_expected,
       ROUND(AVG(is_denied) / AVG(seg_den), 2) AS den_oe
FROM app_expected
GROUP BY lei
HAVING COUNT(*) >= 200
""")


# ---- Pareto frontier: no other lender is <= on both measures and < on one --------
def frontier(view, x, y):
    return f"""
    SELECT a.lei FROM {view} a
    WHERE NOT EXISTS (
        SELECT 1 FROM {view} b
        WHERE b.{x} <= a.{x} AND b.{y} <= a.{y}
          AND (b.{x} < a.{x} OR b.{y} < a.{y})
    )"""


con.execute(f"CREATE VIEW frontier_raw AS {frontier('lender_scorecard', 'walkaway_pct', 'denial_pct')}")
con.execute(f"CREATE VIEW frontier_adj AS {frontier('lender_oe', 'wa_oe', 'den_oe')}")

con.execute("CREATE TABLE names AS SELECT * FROM read_csv_auto('data/lender_names.csv')")

lenders = con.execute("""
SELECT s.lei,
       COALESCE(n.name, s.lei) AS name,
       s.apps, s.walkaway_pct, s.denial_pct, s.purchase_share, s.wa_gap_pp, s.den_gap_pp,
       o.wa_actual, o.wa_expected, o.wa_oe, o.den_actual, o.den_expected, o.den_oe,
       ROUND(s.apps * (o.wa_actual - o.wa_expected) / 100.0) AS excess_walkaways,
       (fr.lei IS NOT NULL) AS on_raw_frontier,
       (fa.lei IS NOT NULL) AS on_adj_frontier
FROM lender_scorecard s
JOIN lender_oe o USING (lei)
LEFT JOIN names n USING (lei)
LEFT JOIN frontier_raw fr USING (lei)
LEFT JOIN frontier_adj fa USING (lei)
ORDER BY s.apps DESC
""").df()
lenders.to_csv("data/lenders.csv", index=False)

# ---- funnel tables -----------------------------------------------------------------
con.execute("""
COPY (
    SELECT purpose_label, outcome, COUNT(*) AS apps
    FROM lar GROUP BY ALL ORDER BY 1, 3 DESC
) TO 'data/outcomes_by_purpose.csv' (HEADER)
""")

con.execute("""
COPY (
    SELECT loan_type, channel_label, COUNT(*) AS apps,
           ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct
    FROM lar GROUP BY ALL HAVING COUNT(*) >= 500 ORDER BY walkaway_pct DESC
) TO 'data/segments.csv' (HEADER)
""")

con.execute("""
COPY (
    SELECT outcome, COUNT(*) AS apps,
           ROUND(100.0 * COUNT(income) / COUNT(*), 1)           AS income_pct,
           ROUND(100.0 * COUNT(cltv) / COUNT(*), 1)             AS cltv_pct,
           ROUND(100.0 * COUNT(dti_num) / COUNT(*), 1)          AS dti_pct,
           ROUND(100.0 * COUNT(interest_rate) / COUNT(*), 1)    AS rate_pct,
           ROUND(100.0 * COUNT(total_loan_costs) / COUNT(*), 1) AS costs_pct
    FROM lar GROUP BY outcome ORDER BY apps DESC
) TO 'data/info_availability.csv' (HEADER)
""")

con.execute("""
COPY (
    SELECT band, MIN(income) AS min_income_k, MAX(income) AS max_income_k, COUNT(*) AS apps,
           ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct
    FROM (SELECT *, NTILE(5) OVER (ORDER BY income) AS band FROM lar WHERE income > 0)
    GROUP BY band ORDER BY band
) TO 'data/income_bands.csv' (HEADER)
""")

print(f"lenders: {len(lenders)} | raw frontier: {int(lenders.on_raw_frontier.sum())} | "
      f"adjusted frontier: {int(lenders.on_adj_frontier.sum())}")
print(lenders.loc[lenders.on_raw_frontier | lenders.on_adj_frontier,
                  ["name", "apps", "walkaway_pct", "denial_pct", "purchase_share", "wa_oe", "den_oe",
                   "on_raw_frontier", "on_adj_frontier"]].to_string(index=False))
