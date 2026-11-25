"""
build_data.py: hmda_clean.parquet -> small CSV tables per state (data/<ST>/*.csv) + a six-state summary (data/states.csv).

For every state:
    1. Funnel       outcomes, leak components by segment, income bands, loan size x channel, explorer grid
    2. Lenders      scorecard, mix-adjusted O/E (+ z-scores, empirical-Bayes shrinkage), income-adjusted O/E, Pareto frontiers
    3. Pricing      originated conventional purchase loans, lender medians, frontier vs rest
    4. Denials      reasons by purpose / loan type, DTI vs denial rate
    5. Geography    county rates, county mix-adjusted O/E, top lender per county
    6. Opportunity  assumptions derived from the data
    7. Data quality checks and what they imply
    8. Verification independent re-computation of key numbers (the script fails if they disagree)

Run:  python build_data.py            all six states
      python build_data.py MD VA      selected states
Needs data/lender_names.csv (fetch_lender_names.py) and data/county_names.csv (prep_geo.py).
ML case-mix model is a separate step: python build_ml.py
"""

import os
import sys

import duckdb
import numpy as np
import pandas as pd

import calc

ALL_STATES = ["MD", "VA", "PA", "DE", "DC", "WV"]
STATES = [s.upper() for s in sys.argv[1:]] or ALL_STATES
NAMES = pd.read_csv("data/lender_names.csv")
COUNTY_NAMES = pd.read_csv("data/county_names.csv", dtype=str).set_index("fips").county.to_dict()
ATTRITION = pd.read_csv("attrition.csv")

REASONS = {"1": "Debt-to-income ratio", "2": "Employment history", "3": "Credit history", "4": "Collateral",
           "5": "Insufficient cash", "6": "Unverifiable information", "7": "Credit application incomplete",
           "8": "Mortgage insurance denied", "9": "Other"}

# Known-good Maryland numbers from the first (Maryland-only) version of this project: guards against regressions.
MD_SNAPSHOT = {"total": 118431, "lenders": 111, "raw": 7, "adj": 7, "inc": 7, "min500": 6, "adj_and_inc": 5,
               "adj_and_raw": 4, "sig_worse": 36, "sig_better": 44}


