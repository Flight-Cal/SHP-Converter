from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import shapefile  # pyshp
from pyproj import CRS, Transformer


@dataclass(frozen=True)
class ShapeRecordData:
    """Normalized shape + attribute payload extracted from a shapefile."""

    shape_type_name: str
    points: list[tuple[float, float]]
    parts: list[int]
    attrs: dict[str, object]


def load_shapefile(upload_bytes: bytes, filename: str) -> tuple[list[ShapeRecordData], str | None]:
    """Load shape records from .zip or .shp upload and return records + optional .prj text."""
    suffix = Path(filename).suffix.lower()

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        uploaded = tmp_path / filename
        uploaded.write_bytes(upload_bytes)

        if suffix == ".zip":
            with ZipFile(uploaded, "r") as archive:
                archive.extractall(tmp_path / "unzipped")
            shp_files = list((tmp_path / "unzipped").rglob("*.shp"))
            if not shp_files:
                raise ValueError("The ZIP file does not contain any .shp file.")
            shp_path = shp_files[0]
        elif suffix == ".shp":
            shp_path = uploaded
        else:
            raise ValueError("Please upload either a .zip containing shapefile parts or a .shp file.")

        reader = shapefile.Reader(str(shp_path))
        field_names = [f[0] for f in reader.fields[1:]]
        shape_records: list[ShapeRecordData] = []

        for sr in reader.iterShapeRecords():
            attrs = dict(zip(field_names, sr.record))
            shape_records.append(
                ShapeRecordData(
                    shape_type_name=sr.shape.shapeTypeName,
                    points=[(float(x), float(y)) for x, y in sr.shape.points],
                    parts=list(sr.shape.parts),
                    attrs=attrs,
                )
            )

        if not shape_records:
            raise ValueError("The shapefile was loaded but contains no features.")

        prj_path = shp_path.with_suffix(".prj")
        prj_text = prj_path.read_text(encoding="utf-8", errors="ignore") if prj_path.exists() else None

    return shape_records, prj_text


def _ensure_wgs84_points(
    records: list[ShapeRecordData],
    prj_text: str | None,
    assume_wgs84_if_missing: bool,
) -> list[ShapeRecordData]:
    """Reproject shape points into EPSG:4326, or optionally assume input is already WGS84."""
    if prj_text is None:
        if not assume_wgs84_if_missing:
            raise ValueError(
                "No .prj CRS file found. Either upload a shapefile with CRS info or enable "
                "'Assume WGS84 when .prj is missing'."
            )
        return records

    source_crs = CRS.from_wkt(prj_text)
    target_crs = CRS.from_epsg(4326)
    if source_crs == target_crs:
        return records

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    converted: list[ShapeRecordData] = []

    for rec in records:
        converted_points = [transformer.transform(x, y) for x, y in rec.points]
        converted.append(
            ShapeRecordData(
                shape_type_name=rec.shape_type_name,
                points=[(float(x), float(y)) for x, y in converted_points],
                parts=rec.parts,
                attrs=rec.attrs,
            )
        )

    return converted


def _build_track_name(feature_index: int, attributes: dict[str, object]) -> str:
    preferred_fields = ("name", "Name", "track", "Track", "id", "ID")
    for key in preferred_fields:
        value = attributes.get(key)
        if value is not None and str(value).strip() and str(value).lower() != "nan":
            return str(value)
    return f"Track {feature_index + 1}"


def _segments_from_record(record: ShapeRecordData) -> list[list[tuple[float, float]]]:
    """Convert pyshp record types into one or more lon/lat coordinate segments."""
    t = record.shape_type_name.upper()
    points = record.points
    if not points:
        return []

    if t in {"POLYLINE", "POLYLINEZ", "POLYLINEM", "POLYLINEZM"}:
        part_indexes = record.parts + [len(points)]
        return [points[part_indexes[i] : part_indexes[i + 1]] for i in range(len(part_indexes) - 1)]

    if t in {"POLYGON", "POLYGONZ", "POLYGONM", "POLYGONZM"}:
        part_indexes = record.parts + [len(points)]
        return [points[part_indexes[i] : part_indexes[i + 1]] for i in range(len(part_indexes) - 1)]

    if t in {"POINT", "POINTZ", "POINTM"}:
        return [[points[0]]]

    return []


