"""
store.py: cached data access and the labels / colours shared by every page.

Everything the app shows comes from small CSV tables in data/<ST>/ (built by build_data.py and build_ml.py).
"""

import json
from types import SimpleNamespace

import pandas as pd
import streamlit as st

STATES = {"MD": "Maryland", "VA": "Virginia", "PA": "Pennsylvania", "DE": "Delaware", "DC": "District of Columbia", "WV": "West Virginia"}

PURPOSE = {"purchase": "Purchase", "refinance": "Refinance", "cash_out_refi": "Cash-out refi"}
LOAN_TYPE = {1: "Conventional", 2: "FHA", 3: "VA", 4: "USDA"}
CHANNEL = {"direct": "Direct", "indirect": "Broker", "other": "Other"}

# one semantic colour per outcome, used on every chart
OUTCOMES = ["originated", "lender_denied", "customer_withdrew", "stalled_incomplete", "customer_declined"]
OUTCOME_LABEL = {"originated": "Funded", "lender_denied": "Denied by lender", "customer_withdrew": "Applicant withdrew",
                 "stalled_incomplete": "File closed incomplete", "customer_declined": "Applicant declined offer"}
COLOR = {"originated": "#2EE6C5", "lender_denied": "#FF5C7A", "customer_withdrew": "#FFC857",
         "stalled_incomplete": "#FF7F32", "customer_declined": "#B79CFF"}
TEAL, ROSE, AMBER, ORANGE, VIOLET, BLUE, GREY = "#2EE6C5", "#FF5C7A", "#FFC857", "#FF7F32", "#B79CFF", "#6EA8FF", "#8FA0C2"
# leak_by_segment / explorer use short column names
SHORT = {"originated": "originated", "lender_denied": "denied", "customer_withdrew": "withdrew",
         "stalled_incomplete": "incomplete", "customer_declined": "declined"}

DENIAL_REASON_COLORS = ["#6EA8FF", "#8FA0C2", "#FF5C7A", "#FFC857", "#B79CFF", "#2EE6C5", "#FF7F32", "#5A8AC8", "#4A5578"]


@st.cache_data
def _csv(path: str, **kw) -> pd.DataFrame:
    return pd.read_csv(path, **kw)


@st.cache_data
def states_table() -> pd.DataFrame:
    return _csv("data/states.csv")


@st.cache_data
def ml_summary() -> pd.DataFrame:
    return _csv("data/ml_summary.csv")


@st.cache_data
def geojson() -> dict:
    with open("data/counties.geojson") as f:
        return json.load(f)


@st.cache_data
def attrition() -> pd.DataFrame:
    return _csv("attrition.csv")


@st.cache_data
def load_state(state: str) -> SimpleNamespace:
    """All tables for one state plus the headline numbers every page uses."""

    def t(name, **kw):
        return _csv(f"data/{state}/{name}.csv", **kw)

    lenders = t("lenders").merge(t("ml_lenders"), on="lei", how="left")
    by_purpose = t("outcomes_by_purpose")
    leak = t("leak_by_segment")
    out = by_purpose.groupby("outcome").apps.sum()
    total = int(out.sum())
    walked = int(out[["customer_withdrew", "stalled_incomplete", "customer_declined"]].sum())
    refi = leak[leak.purpose_label.isin(["refinance", "cash_out_refi"])]
    dr, ir = refi[refi.channel_label == "direct"], refi[refi.channel_label == "indirect"]
    s = states_table().set_index("state").loc[state]
    ml = ml_summary().set_index("state").loc[state]
    counties = t("counties", dtype={"county_code": str})
    return SimpleNamespace(
        state=state, name=STATES[state], total=total, by_purpose=by_purpose, leak=leak, lenders=lenders, counties=counties,
        walked=walked, denied=int(out["lender_denied"]), orig=int(out["originated"]), incomplete=int(out["stalled_incomplete"]),
        by_outcome=out, segments=t("segments"), availability=t("info_availability"), income=t("income_bands"),
        size_channel=t("size_channel"), explorer=t("explorer"), price_groups=t("pricing_groups"), price_corr=t("pricing_corr"),
        price_loantype=t("pricing_by_loan_type"), den_purpose=t("denial_reasons_purpose"), den_loantype=t("denial_reasons_loantype"),
        dti=t("dti_denial"), assumptions=t("assumptions"), quality=t("data_quality"), lender_outcomes=t("lender_outcomes"),
        ml_metrics=t("ml_metrics"), ml_importance=t("ml_importance"), ml_calibration=t("ml_calibration"),
        dir_refi_apps=int(dr.apps.sum()), dir_refi_incomplete=int(dr.incomplete.sum()),
        dir_refi_inc_rate=dr.incomplete.sum() / dr.apps.sum(),
        ind_refi_inc_rate=(ir.incomplete.sum() / ir.apps.sum()) if ir.apps.sum() else float("nan"),
        dir_refi_funded_rate=dr.originated.sum() / dr.apps.sum(),
        s=s, ml=ml,
    )


def current_state() -> str:
    return st.session_state.get("state", "MD")
