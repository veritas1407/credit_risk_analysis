import duckdb

con = duckdb.connect()

con.execute("""
    CREATE VIEW lar AS
    SELECT *
    FROM read_parquet('hmda_clean.parquet')
""")

###
query = """

SELECT 
    outcome ,count(*) as Applications,
    Round( 100.0 *count(*)/ sum (count(*)) over(),1 ) as percentage

from lar
group by outcome 
order by applications desc

"""

query = """

select outcome , count(*) as Applications,

ROUND(100.0 * COUNT(income) / COUNT(*), 1) AS income_pct,
    ROUND(100.0 * COUNT(cltv) / COUNT(*), 1) AS cltv_pct,
    ROUND(100.0 * COUNT(dti_num) / COUNT(*), 1) AS dti_pct,
    ROUND(100.0 * COUNT(interest_rate) / COUNT(*), 1) AS rate_pct,
    ROUND(100.0 * COUNT(rate_spread) / COUNT(*), 1) AS spread_pct,
    ROUND(100.0 * COUNT(total_loan_costs) / COUNT(*), 1) AS costs_pct,
    ROUND(100.0 * COUNT(discount_points) / COUNT(*), 1) AS points_pct

FROM lar
GROUP BY outcome
ORDER BY applications DESC
"""

query = """
SELECT
    purpose_label,
    outcome,
    COUNT(*) AS applications,

    ROUND(
        100.0 * COUNT(dti_num) / COUNT(*),
        1
    ) AS dti_present_pct

FROM lar
GROUP BY purpose_label, outcome
ORDER BY purpose_label, applications DESC
"""
###

query = """
WITH loan_bins AS (
    SELECT
        *,
        NTILE(4) OVER (
            PARTITION BY purpose_label
            ORDER BY loan_amount
        ) AS loan_amount_quartile
    FROM lar
    WHERE channel_label IN ('direct', 'indirect')
      AND loan_amount IS NOT NULL
)
SELECT
    purpose_label,
    loan_amount_quartile,
    channel_label,
    COUNT(*) AS applications,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE outcome = 'originated'
        ) / COUNT(*),
        1
    ) AS originated_pct
FROM loan_bins
GROUP BY
    purpose_label,
    loan_amount_quartile,
    channel_label
HAVING COUNT(*) >= 300
ORDER BY
    purpose_label,
    loan_amount_quartile,
    channel_label
"""

print(con.execute(query).df().to_string(index=False))




con.close()