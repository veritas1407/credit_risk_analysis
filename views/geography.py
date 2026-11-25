import numpy as np
import plotly.graph_objects as go
import streamlit as st

import store
import ui

ctx = store.load_state(store.current_state())
S = ctx.s
FIPS = {"MD": "24", "VA": "51", "PA": "42", "DE": "10", "DC": "11", "WV": "54"}

st.title("Geography")
st.write(f"Does where an applicant lives explain walk-aways? Each {ctx.name} county is compared with what its own loan mix predicts "
         "(**O/E**: 1.0 = as expected). Counties with fewer than 1,000 applications are greyed out as too noisy.")

cg = ctx.counties.copy()
cg = cg[cg.county_code != "NA"]
shown = cg[~cg.noisy]
if shown.empty:
    st.warning("No county has 1,000+ applications.")
    st.stop()

ui.kpis([
    dict(label="Counties with 1,000+ applications", value=int(S.counties_ge1000), decimals=0, color="#6EA8FF", sub=f"of {len(cg)} in {ctx.name}"),
    dict(label="Raw walk-away range", value=shown.walkaway_pct.min(), decimals=1, unit="%", color=store.ORANGE, sub=f"to {shown.walkaway_pct.max():.1f}%"),
    dict(label="Mix-adjusted walk-away O/E, lowest", value=shown.wa_oe.min(), decimals=2, color=store.TEAL, sub=f"highest {shown.wa_oe.max():.2f}"),
])

METRICS = {"Walk-away O/E": ("wa_oe", True), "Walk-away %": ("walkaway_pct", False), "Denial O/E": ("den_oe", True),
           "Denial %": ("denial_pct", False), "Applications": ("apps", False)}
metric = st.segmented_control("Colour the map by", list(METRICS), default="Walk-away O/E", required=True, key="geo_metric")
col, centered = METRICS[metric]

gj = store.geojson()
feats = [f for f in gj["features"] if f["id"].startswith(FIPS[ctx.state])]
coords = np.array([pt for f in feats for ring in (f["geometry"]["coordinates"] if f["geometry"]["type"] == "Polygon" else [r for poly in f["geometry"]["coordinates"] for r in poly]) for pt in ring])
lon_min, lat_min = coords.min(axis=0); lon_max, lat_max = coords.max(axis=0)
zoom = float(np.log2(430 / max(lon_max - lon_min, (lat_max - lat_min) * 1.5)))

cg["z"] = cg[col].where(~cg.noisy)
hover = ("<b>%{customdata[0]}</b><br>%{customdata[1]:,} applications<br>Walk-away %{customdata[2]:.1f}% (O/E %{customdata[3]:.2f})"
         "<br>Denial %{customdata[4]:.1f}% (O/E %{customdata[5]:.2f})<br>Largest lender: %{customdata[6]} (%{customdata[7]:.1f}%)<extra></extra>")
cd = np.c_[cg.county, cg.apps, cg.walkaway_pct, cg.wa_oe, cg.denial_pct, cg.den_oe, cg.top_lender.fillna("n/a"), cg.top_share_pct.fillna(0)]
scale = [[0, "#2EE6C5"], [0.5, "#27304A"], [1, "#FF7F32"]] if centered else ([[0, "#1D2F5C"], [1, "#FF7F32"]] if col != "denial_pct" else [[0, "#1D2F5C"], [1, "#FF5C7A"]])
kw = dict(zmid=1) if centered else {}
if centered:
    span = max(abs(cg.z.max() - 1), abs(1 - cg.z.min()), 0.05)
    kw = dict(zmin=1 - span, zmax=1 + span)
fig = go.Figure(go.Choroplethmap(
    geojson={"type": "FeatureCollection", "features": feats}, locations=cg.county_code, z=cg.z, colorscale=scale, marker_opacity=0.85, marker_line_width=0.6,
    marker_line_color="rgba(232,236,245,.45)", customdata=cd, hovertemplate=hover, colorbar=dict(thickness=10, len=0.7, title=dict(text=metric, side="right")), **kw))
