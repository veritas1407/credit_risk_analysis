# The Approval–Abandonment Frontier

Product analysis of Maryland mortgage applications (HMDA 2024): where do applicants leave, which lenders keep them once
loan mix is accounted for, and what should a digital lender build about it?

**Headline:** 25.7% of applications end because the applicant walks away (11.6% are denied). The clearest leak is
files closed as incomplete in direct-channel refinances (12.2% vs 4.0% through brokers).

- **Live app:** `streamlit run app.py` (tabs: Summary, Funnel, Lenders, Pricing, Denials, Geography, Opportunity & test, Method & data)
- **PM memo:** [memo.md](memo.md)
- **Findings:** [findings.md](findings.md) (12 findings, each with result / interpretation / limitation)

## Pipeline

```
clean.py                raw HMDA CSV -> hmda_clean.parquet (+ attrition.csv)
diagnostics.py          SQL exploration in DuckDB (views, CTEs, NOT EXISTS frontier)
fetch_lender_names.py   lender names from the public GLEIF registry (run once)
build_data.py           SQL + checks -> small CSV tables in data/   (fails if any check fails)
calc.py                 opportunity sizing and sample-size maths (with built-in checks)
app.py                  Streamlit app reading data/
```

Rebuild the data tables: `pip install -r requirements-build.txt && python build_data.py`.

## Method in one paragraph

Walk-away = withdrawn + closed incomplete + customer declined an approved offer. Lender rates are mix-adjusted by indirect
standardization (observed ÷ expected, where expected uses the statewide rate for the same loan purpose × loan type;
optionally also income band) and tested with a z-score. The frontier is the set of lenders no other lender beats on both
walk-away and denial (SQL `NOT EXISTS`), recomputed under three adjustments and verified by brute force. Pricing is compared
on one fixed segment (originated conventional purchase) to limit survivorship bias.

## What `build_data.py` verifies

Outcome table adds to 118,431; 111 lenders; the state-wide walk-away O/E equals exactly 1; every frontier equals an
independent brute-force dominance check; county rows add to the total; opportunity maths scales linearly and the
sample-size formula reproduces a textbook value.

## Limits

One state and year; applications, not borrowers; no credit score; pricing only for funded loans. Descriptive analysis of
public data: no claim about any lender's practices and no demographic (fair-lending) analysis.

Source: FFIEC HMDA Data Browser, Maryland 2024 LAR. Lender names: GLEIF.
