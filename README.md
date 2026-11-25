# The Approval–Abandonment Frontier

Product analysis of Maryland mortgage applications (HMDA 2024): do lenders lose applicants to their own
denials, or because applicants walk away, and which lenders do best on both once loan mix is accounted for?

- **App:** `streamlit run app.py`
- **Findings:** [findings.md](findings.md)
- **Pipeline:** `clean.py` (raw HMDA → `hmda_clean.parquet`) → `diagnostics.py` (SQL exploration, DuckDB)
  → `build_data.py` (small CSVs in `data/`) → `app.py`
- **Lender names:** `fetch_lender_names.py` (public GLEIF registry, run once)

## Rebuild the data

```
pip install -r requirements-build.txt
python build_data.py
```

## Method in one paragraph

Walk-away = withdrawn + incomplete + customer declined. Lender rates are mix-adjusted by indirect
standardization (observed ÷ expected, where expected uses the statewide rate for the same loan purpose × loan type).
The frontier is the set of lenders no other lender beats on both measures (SQL `NOT EXISTS`). Limitations are listed
in the app and in `findings.md`.

Source: FFIEC HMDA Data Browser, Maryland 2024 LAR.
