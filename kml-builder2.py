"""
ArcGIS Feature Service -> iNaturalist-ready KML

Designed for iNaturalist Place boundaries.

Main goals:
    * One KML Place boundary
    * MultiPolygon / MultiGeometry support
    * No overlapping polygons
    * No duplicate internal boundaries
    * Remove tiny slivers
    * Repair invalid geometry
    * Snap nearly coincident vertices
    * Simplify geometry to meet iNaturalist's KML size limit
    * Validate topology before writing
    * Write WGS84 KML

Requirements:

    pip install requests shapely pyproj lxml

Tested with:
    Shapely 2.x
    pyproj 3.x
    requests
    lxml

IMPORTANT:
    Set WORKING_CRS to an appropriate projected CRS for your data.

    For example:
        Massachusetts / New England:
            EPSG:26986  (Massachusetts Mainland State Plane, meters)

        UTM zone 18N:
            EPSG:32618

    Do NOT perform topology operations in EPSG:4326.
"""

from __future__ import annotations

import sys
import importlib

import math
import os
from pathlib import Path

import requests

from lxml import etree

from pyproj import Transformer

from shapely.geometry import (
    shape,
    Polygon,
    MultiPolygon,
    GeometryCollection,
)

from shapely.ops import (
    transform,
    unary_union,
    polygonize,
)

from shapely.validation import make_valid


# =============================================================================
# USER CONFIGURATION
# =============================================================================

FEATURE_SERVICE_URL = (
    "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/"
    "Massachusetts_Property_Tax_Parcels/FeatureServer/0"
)

PLACE = importlib.import_module('places.'+sys.argv[1])

WHERE_CLAUSE = PLACE.WHERE_CLAUSE
OUTPUT_KML = PLACE.OUTPUT_KML
PLACE_NAME = PLACE.PLACE_NAME

OUTPUT_KML = f'kml-files/{OUTPUT_KML}'

# -------------------------------------------------------------------------
# Coordinate systems
# -------------------------------------------------------------------------

SOURCE_CRS = "EPSG:4326"       # CRS of the coordinates coming from ArcGIS
WORKING_CRS = "EPSG:26986"     # Projected CRS used for topology/geometry work
OUTPUT_CRS = "EPSG:4326"       # WGS84 lat/lon for the final KML

# -------------------------------------------------------------------------
# Topology parameters
# -------------------------------------------------------------------------

# Coordinates closer than this are snapped together.
#
# Units are the units of WORKING_CRS.
#
# For a meter-based CRS:
#     0.01 = 1 centimeter
#     0.10 = 10 centimeters
#     1.00 = 1 meter
#
# Do NOT make this unnecessarily large.
SNAP_TOLERANCE = 0.10


# Any polygon smaller than this will be considered a sliver.
#
# Square meters when using a meter-based CRS.
MIN_SLIVER_AREA = 1.0


# -------------------------------------------------------------------------
# KML simplification
# -------------------------------------------------------------------------

# iNaturalist currently documents a 1 MB KML limit for ordinary users
# and 5 MB for Curators.
#
# We target substantially below 1 MB to leave some safety margin.
TARGET_KML_BYTES = 900_000


# First simplification tolerance.
#
# Units = WORKING_CRS units.
INITIAL_SIMPLIFY_TOLERANCE = 0.25


# Maximum simplification tolerance we are willing to use automatically.
MAX_SIMPLIFY_TOLERANCE = 100.0


# How many times to increase simplification tolerance.
MAX_SIMPLIFICATION_ITERATIONS = 20


# KML coordinate decimal places.
#
# 6 decimal places is roughly centimeter-ish to meter-ish depending
# on latitude, and dramatically reduces file size compared with
# excessive precision.
KML_DECIMAL_PLACES = 6


# =============================================================================
# ARC GIS DOWNLOAD
# =============================================================================

