# SHP to GPX Converter (SkyDemon compatible)

A Streamlit app that converts uploaded shapefiles into GPX 1.1 track logs intended for use in SkyDemon.

## Features

- Upload `.zip` shapefile bundles or single `.shp` files.
- Reprojects to WGS84 (EPSG:4326) when needed.
- Outputs GPX 1.1 `<trk>`/`<trkseg>` format for track logs.
- Uses attribute-based naming when available (`name`, `track`, `id`, etc.).

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

- SkyDemon generally imports GPX tracks from standard GPX 1.1 files.
- For predictable results, prefer line-based geometries in the source shapefile.
- If CRS is missing, ensure the source data includes `.prj` before upload.
