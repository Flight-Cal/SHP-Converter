from __future__ import annotations

import math

import pydeck as pdk
import streamlit as st

from converter import (
    collect_supported_geometries,
    geojson_bounds,
    load_shapefile,
    records_to_geojson,
    records_to_gpx,
)


st.set_page_config(page_title="SHP to GPX (SkyDemon)", page_icon="🗺️", layout="wide")

st.title("SHP ➜ GPX converter for SkyDemon")
st.write(
    "Upload a zipped shapefile (.zip recommended) or .shp and download a GPX 1.1 "
    "track log that is compatible with SkyDemon."
)

uploaded = st.file_uploader("Shapefile upload", type=["zip", "shp"])
track_prefix = st.text_input("Track name prefix", value="SkyDemon Track")
assume_wgs84 = st.checkbox("Assume WGS84 when .prj is missing", value=False)

if uploaded is not None:
    with st.spinner("Reading shapefile..."):
        try:
            records, prj_text = load_shapefile(uploaded.getvalue(), uploaded.name)
        except Exception as exc:
            st.error(f"Could not read file: {exc}")
            st.stop()

    st.success("Loaded shapefile")
    st.write(f"Features: **{len(records)}**")
    st.write(f"Geometry types: **{', '.join(collect_supported_geometries(records))}**")
    st.write(f"CRS (.prj): **{'present' if prj_text else 'missing'}**")

    st.subheader("Shapefile viewer")
    try:
        geojson = records_to_geojson(records, prj_text, assume_wgs84_if_missing=assume_wgs84)
        bounds = geojson_bounds(geojson)

        if bounds:
            min_lon, min_lat, max_lon, max_lat = bounds
            center_lon = (min_lon + max_lon) / 2
            center_lat = (min_lat + max_lat) / 2
            span = max(max_lon - min_lon, max_lat - min_lat, 0.0001)
            zoom = float(max(1.0, min(12.0, 8.0 - math.log2(span * 25))))
        else:
            center_lon, center_lat, zoom = 0.0, 0.0, 1.0

        layer = pdk.Layer(
            "GeoJsonLayer",
            geojson,
            pickable=True,
            stroked=True,
            filled=True,
            extruded=False,
            line_width_min_pixels=2,
            get_line_color=[255, 100, 50, 220],
            get_fill_color=[0, 140, 255, 70],
            get_point_radius=40,
        )

        deck = pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom),
            layers=[layer],
            tooltip={"text": "{name} ({shape_type})"},
        )
        st.pydeck_chart(deck, use_container_width=True)
        st.caption("Pan and zoom the map to inspect uploaded features.")
    except Exception as exc:
        st.warning(f"Map preview unavailable: {exc}")

    if st.button("Convert to GPX"):
        with st.spinner("Converting to GPX..."):
            try:
                gpx_xml = records_to_gpx(
                    records,
                    prj_text,
                    track_name_prefix=track_prefix,
                    assume_wgs84_if_missing=assume_wgs84,
                )
            except Exception as exc:
                st.error(f"Conversion failed: {exc}")
                st.stop()

        base_name = uploaded.name.rsplit(".", 1)[0]
        output_name = f"{base_name}.gpx"

        st.download_button(
            label="Download GPX",
            data=gpx_xml.encode("utf-8"),
            file_name=output_name,
            mime="application/gpx+xml",
        )

        st.code(gpx_xml[:2000], language="xml")
        st.caption("Preview shows only the first part of the GPX file.")

st.divider()
st.markdown(
    """
### Notes for best SkyDemon compatibility
- GPX requires latitude/longitude in WGS84 (EPSG:4326).
- If `.prj` is missing, conversion can assume WGS84 only when you explicitly enable it.
- For predictable behavior in SkyDemon, Polyline geometries are preferred.
"""
)