def get_arcgis_metadata(service_url: str) -> dict:
    response = requests.get(
        service_url,
        params={"f": "json"},
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    return data


def get_arcgis_features(service_url: str) -> list[dict]:
    """
    Download all features from an ArcGIS Feature Service.

    Uses object IDs so this works with services that impose
    maxRecordCount limits.
    """

    metadata = get_arcgis_metadata(service_url)

    object_id_field = metadata.get(
        "objectIdField"
    )

    if not object_id_field:
        raise RuntimeError(
            "Could not determine ArcGIS object ID field."
        )

    query_url = f"{service_url}/query"

    # ---------------------------------------------------------------------
    # Get object IDs
    # ---------------------------------------------------------------------

    response = requests.get(
        query_url,
        params={
            "where": WHERE_CLAUSE,
            "returnIdsOnly": "true",
            "f": "json",
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    object_ids = data.get("objectIds", [])

    if not object_ids:
        return []

    object_ids.sort()

    # ---------------------------------------------------------------------
    # Determine service record limit
    # ---------------------------------------------------------------------

    batch_size = metadata.get(
        "maxRecordCount",
        500,
    )

    batch_size = min(
        int(batch_size),
        1000,
    )

    features = []

    # ---------------------------------------------------------------------
    # Download features in batches
    # ---------------------------------------------------------------------

    for start in range(
        0,
        len(object_ids),
        batch_size,
    ):

        batch = object_ids[
            start:start + batch_size
        ]

        params = {
            "objectIds": ",".join(
                str(x) for x in batch
            ),
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": int(SOURCE_CRS.split(':')[-1]),
            "f": "geojson",
        }

        response = requests.get(
            query_url,
            params=params,
            timeout=180,
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        features.extend(
            data.get("features", [])
        )

        print(
            f"Downloaded {len(features):,} "
            f"of {len(object_ids):,} features..."
        )

    return features


# =============================================================================
# GEOMETRY UTILITIES
# =============================================================================

def extract_polygonal_geometry(geom):
    """
    Keep only Polygon/MultiPolygon parts.

    ArcGIS geometry repair can occasionally produce a
    GeometryCollection containing lines or points.
    """

    if geom is None or geom.is_empty:
        return None

    if geom.geom_type == "Polygon":
        return geom

    if geom.geom_type == "MultiPolygon":
        return geom

    if geom.geom_type == "GeometryCollection":

        polygons = []

        for part in geom.geoms:

            if part.geom_type == "Polygon":
                polygons.append(part)

            elif part.geom_type == "MultiPolygon":
                polygons.extend(
                    list(part.geoms)
                )

        if not polygons:
            return None

        return unary_union(polygons)

    return None


def repair_geometry(geom):
    """
    Aggressively repair common invalid polygon geometries.
    """

    if geom is None:
        return None

    if geom.is_empty:
        return None

    # First repair.
    if not geom.is_valid:
        geom = make_valid(geom)

    geom = extract_polygonal_geometry(
        geom
    )

    if geom is None:
        return None

    if geom.is_empty:
        return None

    # Second repair.
    if not geom.is_valid:
        geom = geom.buffer(0)

    geom = extract_polygonal_geometry(
        geom
    )

    if geom is None or geom.is_empty:
        return None

    return geom


def snap_geometry(geom, tolerance):
    """
    Snap coordinates to a common grid.

    This is intentionally a coordinate-grid operation rather than
    pairwise snapping. It makes nearby vertices deterministic.
    """

    if tolerance <= 0:
        return geom

    def snap_xy(x, y, z=None):

        sx = round(x / tolerance) * tolerance
        sy = round(y / tolerance) * tolerance

        if z is None:
            return sx, sy

        return sx, sy, z

    return transform(
        snap_xy,
        geom,
    )


def remove_slivers(geom, minimum_area):
    """
    Remove polygon components below minimum area.
    """

    geom = extract_polygonal_geometry(
        geom
    )

    if geom is None:
        return None

    if geom.geom_type == "Polygon":

        if geom.area < minimum_area:
            return None

        return geom

    if geom.geom_type == "MultiPolygon":

        parts = [
            p
            for p in geom.geoms
            if p.area >= minimum_area
        ]

        if not parts:
            return None

        if len(parts) == 1:
            return parts[0]

        return MultiPolygon(parts)

    return None


# =============================================================================
# BUILD CLEAN PLACE GEOMETRY
# =============================================================================

def prepare_source_geometries(features):
    """
    Convert all source geometries to the working CRS and repair them.
    """

    to_working = Transformer.from_crs(
        SOURCE_CRS,
        WORKING_CRS,
        always_xy=True,
    ).transform

    cleaned = []

    for i, feature in enumerate(features):

        raw_geom = feature.get(
            "geometry"
        )

        if not raw_geom:
            continue

        geom = shape(
            raw_geom
        )

        geom = transform(
            to_working,
            geom,
        )

        geom = repair_geometry(
            geom
        )

        if geom is None:
            continue

        geom = snap_geometry(
            geom,
            SNAP_TOLERANCE,
        )

        geom = repair_geometry(
            geom
        )

        if geom is None:
            continue

        geom = remove_slivers(
            geom,
            MIN_SLIVER_AREA,
        )

        if geom is None:
            continue

        cleaned.append(
            geom
        )

    return cleaned


def transform_to_output_crs(geom):
    """
    Transform a finished geometry from WORKING_CRS to OUTPUT_CRS.

    KML requires WGS84 longitude/latitude.
    """
    to_output = Transformer.from_crs(
        WORKING_CRS,
        OUTPUT_CRS,
        always_xy=True,
    ).transform

    return transform(to_output, geom)


def build_clean_place_geometry(
    source_geometries,
):
    """
    Construct one topology-clean union from all source polygons.

    unary_union removes:
        * overlaps
        * duplicate boundaries
        * internal shared edges

    The result is then polygonized/repaired as needed.
    """

    if not source_geometries:
        raise RuntimeError(
            "No usable polygon geometries."
        )

    print(
        "Building polygon union..."
    )

    union = unary_union(
        source_geometries
    )

    union = repair_geometry(
        union
    )

    if union is None:
        raise RuntimeError(
            "Union produced no polygon geometry."
        )

    # Remove tiny pieces from the union.
    union = remove_slivers(
        union,
        MIN_SLIVER_AREA,
    )

    if union is None:
        raise RuntimeError(
            "All resulting polygons were "
            "removed as slivers."
        )

    return union


# =============================================================================
# TOPOLOGY VALIDATION
# =============================================================================

def polygon_parts(geom):
    """
    Return all Polygon parts.
    """

    if geom is None:
        return []

    if geom.geom_type == "Polygon":
        return [geom]

    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)

    return []


def count_vertices(geom):
    """
    Count exterior + interior ring vertices.
    """

    total = 0

    for polygon in polygon_parts(geom):

        total += len(
            polygon.exterior.coords
        )

        for interior in polygon.interiors:

            total += len(
                interior.coords
            )

    return total


def validate_geometry(
    geom,
    label="geometry",
):
    """
    Validate final geometry.
    """

    print()
    print("=" * 70)
    print(f"VALIDATION: {label}")
    print("=" * 70)

    if geom is None:
        raise RuntimeError(
            "Geometry is None."
        )

    print(
        f"Geometry type       : {geom.geom_type}"
    )

    print(
        f"Valid                : {geom.is_valid}"
    )

    print(
        f"Area                 : {geom.area:,.3f} "
        f"sq units"
    )

    print(
        f"Polygon parts        : "
        f"{len(polygon_parts(geom)):,}"
    )

    print(
        f"Vertices             : "
        f"{count_vertices(geom):,}"
    )

    if not geom.is_valid:

        print(
            "Validity reason:"
        )

        from shapely.validation import (
            explain_validity
        )

        print(
            explain_validity(geom)
        )

        raise RuntimeError(
            "Final geometry is invalid."
        )

    # ---------------------------------------------------------------------
    # Check for overlapping MultiPolygon parts.
    #
    # A valid MultiPolygon should not have overlapping components.
    # ---------------------------------------------------------------------

    parts = polygon_parts(geom)

    overlap_area = 0.0

    for i in range(len(parts)):

        for j in range(
            i + 1,
            len(parts),
        ):

            intersection = (
                parts[i].intersection(
                    parts[j]
                )
            )

            if not intersection.is_empty:

                area = intersection.area

                if area > 0:
                    overlap_area += area

    print(
        f"Internal overlap    : "
        f"{overlap_area:,.6f} sq units"
    )

    if overlap_area > 0:
        raise RuntimeError(
            "Final MultiPolygon contains "
            "overlapping polygon parts."
        )

    print(
        "Topology             : PASS"
    )


# =============================================================================
# KML GENERATION
# =============================================================================

KML_NS = (
    "http://www.opengis.net/kml/2.2"
)

NSMAP = {
    None: KML_NS
}


def format_coordinate(
    x,
    y,
):
    return (
        f"{x:.{KML_DECIMAL_PLACES}f},"
        f"{y:.{KML_DECIMAL_PLACES}f},0"
    )


def ring_to_kml(
    ring,
):
    """
    Convert a Shapely ring to compact KML coordinates.
    """

    return " ".join(
        format_coordinate(
            x,
            y,
        )
        for x, y, *rest in ring.coords
    )


def add_polygon_kml(
    parent,
    polygon,
):
    """
    Add one Polygon to a KML MultiGeometry.
    """

    polygon_el = etree.SubElement(
        parent,
        f"{{{KML_NS}}}Polygon",
    )

    # ---------------------------------------------------------------------
    # Outer boundary
    # ---------------------------------------------------------------------

    outer_el = etree.SubElement(
        polygon_el,
        f"{{{KML_NS}}}outerBoundaryIs",
    )

    outer_ring_el = etree.SubElement(
        outer_el,
        f"{{{KML_NS}}}LinearRing",
    )

    coords_el = etree.SubElement(
        outer_ring_el,
        f"{{{KML_NS}}}coordinates",
    )

    coords_el.text = ring_to_kml(
        polygon.exterior
    )

    # ---------------------------------------------------------------------
    # Holes
    # ---------------------------------------------------------------------

    for interior in polygon.interiors:

        inner_el = etree.SubElement(
            polygon_el,
            f"{{{KML_NS}}}innerBoundaryIs",
        )

        inner_ring_el = etree.SubElement(
            inner_el,
            f"{{{KML_NS}}}LinearRing",
        )

        coords_el = etree.SubElement(
            inner_ring_el,
            f"{{{KML_NS}}}coordinates",
        )

        coords_el.text = ring_to_kml(
            interior
        )


def create_kml_bytes(
    geom,
    place_name,
):
    """
    Create a compact KML byte string.

    The output contains ONE Placemark and ONE MultiGeometry.
    """

    kml = etree.Element(
        f"{{{KML_NS}}}kml",
        nsmap=NSMAP,
    )

    document = etree.SubElement(
        kml,
        f"{{{KML_NS}}}Document",
    )

    placemark = etree.SubElement(
        document,
        f"{{{KML_NS}}}Placemark",
    )

    name = etree.SubElement(
        placemark,
        f"{{{KML_NS}}}name",
    )

    name.text = place_name

    multi = etree.SubElement(
        placemark,
        f"{{{KML_NS}}}MultiGeometry",
    )

    for polygon in polygon_parts(
        geom
    ):

        add_polygon_kml(
            multi,
            polygon,
        )

    # ---------------------------------------------------------------------
    # Compact serialization.
    #
    # No pretty_print = significantly smaller file.
    # ---------------------------------------------------------------------

    return etree.tostring(
        kml,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=False,
    )


def write_kml(
    data,
    output_path,
):
    with open(
        output_path,
        "wb",
    ) as f:

        f.write(data)


# =============================================================================
# SIMPLIFICATION
# =============================================================================

def simplify_geometry(
    geom,
    tolerance,
):
    """
    Simplify while preserving topology.

    preserve_topology=True is important for holes and adjacent
    polygon structures.
    """

    simplified = geom.simplify(
        tolerance,
        preserve_topology=True,
    )

    simplified = repair_geometry(
        simplified
    )

    return simplified


def optimize_for_inaturalist(
    geom,
    place_name,
):
    """
    Iteratively simplify until the KML fits the target size.

    The algorithm is deliberately conservative.

    It first tests the original geometry, then progressively
    increases simplification tolerance.
    """

    print()
    print(
        "Optimizing KML size..."
    )

    # ---------------------------------------------------------------------
    # Try original geometry first.
    # ---------------------------------------------------------------------

    output_geom = transform_to_output_crs(geom)

    data = create_kml_bytes(
        output_geom,
        place_name,
    )

    size = len(data)

    print(
        f"Original KML size: "
        f"{size:,} bytes "
        f"({size / 1024:.1f} KB)"
    )

    if size <= TARGET_KML_BYTES:
        return geom, data, 0.0

    # ---------------------------------------------------------------------
    # Progressive simplification.
    # ---------------------------------------------------------------------

    tolerance = INITIAL_SIMPLIFY_TOLERANCE

    best_geom = None
    best_data = None
    best_tolerance = None

    for iteration in range(
        MAX_SIMPLIFICATION_ITERATIONS
    ):

        if tolerance > MAX_SIMPLIFY_TOLERANCE:
            break

        candidate = simplify_geometry(
            geom,
            tolerance,
        )

        if candidate is None:
            tolerance *= 2
            continue

        # Ensure simplification did not create
        # invalid topology.
        if not candidate.is_valid:
            tolerance *= 2
            continue

        candidate = remove_slivers(
            candidate,
            MIN_SLIVER_AREA,
        )

        if candidate is None:
            tolerance *= 2
            continue

        output_candidate = transform_to_output_crs(candidate)

        data = create_kml_bytes(
            output_candidate,
            place_name,
        )

        size = len(data)

        print(
            f"  iteration {iteration + 1:02d}: "
            f"tolerance={tolerance:g}, "
            f"vertices={count_vertices(candidate):,}, "
            f"size={size:,} bytes"
        )

        best_geom = candidate
        best_data = data
        best_tolerance = tolerance

        if size <= TARGET_KML_BYTES:

            print(
                "KML size target reached."
            )

            return (
                candidate,
                data,
                tolerance,
            )

        tolerance *= 2

    # ---------------------------------------------------------------------
    # We couldn't reach the target.
    # ---------------------------------------------------------------------

    if best_data is not None:

        size = len(best_data)

        raise RuntimeError(
            "\n"
            "Could not reduce KML below the target size.\n"
            f"Best size: {size:,} bytes\n"
            f"Target:    {TARGET_KML_BYTES:,} bytes\n"
            f"Final simplification tolerance: "
            f"{best_tolerance}\n"
            "\n"
            "Increase MAX_SIMPLIFY_TOLERANCE or use a "
            "larger TARGET_KML_BYTES if you are an "
            "iNaturalist Curator."
        )

    raise RuntimeError(
        "Geometry could not be simplified."
    )


# =============================================================================
# FINAL STATISTICS
# =============================================================================

def print_final_statistics(
    geom,
    kml_data,
    simplify_tolerance,
):
    """
    Print statistics useful for checking an iNaturalist upload.
    """

    parts = polygon_parts(
        geom
    )

    vertices = count_vertices(
        geom
    )

    size = len(
        kml_data
    )

    print()
    print("=" * 70)
    print("FINAL INATURALIST KML")
    print("=" * 70)

    print(
        f"File size            : "
        f"{size:,} bytes "
        f"({size / 1024:.1f} KB)"
    )

    print(
        f"Polygon parts         : "
        f"{len(parts):,}"
    )

    print(
        f"Vertices              : "
        f"{vertices:,}"
    )

    print(
        f"Simplification        : "
        f"{simplify_tolerance:g}"
    )

    print(
        f"Area                  : "
        f"{geom.area:,.3f} square "
        f"working-CRS units"
    )

    print(
        f"Topology valid        : "
        f"{geom.is_valid}"
    )

    if size <= 900_000:

        print(
            "iNaturalist 1 MB target: PASS"
        )

    else:

        print(
            "iNaturalist 1 MB target: EXCEEDED"
        )

    print("=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main():

    # ---------------------------------------------------------------------
    # Download
    # ---------------------------------------------------------------------

    print(
        "Downloading ArcGIS Feature Service..."
    )

    features = get_arcgis_features(
        FEATURE_SERVICE_URL
    )

    print(
        f"Downloaded {len(features):,} "
        f"features."
    )

    if not features:
        raise RuntimeError(
            "ArcGIS service returned no features."
        )

    # ---------------------------------------------------------------------
    # Prepare geometries
    # ---------------------------------------------------------------------

    print(
        "Preparing geometries..."
    )

    source_geometries = (
        prepare_source_geometries(
            features
        )
    )

    print(
        f"Usable polygon features: "
        f"{len(source_geometries):,}"
    )

    if not source_geometries:
        raise RuntimeError(
            "No valid polygon geometries found."
        )

    # ---------------------------------------------------------------------
    # Build topology-clean union
    # ---------------------------------------------------------------------

    place_geom = (
        build_clean_place_geometry(
            source_geometries
        )
    )

    # ---------------------------------------------------------------------
    # Validate before simplification
    # ---------------------------------------------------------------------

    validate_geometry(
        place_geom,
        "pre-simplification geometry",
    )

    # ---------------------------------------------------------------------
    # Optimize KML
    # ---------------------------------------------------------------------

    optimized_geom, kml_data, tolerance = (
        optimize_for_inaturalist(
            place_geom,
            PLACE_NAME,
        )
    )

    # ---------------------------------------------------------------------
    # Validate AFTER simplification.
    #
    # This is important. Simplification itself can introduce
    # geometry problems.
    # ---------------------------------------------------------------------

    output_geom = transform_to_output_crs(optimized_geom)

    validate_geometry(
        output_geom,
        "FINAL geometry",
    )

    # ---------------------------------------------------------------------
    # Write KML
    # ---------------------------------------------------------------------

    write_kml(
        kml_data,
        OUTPUT_KML,
    )

    # ---------------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------------

    print_final_statistics(
        optimized_geom,
        kml_data,
        tolerance,
    )

    print()
    print(
        f"KML written to:\n"
        f"{Path(OUTPUT_KML).resolve()}"
    )


if __name__ == "__main__":
    main()
