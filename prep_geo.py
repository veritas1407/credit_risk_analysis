"""
prep_geo.py: county names and map geometry for the six states in the app.

Downloads (public files, nothing about this project is sent):
    Census county codes   https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt
    US county GeoJSON     https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json
                          (Census cartographic boundaries, includes Virginia's independent cities)

Writes:
    data/county_names.csv        fips, state, county
    data/counties.geojson        GeoJSON FeatureCollection (feature id = 5-digit county FIPS), coordinates rounded to 3 dp

Run once:  python prep_geo.py
"""

import json
import os
import urllib.request

import pandas as pd

STATES = {"24": "MD", "51": "VA", "42": "PA", "10": "DE", "11": "DC", "54": "WV"}
URLS = {
    "raw_data/national_county2020.txt": "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt",
    "raw_data/geojson-counties-fips.json": "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
}

os.makedirs("raw_data", exist_ok=True)
os.makedirs("data", exist_ok=True)
for path, url in URLS.items():
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)

# ---------------------------------------------------------------- names
names = pd.read_csv("raw_data/national_county2020.txt", sep="|", dtype=str)
names = names[names.STATEFP.isin(STATES)].copy()
names["fips"] = names.STATEFP + names.COUNTYFP
names["state"] = names.STATEFP.map(STATES)
names["county"] = names.COUNTYNAME.str.replace(r" (County|Parish)$", "", regex=True)
# Virginia independent cities keep the word "city"; Baltimore City is a city, not a county
names.loc[names.COUNTYNAME.str.endswith("city"), "county"] = names.COUNTYNAME
names[["fips", "state", "county"]].sort_values("fips").to_csv("data/county_names.csv", index=False)


# ---------------------------------------------------------------- geometry
def round_coords(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 3), round(c[1], 3)]
    return [round_coords(x) for x in c]


src = json.load(open("raw_data/geojson-counties-fips.json"))
features = []
for f in src["features"]:
    if f["id"][:2] in STATES:
        geom = {"type": f["geometry"]["type"], "coordinates": round_coords(f["geometry"]["coordinates"])}
        features.append({"type": "Feature", "id": f["id"], "properties": {"fips": f["id"]}, "geometry": geom})

json.dump({"type": "FeatureCollection", "features": features}, open("data/counties.geojson", "w"),
          separators=(",", ":"))
missing = sorted(set(names.fips) - {f["id"] for f in features})
print(f"{len(names)} county names, {len(features)} county shapes; names without a shape: {missing}")
