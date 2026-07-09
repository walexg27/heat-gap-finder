"""
San Diego County — Heat-Relief Gap Finder
An interactive map identifying census tracts most in need of a new cooling or
water site: high heat exposure + social vulnerability, far from existing relief,
and populated.

Data: U.S. Census (ACS 2020-2024), CDC/ATSDR SVI 2022, Landsat land-surface
temperature (Google Earth Engine), San Diego County Cool Zones, OpenStreetMap.
"""
import json
import pandas as pd
import streamlit as st
import folium
from folium.features import GeoJson, GeoJsonTooltip
from streamlit_folium import st_folium
import branca.colormap as cm

st.set_page_config(page_title="San Diego Heat-Relief Gap Finder", layout="wide")

st.title("San Diego County — Heat-Relief Gap Finder")
st.caption(
    "Screening tool: which census tracts most need a new cooling or water site? "
    "Combines heat exposure, social vulnerability, population, and distance to "
    "existing relief. Data: U.S. Census, CDC SVI, Landsat land-surface temperature, "
    "San Diego County Cool Zones, and OpenStreetMap."
)


@st.cache_data
def load_data():
    with open("sd_app.geojson") as f:
        tracts = json.load(f)
    with open("coolzones.geojson") as f:
        cool = json.load(f)
    df = pd.DataFrame([feat["properties"] for feat in tracts["features"]])
    return tracts, cool, df


tracts, cool, df = load_data()

METRICS = {
    "Priority for a new site":            "priority_v2",
    "Composite heat-risk (SVI x heat)":   "risk_score",
    "Land-surface temperature (F)":       "mean_lst_f",
    "Distance to nearest relief (km)":    "dist_service_km",
    "Poverty rate":                       "poverty_rate",
    "% households with no vehicle":       "pct_no_vehicle",
}

label   = st.sidebar.selectbox("Color the map by:", list(METRICS.keys()))
metric  = METRICS[label]
show_cz = st.sidebar.checkbox("Show existing Cool Zones", value=True)
topn    = st.sidebar.slider("Rank the top N tracts", 5, 30, 8)

# color scale for the selected metric
vals = df[metric].dropna()
colormap = cm.linear.YlOrRd_09.scale(float(vals.min()), float(vals.max()))
colormap.caption = label


def style_fn(feature):
    v = feature["properties"].get(metric)
    return {
        "fillColor": colormap(v) if v is not None else "#cccccc",
        "color": "white", "weight": 0.3, "fillOpacity": 0.8,
    }


m = folium.Map(location=[32.9, -116.9], zoom_start=9, tiles="cartodbpositron")
GeoJson(
    tracts,
    style_function=style_fn,
    tooltip=GeoJsonTooltip(
        fields=["NAMELSAD", "priority_v2", "risk_score", "mean_lst_f",
                "dist_service_km", "population"],
        aliases=["Tract:", "Priority:", "Risk:", "Temp (F):",
                 "Dist to relief (km):", "Population:"],
        localize=True,
    ),
).add_to(m)
colormap.add_to(m)

if show_cz:
    for feat in cool["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        folium.CircleMarker(
            [lat, lon], radius=3, color="#0066cc", fill=True, fill_opacity=0.9,
            popup=feat["properties"].get("Organization", "Cool Zone"),
        ).add_to(m)

left, right = st.columns([3, 2])
with left:
    st_folium(m, width=720, height=600)
with right:
    st.subheader(f"Top {topn} tracts by: {label}")
    table = (
        df.sort_values(metric, ascending=False)
          .head(topn)[["NAMELSAD", metric, "population"]]
          .rename(columns={"NAMELSAD": "Tract", metric: label})
    )
    st.dataframe(table, hide_index=True, use_container_width=True)

st.caption(
    "Limitations: this is a decision-support screening tool that identifies candidate "
    "underserved areas, not a proven optimal site. Land-surface temperature is surface "
    "(not air) temperature; cooling-center coverage is seasonal and non-exhaustive."
)
