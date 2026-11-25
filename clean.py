
"""
clean.py: Raw HMDA CSVs -> cleaned state-year Parquet files
           -> combined Parquet file + filter attrition report.

Input:
    raw_data/MD_2024.csv

Output:
    clean_parts/MD_2024.parquet
    clean_parts/MD_2024_attrition.csv
    hmda_clean.parquet
    attrition.csv
    scratch.duckdb

Run:
    python clean.py
    python clean.py --force
"""

import glob
import os
import sys

import duckdb
import pandas as pd


# ---------------------------------------------------------
# 0. CONFIGURATION
# ---------------------------------------------------------

RAW_DIR = "raw_data"
PARTS_DIR = "clean_parts"
OUT_FILE = "hmda_clean.parquet"
ATTRITION_FILE = "attrition.csv"

FORCE = "--force" in sys.argv

os.makedirs(PARTS_DIR, exist_ok=True)


def sql_literal(value):
    """Safely quote a Python string as a SQL string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def parse_filename(path):
    """
    Expected filename: STATE_YEAR.csv
    Example: MD_2024.csv
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    parts = stem.split("_")

    if len(parts) != 2:
        raise ValueError(
            f"Invalid filename: {os.path.basename(path)}. "
            "Expected a name like MD_2024.csv."
        )

    state, year_text = parts
    state = state.upper()

    if len(state) != 2 or not state.isalpha() or not year_text.isdigit():
        raise ValueError(
            f"Invalid filename: {os.path.basename(path)}. "
            "Expected a name like MD_2024.csv."
        )

    return state, int(year_text)


# ---------------------------------------------------------
# 1. SCOPE: cumulative filters defining the study population
# ---------------------------------------------------------

FILTERS = [
    (
        "applications only (action 1-5, 8)",
        "action_taken IN ('1','2','3','4','5','8')",
    ),
    (
        "single-family, site-built",
        "derived_dwelling_category = 'Single Family (1-4 Units):Site-Built'",
    ),
    ("first lien", "lien_status = '1'"),
    ("owner-occupied principal residence", "occupancy_type = '1'"),
    (
        "purchase / refi / cash-out refi",
        "loan_purpose IN ('1','31','32')",
    ),
]

WHERE = " AND ".join(condition for _, condition in FILTERS)


# ---------------------------------------------------------
# 2. CLEANING QUERY
# ---------------------------------------------------------

def clean_select(state, year):
    state_sql = sql_literal(state)

    return f"""
    SELECT
        {state_sql} AS state,
        {year} AS year,
        lei,
        county_code,

        -- Application outcome
        TRY_CAST(action_taken AS INTEGER) AS action_taken,

        CASE
            WHEN action_taken = '1' THEN 'originated'
            WHEN action_taken = '3' THEN 'lender_denied'
            WHEN action_taken IN ('2', '8') THEN 'customer_declined'
            WHEN action_taken = '4' THEN 'customer_withdrew'
            WHEN action_taken = '5' THEN 'stalled_incomplete'
        END AS outcome,

        CASE
            WHEN action_taken IN ('2', '4', '5', '8') THEN 1
            ELSE 0
        END AS walked_away,

        -- DTI presence is only a proxy for reaching underwriting
        CASE
            WHEN COALESCE(debt_to_income_ratio, 'NA')
                 IN ('NA', 'Exempt', '1111')
            THEN 0
            ELSE 1
        END AS reached_underwriting,

        -- Applicant and loan characteristics
        loan_purpose,

        CASE loan_purpose
            WHEN '1' THEN 'purchase'
            WHEN '31' THEN 'refinance'
            WHEN '32' THEN 'cash_out_refi'
        END AS purpose_label,

        loan_type,
        TRY_CAST(income AS DOUBLE) AS income,
        TRY_CAST(loan_amount AS DOUBLE) AS loan_amount,
        TRY_CAST(property_value AS DOUBLE) AS property_value,
        TRY_CAST(loan_to_value_ratio AS DOUBLE) AS cltv,

        debt_to_income_ratio AS dti_raw,

        -- Representative values for DTI ranges; these are assumptions
        CASE debt_to_income_ratio
            WHEN '<20%' THEN 15.0
            WHEN '20%-<30%' THEN 25.0
            WHEN '30%-<36%' THEN 33.0
            WHEN '50%-60%' THEN 55.0
            WHEN '>60%' THEN 65.0
            ELSE TRY_CAST(debt_to_income_ratio AS DOUBLE)
        END AS dti_num,

        -- Loan offer and pricing fields
        TRY_CAST(interest_rate AS DOUBLE) AS interest_rate,
        TRY_CAST(rate_spread AS DOUBLE) AS rate_spread,
        TRY_CAST(total_loan_costs AS DOUBLE) AS total_loan_costs,
        TRY_CAST(discount_points AS DOUBLE) AS discount_points,
        TRY_CAST(lender_credits AS DOUBLE) AS lender_credits,

        -- Application channel and product process
        submission_of_application,

        CASE submission_of_application
            WHEN '1' THEN 'direct'
            WHEN '2' THEN 'indirect'
            WHEN '3' THEN 'not_applicable'
            WHEN '1111' THEN 'exempt'
        END AS channel_label,

        "aus-1" AS aus,
        preapproval,

        -- Application-time fields used by the ML case-mix model (build_ml.py)
        TRY_CAST(loan_term AS DOUBLE) AS loan_term,
        TRY_CAST(total_units AS INTEGER) AS total_units,
        conforming_loan_limit,
        "open-end_line_of_credit" AS open_end,
        reverse_mortgage,
        TRY_CAST(tract_to_msa_income_percentage AS DOUBLE) AS tract_income_pct,

        -- 10 = no denial reason; 1111 = exempt
        NULLIF(
            NULLIF("denial_reason-1", '10'),
            '1111'
        ) AS denial_reason

    FROM raw
    WHERE {WHERE}
    """


