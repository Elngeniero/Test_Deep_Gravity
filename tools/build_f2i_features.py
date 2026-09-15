#!/usr/bin/env python3
"""Build auditable F2-I population and OpenStreetMap feature candidates.

The build command delegates to the corrected geometry pipeline in f2i_finalize.
Its Santiago candidates have 19 or 20 location variables (39 or 41 pair inputs).
Neither their dimensions nor a successful execution establish faithful article
reproduction. Legacy helpers remain solely for historical audit tests.

Raw downloads and derived CSV files live under ignored data directories.  The
coverage report is versioned and is the reproducible decision record.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = ROOT / ".f2i_deps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))

import h3  # noqa: E402
import osmium  # noqa: E402
import requests  # noqa: E402
import shapefile  # noqa: E402
from pyproj import Transformer  # noqa: E402
from shapely import STRtree, from_wkb, make_valid  # noqa: E402
from shapely.geometry import Point, Polygon, shape  # noqa: E402
from shapely.ops import transform, unary_union  # noqa: E402


PAPER_FEATURES = (
    "population_census_2024_per_km2",
    "landuse_residential_share",
    "landuse_commercial_share",
    "landuse_industrial_share",
    "landuse_retail_share",
    "landuse_natural_share",
    "road_residential_km_per_km2",
    "road_main_km_per_km2",
    "road_other_km_per_km2",
    "transport_poi_per_km2",
    "transport_area_per_km2",
    "food_poi_per_km2",
    "food_area_per_km2",
    "health_poi_per_km2",
    "health_area_per_km2",
    "education_poi_per_km2",
    "education_area_per_km2",
    "retail_poi_per_km2",
    "retail_area_per_km2",
)

MACRO_FEATURES = (
    "residential_bldg_per_km2",
    "commercial_bldg_per_km2",
    "industrial_bldg_per_km2",
    "leisure_per_km2",
    "edu_per_km2",
    "food_per_km2",
    "health_per_km2",
    "retail_per_km2",
    "transport_per_km2",
    "main_roads_km_per_km2",
    "secondary_roads_km_per_km2",
    "other_per_km2",
)

LANDUSE = {"residential", "commercial", "industrial", "retail"}
NATURAL_LANDUSE = {"forest", "grass", "meadow", "recreation_ground", "village_green", "orchard", "farmland", "farmyard"}
RESIDENTIAL_ROADS = {"residential", "living_street"}
MAIN_ROADS = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}
SECONDARY_MACRO_ROADS = {"secondary", "secondary_link", "tertiary", "tertiary_link"}
OTHER_ROADS = {"unclassified", "service", "road", "track", "pedestrian", "footway", "cycleway", "path", "steps", "bridleway", "busway"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def config_path(value: str, config_file: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (config_file.parent / path).resolve()


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fail_if_exists(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"No se sobrescribe {path}; use --force tras revisar su hash.")
    path.parent.mkdir(parents=True, exist_ok=True)


def download(url: str, destination: Path, *, force: bool, label: str) -> None:
    fail_if_exists(destination, force)
    temporary = destination.with_suffix(destination.suffix + ".part")
    if temporary.exists():
        temporary.unlink()
    print(f"Descargando {label}: {url}", flush=True)
    with requests.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for block in response.iter_content(chunk_size=1024 * 1024):
                if block:
                    handle.write(block)
    temporary.replace(destination)
    print(f"Descarga terminada: {destination} ({destination.stat().st_size:,} bytes)", flush=True)


def fetch_census(config: dict[str, Any], config_file: Path, *, force: bool) -> None:
    source = config["population"]
    destination = config_path(source["raw_path"], config_file)
    manifest = config_path(source["manifest_path"], config_file)
    fail_if_exists(destination, force)
    fail_if_exists(manifest, force)
    if destination.exists() and force:
        destination.unlink()
    if manifest.exists() and force:
        manifest.unlink()
    endpoint = source["endpoint"]
    fields = ",".join(source["fields"])
    print("Descargando Censo 2024 a nivel de manzana/entidad para toda la RM.", flush=True)
    count_response = requests.get(endpoint, params={"where": source["where"], "returnCountOnly": "true", "f": "json"}, timeout=(30, 300))
    count_response.raise_for_status()
    total = int(count_response.json()["count"])

    def page(offset: int) -> tuple[int, list[dict[str, Any]]]:
        params = {
            "where": source["where"], "outFields": fields, "returnGeometry": "true",
            "f": "geojson", "outSR": "4326", "resultOffset": offset,
            "resultRecordCount": 2000, "orderByFields": "OBJECTID",
        }
        response = requests.get(endpoint, params=params, timeout=(30, 300))
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"ArcGIS devolvió error: {payload['error']}")
        return offset, payload.get("features", [])

    offsets = list(range(0, total, 2000))
    with ThreadPoolExecutor(max_workers=8) as executor:
        batches = sorted(executor.map(page, offsets), key=lambda item: item[0])
    features = [feature for _, batch in batches for feature in batch]
    if len(features) != total:
        raise RuntimeError(f"El servicio declaró {total:,} filas, pero entregó {len(features):,}.")
    print(f"  {len(features):,} filas recuperadas en {len(offsets)} páginas.", flush=True)
    collection = {"type": "FeatureCollection", "features": features}
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(collection, handle, ensure_ascii=False, separators=(",", ":"))
    record = {
        "stage": "F2-I", "retrieved_at": utc_now(), "source_name": source["source_name"],
        "year": source["year"], "license": source["license"], "endpoint": endpoint,
        "where": source["where"], "fields": source["fields"], "feature_count": len(features),
        "sha256": sha256(destination), "file": str(destination),
    }
    with manifest.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def fetch_osm(config: dict[str, Any], config_file: Path, *, force: bool) -> None:
    source = config["osm"]
    destination = config_path(source["raw_path"], config_file)
    download(source["url"], destination, force=force, label="extracto histórico OSM de Chile")


def unit_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "unit_id" not in rows[0]:
        raise ValueError(f"{path} no contiene la columna unit_id.")
    return rows


def zone_geometries(path: Path, transformer: Transformer) -> dict[str, Any]:
    # The official DTPM DBF has no encoding sidecar and contains Spanish names.
    # Zone ids are numeric, but cp1252 prevents a decoder failure while reading all
    # records in the original archive.
    reader = shapefile.Reader(str(path), encoding="cp1252")
    names = [field[0] for field in reader.fields[1:]]
    try:
        zone_index = names.index("ZONA777")
    except ValueError as error:
        raise ValueError("El shapefile Zona777 no contiene ZONA777.") from error
    grouped: dict[str, list[Any]] = defaultdict(list)
    for record, geometry in zip(reader.records(), reader.shapes()):
        item = shape(geometry.__geo_interface__)
        if not item.is_valid:
            item = make_valid(item)
        grouped[str(int(record[zone_index]))].append(transform(transformer.transform, item))
    return {zone: unary_union(parts) for zone, parts in grouped.items()}


def h3_geometries(unit_ids: Iterable[str], transformer: Transformer) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for unit_id in unit_ids:
        boundary = h3.cell_to_boundary(unit_id)
        output[unit_id] = transform(transformer.transform, Polygon([(lng, lat) for lat, lng in boundary]))
    return output


class UnitIndex:
    def __init__(self, geometries: dict[str, Any]):
        self.ids = list(geometries)
        self.geometries = [geometries[unit_id] for unit_id in self.ids]
        self.tree = STRtree(self.geometries)

    def intersecting(self, geometry: Any) -> Iterable[tuple[str, Any]]:
        for index in self.tree.query(geometry):
            candidate = self.geometries[int(index)]
            if candidate.intersects(geometry):
                yield self.ids[int(index)], candidate

    def containing(self, point: Point) -> Iterable[str]:
        for index in self.tree.query(point):
            candidate = self.geometries[int(index)]
            if candidate.contains(point):
                yield self.ids[int(index)]


def classify_land(tags: dict[str, str]) -> str | None:
    landuse = tags.get("landuse", "")
    if landuse in LANDUSE:
        return landuse
    if landuse in NATURAL_LANDUSE or tags.get("natural") in {"wood", "scrub", "grassland", "heath", "wetland", "water"}:
        return "natural"
    return None


def classify_road(tags: dict[str, str]) -> tuple[str | None, str | None]:
    highway = tags.get("highway", "")
    if highway in RESIDENTIAL_ROADS:
        return "residential", None
    if highway in MAIN_ROADS:
        return "main", "main" if highway not in SECONDARY_MACRO_ROADS else "secondary"
    if highway in OTHER_ROADS:
        return "other", None
    return None, None


def classify_facility(tags: dict[str, str]) -> str | None:
    """Return one category per object, using an explicit priority."""
    amenity, healthcare, shop = tags.get("amenity", ""), tags.get("healthcare", ""), tags.get("shop", "")
    if healthcare or amenity in {"hospital", "clinic", "doctors", "pharmacy", "dentist", "veterinary"}:
        return "health"
    if amenity in {"school", "university", "college", "kindergarten", "library", "driving_school", "language_school"} or tags.get("office") == "educational_institution":
        return "education"
    if amenity in {"restaurant", "cafe", "fast_food", "bar", "pub", "food_court", "ice_cream"}:
        return "food"
    if shop or amenity in {"marketplace", "bank", "bureau_de_change"}:
        return "retail"
    if tags.get("public_transport") in {"platform", "stop_position", "station"} or tags.get("railway") in {"station", "halt", "tram_stop", "subway_entrance"} or tags.get("aeroway") in {"aerodrome", "terminal", "gate"} or tags.get("highway") == "bus_stop" or amenity in {"bus_station", "ferry_terminal"}:
        return "transport"
    return None


def classify_building(tags: dict[str, str]) -> str | None:
    value = tags.get("building", "")
    if value in {"residential", "apartments", "house", "detached", "terrace", "semidetached_house", "bungalow"}:
        return "residential_bldg"
    if value in {"commercial", "office", "retail"}:
        return "commercial_bldg"
    if value in {"industrial", "warehouse"}:
        return "industrial_bldg"
    return None


def classify_leisure(tags: dict[str, str]) -> bool:
    return tags.get("leisure") in {"park", "sports_centre", "pitch", "garden", "playground", "stadium", "fitness_centre"}


def is_other_supported(tags: dict[str, str]) -> bool:
    return bool(tags.get("amenity") or tags.get("office") or tags.get("tourism") or tags.get("leisure"))


def normalized_name(tags: dict[str, str]) -> str | None:
    value = tags.get("name", "").strip().casefold()
    return " ".join(value.split()) or None


class OSMCollector(osmium.SimpleHandler):
    """Keep tagged geometry only; all assignment happens in the metric CRS."""

    def __init__(self, minimum_bounds: tuple[float, float, float, float]):
        super().__init__()
        self.minimum_bounds = minimum_bounds
        self.wkb = osmium.geom.WKBFactory()
        self.points: list[tuple[str, str | None, Point]] = []
        self.areas: list[tuple[str, str | None, str | None, str | None, bool, bool, Any]] = []
        self.roads: list[tuple[str, str | None, Any]] = []
        self.tagged_other = Counter()

    def _within_bounds(self, geometry: Any) -> bool:
        west, south, east, north = self.minimum_bounds
        minx, miny, maxx, maxy = geometry.bounds
        return not (maxx < west or minx > east or maxy < south or miny > north)

    def node(self, node: Any) -> None:
        tags = dict(node.tags)
        facility = classify_facility(tags)
        leisure = classify_leisure(tags)
        if not facility and not leisure and not is_other_supported(tags):
            return
        try:
            point = Point(node.location.lon, node.location.lat)
        except (osmium.InvalidLocationError, RuntimeError):
            return
        if not self._within_bounds(point):
            return
        if facility:
            self.points.append((facility, normalized_name(tags), point))
        elif leisure:
            self.points.append(("leisure", normalized_name(tags), point))
        else:
            self.points.append(("other", normalized_name(tags), point))

    def way(self, way: Any) -> None:
        tags = dict(way.tags)
        road, macro_road = classify_road(tags)
        if not road:
            return
        try:
            geometry = from_wkb(self.wkb.create_linestring(way))
        except Exception:  # malformed OSM way; retain the source run and skip only that object
            return
        if self._within_bounds(geometry):
            self.roads.append((road, macro_road, geometry))

    def area(self, area: Any) -> None:
        tags = dict(area.tags)
        land, facility, building = classify_land(tags), classify_facility(tags), classify_building(tags)
        leisure, other = classify_leisure(tags), is_other_supported(tags)
        if not any((land, facility, building, leisure, other)):
            return
        try:
            geometry = from_wkb(self.wkb.create_multipolygon(area))
        except Exception:  # malformed multipolygon or relation; skip only that OSM object
            return
        if geometry.is_empty or not self._within_bounds(geometry):
            return
        self.areas.append((land or "", facility, building, normalized_name(tags), leisure, other, geometry))
        if other and not facility and not leisure:
            self.tagged_other["area"] += 1


def append_area_fragments(index: UnitIndex, values: dict[str, dict[str, float]], geometry: Any, category: str) -> None:
    for unit_id, unit_geometry in index.intersecting(geometry):
        fragment = geometry.intersection(unit_geometry)
        if not fragment.is_empty:
            values[unit_id][f"landuse_{category}_area_km2"] += fragment.area / 1_000_000


def add_length(index: UnitIndex, values: dict[str, dict[str, float]], geometry: Any, category: str, *, column: str | None = None) -> None:
    for unit_id, unit_geometry in index.intersecting(geometry):
        segment = geometry.intersection(unit_geometry)
        if not segment.is_empty:
            values[unit_id][column or f"road_{category}_km"] += segment.length / 1_000


def add_point(index: UnitIndex, values: dict[str, dict[str, float]], point: Point, column: str) -> None:
    for unit_id in index.containing(point):
        values[unit_id][column] += 1


def wgs_bounds(index: UnitIndex, reverse: Transformer) -> tuple[float, float, float, float]:
    parts = [transform(reverse.transform, geometry).bounds for geometry in index.geometries]
    return min(value[0] for value in parts), min(value[1] for value in parts), max(value[2] for value in parts), max(value[3] for value in parts)


def initial_values(geometries: dict[str, Any], unit_ids: Iterable[str]) -> dict[str, dict[str, float]]:
    fields = ["population_census_2024", *[f"landuse_{kind}_area_km2" for kind in (*sorted(LANDUSE), "natural")],
              "road_residential_km", "road_main_km", "road_other_km",
              *[f"{kind}_{form}_count" for kind in ("transport", "food", "health", "education", "retail") for form in ("poi", "area")],
              "residential_bldg_count", "commercial_bldg_count", "industrial_bldg_count", "leisure_count", "other_count",
              "main_roads_km", "secondary_roads_km"]
    result = {unit_id: {field: 0.0 for field in fields} for unit_id in unit_ids}
    for unit_id, geometry in geometries.items():
        result[unit_id]["unit_area_km2"] = geometry.area / 1_000_000
    for unit_id in result:
        result[unit_id].setdefault("unit_area_km2", math.nan)
    return result


def allocate_census(path: Path, index: UnitIndex, values: dict[str, dict[str, float]], transformer: Transformer) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        collection = json.load(handle)
    bad_population, bad_geometry, source_population, allocated_population = 0, 0, 0.0, 0.0
    for feature in collection.get("features", []):
        raw_value = feature.get("properties", {}).get("n_per")
        try:
            population = float(raw_value)
        except (TypeError, ValueError):
            bad_population += 1
            continue
        if not math.isfinite(population) or population < 0:
            bad_population += 1
            continue
        try:
            geometry = transform(transformer.transform, shape(feature["geometry"]))
            if not geometry.is_valid:
                geometry = make_valid(geometry)
        except (KeyError, TypeError, ValueError):
            bad_geometry += 1
            continue
        if geometry.is_empty or geometry.area <= 0:
            bad_geometry += 1
            continue
        source_population += population
        for unit_id, unit_geometry in index.intersecting(geometry):
            overlap = geometry.intersection(unit_geometry).area
            if overlap > 0:
                assigned = population * overlap / geometry.area
                values[unit_id]["population_census_2024"] += assigned
                allocated_population += assigned
    return {"source_feature_count": len(collection.get("features", [])), "source_population": source_population,
            "allocated_population": allocated_population, "invalid_population_rows": bad_population, "invalid_geometry_rows": bad_geometry}


def apply_osm(pbf: Path, indexes: dict[str, UnitIndex], values: dict[str, dict[str, dict[str, float]]], transformer: Transformer, reverse: Transformer) -> dict[str, Any]:
    overall = unary_union([geometry for index in indexes.values() for geometry in index.geometries])
    bounds = transform(reverse.transform, overall).bounds
    collector = OSMCollector(bounds)
    print("Leyendo OSM PBF y construyendo áreas multipolígono; puede tardar varios minutos.", flush=True)
    collector.apply_file(str(pbf), locations=True, idx="flex_mem")
    print(f"OSM retenido: {len(collector.points):,} puntos, {len(collector.areas):,} áreas, {len(collector.roads):,} vías.", flush=True)

    # First handle areas.  Facility / building / leisure objects are counted at a
    # representative point.  Land-use is area-weighted and roads are length-weighted.
    facility_areas: list[tuple[str, str | None, Any]] = []
    for land, facility, building, name, leisure, other, geometry in collector.areas:
        projected = transform(transformer.transform, geometry)
        if not projected.is_valid:
            projected = make_valid(projected)
        if projected.is_empty:
            continue
        if facility:
            facility_areas.append((facility, name, projected))
        for key, index in indexes.items():
            if land:
                append_area_fragments(index, values[key], projected, land)
            representative = projected.representative_point()
            if facility:
                add_point(index, values[key], representative, f"{facility}_area_count")
            if building:
                add_point(index, values[key], representative, f"{building}_count")
            if leisure:
                add_point(index, values[key], representative, "leisure_count")
            if other and not facility and not leisure:
                add_point(index, values[key], representative, "other_count")

    # Named POIs inside a same-category, same-name polygon are mapped by OSM as a
    # node-and-area representation of one place.  Suppress exactly those duplicates.
    facility_area_trees: dict[str, tuple[STRtree, list[tuple[str | None, Any]]]] = {}
    for category in ("transport", "food", "health", "education", "retail"):
        objects = [(name, geometry) for current, name, geometry in facility_areas if current == category and name]
        if objects:
            facility_area_trees[category] = (STRtree([geometry for _, geometry in objects]), objects)
    suppressed = 0
    for category, name, point in collector.points:
        projected = transform(transformer.transform, point)
        duplicate = False
        if category in facility_area_trees and name:
            tree, objects = facility_area_trees[category]
            for item in tree.query(projected):
                area_name, area_geometry = objects[int(item)]
                if area_name == name and area_geometry.contains(projected):
                    duplicate = True
                    suppressed += 1
                    break
        if duplicate:
            continue
        for key, index in indexes.items():
            if category in {"transport", "food", "health", "education", "retail"}:
                add_point(index, values[key], projected, f"{category}_poi_count")
            elif category == "leisure":
                add_point(index, values[key], projected, "leisure_count")
            else:
                add_point(index, values[key], projected, "other_count")

    for category, macro_category, geometry in collector.roads:
        projected = transform(transformer.transform, geometry)
        for key, index in indexes.items():
            add_length(index, values[key], projected, category)
            if macro_category == "main":
                add_length(index, values[key], projected, "main", column="main_roads_km")
            elif macro_category == "secondary":
                add_length(index, values[key], projected, "secondary", column="secondary_roads_km")
    return {"point_records": len(collector.points), "area_records": len(collector.areas), "road_records": len(collector.roads),
            "node_area_duplicates_suppressed": suppressed, "unclassified_supported_area_records": collector.tagged_other["area"]}


def paper_row(values: dict[str, float]) -> dict[str, float]:
    area = values["unit_area_km2"]
    if not math.isfinite(area) or area <= 0:
        return {column: math.nan for column in PAPER_FEATURES}
    output = {"population_census_2024_per_km2": values["population_census_2024"] / area}
    for category in ("residential", "commercial", "industrial", "retail", "natural"):
        output[f"landuse_{category}_share"] = values[f"landuse_{category}_area_km2"] / area
    for category in ("residential", "main", "other"):
        output[f"road_{category}_km_per_km2"] = values[f"road_{category}_km"] / area
    for category in ("transport", "food", "health", "education", "retail"):
        for form in ("poi", "area"):
            output[f"{category}_{form}_per_km2"] = values[f"{category}_{form}_count"] / area
    return output


def macro_row(values: dict[str, float]) -> dict[str, float]:
    area = values["unit_area_km2"]
    if not math.isfinite(area) or area <= 0:
        return {column: math.nan for column in MACRO_FEATURES}
    output = {f"{category}_per_km2": values[f"{category}_count"] / area for category in ("residential_bldg", "commercial_bldg", "industrial_bldg", "leisure", "other")}
    for category, source in (("edu", "education"), ("food", "food"), ("health", "health"), ("retail", "retail"), ("transport", "transport")):
        output[f"{category}_per_km2"] = (values[f"{source}_poi_count"] + values[f"{source}_area_count"]) / area
    output["main_roads_km_per_km2"] = values["main_roads_km"] / area
    output["secondary_roads_km_per_km2"] = values["secondary_roads_km"] / area
    return {column: output[column] for column in MACRO_FEATURES}


def number(value: float) -> str:
    return "" if not math.isfinite(value) else f"{value:.12g}"


def write_candidate(path: Path, unit_ids: list[str], rows: dict[str, dict[str, float]], features: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["unit_id", *features])
        writer.writeheader()
        for unit_id in unit_ids:
            writer.writerow({"unit_id": unit_id, **{key: number(rows[unit_id][key]) for key in features}})


def summarize(rows: dict[str, dict[str, float]], features: tuple[str, ...], expected_units: list[str]) -> dict[str, Any]:
    incomplete = [unit_id for unit_id in expected_units if not all(math.isfinite(rows[unit_id][column]) for column in features)]
    return {"unit_count": len(expected_units), "finite_vector_count": len(expected_units) - len(incomplete), "incomplete_unit_ids": incomplete,
            "nonzero_units_by_feature": {column: sum(rows[unit_id][column] > 0 for unit_id in expected_units if math.isfinite(rows[unit_id][column])) for column in features}}


def render_report(config: dict[str, Any], results: dict[str, Any], output_root: Path) -> str:
    lines = [
        "# F2-I — Cobertura reproducible de población y OSM", "",
        f"Generado: `{utc_now()}`. Este reporte genera alternativas y **no congela** la ontología ni la fuente sin la decisión del investigador.", "",
        "## Fuentes", "",
        f"- Población: {config['population']['source_name']} ({config['population']['year']}); licencia {config['population']['license']}.",
        f"- OSM: {config['osm']['source_name']}; instantánea declarada {config['osm']['snapshot']}; licencia {config['osm']['license']}.",
        f"- Huella Censo: `{results['census_file_sha256']}`.",
        f"- Huella OSM: `{results['osm_file_sha256']}`.", "",
        "## Reglas aplicadas", "",
        "- Población: reparto areal exacto de las manzanas/entidades Censo sobre la geometría completa de cada unidad, en EPSG:32719.",
        "- Usos de suelo: área de la intersección por unidad; vialidad: longitud de la intersección; POI y edificios: conteo por punto representativo interior.",
        "- Cada vía entra a una sola clase. Los POI se priorizan salud, educación, alimentación, comercio y transporte. Un nodo y polígono con igual nombre y categoría se cuentan una vez.",
        "- Los puntos en límite quedan sin asignar. `other` solo registra servicios etiquetados fuera de las clases fijas y no entra al vector paper19.", "",
        "## Candidatos evaluados", "",
        f"- `paper19`: 19 atributos de ubicación (población + 18 OSM); vector de par `39 = 19 + 19 + distancia`.",
        f"- `macro12`: 12 atributos OSM de la propuesta Santiago; vector de par `27 = 12 + 12 + población origen + población destino + distancia`.",
        "",
        "## Cobertura", "",
        "| Representación | Unidades | paper19 finitas | macro12 finitas | Estado |", "|---|---:|---:|---:|---|",
    ]
    for name, result in results["representations"].items():
        paper, macro = result["paper19"], result["macro12"]
        state = "apta para selección" if paper["finite_vector_count"] == paper["unit_count"] else "bloqueada por geometría no oficial"
        lines.append(f"| {name} | {paper['unit_count']} | {paper['finite_vector_count']} | {macro['finite_vector_count']} | {state} |")
    zona = results["representations"].get("zona777", {})
    missing = zona.get("paper19", {}).get("incomplete_unit_ids", [])
    if missing:
        lines.extend(["", "## Bloqueo Zona777", "", f"Las zonas `{', '.join(missing)}` están en el universo activo, pero no tienen polígono oficial en el shapefile DTPM. Bajo `zone_geometry_policy=strict` no se fabrican atributos ni se habilita el entrenamiento científico de Zona777."])
    lines.extend(["", "## Archivos generados", "", f"`{output_root}` contiene, para cada representación, `paper19_features.csv`, `macro12_features.csv` y el diccionario JSON correspondiente. Los CSV no se cargan al modelo hasta la decisión de ontología.", ""])
    return "\n".join(lines)


def build(config: dict[str, Any], config_file: Path) -> None:
    from f2i_finalize import build_candidates
    build_candidates(config_file, config_path(config['output_root'], config_file) / 'v2',
                     config_path(config['report_path'], config_file).parent,
                     ROOT / 'deepgravity/data/santiago/cache/f2i/osm_tagged_v1.sqlite')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch-census", "fetch-osm", "build"))
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "f2i_santiago.example.json")
    parser.add_argument("--force", action="store_true", help="Permite reemplazar una descarga raw tras revisar su hash; nunca reemplaza resultados build.")
    args = parser.parse_args()
    config_file = args.config.resolve()
    config = load_config(config_file)
    if args.command == "fetch-census":
        fetch_census(config, config_file, force=args.force)
    elif args.command == "fetch-osm":
        fetch_osm(config, config_file, force=args.force)
    else:
        build(config, config_file)


if __name__ == "__main__":
    main()
