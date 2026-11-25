"""
fetch_lender_names.py: map lender LEIs to legal names using the public GLEIF registry.

Input : hmda_clean.parquet (lenders with >= 200 applications)
Output: data/lender_names.csv  (lei, name)

Only LEIs (public identifiers) are sent to GLEIF. Run once; the app reads the CSV.
"""

import json
import os
import urllib.parse
import urllib.request

import duckdb
import pandas as pd

os.makedirs("data", exist_ok=True)

leis = [
    r[0]
    for r in duckdb.sql(
        "SELECT lei FROM read_parquet('hmda_clean.parquet') GROUP BY lei HAVING COUNT(*) >= 200"
    ).fetchall()
]

rows = []
for i in range(0, len(leis), 50):
    batch = leis[i : i + 50]
    params = urllib.parse.urlencode(
        {"filter[lei]": ",".join(batch), "page[size]": 50}
    )
    req = urllib.request.Request(
        f"https://api.gleif.org/api/v1/lei-records?{params}",
        headers={"Accept": "application/vnd.api+json", "User-Agent": "python-urllib"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    for rec in payload["data"]:
        attrs = rec["attributes"]
        rows.append({"lei": attrs["lei"], "name": attrs["entity"]["legalName"]["name"]})

names = pd.DataFrame(rows).drop_duplicates("lei")
missing = set(leis) - set(names["lei"])
print(f"{len(names)} names found, {len(missing)} missing")
names.to_csv("data/lender_names.csv", index=False)
