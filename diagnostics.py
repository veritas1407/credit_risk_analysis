import duckdb

con = duckdb.connect()

con.execute("""
    CREATE VIEW lar AS
    SELECT *
    FROM read_parquet('hmda_clean.parquet')
""")

# Q2 -- one row per lender (>= 200 apps) with gaps vs Maryland average
con.execute("""
CREATE VIEW lender_scorecard AS
with lender_stats as (
select
    lei,Count(*) as apps,

    round(100.0*avg(walked_away),1) as walkaway_pct,

    round(100.0*count(*) Filter(where outcome ='lender_denied')/count(*),1) as denial_pct,

    round(100.0*count(*) Filter(where purpose_label= 'purchase')/count(*),1) as purchase_share

from lar
group by lei
having count(*) >= 200
)

,state as (
select

    round(100.0*avg(walked_away),1) as state_wa_pct,

    round(100.0*count(*) Filter(where outcome ='lender_denied')/count(*),1) as state_den_pct

from lar
)
select
    l.lei,
    l.apps,
    l.walkaway_pct,
    l.denial_pct,
    l.purchase_share,
    ROUND(l.walkaway_pct - s.state_wa_pct, 1) AS wa_gap_pp,
    ROUND(l.denial_pct - s.state_den_pct, 1)  AS den_gap_pp
FROM lender_stats l
cross join state s
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

# Q4 -- mix-adjusted walk-away + denial, saved as a view
con.execute("""
CREATE VIEW lender_oe AS



with seg_rate as(
select 
        purpose_label,
        loan_type,
        avg(walked_away) as seg_wa,
        avg(case when outcome ='lender_denied' then 1 else 0 end) as seg_den,
        count(*) as seg_apps

from lar
group by purpose_label,loan_type


)
,app_expected as (

select a.lei , a.walked_away,case when a.outcome = 'lender_denied' then 1 else 0 end as is_denied,s.seg_wa,s.seg_den
from lar a
join seg_rate s

on a.purpose_label = s.purpose_label
and a.loan_type = s.loan_type
)
,lender_oe as (
select lei,
        count(*) as apps,
        round(100.0*avg(walked_away),1) as wa_actual,
        round(100.0*avg(seg_wa),1) as wa_expected,
        round(avg(walked_away) / avg(seg_wa), 2)       as wa_oe,
        round(100.0 * avg(is_denied), 1)                 as den_actual,
        round(100.0 * avg(seg_den), 1)                 as den_expected,
        round(avg(is_denied) / avg(seg_den), 2)             as den_oe

from app_expected
group by lei
having count(*) >= 200
)
select * from lender_oe




""")

query = ("""

select a.lei , a.apps, a.wa_oe,a.den_oe
from lender_oe a
where not exists(
    select 1
    from lender_oe b
    where a.wa_oe >= b.wa_oe
    and   a.den_oe >= b.den_oe
    and  (b.wa_oe < a.wa_oe OR b.den_oe < a.den_oe)
)
order by a.wa_oe







 """
         
         )






print(con.execute(query).df().to_string(index=False))




con.close()