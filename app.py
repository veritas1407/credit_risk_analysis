"""
The Approval-Abandonment Frontier: where mortgage applicants leave, which lenders keep them, and what a product team should do.
HMDA 2024 data for Maryland and its five neighbours.

Run locally:  streamlit run app.py
Data tables are built by build_data.py / build_ml.py from the cleaned HMDA parquet (see README).
"""

import streamlit as st

import store
import ui

st.set_page_config(page_title="Approval–Abandonment Frontier", page_icon=":material/insights:", layout="wide",
                   initial_sidebar_state="auto")
ui.inject_css()

PAGES = [
    st.Page("views/overview.py", title="Overview", icon=":material/insights:", default=True, url_path="overview"),
    st.Page("views/funnel.py", title="Funnel explorer", icon=":material/filter_alt:", url_path="funnel"),
    st.Page("views/lenders.py", title="Lender frontier", icon=":material/scatter_plot:", url_path="lenders"),
    st.Page("views/ml.py", title="Case-mix model", icon=":material/psychology:", url_path="model"),
    st.Page("views/pricing.py", title="Pricing", icon=":material/payments:", url_path="pricing"),
    st.Page("views/denials.py", title="Denials", icon=":material/block:", url_path="denials"),
    st.Page("views/geography.py", title="Geography", icon=":material/map:", url_path="geography"),
    st.Page("views/states.py", title="Six-state check", icon=":material/compare_arrows:", url_path="states"),
    st.Page("views/opportunity.py", title="Opportunity & test", icon=":material/rocket_launch:", url_path="opportunity"),
    st.Page("views/method.py", title="Method & data", icon=":material/menu_book:", url_path="method"),
]

with st.sidebar:
    st.html('<div class="brand"><div class="logo">A</div><div><div class="t">Approval–Abandonment<br>Frontier</div>'
            '<div class="s">HMDA 2024 · mortgage funnel</div></div></div>')
    _q = st.query_params.get("state", "MD")
    st.segmented_control("State", list(store.STATES), default=_q if _q in store.STATES else "MD", required=True, key="state",
                         format_func=lambda s: s, help="Every page re-computes for the selected state. " +
                         ", ".join(f"{k} = {v}" for k, v in store.STATES.items()))
    st.query_params["state"] = store.current_state()
    st.caption(f"**{store.STATES[store.current_state()]}**")
    st.space("small")
    for p in PAGES:
        st.page_link(p)
    st.space("small")
    st.caption("Public HMDA data (FFIEC) · lender names from the GLEIF registry. Descriptive analysis only: no claim about any "
               "lender's practices, and no demographic analysis.")

st.navigation(PAGES, position="hidden").run()
