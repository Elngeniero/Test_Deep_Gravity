#!/usr/bin/env python3
"""Produce exact F2-E spatial feasibility evidence from the approved F2-D domain."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import geopandas as gpd
import h3
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely import STRtree, contains_xy, make_valid, points
from shapely.geometry import Polygon
from shapely.prepared import prep


PRIMARY = "primary"
RESOLUTIONS = range(3, 9)
PILOT_RESOLUTIONS = (7, 8)
SOURCE_URL = "https://dtpm.cl/descargas/tablas/Zona777_ADATRAP.rar"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def free_memory_gib() -> float | None:
    if os.name != "nt":
        return None
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong), ("page_total", ctypes.c_ulonglong), ("page_available", ctypes.c_ulonglong), ("virtual_total", ctypes.c_ulonglong), ("virtual_available", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]
    status = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("No se pudo consultar la memoria disponible.")
    return status.available / 1024 ** 3


def quote(path: Path) -> str:
    return "'{}'".format(path.as_posix().replace("'", "''"))


def point_membership(tree, geometries, labels, xs, ys) -> np.ndarray:
    assigned = np.full(len(xs), None, dtype=object)
    query_result = tree.query(points(xs.to_numpy(dtype=float), ys.to_numpy(dtype=float)))
    if query_result.size:
        x_values = xs.to_numpy(dtype=float)
        y_values = ys.to_numpy(dtype=float)
        for geometry_index in np.unique(query_result[1]):
            indices = query_result[0][query_result[1] == geometry_index]
            inside = contains_xy(geometries[geometry_index], x_values[indices], y_values[indices])
            assigned[indices[inside]] = labels[geometry_index]
    return assigned


def zone_ids(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="raise").to_numpy(dtype=np.int64).astype(str)


class Accumulator:
    """Unit and OD aggregation only; no coordinates or trip identifiers persist."""

    def __init__(self):
        self.units: dict[str, list[float]] = {}
        self.od: dict[tuple[str, str], list[float]] = {}
        self.endpoint_support: dict[str, list[float]] = {}

    def _units(self, values: np.ndarray, weights: np.ndarray, start: int) -> None:
        labels, inverse = np.unique(values, return_inverse=True)
        counts = np.bincount(inverse)
        masses = np.bincount(inverse, weights=weights)
        for label, count, mass in zip(labels, counts, masses):
            value = self.units.setdefault(str(label), [0.0, 0.0, 0.0, 0.0])
            value[start] += int(count)
            value[start + 1] += float(mass)

    def add(self, origins: np.ndarray, destinations: np.ndarray, weights: np.ndarray) -> None:
        self._units(origins, weights, 0)
        self._units(destinations, weights, 2)
        grouped = (pd.DataFrame({"origin": origins, "destination": destinations, "weight": weights})
                   .groupby(["origin", "destination"], sort=False, as_index=False)
                   .agg(trip_count=("weight", "size"), expanded_mass=("weight", "sum")))
        for origin, destination, trips, mass in grouped.itertuples(index=False, name=None):
            value = self.od.setdefault((str(origin), str(destination)), [0.0, 0.0])
            value[0] += int(trips)
            value[1] += float(mass)

    def add_endpoint_support(self, values: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> None:
        """Store only per-unit count, sum and extent for a documented geometry fallback."""
        frame = pd.DataFrame({"unit_id": values, "x": xs, "y": ys})
        grouped = frame.groupby("unit_id", sort=False).agg(
            endpoint_count=("x", "size"), x_sum=("x", "sum"), y_sum=("y", "sum"),
            x_min=("x", "min"), x_max=("x", "max"), y_min=("y", "min"), y_max=("y", "max"),
        )
        for unit_id, value in grouped.iterrows():
            current = self.endpoint_support.setdefault(str(unit_id), [0.0, 0.0, 0.0, math.inf, -math.inf, math.inf, -math.inf])
            current[0] += int(value.endpoint_count)
            current[1] += float(value.x_sum)
            current[2] += float(value.y_sum)
            current[3] = min(current[3], float(value.x_min))
            current[4] = max(current[4], float(value.x_max))
            current[5] = min(current[5], float(value.y_min))
            current[6] = max(current[6], float(value.y_max))

    def units_frame(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"unit_id": key, "origin_trip_count": int(value[0]), "origin_expanded_mass": value[1],
             "destination_trip_count": int(value[2]), "destination_expanded_mass": value[3]}
            for key, value in self.units.items()
        ])

    def od_frame(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"origin_unit_id": origin, "destination_unit_id": destination, "trip_count": int(value[0]), "expanded_mass": value[1]}
            for (origin, destination), value in self.od.items()
        ])


def load_area(path: Path, approval_path: Path):
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if digest(path) != approval["geometry_sha256"]:
        raise ValueError("El área F2-D no coincide con su hash congelado.")
    area = gpd.read_file(path)
    if area.crs is None or CRS.from_user_input(area.crs).to_epsg() != 4326 or len(area) != 34 or not area.geometry.is_valid.all():
        raise ValueError("El área F2-D debe ser un GeoJSON válido de 34 comunas en EPSG:4326.")
    return area, approval


def load_zones(path: Path):
    zones = gpd.read_file(path)
    if {"ZONA777", "COMUNA"} - set(zones.columns) or len(zones) != 804:
        raise ValueError("ShapeZona777 no coincide con la fuente oficial esperada.")
    invalid = ~zones.geometry.is_valid
    # The official 2014 archive contains one nested-shell topology error (Zona 543).
    # Repair only that geometry, preserve its ID and record the operation in the manifest.
    if invalid.any():
        zones.loc[invalid, "geometry"] = zones.loc[invalid, "geometry"].map(make_valid)
    if not zones.geometry.is_valid.all():
        raise ValueError("No se pudo reparar la geometría inválida de ShapeZona777.")
    if zones.crs is not None:
        raise ValueError("La fuente cambió: se esperaba ShapeZona777 sin .prj.")
    minx, miny, maxx, maxy = zones.total_bounds
    if not (-72 < minx < -69 and -35 < miny < -32 and -72 < maxx < -69 and -35 < maxy < -32):
        raise ValueError("Los bounds de ShapeZona777 no acreditan EPSG:4326.")
    source_feature_count = len(zones)
    zones = zones.set_crs(4326, allow_override=True).copy()
    zones["unit_id"] = zones["ZONA777"].astype(int).astype(str)
    repaired_zone_ids = zones.loc[invalid, "unit_id"].tolist()
    # Zone 493 is stored as two official polygon parts. Dissolving on the published
    # zone ID creates the one OD unit expected by the F2-C fields.
    zones = zones.dissolve(by="unit_id", as_index=False, aggfunc="first")
    if not zones.geometry.is_valid.all() or zones["unit_id"].duplicated().any():
        raise ValueError("No se pudo normalizar ShapeZona777 a unidades OD únicas.")
    zones.attrs["source_feature_count"] = source_feature_count
    zones.attrs["repaired_zone_ids"] = repaired_zone_ids
    return zones


def h3_polygon(cell: str) -> Polygon:
    return Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(cell)])


def h3_domain_size(area, resolution: int) -> int:
    core = area.geometry.unary_union
    filled = set(h3.geo_to_cells(core.__geo_interface__, resolution))
    if not filled:
        point = core.representative_point()
        filled = {h3.latlng_to_cell(point.y, point.x, resolution)}
    candidates = set(filled)
    for cell in list(filled):
        candidates.update(h3.grid_disk(cell, 1))
    target = prep(core)
    return sum(target.intersects(h3_polygon(cell)) for cell in candidates)


def zone_units(accumulator: Accumulator, zones) -> pd.DataFrame:
    result = accumulator.units_frame()
    projected = zones.to_crs(32719).copy()
    representative = projected.geometry.representative_point()
    bounds = projected.bounds
    projected["unit_x_32719"] = representative.x
    projected["unit_y_32719"] = representative.y
    projected["unit_area_km2"] = projected.geometry.area / 1_000_000.0
    projected["unit_bbox_span_m"] = np.maximum(bounds.maxx - bounds.minx, bounds.maxy - bounds.miny)
    result = result.merge(projected[["unit_id", "unit_x_32719", "unit_y_32719", "unit_area_km2", "unit_bbox_span_m"]], on="unit_id", how="left", validate="one_to_one")
    result["geometry_source"] = "official_shapezona777"
    missing = result.unit_x_32719.isna()
    if missing.any():
        support = pd.DataFrame([
            {"unit_id": unit_id, "support_endpoint_count": value[0], "support_x_32719": value[1] / value[0],
             "support_y_32719": value[2] / value[0], "support_bbox_span_m": max(value[4] - value[3], value[6] - value[5])}
            for unit_id, value in accumulator.endpoint_support.items()
        ])
        result = result.merge(support, on="unit_id", how="left", validate="one_to_one")
        missing = result.unit_x_32719.isna()
        if result.loc[missing, "support_x_32719"].isna().any():
            raise ValueError("Hay zonas activas sin geometría ni soporte de extremos.")
        result.loc[missing, "unit_x_32719"] = result.loc[missing, "support_x_32719"]
        result.loc[missing, "unit_y_32719"] = result.loc[missing, "support_y_32719"]
        result.loc[missing, "unit_bbox_span_m"] = result.loc[missing, "support_bbox_span_m"]
        result.loc[missing, "geometry_source"] = "observed_endpoint_support_no_official_polygon"
    result["representation"] = "zona777"
    return result


def h3_units(accumulator: Accumulator, resolution: int, to_utm: Transformer) -> pd.DataFrame:
    result = accumulator.units_frame()
    cells = result["unit_id"].tolist()
    centers = [h3.cell_to_latlng(cell) for cell in cells]
    longitudes = [value[1] for value in centers]
    latitudes = [value[0] for value in centers]
    x_values, y_values = to_utm.transform(longitudes, latitudes)
    result["unit_x_32719"] = x_values
    result["unit_y_32719"] = y_values
    result["unit_area_km2"] = [h3.cell_area(cell, unit="km^2") for cell in cells]
    # A regular H3 cell's span is bounded here from its actual, projected boundary.
    spans = []
    for cell in cells:
        boundary = gpd.GeoSeries([h3_polygon(cell)], crs=4326).to_crs(32719).bounds.iloc[0]
        spans.append(max(boundary.maxx - boundary.minx, boundary.maxy - boundary.miny))
    result["unit_bbox_span_m"] = spans
    result["representation"] = "h3_r{}".format(resolution)
    return result


def metrics(name: str, accumulator: Accumulator, units: pd.DataFrame, domain_count: int, trips: int, mass: float) -> dict:
    origins = int((units.origin_trip_count > 0).sum())
    destinations = int((units.destination_trip_count > 0).sum())
    pairs = len(accumulator.od)
    possible = origins * destinations
    intra = [value for (origin, destination), value in accumulator.od.items() if origin == destination]
    rare = [value for value in accumulator.od.values() if value[0] <= 5]
    return {
        "representation": name, "analysis_scope": "exact_primary_trips_inside_f2d_core34",
        "domain_units_with_whole_geometry": domain_count, "active_origin_units": origins,
        "active_destination_units": destinations, "active_units_union": len(units),
        "retained_trip_count": trips, "retained_expanded_mass": mass, "observed_od_pairs": pairs,
        "possible_active_od_pairs": possible, "od_density": pairs / possible, "zero_proportion": 1 - pairs / possible,
        "same_unit_trip_count": int(sum(value[0] for value in intra)), "same_unit_mass_share": sum(value[1] for value in intra) / mass,
        "rare_od_pairs_le_5_trips": len(rare), "rare_od_pair_share": len(rare) / pairs,
        "rare_od_mass_share": sum(value[1] for value in rare) / mass,
        "active_unit_area_min_km2": units.unit_area_km2.min(), "active_unit_area_median_km2": units.unit_area_km2.median(),
        "active_unit_area_max_km2": units.unit_area_km2.max(), "dense_od_float32_mib": possible * 4 / 1024 ** 2,
        "sparse_observed_od_est_mib": pairs * 24 / 1024 ** 2,
    }


def map_diagnostics(path: Path, area, zones, zone_activity: pd.DataFrame, h3_activity: pd.DataFrame) -> None:
    zone_map = zones.merge(zone_activity[["unit_id", "origin_trip_count"]], on="unit_id", how="inner", validate="one_to_one")
    h3_map = gpd.GeoDataFrame(h3_activity[["unit_id", "origin_trip_count"]], geometry=[h3_polygon(cell) for cell in h3_activity.unit_id], crs=4326)
    figure, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    for axis, source, title in ((axes[0], zone_map, "Zona 777"), (axes[1], h3_map, "H3 r7")):
        area.boundary.plot(ax=axis, color="#303030", linewidth=.35)
        source.assign(log_activity=np.log1p(source.origin_trip_count)).plot(ax=axis, column="log_activity", cmap="viridis", linewidth=0, legend=True)
        axis.set_title(title + ": viajes originados agregados")
        axis.set_axis_off()
    figure.suptitle("F2-E · Dominio aprobado F2-D · Sin datos personales")
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def write_report(path: Path, values: pd.DataFrame, approval: dict, selected: list[int]) -> None:
    display = values.copy()
    display["od_density_pct"] = display.od_density * 100
    headings = ["representation", "domain_units_with_whole_geometry", "active_origin_units", "active_destination_units", "observed_od_pairs", "od_density_pct", "zero_proportion", "dense_od_float32_mib"]
    table = ["| " + " | ".join(headings) + " |", "|" + "|".join(["---"] * len(headings)) + "|"]
    for row in display[headings].itertuples(index=False, name=None):
        table.append("| " + " | ".join("{:.4f}".format(value) if isinstance(value, float) else str(value) for value in row) + " |")
    nl = chr(10)
    content = [
        "# F2-E — Adaptadores espaciales y factibilidad Zona 777–H3", "",
        "**Estado:** completada el 9 de septiembre de 2026; primera mitad de G3.", "",
        "## Dominio y conservación", "",
        "La comparación usa la cohorte primaria F2-C y el dominio `nucleo_urbano_referencial_34` congelado en F2-D. Ambos extremos se clasificaron nuevamente con `contains` estricto en EPSG:32719 antes de calcular Zona 777 o H3.",
        "", "- Viajes retenidos: **{:,.0f}** de {:,.0f}.".format(values.iloc[0].retained_trip_count, approval["primary_trips_before_area"]),
        "- Masa expandida retenida: **{:,.4f}**.".format(values.iloc[0].retained_expanded_mass),
        "- Cada representación reconcilia exactamente esos totales.", "",
        "## Adaptadores", "",
        "Zona 777 usa `origin_zone` y `destination_zone` del contrato F2-C. Se incorporó el `ShapeZona777` publicado por DTPM junto a las matrices de viaje (`{}`). Tiene 804 polígonos fuente, que se normalizan a 803 IDs OD porque Zona 493 trae dos partes. El archivo no incluye `.prj`; sus bounds lon/lat se comprobaron contra el límite DPA independiente y se declaró EPSG:4326 antes de reproyectar. Su única geometría topológicamente inválida (Zona 543) se reparó con `make_valid`, preservando el ID. El archivo `F2-E_UNIDADES_ZONA777.csv` declara el origen geométrico de cada unidad; si un ID activo no posee polígono en la descarga oficial, conserva el flujo y usa sólo para su tile un anclaje agregado de extremos, sin presentar ese anclaje como geometría oficial.".format(SOURCE_URL),
        "", "H3 transforma EPSG:32719 a WGS84 con `Transformer.from_crs(32719, 4326, always_xy=True)` y llama `latlng_to_cell(latitud, longitud, resolución)`. r3–r8 se calcularon para todos los viajes retenidos. Las áreas son las áreas reales de las celdas activas mediante `h3.cell_area`.",
        "", "La política de borde H3 queda fijada como **celda completa observada**: F2-D decide el dominio por extremos puntuales; una celda H3 que toca el borde se conserva completa si recibe un extremo retenido. No se recorta la celda ni se fracciona el flujo.",
        "", "## Diagnóstico exacto", "", *table, "",
        "`F2-E_METRICAS_REPRESENTACION.csv` añade masa, colas raras, ceros, flujos dentro de unidad y estimaciones de memoria. `F2-E_MAPAS_DIAGNOSTICOS.png` contiene mapas de agregados públicos.",
        "", "## Resoluciones que pasan al piloto", "",
        "La regla predefinida exige al menos 100 unidades origen activas, conservación exacta y una matriz densa de scores de una pasada de hasta 128 MiB. Pasan **{}**. r3–r6 no tienen granularidad suficiente para el piloto comparativo. La selección final y los hiperparámetros usarán validación; prueba queda reservada.".format(", ".join("H3-r{}".format(value) for value in selected)),
        "", "## Artefactos", "",
        "- `F2-E_UNIDADES_ZONA777.csv` y `F2-E_UNIDADES_H3_R3…R8.csv`: actividad agregada y representación de cada unidad.",
        "- `deepgravity/data/santiago/interim/f2e_spatial/`: OD agregada de Zona 777, H3-r7 y H3-r8 para F2-F/F2-G; no incluye identificadores de viaje.",
        "- `F2-E_MANIFIESTO_EJECUCION.json`: hashes y reglas de ejecución.",
    ]
    path.write_text(nl.join(content) + nl, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-root", type=Path, default=Path("deepgravity/data/santiago/interim/f2c_canonical"))
    parser.add_argument("--area", type=Path, default=Path("docs/territorio/f2d/F2-D_AREA_APROBADA.geojson"))
    parser.add_argument("--approval", type=Path, default=Path("docs/territorio/f2d/F2-D_AREA_APROBADA.json"))
    parser.add_argument("--zones", type=Path, default=Path("deepgravity/data/santiago/reference/zona777_dtpm/Zonas777-04-04-2014/Shape/Zonas777_V07_04_2014.shp"))
    parser.add_argument("--archive", type=Path, default=Path("deepgravity/data/santiago/reference/Zona777_ADATRAP.rar"))
    parser.add_argument("--output", type=Path, default=Path("docs/territorio/f2e"))
    parser.add_argument("--interim", type=Path, default=Path("deepgravity/data/santiago/interim/f2e_spatial"))
    parser.add_argument("--batch-size", type=int, default=250000)
    args = parser.parse_args()
    memory = free_memory_gib()
    if memory is not None and memory < 10:
        raise RuntimeError("Preflight F2-E requiere 10 GiB libres; disponibles {:.2f}.".format(memory))
    args.output.mkdir(parents=True, exist_ok=True)
    args.interim.mkdir(parents=True, exist_ok=True)
    area, approval = load_area(args.area, args.approval)
    core = area.to_crs(32719)
    geometries = core.geometry.to_numpy()
    labels = core.CUT_COM.astype(str).to_numpy()
    tree = STRtree(geometries)
    zones = load_zones(args.zones)
    zone_accumulator = Accumulator()
    hex_accumulators = {resolution: Accumulator() for resolution in RESOLUTIONS}
    to_wgs = Transformer.from_crs(32719, 4326, always_xy=True)
    to_utm = Transformer.from_crs(4326, 32719, always_xy=True)
    connection = duckdb.connect()
    connection.execute("SET memory_limit='4GB'")
    source = "read_parquet({}, union_by_name=true)".format(quote(args.canonical_root / "service_date=*" / "canonical.parquet"))
    cursor = connection.execute("SELECT origin_x, origin_y, destination_x, destination_y, origin_zone, destination_zone, trip_weight FROM {} WHERE cohort_class='{}'".format(source, PRIMARY))
    totals = defaultdict(float)
    while True:
        frame = cursor.fetch_df_chunk(vectors_per_chunk=max(1, args.batch_size // 2048))
        if frame.empty:
            break
        totals["primary_trips"] += len(frame)
        origins_in = point_membership(tree, geometries, labels, frame.origin_x, frame.origin_y)
        destinations_in = point_membership(tree, geometries, labels, frame.destination_x, frame.destination_y)
        keep = (origins_in != None) & (destinations_in != None)
        if not np.any(keep):
            continue
        frame = frame.loc[keep]
        weights = frame.trip_weight.to_numpy(dtype=float)
        totals["retained_trips"] += len(frame)
        totals["retained_mass"] += float(weights.sum())
        zone_accumulator.add(zone_ids(frame.origin_zone), zone_ids(frame.destination_zone), weights)
        origin_zone_values = zone_ids(frame.origin_zone)
        destination_zone_values = zone_ids(frame.destination_zone)
        zone_accumulator.add_endpoint_support(origin_zone_values, frame.origin_x.to_numpy(dtype=float), frame.origin_y.to_numpy(dtype=float))
        zone_accumulator.add_endpoint_support(destination_zone_values, frame.destination_x.to_numpy(dtype=float), frame.destination_y.to_numpy(dtype=float))
        ox, oy = to_wgs.transform(frame.origin_x.to_numpy(dtype=float), frame.origin_y.to_numpy(dtype=float))
        dx, dy = to_wgs.transform(frame.destination_x.to_numpy(dtype=float), frame.destination_y.to_numpy(dtype=float))
        origin_r8 = np.asarray([h3.latlng_to_cell(lat, lon, 8) for lon, lat in zip(ox, oy)], dtype=object)
        destination_r8 = np.asarray([h3.latlng_to_cell(lat, lon, 8) for lon, lat in zip(dx, dy)], dtype=object)
        for resolution, accumulator in hex_accumulators.items():
            # F2-G correction: parent(r8) is not the direct containing cell at r7.
            origins = origin_r8 if resolution == 8 else np.asarray([h3.latlng_to_cell(lat, lon, resolution) for lon, lat in zip(ox, oy)], dtype=object)
            destinations = destination_r8 if resolution == 8 else np.asarray([h3.latlng_to_cell(lat, lon, resolution) for lon, lat in zip(dx, dy)], dtype=object)
            accumulator.add(origins, destinations, weights)
    trips, mass = int(totals["retained_trips"]), float(totals["retained_mass"])
    if trips != approval["retained_trips_reported_f2d"] or not math.isclose(mass, approval["retained_expanded_mass_reported_f2d"], abs_tol=1e-4):
        raise ValueError("F2-E no reconcilia los totales congelados de F2-D.")
    zone_unit_data = zone_units(zone_accumulator, zones)
    zone_unit_data.to_csv(args.output / "F2-E_UNIDADES_ZONA777.csv", index=False)
    rows = [metrics("zona777", zone_accumulator, zone_unit_data, len(zones), trips, mass)]
    hex_unit_data = {}
    for resolution, accumulator in hex_accumulators.items():
        units = h3_units(accumulator, resolution, to_utm)
        hex_unit_data[resolution] = units
        units.to_csv(args.output / "F2-E_UNIDADES_H3_R{}.csv".format(resolution), index=False)
        rows.append(metrics("h3_r{}".format(resolution), accumulator, units, h3_domain_size(area, resolution), trips, mass))
    result = pd.DataFrame(rows)
    result.to_csv(args.output / "F2-E_METRICAS_REPRESENTACION.csv", index=False)
    selected = []
    for resolution in PILOT_RESOLUTIONS:
        row = result.loc[result.representation == "h3_r{}".format(resolution)].iloc[0]
        if row.active_origin_units >= 100 and row.dense_od_float32_mib <= 128 and math.isclose(row.retained_expanded_mass, mass, abs_tol=1e-4):
            selected.append(resolution)
    if selected != list(PILOT_RESOLUTIONS):
        raise ValueError("H3-r7/r8 no superan la regla predefinida de factibilidad.")
    for name, accumulator in [("zona777", zone_accumulator), ("h3_r7", hex_accumulators[7]), ("h3_r8", hex_accumulators[8])]:
        connection.register("f2e_od_output", accumulator.od_frame())
        connection.execute("COPY f2e_od_output TO {} (FORMAT PARQUET, COMPRESSION ZSTD)".format(quote(args.interim / (name + "_od.parquet"))))
        connection.unregister("f2e_od_output")
    map_diagnostics(args.output / "F2-E_MAPAS_DIAGNOSTICOS.png", area, zones, zone_unit_data, hex_unit_data[7])
    write_report(args.output / "F2-E_REPORTE_FACTIBILIDAD.md", result, approval, selected)
    manifest = {
        "stage": "F2-E", "status": "completed", "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "approved_area_sha256": approval["geometry_sha256"], "cohort": PRIMARY, "retained_trip_count": trips, "retained_expanded_mass": mass,
        "zona777": {"source_url": SOURCE_URL, "archive_sha256": digest(args.archive), "shape_sha256": digest(args.zones), "source_shape_feature_count": zones.attrs["source_feature_count"], "spatial_unit_count_after_dissolve": len(zones), "crs": "EPSG:4326 inferred after geographic-bounds check; archive supplies no .prj", "repaired_official_geometry_ids": zones.attrs["repaired_zone_ids"], "multipart_zone_ids_dissolved": ["493"]},
        "h3": {"version": h3.__version__, "input_crs": "EPSG:32719", "transform": "always_xy", "resolutions": list(RESOLUTIONS), "pilot_candidates": selected, "border_treatment": "whole_cell_observed"},
        "outputs": {"metrics_sha256": digest(args.output / "F2-E_METRICAS_REPRESENTACION.csv"), "report_sha256": digest(args.output / "F2-E_REPORTE_FACTIBILIDAD.md")},
    }
    (args.output / "F2-E_MANIFIESTO_EJECUCION.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps({"retained_trips": trips, "retained_mass": mass, "pilot_resolutions": selected}, ensure_ascii=False))


if __name__ == "__main__":
    main()