def records_to_geojson(
    records: list[ShapeRecordData],
    prj_text: str | None,
    assume_wgs84_if_missing: bool = False,
) -> dict:
    """Convert records into WGS84 GeoJSON for map display."""
    wgs84_records = _ensure_wgs84_points(records, prj_text, assume_wgs84_if_missing)
    features: list[dict] = []

    for idx, rec in enumerate(wgs84_records):
        segments = [seg for seg in _segments_from_record(rec) if seg]
        if not segments:
            continue

        kind = rec.shape_type_name.upper()
        props = {
            "name": _build_track_name(idx, rec.attrs),
            "shape_type": rec.shape_type_name,
        }

        if kind.startswith("POINT"):
            geom = {"type": "Point", "coordinates": [segments[0][0][0], segments[0][0][1]]}
        elif kind.startswith("POLYGON"):
            rings = [[[lon, lat] for lon, lat in seg] for seg in segments]
            geom = {"type": "Polygon", "coordinates": rings}
        elif len(segments) == 1:
            geom = {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in segments[0]]}
        else:
            geom = {
                "type": "MultiLineString",
                "coordinates": [[[lon, lat] for lon, lat in seg] for seg in segments],
            }

        features.append({"type": "Feature", "properties": props, "geometry": geom})

    return {"type": "FeatureCollection", "features": features}


def geojson_bounds(geojson: dict) -> tuple[float, float, float, float] | None:
    """Return (min_lon, min_lat, max_lon, max_lat) for a FeatureCollection."""
    all_points: list[tuple[float, float]] = []

    def add_points(coords):
        if isinstance(coords, list) and coords and isinstance(coords[0], (int, float)):
            all_points.append((float(coords[0]), float(coords[1])))
            return
        for item in coords or []:
            add_points(item)

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates")
        if coords is not None:
            add_points(coords)

    if not all_points:
        return None

    lons = [p[0] for p in all_points]
    lats = [p[1] for p in all_points]
    return min(lons), min(lats), max(lons), max(lats)


def records_to_gpx(
    records: list[ShapeRecordData],
    prj_text: str | None,
    track_name_prefix: str = "SHP Track",
    assume_wgs84_if_missing: bool = False,
) -> str:
    """Convert shape records into a GPX 1.1 document with track segments."""
    records = _ensure_wgs84_points(records, prj_text, assume_wgs84_if_missing)

    ET.register_namespace("", "http://www.topografix.com/GPX/1/1")
    root = ET.Element(
        "{http://www.topografix.com/GPX/1/1}gpx",
        attrib={
            "version": "1.1",
            "creator": "SHP-to-GPX Streamlit Converter",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": (
                "http://www.topografix.com/GPX/1/1 "
                "http://www.topografix.com/GPX/1/1/gpx.xsd"
            ),
        },
    )

    metadata = ET.SubElement(root, "{http://www.topografix.com/GPX/1/1}metadata")
    time_elem = ET.SubElement(metadata, "{http://www.topografix.com/GPX/1/1}time")
    time_elem.text = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    tracks_added = 0
    for i, record in enumerate(records):
        segments = [seg for seg in _segments_from_record(record) if seg]
        if not segments:
            continue

        trk = ET.SubElement(root, "{http://www.topografix.com/GPX/1/1}trk")
        name = ET.SubElement(trk, "{http://www.topografix.com/GPX/1/1}name")
        name.text = f"{track_name_prefix}: {_build_track_name(i, record.attrs)}"

        for segment in segments:
            trkseg = ET.SubElement(trk, "{http://www.topografix.com/GPX/1/1}trkseg")
            for lon, lat in segment:
                ET.SubElement(
                    trkseg,
                    "{http://www.topografix.com/GPX/1/1}trkpt",
                    attrib={"lat": f"{lat:.8f}", "lon": f"{lon:.8f}"},
                )

        tracks_added += 1

    if tracks_added == 0:
        raise ValueError("No supported geometries found. Use Polyline, Polygon, or Point shapefiles.")

    _indent_xml(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    indent = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        for child in elem:
            _indent_xml(child, level + 1)
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = indent
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = indent


def collect_supported_geometries(records: list[ShapeRecordData]) -> Iterable[str]:
    return sorted({r.shape_type_name for r in records})