def build(state: str) -> dict:
    out = f"data/{state}"
    os.makedirs(out, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW lar AS SELECT * FROM read_parquet('hmda_clean.parquet') WHERE state = '{state}'")

    def save(df: pd.DataFrame, name: str) -> pd.DataFrame:
        df.to_csv(f"{out}/{name}.csv", index=False)
        return df

    def q(sql: str) -> pd.DataFrame:
        return con.execute(sql).df()

    TOTAL = int(q("SELECT COUNT(*) n FROM lar").n[0])
    summary: dict = {"state": state, "apps": TOTAL}

    # ============================================================== 1. FUNNEL
    by_purpose = save(
        q("SELECT purpose_label, outcome, COUNT(*) AS apps FROM lar GROUP BY ALL ORDER BY 1, 3 DESC"),
        "outcomes_by_purpose",
    )
    by_outcome = by_purpose.groupby("outcome").apps.sum()
    summary |= {
        "orig_pct": 100 * by_outcome.get("originated", 0) / TOTAL,
        "walk_pct": 100 * by_outcome[["customer_withdrew", "stalled_incomplete", "customer_declined"]].sum() / TOTAL,
        "den_pct": 100 * by_outcome.get("lender_denied", 0) / TOTAL,
        "incomplete_pct": 100 * by_outcome.get("stalled_incomplete", 0) / TOTAL,
    }

    save(
        q("""
        SELECT loan_type, channel_label, COUNT(*) AS apps,
               ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
               ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct
        FROM lar GROUP BY ALL HAVING COUNT(*) >= 500 ORDER BY walkaway_pct DESC
        """),
        "segments",
    )

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

    def inc_rate(purposes, channel):
        d = leak[leak.purpose_label.isin(purposes) & (leak.channel_label == channel)]
        return (d.incomplete.sum() / d.apps.sum() * 100) if d.apps.sum() else np.nan

    refi = ["refinance", "cash_out_refi"]
    dir_refi = leak[leak.purpose_label.isin(refi) & (leak.channel_label == "direct")]
    summary |= {
        "dir_refi_apps": int(dir_refi.apps.sum()),
        "dir_refi_inc_pct": inc_rate(refi, "direct"),
        "ind_refi_apps": int(leak[leak.purpose_label.isin(refi) & (leak.channel_label == "indirect")].apps.sum()),
        "ind_refi_inc_pct": inc_rate(refi, "indirect"),
        "dir_purch_inc_pct": inc_rate(["purchase"], "direct"),
        "share_of_stalled_dir_refi": 100 * dir_refi.incomplete.sum() / max(by_outcome.get("stalled_incomplete", 1), 1),
    }

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

    income = save(
        q("""
        SELECT band, MIN(income) AS min_income_k, MAX(income) AS max_income_k, COUNT(*) AS apps,
               ROUND(100.0 * AVG(walked_away), 1) AS walkaway_pct,
               ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'lender_denied') / COUNT(*), 1) AS denial_pct
        FROM (SELECT *, NTILE(5) OVER (ORDER BY income) AS band FROM lar WHERE income > 0)
        GROUP BY band ORDER BY band
        """),
        "income_bands",
    )
    summary |= {
        "wa_q1": income.walkaway_pct.iloc[0], "wa_q5": income.walkaway_pct.iloc[-1],
        "den_q1": income.denial_pct.iloc[0], "den_q5": income.denial_pct.iloc[-1],
        "wa_band_range": income.walkaway_pct.max() - income.walkaway_pct.min(),
    }

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

    # one row per cell of the interactive explorer: purpose x loan type x channel x income quintile x loan-size quartile
    con.execute("""
    CREATE VIEW lar_inc AS
    SELECT *,
           CASE WHEN income > 0
                THEN NTILE(5) OVER (PARTITION BY COALESCE(income > 0, FALSE) ORDER BY income)
                ELSE 0 END AS inc_band
    FROM lar
    """)
    explorer = save(
        q("""
        WITH b AS (
            SELECT *, COALESCE(NTILE(4) OVER (PARTITION BY purpose_label ORDER BY loan_amount), 0) AS size_band
            FROM lar_inc
        )
        SELECT purpose_label, loan_type, COALESCE(channel_label, 'other') AS channel, inc_band, size_band,
               COUNT(*) AS apps,
               COUNT(*) FILTER (WHERE outcome = 'originated')         AS originated,
               COUNT(*) FILTER (WHERE outcome = 'lender_denied')      AS denied,
               COUNT(*) FILTER (WHERE outcome = 'customer_withdrew')  AS withdrew,
               COUNT(*) FILTER (WHERE outcome = 'stalled_incomplete') AS incomplete,
               COUNT(*) FILTER (WHERE outcome = 'customer_declined')  AS declined
        FROM b GROUP BY ALL ORDER BY ALL
        """),
        "explorer",
    )

    # ============================================================== 2. LENDERS
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

    den_reason = q("""
        SELECT lei, COUNT(*) AS denials,
               ROUND(100.0 * COUNT(*) FILTER (WHERE denial_reason = '7') / COUNT(*), 1) AS den_incomplete_share
        FROM lar WHERE outcome = 'lender_denied' GROUP BY lei
    """)
    direct_share = q("""
        SELECT lei, ROUND(100.0 * COUNT(*) FILTER (WHERE channel_label = 'direct') / COUNT(*), 1) AS direct_share
        FROM lar GROUP BY lei
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
    lenders = lenders.merge(NAMES, on="lei", how="left").merge(den_reason, on="lei", how="left")
    lenders = lenders.merge(direct_share, on="lei", how="left")
    lenders["name"] = lenders["name"].fillna(lenders["lei"])
    lenders["excess_walkaways"] = (lenders.wa_obs - lenders.wa_exp).round()
    lenders["wa_z"] = ((lenders.wa_obs - lenders.wa_exp) / np.sqrt(lenders.wa_var)).round(2)
    lenders["den_z"] = ((lenders.den_obs - lenders.den_exp) / np.sqrt(lenders.den_var)).round(2)
    # 95% limits for walk-away O/E if the lender were exactly as expected (funnel-plot control limits)
    lenders["wa_lo"] = ((lenders.wa_exp - 1.96 * np.sqrt(lenders.wa_var)) / lenders.wa_exp).round(3)
    lenders["wa_hi"] = ((lenders.wa_exp + 1.96 * np.sqrt(lenders.wa_var)) / lenders.wa_exp).round(3)

    # empirical-Bayes shrinkage (DerSimonian-Laird): how much of the spread in O/E is real, not chance?
    eb = calc.eb_shrink(lenders.wa_obs, lenders.wa_exp, lenders.wa_var)
    y_i, ybar = eb["y"], eb["ybar"]
    lenders["wa_oe_eb"] = eb["shrunk"].round(3)
    lenders["shrink_weight"] = eb["weight"].round(3)
    summary |= {"tau": eb["tau"], "Q_ratio": eb["Q_ratio"], "ybar": ybar}

    lenders["on_raw_frontier"] = lenders.lei.isin(f_raw)
    lenders["on_adj_frontier"] = lenders.lei.isin(f_adj)
    lenders["on_inc_frontier"] = lenders.lei.isin(f_inc)
    lenders["on_500_frontier"] = lenders.lei.isin(f_500)
    lenders["robust_frontier"] = lenders.on_adj_frontier & lenders.on_inc_frontier

    # ============================================================== 3. PRICING
    # Pricing fields exist only for originated loans -> hold the segment fixed (conventional purchase)
    price_loans = q("""
        SELECT lei, rate_spread, total_loan_costs, discount_points, interest_rate
        FROM lar WHERE outcome = 'originated' AND loan_type = '1' AND purpose_label = 'purchase'
    """)
    price_lender = (
        price_loans.groupby("lei")
        .agg(price_loans=("lei", "size"), med_spread=("rate_spread", "median"), med_costs=("total_loan_costs", "median"),
             med_points=("discount_points", "median"), med_rate=("interest_rate", "median"))
        .reset_index()
    )
    price_lender = price_lender[price_lender.price_loans >= 100]
    lenders = lenders.merge(price_lender, on="lei", how="left")
    save(lenders.round(3), "lenders")

    pl = price_loans[price_loans.lei.isin(price_lender.lei)].merge(
        lenders[["lei", "robust_frontier", "on_adj_frontier"]], on="lei", how="inner")
    pl["grp"] = np.where(pl.robust_frontier, "Robust frontier (adjusted and income-adjusted)",
                         np.where(pl.on_adj_frontier, "Adjusted frontier only", "All other lenders"))
    price_groups = save(
        pl.groupby("grp")
        .agg(lenders=("lei", "nunique"), loans=("lei", "size"), med_spread=("rate_spread", "median"),
             med_costs=("total_loan_costs", "median"), med_points=("discount_points", "median"),
             med_rate=("interest_rate", "median"))
        .reset_index().round(2),
        "pricing_groups",
    )

    pc = lenders.dropna(subset=["med_spread"])
    rows = []
    for xcol, xlab in [("wa_oe", "Walk-away O/E"), ("den_oe", "Denial O/E")]:
        for ycol, ylab in [("med_spread", "Median rate spread"), ("med_costs", "Median loan costs"),
                           ("med_points", "Median discount points"), ("med_rate", "Median interest rate")]:
            rho = pc[xcol].rank().corr(pc[ycol].rank()) if len(pc) >= 8 else np.nan
            rows.append({"measure": xlab, "price": ylab, "spearman": round(rho, 2), "lenders": len(pc)})
    price_corr = save(pd.DataFrame(rows), "pricing_corr")
    summary |= {
        "price_lenders": len(pc),
        "price_rho_wa_spread": float(price_corr[(price_corr.measure == "Walk-away O/E") & (price_corr.price == "Median rate spread")].spearman.iloc[0]),
        "price_rho_wa_max_abs": float(price_corr[price_corr.measure == "Walk-away O/E"].spearman.abs().max()),
    }

    save(
        q("""
        SELECT loan_type, COUNT(*) AS loans, ROUND(MEDIAN(rate_spread), 2) AS med_spread,
               ROUND(MEDIAN(total_loan_costs)) AS med_costs, ROUND(MEDIAN(interest_rate), 2) AS med_rate
        FROM lar WHERE outcome = 'originated' AND purpose_label = 'purchase' GROUP BY 1 ORDER BY 1
        """),
        "pricing_by_loan_type",
    )

    # ============================================================== 4. DENIALS
    dr = q("""
        SELECT purpose_label, loan_type, COALESCE(denial_reason, 'NA') AS code, COUNT(*) AS denials
        FROM lar WHERE outcome = 'lender_denied' GROUP BY ALL
    """)
    dr["reason"] = dr.code.map(REASONS).fillna("Not reported")
    den_purpose = save(dr.groupby(["purpose_label", "code", "reason"], as_index=False).denials.sum(), "denial_reasons_purpose")
    save(dr.groupby(["loan_type", "code", "reason"], as_index=False).denials.sum(), "denial_reasons_loantype")
    tot_den = den_purpose.groupby("purpose_label").denials.sum()
    inc7 = den_purpose[den_purpose.code.astype(str) == "7"].set_index("purpose_label").denials
    summary |= {
        f"den_incomplete_share_{p}": 100 * inc7.get(p, 0) / tot_den[p] for p in ["purchase", "refinance", "cash_out_refi"]
        if p in tot_den.index
    }

    dti = save(
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
    d_ = dti.set_index("dti_band").denial_rate_pct
    summary |= {"dti_43_49": d_.get("5: 43-49", np.nan), "dti_50_60": d_.get("6: 50-60", np.nan), "dti_60p": d_.get("7: >60", np.nan)}

    # ============================================================== 5. GEOGRAPHY
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
        NAMES.rename(columns={"lei": "top_lei", "name": "top_lender"}), on="top_lei", how="left")
    county["county"] = county.county_code.map(COUNTY_NAMES).fillna("County not reported")
    county["noisy"] = county.apps < 1000
    save(county, "counties")
    cq = county[~county.noisy & (county.county_code != "NA")]
    summary |= {
        "county_wa_oe_lo": cq.wa_oe.min() if len(cq) else np.nan,
        "county_wa_oe_hi": cq.wa_oe.max() if len(cq) else np.nan,
        "counties_ge1000": len(cq),
    }

    # ============================================================== 6. OPPORTUNITY INPUTS
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
    summary["approval_given_stay"] = float(approval_given_stay)
    summary["med_loan_all"] = float(assumptions_df[assumptions_df.key == "med_loan_all"].value.iloc[0])

    # lender x purpose x outcome counts for the lender detail card
    save(
        q("""
        SELECT lei, purpose_label, outcome, COUNT(*) AS apps FROM lar
        WHERE lei IN (SELECT lei FROM lender_scorecard) GROUP BY ALL ORDER BY ALL
        """),
        "lender_outcomes",
    )

    # ============================================================== 7. DATA QUALITY
    dq = []

    def add(check, result, implication):
        dq.append({"check": check, "result": result, "implication": implication})

    raw_rows = int(ATTRITION[(ATTRITION.state == state) & (ATTRITION.step == "raw file")].rows.iloc[0])
    n_lenders_all = int(q("SELECT COUNT(DISTINCT lei) n FROM lar").n[0])
    add("Scope", f"{TOTAL:,} applications after filtering {raw_rows:,} raw rows (attrition table below)",
        "First-lien, owner-occupied, site-built 1-4 unit; purchase / refinance / cash-out refi only.")
    inc_bad = q("SELECT COUNT(*) FILTER (WHERE income IS NULL) n, COUNT(*) FILTER (WHERE income <= 0) z, "
                "COUNT(*) FILTER (WHERE income > 2000) hi FROM lar").iloc[0]
    add("Income missing / non-positive / above $2M", f"{int(inc_bad.n):,} / {int(inc_bad.z):,} / {int(inc_bad.hi):,}",
        "Excluded from income bands (and set to band 0 in the income-adjusted check). Income is in $000s.")
    miss = q("""SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE dti_num IS NULL) / COUNT(*), 1) AS dti_na
                FROM lar WHERE outcome IN ('customer_withdrew', 'stalled_incomplete')""").iloc[0, 0]
    add("DTI, CLTV, property value for withdrawn / incomplete files",
        f"DTI missing for {miss}% (also ~100% for CLTV and property value)",
        "HMDA blank-by-rule: a 'reached_underwriting' flag built from these fields is circular, so it is not used.")
    aus6 = q("""SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'customer_withdrew' AND aus = '6')
                              / NULLIF(COUNT(*) FILTER (WHERE outcome = 'customer_withdrew'), 0), 1) AS share_of_withdrawn,
                       ROUND(100.0 * AVG(walked_away) FILTER (WHERE aus = '6'), 1) AS wa_rate
                FROM lar""").iloc[0]
    add("Automated underwriting system = 'not applicable'",
        f"{aus6.share_of_withdrawn}% of withdrawn files; {aus6.wa_rate}% walk-away rate for that group",
        "AUS code is a result of the funnel stage, not a cause of abandonment: not used as a driver.")
    pre = q("""SELECT COUNT(*) FILTER (WHERE preapproval = '1') n,
                      COUNT(*) FILTER (WHERE preapproval = '1' AND outcome = 'lender_denied') d FROM lar""").iloc[0]
    add("Pre-approval requested", f"{int(pre.n):,} files, {int(pre.d)} lender denials",
        "Denied pre-approval requests are a separate HMDA action outside the scope, so pre-approved files look unrealistically good: not used.")
    dup = q("""SELECT COUNT(*) - COUNT(DISTINCT (lei, county_code, loan_amount, income, property_value, action_taken, interest_rate))
               FROM lar""").iloc[0, 0]
    add("Possible duplicate rows (same lender, county, amount, income, value, action, rate)", f"{int(dup):,}",
        "HMDA has no application ID, so these cannot be separated from genuine near-identical applications. Kept.")
    cov = lenders.apps.sum() / TOTAL
    add("Lenders with 200+ applications", f"{len(lenders)} of {n_lenders_all} lenders cover {cov:.1%} of applications",
        "Smaller lenders are excluded from lender comparisons (their rates are too noisy).")
    add("Pricing fields", "Present only for originated loans (rate also for approved-not-accepted)",
        "Pricing comparisons use one fixed segment (conventional purchase) and carry survivorship bias.")
    add("Unit of analysis", "Application, not borrower", "HMDA has no applicant id, so repeat applicants cannot be linked.")
    save(pd.DataFrame(dq), "data_quality")

    # ============================================================== 8. VERIFICATION
    assert by_purpose.apps.sum() == TOTAL, f"{state}: outcome table does not add up"
    kept = int(ATTRITION[ATTRITION.state == state].rows.iloc[-1])
    assert kept == TOTAL, f"{state}: {TOTAL} rows in parquet but attrition report says {kept}"
    assert explorer.apps.sum() == TOTAL, f"{state}: explorer grid does not add up"
    lo_cols = ["originated", "denied", "withdrew", "incomplete", "declined"]
    assert (explorer[lo_cols].sum(axis=1) == explorer.apps).all(), f"{state}: explorer outcomes do not add up per cell"
    all_oe = q("""
        WITH seg AS (SELECT purpose_label, loan_type, AVG(walked_away) AS r FROM lar GROUP BY ALL)
        SELECT SUM(walked_away) / SUM(r) AS ratio FROM lar JOIN seg USING (purpose_label, loan_type)
    """).ratio[0]
    assert abs(all_oe - 1) < 1e-9, f"{state}: state-wide walk-away O/E must be exactly 1"

    def brute_frontier(df, x, y):
        out_ = set()
        for _, a in df.iterrows():
            dominated = ((df[x] <= a[x]) & (df[y] <= a[y]) & ((df[x] < a[x]) | (df[y] < a[y]))).any()
            if not dominated:
                out_.add(a.lei)
        return out_

    assert brute_frontier(lenders, "walkaway_pct", "denial_pct") == f_raw, f"{state}: raw frontier mismatch"
    assert brute_frontier(lenders, "wa_oe", "den_oe") == f_adj, f"{state}: adjusted frontier mismatch"
    assert brute_frontier(lenders, "wa_oe_inc", "den_oe_inc") == f_inc, f"{state}: income-adjusted frontier mismatch"
    assert county.apps.sum() == TOTAL, f"{state}: county apps do not add up"
    lo = pd.read_csv(f"{out}/lender_outcomes.csv")
    assert lo.groupby("lei").apps.sum().reindex(lenders.lei).eq(lenders.apps.values).all(), f"{state}: lender outcome counts"
    assert (np.abs(lenders.wa_oe_eb - ybar) <= np.abs(y_i - ybar) + 1e-3).all(), f"{state}: shrinkage must not expand"
    calc.selfcheck(leak, assumptions_df, lenders)

    n_sig_worse = int((lenders.wa_z > 1.96).sum())
    n_sig_better = int((lenders.wa_z < -1.96).sum())
    summary |= {
        "lenders": len(lenders), "lender_coverage_pct": 100 * cov,
        "f_raw": len(f_raw), "f_adj": len(f_adj), "f_inc": len(f_inc), "f_500": len(f_500),
        "f_adj_and_raw": len(f_adj & f_raw), "f_adj_and_inc": len(f_adj & f_inc), "f_adj_and_500": len(f_adj & f_500),
        "sig_worse": n_sig_worse, "sig_better": n_sig_better,
        "excess_walkaways_sig_worse": float(lenders[lenders.wa_z > 1.96].excess_walkaways.sum()),
    }
    if state == "MD":
        got ={"total": TOTAL, "lenders": len(lenders), "raw": len(f_raw), "adj": len(f_adj), "inc": len(f_inc),
               "min500": len(f_500), "adj_and_inc": len(f_adj & f_inc), "adj_and_raw": len(f_adj & f_raw),
               "sig_worse": n_sig_worse, "sig_better": n_sig_better}
        assert got == MD_SNAPSHOT, f"Maryland numbers changed vs the first version: {got} != {MD_SNAPSHOT}"

    print(f"{state}: {TOTAL:>7,} apps | {len(lenders):>3} lenders | frontier raw/adj/inc/500 = "
          f"{len(f_raw)}/{len(f_adj)}/{len(f_inc)}/{len(f_500)} | adj&raw {len(f_adj & f_raw)}, adj&inc {len(f_adj & f_inc)} | "
          f"sig worse/better {n_sig_worse}/{n_sig_better} | tau {summary['tau']:.3f} | assertions passed")
    con.close()
    return summary


if __name__ == "__main__":
    rows = [build(s) for s in STATES]
    new = pd.DataFrame(rows)
    path = "data/states.csv"
    if os.path.exists(path) and sys.argv[1:]:  # partial rebuild: keep the other states' rows
        old = pd.read_csv(path)
        new = pd.concat([old[~old.state.isin(new.state)], new]).set_index("state").loc[ALL_STATES].reset_index()
    new.round(4).to_csv(path, index=False)
    print(f"wrote {path} ({len(new)} states)")
