from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point, Polygon


@dataclass(frozen=True)
class TrackSegment:
    """A normalized sequence of (lon, lat) coordinates used for GPX track segments."""

    coordinates: list[tuple[float, float]]


def load_shapefile(upload_bytes: bytes, filename: str) -> gpd.GeoDataFrame:
    """Load a shapefile from an uploaded zip or .shp stream into a GeoDataFrame."""
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

        gdf = gpd.read_file(shp_path)

    if gdf.empty:
        raise ValueError("The shapefile was loaded but contains no features.")

    return gdf


def _geometry_to_segments(geometry) -> list[TrackSegment]:
    """Convert supported geometries into one or more GPX track segments."""
    segments: list[TrackSegment] = []

    if isinstance(geometry, LineString):
        segments.append(TrackSegment(coordinates=list(geometry.coords)))
    elif isinstance(geometry, MultiLineString):
        for line in geometry.geoms:
            segments.append(TrackSegment(coordinates=list(line.coords)))
    elif isinstance(geometry, Polygon):
        # Use the polygon's exterior ring as a track segment.
        segments.append(TrackSegment(coordinates=list(geometry.exterior.coords)))
    elif isinstance(geometry, Point):
        # For a point, create a one-point track segment.
        segments.append(TrackSegment(coordinates=[(geometry.x, geometry.y)]))
    else:
        # Geometry type not supported for track conversion.
        return []

    return [s for s in segments if len(s.coordinates) > 0]


def _build_track_name(feature_index: int, attributes: dict) -> str:
    """Infer a readable track name from common fields, with a stable fallback."""
    preferred_fields = ("name", "Name", "track", "Track", "id", "ID")
    for key in preferred_fields:
        value = attributes.get(key)
        if value is not None and str(value).strip() and str(value).lower() != "nan":
            return str(value)
    return f"Track {feature_index + 1}"


def _ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ensure data are in WGS84 (EPSG:4326), the coordinate system expected by GPX."""
    if gdf.crs is None:
        raise ValueError(
            "The shapefile has no CRS information (.prj missing or unreadable). "
            "Please provide a valid CRS so it can be converted to WGS84."
        )

    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


def geodataframe_to_gpx(gdf: gpd.GeoDataFrame, track_name_prefix: str = "SHP Track") -> str:
    """Convert a GeoDataFrame into a GPX 1.1 document containing tracks and segments."""
    gdf = _ensure_wgs84(gdf)

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

    for i, row in gdf.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue

        segments = _geometry_to_segments(geometry)
        if not segments:
            continue

        trk = ET.SubElement(root, "{http://www.topografix.com/GPX/1/1}trk")
        name = ET.SubElement(trk, "{http://www.topografix.com/GPX/1/1}name")
        attrs = row.drop(labels=["geometry"]).to_dict()
        inferred_name = _build_track_name(i, attrs)
        name.text = f"{track_name_prefix}: {inferred_name}"

        for segment in segments:
            trkseg = ET.SubElement(trk, "{http://www.topografix.com/GPX/1/1}trkseg")
            for lon, lat, *rest in segment.coordinates:
                trkpt = ET.SubElement(
                    trkseg,
                    "{http://www.topografix.com/GPX/1/1}trkpt",
                    attrib={"lat": f"{lat:.8f}", "lon": f"{lon:.8f}"},
                )
                if rest:
                    ele = ET.SubElement(trkpt, "{http://www.topografix.com/GPX/1/1}ele")
                    ele.text = f"{float(rest[0]):.2f}"

        tracks_added += 1

    if tracks_added == 0:
        raise ValueError("No supported geometries were found. Use LineString, MultiLineString, Polygon, or Point.")

    _indent_xml(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """In-place pretty-print indentation for XML serialization."""
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


def collect_supported_geometries(gdf: gpd.GeoDataFrame) -> Iterable[str]:
    """Return sorted geometry types present in the file."""
    return sorted({str(geom_type) for geom_type in gdf.geom_type.unique()})
