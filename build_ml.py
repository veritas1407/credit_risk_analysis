"""
build_ml.py: a machine-learning case-mix adjustment for the lender comparison.

Question: the lender O/E in build_data.py only adjusts for loan purpose x loan type. If a much richer model of "who walks away"
is used instead, do lenders still differ, and does the frontier survive?

Model (one per state, per target):
    target     walked away (withdrew / closed incomplete / declined offer)     and     denied by the lender
    features   ONLY facts known when the application arrives and that do not identify the lender:
               loan purpose, loan type, income, loan amount, loan-to-income, loan term, units, conforming limit, open-end,
               reverse mortgage, tract income level, county, pre-approval request
               (variant B also adds the application channel: direct / broker)
    NOT used   DTI, CLTV, property value, AUS result, rate, costs (blank by rule for withdrawn files: using them would leak the answer),
               lender id, applicant race / ethnicity / sex / age, tract minority share (fair-lending: no protected attributes).
    algorithm  gradient-boosted trees (scikit-learn HistGradientBoostingClassifier)
    honest out-of-sample predictions: 5-fold GroupKFold BY LENDER, so every application is scored by a model that never saw
               that lender. Expected walk-aways for a lender = sum of its applications' predicted probabilities.

Outputs per state in data/<ST>/: ml_lenders.csv, ml_metrics.csv, ml_importance.csv, ml_calibration.csv; data/ml_summary.csv.
Run:  python build_ml.py            (needs build_data.py to have run)
      python build_ml.py MD VA
"""

import os
import sys
import time

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

import calc

ALL_STATES = ["MD", "VA", "PA", "DE", "DC", "WV"]
STATES = [s.upper() for s in sys.argv[1:]] or ALL_STATES
SEED = 7

FEATURES = ["purpose", "loan_type", "log_income", "log_loan_amount", "loan_to_income", "loan_term", "total_units",
            "conforming", "open_end", "reverse_mortgage", "tract_income_pct", "county", "preapproval"]
CATEGORICAL = ["purpose", "loan_type", "conforming", "open_end", "reverse_mortgage", "county", "preapproval", "channel"]


def load(state: str) -> pd.DataFrame:
    return duckdb.sql(f"""
        SELECT lei, county_code AS county, outcome, walked_away, purpose_label AS purpose, loan_type, channel_label AS channel,
               income, loan_amount, loan_term, total_units, conforming_loan_limit AS conforming, open_end, reverse_mortgage,
               tract_income_pct, preapproval
        FROM read_parquet('hmda_clean.parquet') WHERE state = '{state}'
    """).df()


def make_features(df: pd.DataFrame, with_channel: bool) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    inc = df.income.where(df.income > 0)
    x["log_income"] = np.log(inc.clip(upper=inc.quantile(0.995)))
    x["log_loan_amount"] = np.log(df.loan_amount.clip(lower=1))
    x["loan_to_income"] = (df.loan_amount / (inc * 1000)).clip(upper=20)
    x["loan_term"] = df.loan_term.clip(0, 480)
    x["total_units"] = df.total_units
    x["tract_income_pct"] = df.tract_income_pct.clip(0, 400)
    cols = FEATURES + (["channel"] if with_channel else [])
    for c in [c for c in cols if c in CATEGORICAL]:
        x[c] = df[c].fillna("missing").astype(str).astype("category")
    return x[cols]


def new_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.08, max_leaf_nodes=24, min_samples_leaf=100, l2_regularization=1.0,
        categorical_features="from_dtype", early_stopping=False, random_state=SEED)


def out_of_fold(x: pd.DataFrame, y: np.ndarray, groups: pd.Series, importance: bool):
    """Predictions for every row from models that never saw that row's lender (GroupKFold by lender)."""
    pred = np.zeros(len(y))
    imp = None
    rng = np.random.default_rng(SEED)
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=5).split(x, y, groups)):
        model = new_model().fit(x.iloc[tr], y[tr])
        pred[te] = model.predict_proba(x.iloc[te])[:, 1]
        if importance and fold == 0:
            idx = rng.choice(te, size=min(25_000, len(te)), replace=False)
            r = permutation_importance(model, x.iloc[idx], y[idx], scoring="roc_auc", n_repeats=3, random_state=SEED)
            imp = pd.DataFrame({"feature": x.columns, "importance": r.importances_mean, "importance_sd": r.importances_std})
    return pred, imp


