from __future__ import annotations

from converter import ShapeRecordData, geojson_bounds, records_to_geojson, records_to_gpx


def test_generates_gpx_tracks_for_polyline_parts() -> None:
    records = [
        ShapeRecordData(
            shape_type_name="POLYLINE",
            points=[(7.0, 50.0), (7.1, 50.1), (8.0, 51.0), (8.1, 51.1)],
            parts=[0, 2],
            attrs={"name": "Alpha"},
        )
    ]

    gpx = records_to_gpx(records, prj_text=None, track_name_prefix="SkyDemon", assume_wgs84_if_missing=True)

    assert "<gpx" in gpx
    assert "<trk>" in gpx
    assert "SkyDemon: Alpha" in gpx
    assert gpx.count("<trkseg>") == 2


def test_geojson_bounds_for_points() -> None:
    records = [
        ShapeRecordData(shape_type_name="POINT", points=[(-1.0, 10.0)], parts=[0], attrs={}),
        ShapeRecordData(shape_type_name="POINT", points=[(2.0, 20.0)], parts=[0], attrs={}),
    ]

    geojson = records_to_geojson(records, prj_text=None, assume_wgs84_if_missing=True)
    bounds = geojson_bounds(geojson)

    assert bounds == (-1.0, 10.0, 2.0, 20.0)


def test_missing_prj_raises_error_by_default() -> None:
    records = [
        ShapeRecordData(
            shape_type_name="POINT",
            points=[(7.0, 50.0)],
            parts=[0],
            attrs={},
        )
    ]

    try:
        records_to_gpx(records, prj_text=None)
    except ValueError as exc:
        assert "No .prj" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing .prj")
