# The Approval–Abandonment Frontier

Product analysis of home loan applications (HMDA 2024) in Maryland and its five neighbours: where do applicants leave,
which lenders keep them once loan mix is accounted for, and what should a digital lender build about it?

**Live app:** https://creditriskanalysis-hmda.streamlit.app/

**Headline:** across 553,213 applications, 21–26% end because the applicant walks away and only 10–14% are denied. One concentrated leak is
files closed as incomplete in direct-channel refinances (9.3–12.2% vs 3.3–6.1% through brokers), and it replicates in all six
states. Walk-away in general is hard to predict (AUC ≈ 0.6) and a 13-feature ML model does not explain the gaps between
lenders. Unfinished files are more predictable: a model trained on Maryland scores the other five states at AUC 0.73–0.78.
The data records no reason for leaving, so the cause is a hypothesis for the proposed A/B test.

**A year apart:** the same gaps appear in 2023, and 103 of 128 followable "worse than mix" lender flags from 2023 were still
significant in 2024. Frontier membership was far less stable (14 of 31 places carried over), and the direct-refinance rate fell
in all six states with no test, so the A/B test needs a concurrent control group.

- **App:** [open it online](https://creditriskanalysis-hmda.streamlit.app/), or run `streamlit run app.py`. Ten pages: overview with an animated funnel, funnel explorer, lender frontier, case-mix model
  (ML), pricing, denials, county map, six-state replication scoreboard, opportunity sizing and A/B calculator, method and data.
  Switch state in the sidebar (also `?state=VA` in the URL).
- **PM memo:** [memo.md](memo.md)
- **Findings:** [findings.md](findings.md) (18 findings, each with result / interpretation / limitation)

## Pipeline

```
clean.py                raw HMDA CSVs (raw_data/<ST>_2024.csv) -> hmda_clean.parquet (+ attrition.csv)
fetch_lender_names.py   lender names from the public GLEIF registry
prep_geo.py             county names and map shapes (Census)
build_data.py           SQL (DuckDB) + checks -> per-state tables in data/<ST>/ and data/states.csv
build_ml.py             out-of-lender gradient-boosted case-mix model -> data/<ST>/ml_*.csv
build_transfer.py       train on Maryland, test on the other five states, with a missing-income leak check
build_temporal.py       2023 vs 2024: headlines, train-2023/test-2024 model, lender flags and frontier (raw_data/y2023/)
calc.py                 opportunity sizing, sample-size maths, empirical-Bayes shrinkage (with built-in checks)
store.py ui.py charts.py views/*.py   the Streamlit app (app.py is the entry point)
diagnostics.py          early SQL exploration in DuckDB (views, CTEs, NOT EXISTS frontier)
```

Raw files come from the FFIEC HMDA Data Browser API
(`https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?states=MD&years=2024`).
Rebuild: `pip install -r requirements-build.txt`, then run the scripts above in order. The deployed app needs only
`requirements.txt` and the committed `data/` tables.

## Method in one paragraph

Walk-away = withdrawn + closed incomplete + customer declined an approved offer. Lender rates are mix-adjusted by indirect
standardisation (observed ÷ expected, where expected uses the state-wide rate for the same loan purpose × loan type; optionally
also income band, or a gradient-boosted model scored out-of-lender) and tested with a z-score. A DerSimonian–Laird
empirical-Bayes step estimates the true lender spread and shrinks noisy small lenders. The frontier is the set of lenders no
other lender beats on both walk-away and denial (SQL `NOT EXISTS`), recomputed under four adjustments and verified by brute
force. Pricing is compared on one fixed segment (originated conventional purchase) to limit survivorship bias.

## What the build verifies

For every state: the outcome table adds to the row count in the attrition report; the state-wide walk-away O/E equals exactly 1;
every frontier equals an independent brute-force dominance check; county and lender tables add to the totals; shrinkage never
expands an estimate; opportunity maths scales linearly and the sample-size formula reproduces a textbook value. The Maryland
numbers are pinned to the first version of the project. The ML step asserts calibration in the large for the big states.

## Limits

Pages show 2024 and 2023 is used only for the year check; applications, not borrowers; no credit score or timestamps; pricing only for funded loans; neighbouring states
are not independent samples. Descriptive analysis of public data: no claim about any lender's practices, no demographic
(fair-lending) analysis, and no model uses protected characteristics.

Source: FFIEC HMDA Data Browser, 2024 LAR. Lender names: GLEIF. Map shapes: US Census cartographic boundaries.
