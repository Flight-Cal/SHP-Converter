from __future__ import annotations

import streamlit as st

from converter import collect_supported_geometries, geodataframe_to_gpx, load_shapefile


st.set_page_config(page_title="SHP to GPX (SkyDemon)", page_icon="🗺️", layout="centered")

st.title("SHP ➜ GPX converter for SkyDemon")
st.write(
    "Upload a zipped shapefile (.zip) or .shp and download a GPX 1.1 track log "
    "that is compatible with SkyDemon."
)

uploaded = st.file_uploader("Shapefile upload", type=["zip", "shp"])
track_prefix = st.text_input("Track name prefix", value="SkyDemon Track")

if uploaded is not None:
    with st.spinner("Reading shapefile..."):
        try:
            gdf = load_shapefile(uploaded.getvalue(), uploaded.name)
        except Exception as exc:
            st.error(f"Could not read file: {exc}")
            st.stop()

    st.success("Loaded shapefile")
    st.write(f"Features: **{len(gdf)}**")
    st.write(f"Geometry types: **{', '.join(collect_supported_geometries(gdf))}**")
    st.write(f"Input CRS: **{gdf.crs}**")

    if st.button("Convert to GPX"):
        with st.spinner("Converting to GPX..."):
            try:
                gpx_xml = geodataframe_to_gpx(gdf, track_name_prefix=track_prefix)
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
- GPX requires latitude/longitude in WGS84 (EPSG:4326). This app auto-reprojects if CRS is present.
- Keep geometries as LineString/MultiLineString for best route/track behavior.
- If your shapefile has no CRS info (.prj), conversion is blocked until CRS is fixed.
"""
)
