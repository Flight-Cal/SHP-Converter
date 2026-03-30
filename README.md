# SHP to GPX Converter (SkyDemon compatible)

A Streamlit app that converts uploaded shapefiles into GPX 1.1 track logs intended for use in SkyDemon.

## Why this dependency set works better on Streamlit Cloud

This app intentionally avoids `fiona`/`gdal` and `geopandas` runtime requirements so it can install reliably on Streamlit Community Cloud (including Python 3.14 images), where compiling GDAL-backed dependencies may fail.

## Features

- Upload `.zip` shapefile bundles (recommended) or single `.shp` files.
- Reads shapefiles with pure-Python `pyshp`.
- Reprojects to WGS84 (EPSG:4326) when `.prj` CRS data is available.
- Optional fallback to assume WGS84 when `.prj` is missing.
- Interactive global map viewer (pan/zoom) showing uploaded features before conversion.
- Outputs GPX 1.1 `<trk>`/`<trkseg>` format for track logs.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create a new app pointing to this repo.
3. Set `app.py` as the main file.

## Notes for SkyDemon

- SkyDemon imports GPX tracks from standard GPX 1.1 files.
- For most predictable results, prefer Polyline source geometries.
- If `.prj` is missing, only enable “assume WGS84” when you are certain coordinates are already lon/lat WGS84.
