"""
calc.py: small, testable calculations shared by the Streamlit app, the memo and build_data.py.

    opportunity_direct_refi   funded loans / volume from closing part of the direct-vs-indirect incomplete-file gap
    opportunity_lender_gap    funded loans / volume if lenders significantly worse than their mix close part of the gap
    sample_size_per_arm       two-proportion A/B test sample size per arm
    selfcheck                 invariants that must hold (run by build_data.py)
"""

from math import ceil, sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd


def _assump(assumptions: pd.DataFrame) -> dict:
    return dict(zip(assumptions["key"], assumptions["value"]))


def opportunity_direct_refi(leak: pd.DataFrame, assumptions: pd.DataFrame, share_closed: float, bps: float) -> pd.DataFrame:
    """Direct-channel refinance files closed as incomplete, compared with the same purpose through brokers.

    gap_files = (direct incomplete rate - indirect incomplete rate) x direct applications
    A share of the gap is assumed closable; recovered files then behave like average files that stay to a decision.
    """
    a = _assump(assumptions)
    rows = []
    for purpose in ["refinance", "cash_out_refi"]:
        d_rows = leak[(leak.purpose_label == purpose) & (leak.channel_label == "direct")]
        i_rows = leak[(leak.purpose_label == purpose) & (leak.channel_label == "indirect")]
        if d_rows.empty or i_rows.empty:  # a small state may have no broker refinances to compare with
            continue
        d, i = d_rows.iloc[0], i_rows.iloc[0]
        d_rate, i_rate = d.incomplete / d.apps, i.incomplete / i.apps
        gap_files = max(d_rate - i_rate, 0) * d.apps
        recovered = gap_files * share_closed
        funded = recovered * a["approval_given_stay"]
        volume = funded * a[f"med_loan_{purpose}"]
        rows.append({
            "purpose": purpose, "direct_apps": int(d.apps), "direct_incomplete_pct": 100 * d_rate,
            "indirect_incomplete_pct": 100 * i_rate, "gap_files": gap_files, "recovered_files": recovered,
            "funded_loans": funded, "volume": volume, "revenue": volume * bps / 10000,
        })
    return pd.DataFrame(rows, columns=[
        "purpose", "direct_apps", "direct_incomplete_pct", "indirect_incomplete_pct", "gap_files",
        "recovered_files", "funded_loans", "volume", "revenue"])


def opportunity_lender_gap(lenders: pd.DataFrame, assumptions: pd.DataFrame, share_closed: float, bps: float,
                           z_cut: float = 1.96) -> dict:
    """Lenders whose walk-away count is significantly above what their loan mix predicts (z > z_cut)."""
    a = _assump(assumptions)
    flagged = lenders[lenders.wa_z > z_cut]
    excess = flagged.excess_walkaways.sum()
    recovered = excess * share_closed
    funded = recovered * a["approval_given_stay"]
    volume = funded * a["med_loan_all"]
    return {"lenders": len(flagged), "excess_walkaways": excess, "recovered_files": recovered,
            "funded_loans": funded, "volume": volume, "revenue": volume * bps / 10000}


def eb_shrink(obs, exp, var) -> dict:
    """Empirical-Bayes (DerSimonian-Laird) view of lender O/E.

    y_i = obs/exp is each lender's observed-to-expected ratio and s_i^2 = var/exp^2 is its sampling variance if the lender
    were exactly as expected. tau is the standard deviation of the TRUE O/E across lenders (what is left after chance is
    removed); shrunk_i pulls each noisy O/E toward the precision-weighted mean in proportion to how noisy it is.
    """
    obs, exp, var = (np.asarray(a, dtype=float) for a in (obs, exp, var))
    y = obs / exp
    s2 = var / exp**2
    w = 1 / s2
    k = len(y)
    ybar = float((w * y).sum() / w.sum())
    Q = float((w * (y - ybar) ** 2).sum())
    c = float(w.sum() - (w**2).sum() / w.sum())
    tau2 = max(0.0, (Q - (k - 1)) / c) if k > 1 else 0.0
    B = tau2 / (tau2 + s2)
    return {"tau": sqrt(tau2), "ybar": ybar, "Q_ratio": Q / max(k - 1, 1), "weight": B, "shrunk": ybar + B * (y - ybar), "y": y}


def sample_size_per_arm(p_control: float, p_treatment: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Per-arm n for a two-sided two-proportion z-test (unpooled variance under the alternative)."""
    p1, p2 = p_control, p_treatment
    nd = NormalDist()
    za, zb = nd.inv_cdf(1 - alpha / 2), nd.inv_cdf(power)
    pbar = (p1 + p2) / 2
    n = (za * sqrt(2 * pbar * (1 - pbar)) + zb * sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
    return ceil(n)


def selfcheck(leak: pd.DataFrame, assumptions: pd.DataFrame, lenders: pd.DataFrame) -> None:
    zero = opportunity_direct_refi(leak, assumptions, 0.0, 100)
    assert (zero.funded_loans == 0).all() and (zero.revenue == 0).all()
    full = opportunity_direct_refi(leak, assumptions, 1.0, 100)
    half = opportunity_direct_refi(leak, assumptions, 0.5, 100)
    assert abs(half.funded_loans.sum() * 2 - full.funded_loans.sum()) < 1e-6, "opportunity must scale linearly"
    assert (full.gap_files <= full.direct_apps).all()
    assert opportunity_lender_gap(lenders, assumptions, 0.0, 100)["funded_loans"] == 0
    # textbook check: 10% vs 12%, alpha .05, power .8 -> about 3,840 per arm
    assert 3800 <= sample_size_per_arm(0.10, 0.12) <= 3900
    assert sample_size_per_arm(0.10, 0.14) < sample_size_per_arm(0.10, 0.12), "larger effect needs fewer files"
    # shrinkage: lenders exactly as expected -> no true spread; real spread -> noisy lenders shrink more than precise ones
    flat = eb_shrink([100, 200, 300], [100, 200, 300], [90, 180, 270])
    assert flat["tau"] == 0 and np.allclose(flat["shrunk"], 1.0)
    spread = eb_shrink([150, 300, 1500, 10_000], [100, 200, 1000, 10_000], [90, 180, 900, 9_000])
    assert spread["tau"] > 0 and spread["weight"][0] < spread["weight"][3], "less precise lenders must shrink more"