def lender_table(df: pd.DataFrame, pred: np.ndarray, y: np.ndarray, lenders: pd.DataFrame) -> pd.DataFrame:
    t = pd.DataFrame({"lei": df.lei.to_numpy(), "y": y, "p": pred, "v": pred * (1 - pred)})
    g = t.groupby("lei").agg(obs=("y", "sum"), exp=("p", "sum"), var=("v", "sum")).reindex(lenders.lei)
    return g


def brute_frontier(d: pd.DataFrame, x: str, y: str) -> set:
    out = set()
    for lei, a in d.iterrows():
        if not ((d[x] <= a[x]) & (d[y] <= a[y]) & ((d[x] < a[x]) | (d[y] < a[y]))).any():
            out.add(lei)
    return out


def run(state: str) -> dict:
    t0 = time.time()
    out = f"data/{state}"
    df = load(state)
    lenders = pd.read_csv(f"{out}/lenders.csv")
    y_wa = df.walked_away.to_numpy()
    y_den = (df.outcome == "lender_denied").astype(int).to_numpy()
    xa, xb = make_features(df, False), make_features(df, True)

    pred_wa, imp_wa = out_of_fold(xa, y_wa, df.lei, importance=True)
    pred_den, imp_den = out_of_fold(xa, y_den, df.lei, importance=True)
    pred_ch, imp_ch = out_of_fold(xb, y_wa, df.lei, importance=True)

    # ---- model quality against the simple segment baseline (purpose x loan type)
    seg = df.groupby(["purpose", "loan_type"]).walked_away.transform("mean").to_numpy()
    seg_den = pd.Series(y_den).groupby([df.purpose, df.loan_type]).transform("mean").to_numpy()
    rows, cal = [], []
    for name, y, p, p_seg, with_ch in [("Walk-away", y_wa, pred_wa, seg, False), ("Denial", y_den, pred_den, seg_den, False),
                                        ("Walk-away + channel", y_wa, pred_ch, seg, True)]:
        null_ll = log_loss(y, np.full(len(y), y.mean()))
        rows.append({
            "model": name, "n": len(y), "base_rate": y.mean(), "auc_segment": roc_auc_score(y, p_seg),
            "auc_model": roc_auc_score(y, p), "logloss_gain_segment_pct": 100 * (1 - log_loss(y, p_seg) / null_ll),
            "logloss_gain_model_pct": 100 * (1 - log_loss(y, p) / null_ll),
        })
        q = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
        c = pd.DataFrame({"decile": q, "pred": p, "obs": y}).groupby("decile").agg(pred=("pred", "mean"), obs=("obs", "mean"), n=("obs", "size"))
        c["model"] = name
        cal.append(c.reset_index())
    pd.DataFrame(rows).round(4).to_csv(f"{out}/ml_metrics.csv", index=False)
    pd.concat(cal).round(4).to_csv(f"{out}/ml_calibration.csv", index=False)
    imp = pd.concat([imp_wa.assign(model="Walk-away"), imp_den.assign(model="Denial"), imp_ch.assign(model="Walk-away + channel")])
    imp.round(5).to_csv(f"{out}/ml_importance.csv", index=False)

    # ---- lender O/E under each adjustment
    gw, gd, gc = (lender_table(df, p, y, lenders) for p, y in [(pred_wa, y_wa), (pred_den, y_den), (pred_ch, y_wa)])
    res = lenders[["lei"]].copy()
    res["wa_exp_ml"] = gw["exp"].to_numpy()
    res["wa_oe_ml"] = (gw["obs"] / gw["exp"]).to_numpy()
    res["wa_z_ml"] = ((gw["obs"] - gw["exp"]) / np.sqrt(gw["var"])).to_numpy()
    res["den_oe_ml"] = (gd["obs"] / gd["exp"]).to_numpy()
    res["den_z_ml"] = ((gd["obs"] - gd["exp"]) / np.sqrt(gd["var"])).to_numpy()
    res["wa_oe_ch"] = (gc["obs"] / gc["exp"]).to_numpy()
    res["wa_z_ch"] = ((gc["obs"] - gc["exp"]) / np.sqrt(gc["var"])).to_numpy()
    eb_ml = calc.eb_shrink(gw["obs"], gw["exp"], gw["var"])
    eb_ch = calc.eb_shrink(gc["obs"], gc["exp"], gc["var"])
    res["wa_oe_ml_eb"] = eb_ml["shrunk"]
    f_ml = brute_frontier(res.set_index("lei"), "wa_oe_ml", "den_oe_ml")
    res["on_ml_frontier"] = res.lei.isin(f_ml)
    res.round(4).to_csv(f"{out}/ml_lenders.csv", index=False)

    # ---- sanity: predicted total should be close to the observed total (calibration in the large).
    # Holding out whole lenders is a harsh test: in a small state one big lender can move the total, so only large states are asserted.
    calib_wa, calib_den = pred_wa.sum() / y_wa.sum(), pred_den.sum() / y_den.sum()
    if len(df) >= 50_000:
        assert abs(calib_wa - 1) < 0.03, f"{state}: walk-away model badly calibrated in the large ({calib_wa:.3f})"
        assert abs(calib_den - 1) < 0.05, f"{state}: denial model badly calibrated in the large ({calib_den:.3f})"

    base = lenders.merge(res, on="lei")
    f_adj = set(base[base.on_adj_frontier].lei)
    m = {r["model"]: r for r in rows}
    summary = {
        "state": state, "n_features": len(FEATURES), "calib_wa": calib_wa, "calib_den": calib_den,
        "auc_segment_wa": m["Walk-away"]["auc_segment"], "auc_ml_wa": m["Walk-away"]["auc_model"],
        "auc_ml_wa_channel": m["Walk-away + channel"]["auc_model"],
        "auc_segment_den": m["Denial"]["auc_segment"], "auc_ml_den": m["Denial"]["auc_model"],
        "tau_segment": calc.eb_shrink(base.wa_obs, base.wa_exp, base.wa_var)["tau"],
        "tau_ml": eb_ml["tau"], "tau_channel": eb_ch["tau"],
        "rho_seg_vs_ml": base.wa_oe.rank().corr(base.wa_oe_ml.rank()),
        "rho_seg_vs_channel": base.wa_oe.rank().corr(base.wa_oe_ch.rank()),
        "rho_ml_vs_direct_share": base.wa_oe_ml.rank().corr(base.direct_share.rank()),
        "f_ml": len(f_ml), "f_ml_and_adj": len(f_ml & f_adj), "f_adj": len(f_adj),
        "sig_worse_ml": int((res.wa_z_ml > 1.96).sum()), "sig_worse_seg": int((base.wa_z > 1.96).sum()),
        "sig_worse_channel": int((res.wa_z_ch > 1.96).sum()), "lenders": len(res),
    }
    print(f"{state}: AUC walk-away segment {summary['auc_segment_wa']:.3f} -> ML {summary['auc_ml_wa']:.3f} (+channel {summary['auc_ml_wa_channel']:.3f}) | "
          f"denial {summary['auc_segment_den']:.3f} -> {summary['auc_ml_den']:.3f} | tau {summary['tau_segment']:.3f} -> {summary['tau_ml']:.3f} -> "
          f"{summary['tau_channel']:.3f} (+channel) | rank rho seg/ML {summary['rho_seg_vs_ml']:.2f} | frontier ML {len(f_ml)}, overlap {len(f_ml & f_adj)}/{len(f_adj)} "
          f"| {time.time() - t0:.0f}s", flush=True)
    return summary


if __name__ == "__main__":
    rows = [run(s) for s in STATES]
    new = pd.DataFrame(rows)
    path = "data/ml_summary.csv"
    if os.path.exists(path) and sys.argv[1:]:
        old = pd.read_csv(path)
        new = pd.concat([old[~old.state.isin(new.state)], new]).set_index("state").loc[ALL_STATES].reset_index()
    new.round(4).to_csv(path, index=False)
    print(f"wrote {path}")
