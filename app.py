"""
San Diego County - Heat-Relief Gap Finder
Interactive map: which census tracts most need a new cooling or water site.
Combines heat (day surface, night surface, air temperature), social vulnerability,
population, and distance to existing relief.

Data: U.S. Census (ACS 2020-2024), CDC/ATSDR SVI 2022, Landsat + MODIS + Daymet
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

st.title("San Diego County - Heat-Relief Gap Finder")
st.caption(
    "A screening tool for where a new cooling or water site is most needed. "
    "It combines heat exposure, social vulnerability, population, and distance to "
    "existing relief. Data: U.S. Census, CDC SVI, satellite and modeled temperature, "
    "San Diego County Cool Zones, and OpenStreetMap."
)


@st.cache_data
def load_data():
    with open("sd_tracts.geojson") as f:
        tracts = json.load(f)
    with open("coolzones.geojson") as f:
        cool = json.load(f)
    df = pd.DataFrame([feat["properties"] for feat in tracts["features"]])
    return tracts, cool, df


tracts, cool, df = load_data()

# ---------- Layer menu: main layers on top, alternates grouped below ----------
st.sidebar.header("Map layer")

PRIMARY = {
    "Priority (recommended)":   "priority_multi",
    "Confidence (Monte Carlo)": "sel_prob",
    "Heat - daytime surface":   "mean_lst_f",
    "Vulnerability + heat":     "risk_score",
    "Distance to relief":       "dist_service_km",
}
PRIMARY_CAPTIONS = [
    "The headline. Where a new site is most needed, using the blended heat measure.",
    "How often a tract is top-priority across 5,000 randomized runs (1.0 = every run).",
    "Satellite land-surface temperature on a summer day.",
    "Composite of social vulnerability (CDC SVI) and heat.",
    "Kilometers from the tract to its nearest Cool Zone or water point.",
]
primary = st.sidebar.radio("Main layers", list(PRIMARY.keys()), captions=PRIMARY_CAPTIONS)

SECONDARY = {
    "- use main layer above -":         None,
    "Priority - daytime heat only":     "priority_v2",
    "Heat - nighttime surface":         "night_lst_f",
    "Heat - air temperature":           "air_tmax_f",
    "Vulnerability - poverty rate":     "poverty_rate",
    "Vulnerability - no-vehicle share": "pct_no_vehicle",
}
secondary = st.sidebar.selectbox(
    "More layers", list(SECONDARY.keys()),
    help=("Alternate versions grouped by theme. "
          "Priority: daytime-only vs the blended-heat version up top. "
          "Heat: nighttime surface and air temperature. "
          "Vulnerability: the raw poverty and vehicle-access components. "
          "Pick one to override the main layer above."),
)

DESCRIPTIONS = {
    "priority_multi":  "Blended-heat priority = risk x service gap x population.",
    "sel_prob":        "Share of 5,000 randomized model runs where the tract was top-20.",
    "mean_lst_f":      "Daytime land-surface temperature (Landsat), warm season, deg F.",
    "risk_score":      "Composite of CDC social vulnerability and heat (0 to 1).",
    "dist_service_km": "Distance to the nearest Cool Zone or water point (km).",
    "priority_v2":     "Priority using only daytime surface heat.",
    "night_lst_f":     "Nighttime land-surface temperature (MODIS), warm season, deg F.",
    "air_tmax_f":      "Modeled daily-high air temperature (Daymet), warm season, deg F.",
    "poverty_rate":    "Share of residents below the poverty line (ACS).",
    "pct_no_vehicle":  "Share of households with no vehicle (ACS).",
}

metric = SECONDARY[secondary] if SECONDARY[secondary] else PRIMARY[primary]
label  = secondary if SECONDARY[secondary] else primary
st.sidebar.caption("Showing: " + DESCRIPTIONS.get(metric, ""))

show_cz = st.sidebar.checkbox("Show existing Cool Zones", value=True)
topn    = st.sidebar.slider("Rank the top N tracts", 5, 30, 8)

# ---------- Map ----------
vals = df[metric].dropna()
colormap = cm.linear.YlOrRd_09.scale(float(vals.min()), float(vals.max()))
colormap.caption = label


def style_fn(feature):
    v = feature["properties"].get(metric)
    return {"fillColor": colormap(v) if v is not None else "#cccccc",
            "color": "white", "weight": 0.3, "fillOpacity": 0.8}


m = folium.Map(location=[32.9, -116.9], zoom_start=9, tiles="cartodbpositron")
GeoJson(
    tracts, style_function=style_fn,
    tooltip=GeoJsonTooltip(
        fields=["area", "priority_multi", "sel_prob", "mean_lst_f", "night_lst_f",
                "air_tmax_f", "dist_service_km", "population"],
        aliases=["Area:", "Priority:", "Confidence:", "Day temp (F):", "Night temp (F):",
                 "Air temp (F):", "Dist to relief (km):", "Population:"],
        localize=True),
).add_to(m)
colormap.add_to(m)

if show_cz:
    for feat in cool["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        folium.CircleMarker([lat, lon], radius=3, color="#0066cc", fill=True,
                            fill_opacity=0.9,
                            popup=feat["properties"].get("Organization", "Cool Zone")).add_to(m)

left, right = st.columns([3, 2])
with left:
    st_folium(m, width=720, height=600)
with right:
    st.subheader(f"Top {topn} tracts by: {label}")
    st.dataframe(
        df.sort_values(metric, ascending=False)
          .head(topn)[["area", metric, "population"]]
          .rename(columns={"area": "Area", metric: label}),
        hide_index=True, use_container_width=True)

st.caption(
    "Screening tool: it flags candidate underserved areas, not a proven optimal site. "
    "Surface temperature is not air temperature, so the app reports day, night, air, and a "
    "blended measure. Cooling-center coverage is seasonal and not exhaustive."
)
