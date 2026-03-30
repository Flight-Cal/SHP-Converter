from __future__ import annotations

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString

from converter import geodataframe_to_gpx


def test_generates_gpx_tracks_for_lines() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "name": ["Alpha", "Beta"],
            "geometry": [
                LineString([(7.0, 50.0), (7.1, 50.1)]),
                MultiLineString([[(8.0, 51.0), (8.2, 51.2)], [(8.3, 51.3), (8.4, 51.4)]]),
            ],
        },
        crs="EPSG:4326",
    )

    gpx = geodataframe_to_gpx(gdf, track_name_prefix="SkyDemon")

    assert "<gpx" in gpx
    assert "<trk>" in gpx
    assert "SkyDemon: Alpha" in gpx
    assert "SkyDemon: Beta" in gpx
    assert gpx.count("<trkseg>") == 3


def test_missing_crs_raises_error() -> None:
    gdf = gpd.GeoDataFrame(
        {"geometry": [LineString([(7.0, 50.0), (7.1, 50.1)])]},
    )

    try:
        geodataframe_to_gpx(gdf)
    except ValueError as exc:
        assert "no CRS" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing CRS")
