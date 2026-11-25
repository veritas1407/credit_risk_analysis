"""
fetch_lender_names.py: map lender LEIs to legal names using the public GLEIF registry.

Input : hmda_clean.parquet (lenders with >= 200 applications in any state + top lender per county)
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

# lenders with >= 200 applications, plus the largest lender in every county (shown in the app)
leis = [
    r[0]
    for r in duckdb.sql("""
        WITH cl AS (SELECT state, county_code, lei, COUNT(*) AS n FROM read_parquet('hmda_clean.parquet') GROUP BY ALL),
             top AS (SELECT lei FROM cl
                     WHERE n = (SELECT MAX(n) FROM cl c2 WHERE c2.state = cl.state AND c2.county_code = cl.county_code)),
             big AS (SELECT lei FROM read_parquet('hmda_clean.parquet') GROUP BY state, lei HAVING COUNT(*) >= 200)
        SELECT lei FROM big UNION SELECT lei FROM top
    """).fetchall()
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