fig.update_layout(map=dict(style="carto-darkmatter", center=dict(lat=(lat_min + lat_max) / 2, lon=(lon_min + lon_max) / 2), zoom=zoom))
c1, c2 = st.columns([1.5, 1])
with c1:
    st.plotly_chart(ui.style(fig, 560, legend=False, margin=dict(l=0, r=0, t=0, b=0)), width="stretch", key="geo_map", config={"displayModeBar": False, "scrollZoom": False},
                    alt=f"Map of {ctx.name} counties coloured by {metric}")
with c2:
    st.markdown(f"**Counties ranked by {metric}**")
    rk = shown.sort_values(col).tail(15) if len(shown) > 15 else shown.sort_values(col)
    if centered:
        fig = go.Figure(go.Bar(y=rk.county, x=rk[col] - 1, base=1, orientation="h", marker_color=np.where(rk[col] > 1, store.ORANGE, store.TEAL),
                               text=[f"{v:.2f}" for v in rk[col]], textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{customdata:.2f}<extra></extra>", customdata=rk[col]))
        fig.add_vline(x=1, line=dict(color="rgba(255,255,255,.4)", dash="dot"))
    else:
        fig = go.Figure(go.Bar(y=rk.county, x=rk[col], orientation="h", marker_color=store.ROSE if "Denial" in metric else store.ORANGE,
                               text=[f"{v:,.0f}" if col == "apps" else f"{v:,.1f}" for v in rk[col]], textposition="outside", cliponaxis=False))
    fig.update_xaxes(title=None, **({} if centered else {"rangemode": "tozero"})); fig.update_yaxes(title=None)
    st.plotly_chart(ui.style(fig, 560, legend=False, margin=dict(l=4, r=40, t=4, b=4)), width="stretch", config={"displayModeBar": False}, key="geo_rank", alt="Ranking of counties")

lo, hi = shown.wa_oe.min(), shown.wa_oe.max()
worst = shown.sort_values("den_oe", ascending=False).head(2)
ui.callout(f"<b>Geography matters little once loan mix is removed.</b> Raw walk-away runs from {shown.walkaway_pct.min():.1f}% to {shown.walkaway_pct.max():.1f}% across counties, "
           f"but the observed ÷ expected ratio spans only {lo:.2f}–{hi:.2f}. Denials vary more: {worst.iloc[0].county} has the highest denial O/E ({worst.iloc[0].den_oe:.2f})"
           + (f", then {worst.iloc[1].county} ({worst.iloc[1].den_oe:.2f})" if len(worst) > 1 else "") + ".", "good")
tbl = ctx.counties.copy()
st.dataframe(tbl[["county", "apps", "walkaway_pct", "wa_oe", "denial_pct", "den_oe", "purchase_share", "top_lender", "top_share_pct", "noisy"]], hide_index=True, width="stretch",
             column_config={"county": "County", "apps": st.column_config.NumberColumn("Applications", format="%d"),
                            "walkaway_pct": st.column_config.NumberColumn("Walk-away %", format="%.1f"), "wa_oe": st.column_config.NumberColumn("Walk-away O/E", format="%.2f"),
                            "denial_pct": st.column_config.NumberColumn("Denial %", format="%.1f"), "den_oe": st.column_config.NumberColumn("Denial O/E", format="%.2f"),
                            "purchase_share": st.column_config.NumberColumn("Purchase share %", format="%.1f"), "top_lender": "Largest lender",
                            "top_share_pct": st.column_config.NumberColumn("Its share %", format="%.1f"), "noisy": st.column_config.CheckboxColumn("Under 1,000 apps")})
st.caption("'County not reported' is a data gap, not a place. Largest lenders hold a small share of each county, so no county is dominated by one lender.")
