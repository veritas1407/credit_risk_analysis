"""
build_temporal.py: do the patterns hold from one year to the next? (2023 -> 2024)

The same six states, the same cleaning rules (clean.py) and the same model recipe as build_transfer.py.

1. Model: for each state, train on its 2023 applications and score its 2024 applications. As in the transfer test, income-based
   fields and county are left out and the baseline is a lookup table (2023 rate for each loan purpose x channel).
2. Headlines: compute the main descriptive numbers for both years. The 2024 values must reproduce data/states.csv.
3. Lenders: mix-adjusted walk-away and denial O/E in each year. How similar is a lender's 2023 result to its 2024 result,
   and does a "significantly worse" flag from 2023 still hold in 2024,
   and are the same lenders on the mix-adjusted frontier?

Input:   raw_data/y2023/<ST>_2023.csv   (a subfolder, so clean.py never mixes 2023 into the 2024 dataset)
         https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?states=MD&years=2023
Outputs: data/temporal_metrics.csv, data/temporal_headlines.csv, data/temporal_lenders.csv, data/temporal_summary.csv
Run:     python build_temporal.py          (needs build_data.py to have run)

Limits: one pair of adjacent years. It says nothing about a different rate environment further apart in time.
"""

import os

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import build_ml as ml
import clean
from build_transfer import INCOME_FIELDS, TARGETS, top_share_captured

STATES = ml.ALL_STATES
RAW_DIR = os.path.join(clean.RAW_DIR, "y2023")
MIN_APPS = 200


def clean_2023(state: str) -> str:
    """Apply clean.py's scope filters and column casts to one 2023 file. Returns the parquet path."""
    part = os.path.join(clean.PARTS_DIR, f"{state}_2023.parquet").replace("\\", "/")
    if os.path.exists(part):
        return part
    src = os.path.join(RAW_DIR, f"{state}_2023.csv").replace("\\", "/")
    con = duckdb.connect()
    con.execute(f"CREATE TABLE raw AS SELECT * FROM read_csv_auto({clean.sql_literal(src)}, all_varchar = true)")
    clean.log_attrition(con, state, 2023)
    con.execute(f"COPY ({clean.clean_select(state, 2023)}) TO {clean.sql_literal(part)} (FORMAT PARQUET)")
    con.close()
    return part


def load(state: str, source: str) -> pd.DataFrame:
    return duckdb.sql(f"""
        SELECT lei, county_code AS county, outcome, walked_away, purpose_label AS purpose, loan_type, channel_label AS channel,
               income, loan_amount, loan_term, total_units, conforming_loan_limit AS conforming, open_end, reverse_mortgage,
               tract_income_pct, preapproval
        FROM read_parquet('{source}') WHERE state = '{state}'
    """).df()


def headlines(d: pd.DataFrame) -> dict:
    incomplete = d.outcome == "stalled_incomplete"
    refi = d.purpose.isin(["refinance", "cash_out_refi"])
    direct, broker = d.channel == "direct", d.channel == "indirect"
    return {
        "apps": len(d),
        "walk_pct": 100 * d.walked_away.mean(),
        "den_pct": 100 * (d.outcome == "lender_denied").mean(),
        "incomplete_pct": 100 * incomplete.mean(),
        "dir_refi_apps": int((refi & direct).sum()),
        "dir_refi_inc_pct": 100 * incomplete[refi & direct].mean(),
        "ind_refi_apps": int((refi & broker).sum()),
        "ind_refi_inc_pct": 100 * incomplete[refi & broker].mean(),
        "dir_purch_inc_pct": 100 * incomplete[(d.purpose == "purchase") & direct].mean(),
        "share_of_stalled_dir_refi": 100 * (refi & direct & incomplete).sum() / incomplete.sum(),
    }


def lender_oe(d: pd.DataFrame) -> pd.DataFrame:
    """Indirect standardisation by loan purpose x loan type, lenders with 200+ applications (same rule as build_data.py)."""
    cells = [d.purpose, d.loan_type]
    out = {}
    for key, y in [("wa", d.walked_away.astype(float)), ("den", (d.outcome == "lender_denied").astype(float))]:
        p = y.groupby(cells).transform("mean")
        g = pd.DataFrame({"lei": d.lei, "obs": y, "exp": p, "var": p * (1 - p)}).groupby("lei").sum()
        out[f"{key}_oe"] = g.obs / g.exp
        out[f"{key}_z"] = (g.obs - g.exp) / np.sqrt(g["var"])
    res = pd.DataFrame(out)
    res["apps"] = d.groupby("lei").size()
    return res[res.apps >= MIN_APPS]