# ---------------------------------------------------------
# 3. LOG ROW COUNTS AFTER EACH CUMULATIVE FILTER
# ---------------------------------------------------------

def log_attrition(con, state, year):
    """Count rows remaining after each filtering step."""

    rows = [
        {
            "state": state,
            "year": year,
            "step": "raw file",
            "rows": con.execute(
                "SELECT COUNT(*) FROM raw"
            ).fetchone()[0],
        }
    ]

    conditions = []

    for label, condition in FILTERS:
        conditions.append(condition)

        combined_conditions = " AND ".join(conditions)

        query = f"""
            SELECT COUNT(*)
            FROM raw
            WHERE {combined_conditions}
        """

        count = con.execute(query).fetchone()[0]

        rows.append(
            {
                "state": state,
                "year": year,
                "step": label,
                "rows": count,
            }
        )

    attrition_path = os.path.join(
        PARTS_DIR, f"{state}_{year}_attrition.csv"
    )

    pd.DataFrame(rows).to_csv(attrition_path, index=False)

    return rows[0]["rows"], rows[-1]["rows"]


# ---------------------------------------------------------
# 4. PROCESS INPUT CSV FILES
# ---------------------------------------------------------

def main():
    input_files = sorted(glob.glob(os.path.join(RAW_DIR, "*.csv")))

    if not input_files:
        sys.exit(
            "No CSV files found in raw_data/. "
            "Add a file named like MD_2024.csv."
        )

    # Validate filenames before starting the pipeline.
    jobs = []

    try:
        for path in input_files:
            state, year = parse_filename(path)
            jobs.append((path, state, year))
    except ValueError as error:
        sys.exit(str(error))

    con = duckdb.connect("scratch.duckdb")

    active_parts = []
    active_attrition = []

    try:
        for path, state, year in jobs:
            part_path = os.path.join(
                PARTS_DIR, f"{state}_{year}.parquet"
            )
            attrition_path = os.path.join(
                PARTS_DIR, f"{state}_{year}_attrition.csv"
            )

            # Reuse a state-year only if both outputs already exist.
            if (
                os.path.exists(part_path)
                and os.path.exists(attrition_path)
                and not FORCE
            ):
                print(
                    f"Skipping {state} {year}: "
                    "cleaned files already exist.",
                    flush=True,
                )
                active_parts.append(part_path)
                active_attrition.append(attrition_path)
                continue

            print(f"Cleaning {state} {year} ...", flush=True)

            # Read every column as text first; cast explicitly in SQL.
            input_sql = sql_literal(
                os.path.abspath(path).replace("\\", "/")
            )

            con.execute(
                f"""
                CREATE OR REPLACE TABLE raw AS
                SELECT *
                FROM read_csv_auto(
                    {input_sql},
                    all_varchar = true
                )
                """
            )

            raw_count, kept_count = log_attrition(
                con, state, year
            )

            if os.path.exists(part_path):
                os.remove(part_path)

            output_sql = sql_literal(
                os.path.abspath(part_path).replace("\\", "/")
            )

            con.execute(
                f"""
                COPY ({clean_select(state, year)})
                TO {output_sql}
                (FORMAT PARQUET)
                """
            )

            if raw_count:
                percentage = 100 * kept_count / raw_count
            else:
                percentage = 0.0

            print(
                f"  {raw_count:,} raw -> {kept_count:,} kept "
                f"({percentage:.1f}%)",
                flush=True,
            )

            active_parts.append(part_path)
            active_attrition.append(attrition_path)

        con.execute("DROP TABLE IF EXISTS raw")

        # -------------------------------------------------
        # 5. COMBINE ONLY THE FILES FOR CURRENT INPUTS
        # -------------------------------------------------

        if not active_parts:
            sys.exit("No cleaned Parquet files are available.")

        # An explicit list prevents unrelated old Parquet files
        # in clean_parts/ from contaminating the combined dataset.
        union_queries = []

        for part_path in active_parts:
            part_sql = sql_literal(
                os.path.abspath(part_path).replace("\\", "/")
            )
            union_queries.append(
                f"SELECT * FROM read_parquet({part_sql})"
            )

        combined_query = " UNION ALL ".join(union_queries)

        if os.path.exists(OUT_FILE):
            os.remove(OUT_FILE)

        output_sql = sql_literal(
            os.path.abspath(OUT_FILE).replace("\\", "/")
        )

        con.execute(
            f"""
            COPY ({combined_query})
            TO {output_sql}
            (FORMAT PARQUET)
            """
        )

        # -------------------------------------------------
        # 6. COMBINE ATTRITION REPORTS
        # -------------------------------------------------

        attrition_frames = [
            pd.read_csv(path) for path in active_attrition
        ]

        attrition = pd.concat(
            attrition_frames,
            ignore_index=True,
        )

        attrition.to_csv(ATTRITION_FILE, index=False)

        summary = (
            attrition.groupby(["state", "year"])["rows"]
            .agg(raw="max", kept="min")
        )

        summary["pct_kept"] = (
            100 * summary["kept"] / summary["raw"].replace(0, pd.NA)
        ).round(1)

        print("\nROWS KEPT PER STATE-YEAR")
        print(summary.to_string())

        # -------------------------------------------------
        # 7. VALIDATION CHECKS
        # -------------------------------------------------

        con.execute(
            f"""
            CREATE OR REPLACE VIEW lar AS
            SELECT * FROM read_parquet({output_sql})
            """
        )

        print("\nFUNNEL BY STATE (% OF SCOPED APPLICATIONS)")

        funnel_query = """
            SELECT
                state,
                year,
                COUNT(*) AS n,

                ROUND(
                    100.0 * COUNT(*) FILTER (
                        WHERE outcome = 'originated'
                    ) / COUNT(*),
                    1
                ) AS originated_pct,

                ROUND(
                    100.0 * COUNT(*) FILTER (
                        WHERE walked_away = 1
                    ) / COUNT(*),
                    1
                ) AS walked_away_pct,

                ROUND(
                    100.0 * COUNT(*) FILTER (
                        WHERE outcome = 'lender_denied'
                    ) / COUNT(*),
                    1
                ) AS denied_pct

            FROM lar
            GROUP BY state, year
            ORDER BY state, year
        """

        print(
            con.execute(funnel_query)
            .df()
            .to_string(index=False)
        )

        print("\nCOLUMN TYPES (CAST VALIDATION)")

        print(
            con.execute("DESCRIBE lar")
            .df()[["column_name", "column_type"]]
            .to_string(index=False)
        )

        print("\nPipeline completed successfully.")
        print(f"Combined dataset: {OUT_FILE}")
        print(f"Attrition report: {ATTRITION_FILE}")

    finally:
        con.close()


if __name__ == "__main__":
    main()
