"""
build_transfer.py: do the patterns carry over to data the model has never seen?

1. Train on Maryland only, score the other five states, for three targets:
       closed incomplete (what the proposed file-completion assistant targets), any walk-away, denial.
   County is dropped because Maryland counties do not exist elsewhere. The baseline is a plain lookup table:
   Maryland's rate for each loan purpose x channel.

2. Leak check. Income is blank far more often on files closed incomplete than on others, so "income is missing" can give the
   answer away. The headline model therefore uses NO income-based fields. Two sensitivity columns show the alternative:
       auc_all_inputs        income and loan-to-income included
       auc_income_reported   income included, but trained and tested only on files that report it (a different population)

3. Lender persistence: for lenders with 200+ applications in two states, does mix-adjusted O/E in one match the other?

Outputs: data/transfer_metrics.csv, data/lender_persistence.csv
Run:     python build_transfer.py          (needs build_data.py to have run)

Limits: all data is from 2024 and the states are neighbours that share many lenders. This test says nothing about other years (see build_temporal.py).
"""

import itertools

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import build_ml as ml

TRAIN = "MD"
TEST = ["VA", "PA", "DE", "DC", "WV"]
INCOME_FIELDS = ["log_income", "loan_to_income"]
MIN_SHARED = 15
TARGETS = {
    "Closed incomplete": lambda d: (d.outcome == "stalled_incomplete").astype(int),
    "Any walk-away": lambda d: d.walked_away.astype(int),
    "Denial": lambda d: (d.outcome == "lender_denied").astype(int),
}


def top_share_captured(y: np.ndarray, score: np.ndarray, frac: float = 0.2) -> float:
    """Share of all positives found in the top `frac` of files by score. Tied scores share their positives evenly,
    so a coarse lookup table is not helped or hurt by row order."""
    t = pd.DataFrame({"y": y, "s": score})
    t["ey"] = t.groupby("s").y.transform("mean")
    k = int(round(frac * len(t)))
    return float(t.sort_values("s", ascending=False).ey.head(k).sum() / t.y.sum())


def main() -> None:
    df = pd.concat([ml.load(s).assign(state=s) for s in [TRAIN] + TEST], ignore_index=True)
    # one shared feature table so category codes mean the same thing in every state
    everything = ml.make_features(df, with_channel=True).drop(columns="county")
    safe = everything.drop(columns=INCOME_FIELDS)
    assert not set(INCOME_FIELDS) & set(safe.columns)

    train = (df.state == TRAIN).to_numpy()
    reported = (df.income > 0).to_numpy()
    channel = df.channel.fillna("missing")
    keys = pd.MultiIndex.from_arrays([df.purpose, channel])

    rows = []
    for target, make_y in TARGETS.items():
        y = make_y(df).to_numpy()
        model = ml.new_model().fit(safe[train], y[train])
        model_all = ml.new_model().fit(everything[train], y[train])
        model_rep = ml.new_model().fit(everything[train & reported], y[train & reported])
        table = pd.DataFrame({"p": df.purpose[train], "c": channel[train], "y": y[train]}).groupby(["p", "c"]).y.mean()
        lookup = table.reindex(keys).fillna(y[train].mean()).to_numpy()

        for state in TEST:
            te = (df.state == state).to_numpy()
            te_rep = te & reported
            pred = model.predict_proba(safe[te])[:, 1]
            rows.append({
                "target": target, "train_state": TRAIN, "test_state": state, "n": int(te.sum()), "base_rate": y[te].mean(),
                "auc_table": roc_auc_score(y[te], lookup[te]),
                "auc_model": roc_auc_score(y[te], pred),
                "auc_all_inputs": roc_auc_score(y[te], model_all.predict_proba(everything[te])[:, 1]),
                "auc_income_reported": roc_auc_score(y[te_rep], model_rep.predict_proba(everything[te_rep])[:, 1]),
                "pred_over_obs": pred.sum() / y[te].sum(),
                "top20_table": top_share_captured(y[te], lookup[te]),
                "top20_model": top_share_captured(y[te], pred),
                "income_blank_if_positive": float((~reported[te])[y[te] == 1].mean()),
                "income_blank_if_negative": float((~reported[te])[y[te] == 0].mean()),
            })
    out = pd.DataFrame(rows)
    assert out.n.groupby(out.target).sum().eq(int((~train).sum())).all(), "every unseen application must be scored once"
    assert out[["auc_table", "auc_model"]].apply(lambda c: c.between(0.5, 1)).all().all()
    out.round(4).to_csv("data/transfer_metrics.csv", index=False)

    lenders = {s: pd.read_csv(f"data/{s}/lenders.csv")[["lei", "wa_oe", "den_oe"]] for s in [TRAIN] + TEST}
    pairs = []
    for a, b in itertools.combinations([TRAIN] + TEST, 2):
        j = lenders[a].merge(lenders[b], on="lei", suffixes=("_a", "_b"))
        if len(j) >= MIN_SHARED:
            pairs.append({"state_a": a, "state_b": b, "shared_lenders": len(j),
                          "rho_walkaway": j.wa_oe_a.rank().corr(j.wa_oe_b.rank()),
                          "rho_denial": j.den_oe_a.rank().corr(j.den_oe_b.rank())})
    per = pd.DataFrame(pairs)
    per.round(4).to_csv("data/lender_persistence.csv", index=False)

    pd.set_option("display.width", 220)
    print(out[["target", "test_state", "auc_table", "auc_model", "auc_all_inputs", "auc_income_reported", "pred_over_obs",
               "top20_table", "top20_model"]].round(3).to_string(index=False))
    print(per.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