def model_rows(state: str, old: pd.DataFrame, new: pd.DataFrame) -> list:
    df = pd.concat([old, new], ignore_index=True)
    # one shared feature table so category codes mean the same thing in both years
    everything = ml.make_features(df, with_channel=True).drop(columns="county")
    safe = everything.drop(columns=INCOME_FIELDS)
    train = np.arange(len(df)) < len(old)
    test = ~train
    reported = (df.income > 0).to_numpy()
    channel = df.channel.fillna("missing")
    keys = pd.MultiIndex.from_arrays([df.purpose, channel])
    rows = []
    for target, make_y in TARGETS.items():
        y = make_y(df).to_numpy()
        model = ml.new_model().fit(safe[train], y[train])
        model_all = ml.new_model().fit(everything[train], y[train])
        table = pd.DataFrame({"p": df.purpose[train], "c": channel[train], "y": y[train]}).groupby(["p", "c"]).y.mean()
        lookup = table.reindex(keys).fillna(y[train].mean()).to_numpy()
        pred = model.predict_proba(safe[test])[:, 1]
        rows.append({
            "target": target, "state": state, "train_year": 2023, "test_year": 2024,
            "n_train": int(train.sum()), "n_test": int(test.sum()),
            "base_rate_2023": y[train].mean(), "base_rate_2024": y[test].mean(),
            "auc_table": roc_auc_score(y[test], lookup[test]),
            "auc_model": roc_auc_score(y[test], pred),
            "auc_all_inputs": roc_auc_score(y[test], model_all.predict_proba(everything[test])[:, 1]),
            "pred_over_obs": pred.sum() / y[test].sum(),
            "top20_table": top_share_captured(y[test], lookup[test]),
            "top20_model": top_share_captured(y[test], pred),
            "income_blank_if_positive": float((~reported[test])[y[test] == 1].mean()),
            "income_blank_if_negative": float((~reported[test])[y[test] == 0].mean()),
        })
    return rows


def main() -> None:
    published = pd.read_csv("data/states.csv").set_index("state")
    metrics, heads, pairs, summary = [], [], [], []
    for state in STATES:
        old, new = load(state, clean_2023(state)), load(state, "hmda_clean.parquet")
        h_old, h_new = headlines(old), headlines(new)

        # guard: this script's definitions must reproduce the published 2024 numbers before its 2023 numbers mean anything
        for k, v in h_new.items():
            assert abs(v - published.loc[state, k]) < 6e-5, f"{state}: 2024 {k} is {v}, published {published.loc[state, k]}"
        pub = pd.read_csv(f"data/{state}/lenders.csv").set_index("lei")
        oe_old, oe_new = lender_oe(old), lender_oe(new)
        assert set(oe_new.index) == set(pub.index), f"{state}: 2024 lender set differs from lenders.csv"
        for c in ["wa_oe", "den_oe", "wa_z"]:
            assert (oe_new[c] - pub.loc[oe_new.index, c]).abs().max() < 0.01, f"{state}: 2024 {c} does not reproduce lenders.csv"

        heads += [{"state": state, "year": 2023, **h_old}, {"state": state, "year": 2024, **h_new}]
        metrics += model_rows(state, old, new)

        j = oe_old.merge(oe_new, left_index=True, right_index=True, suffixes=("_2023", "_2024"))
        pairs.append(j.reset_index().assign(state=state))
        flagged = j[j.wa_z_2023 > 1.96]
        front_old = ml.brute_frontier(oe_old[["wa_oe", "den_oe"]].round(2), "wa_oe", "den_oe")
        front_new = ml.brute_frontier(oe_new[["wa_oe", "den_oe"]].round(2), "wa_oe", "den_oe")
        assert front_new == set(pub[pub.on_adj_frontier].index), f"{state}: 2024 frontier does not reproduce lenders.csv"
        summary.append({
            "state": state, "lenders_2023": len(oe_old), "lenders_2024": len(oe_new), "shared_lenders": len(j),
            "rho_walkaway": j.wa_oe_2023.rank().corr(j.wa_oe_2024.rank()),
            "rho_denial": j.den_oe_2023.rank().corr(j.den_oe_2024.rank()),
            # flagged lenders that fall under 200 applications in 2024 cannot be followed up: report how many were lost
            "flagged_2023_all": int((oe_old.wa_z > 1.96).sum()),
            "flagged_2023": len(flagged),
            "flagged_still_above_1": int((flagged.wa_oe_2024 > 1).sum()),
            "flagged_still_significant": int((flagged.wa_z_2024 > 1.96).sum()),
            "frontier_2023": len(front_old), "frontier_2024": len(front_new), "frontier_both": len(front_old & front_new),
        })
        print(f"{state} done", flush=True)

    m, h, s = pd.DataFrame(metrics), pd.DataFrame(heads), pd.DataFrame(summary)
    assert len(m) == len(STATES) * len(TARGETS)
    assert m[["auc_table", "auc_model"]].apply(lambda c: c.between(0.5, 1)).all().all()
    m.round(4).to_csv("data/temporal_metrics.csv", index=False)
    h.round(4).to_csv("data/temporal_headlines.csv", index=False)
    pd.concat(pairs)[["state", "lei", "apps_2023", "apps_2024", "wa_oe_2023", "wa_oe_2024", "den_oe_2023", "den_oe_2024",
                      "wa_z_2023", "wa_z_2024"]].round(4).to_csv("data/temporal_lenders.csv", index=False)
    s.round(4).to_csv("data/temporal_summary.csv", index=False)

    pd.set_option("display.width", 220)
    print(h.round(2).to_string(index=False))
    print(m.drop(columns=["train_year", "test_year", "n_train"]).round(3).to_string(index=False))
    print(s.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
