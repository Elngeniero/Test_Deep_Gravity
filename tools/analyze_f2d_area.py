#!/usr/bin/env python3
"""Generate F2-D territorial alternatives from canonical DTPM trips without identifiers."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely import STRtree, contains_xy, points, prepare


PRIMARY = "primary"
CORE_34 = {
    "Cerrillos", "Cerro Navia", "Conchalí", "El Bosque", "Estación Central", "Huechuraba",
    "Independencia", "La Cisterna", "La Florida", "La Granja", "La Pintana", "La Reina",
    "Las Condes", "Lo Barnechea", "Lo Espejo", "Lo Prado", "Macul", "Maipú", "Ñuñoa",
    "Pedro Aguirre Cerda", "Peñalolén", "Providencia", "Pudahuel", "Puente Alto", "Quilicura",
    "Quinta Normal", "Recoleta", "Renca", "San Bernardo", "San Joaquín", "San Miguel",
    "San Ramón", "Santiago", "Vitacura",
}


def normalized(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]", "", value)


def available_memory_gib():
    if os.name != "nt":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("No se pudo consultar la memoria disponible.")
    return status.ullAvailPhys / 1024 ** 3


def import_duckdb(extra_dir):
    try:
        import duckdb
        return duckdb
    except ImportError:
        if extra_dir:
            sys.path.insert(0, str(extra_dir))
            import duckdb
            return duckdb
        raise


def quoted(path):
    return "'{}'".format(path.as_posix().replace("'", "''"))


def parquet_source(root):
    return "read_parquet({}, union_by_name=true)".format(quoted(root / "service_date=*" / "canonical.parquet"))


def fetch_dataframe(connection, query):
    return connection.execute(query).fetchdf()


def validate_boundaries(path):
    communes = gpd.read_file(path)
    required = {"CUT_COM", "COMUNA", "SUPERFICIE"}
    if required - set(communes.columns):
        raise ValueError("Los límites comunales no contienen {}.".format(", ".join(sorted(required - set(communes.columns)))))
    if communes.crs is None or CRS.from_user_input(communes.crs).to_epsg() != 4326:
        raise ValueError("Los límites comunales deben estar en EPSG:4326.")
    if len(communes) != 52 or not communes.geometry.is_valid.all():
        raise ValueError("Los límites comunales deben contener 52 geometrías válidas de la RM.")
    communes = communes.copy()
    communes["canonical_name"] = communes["COMUNA"].map(normalized)
    if communes["canonical_name"].duplicated().any():
        raise ValueError("Los nombres comunales DPA no son únicos después de normalizar.")
    projected = communes.to_crs(32719)
    communes["area_km2_geometry"] = projected.geometry.area / 1_000_000.0
    return communes, projected


def classify_points(tree, geometries, codes, x_values, y_values):
    assigned = np.full(len(x_values), None, dtype=object)
    location_points = points(x_values.to_numpy(dtype=float), y_values.to_numpy(dtype=float))
    pairs = tree.query(location_points)
    if pairs.size:
        x_coordinates = x_values.to_numpy(dtype=float)
        y_coordinates = y_values.to_numpy(dtype=float)
        for polygon_index in np.unique(pairs[1]):
            candidate_indices = pairs[0][pairs[1] == polygon_index]
            inside = contains_xy(
                geometries[polygon_index], x_coordinates[candidate_indices], y_coordinates[candidate_indices]
            )
            assigned[candidate_indices[inside]] = codes[polygon_index]
    return assigned


def add_grouped(target, grouped, keys):
    values = grouped[list(keys) + ["trip_count", "expanded_mass", "intrazonal_trip_count", "intrazonal_expanded_mass"]]
    for row in values.itertuples(index=False, name=None):
        key = row[:len(keys)]
        current = target.get(key)
        if current is None:
            target[key] = list(row[len(keys):])
        else:
            for index, value in enumerate(row[len(keys):]):
                current[index] += value


def accumulator_dataframe(accumulator, keys):
    rows = [list(key) + values for key, values in accumulator.items()]
    return pd.DataFrame(
        rows,
        columns=list(keys) + ["trip_count", "expanded_mass", "intrazonal_trip_count", "intrazonal_expanded_mass"],
    )


def spatial_aggregate(connection, source, projected, batch_size):
    """Classify every primary endpoint with prepared official polygons, then aggregate."""
    geometries = projected.geometry.to_numpy()
    prepare(geometries)
    tree = STRtree(geometries)
    dpa_codes = projected["CUT_COM"].astype(str).to_numpy()
    commune_accumulator = {}
    zone_accumulator = {}
    dtpm_code_accumulator = {"origin": Counter(), "destination": Counter()}
    totals = Counter()
    sql = """
        SELECT origin_x, origin_y, destination_x, destination_y, origin_commune, destination_commune,
               origin_zone, destination_zone, trip_weight, is_intrazonal
        FROM {source}
        WHERE cohort_class='{cohort}'
    """.format(source=source, cohort=PRIMARY)
    cursor = connection.execute(sql)
    while True:
        frame = cursor.fetch_df_chunk(vectors_per_chunk=max(1, batch_size // 2048))
        if frame.empty:
            break
        totals["primary_trips"] += len(frame)
        totals["primary_expanded_mass"] += float(frame["trip_weight"].sum())
        origin_codes = classify_points(tree, geometries, dpa_codes, frame["origin_x"], frame["origin_y"])
        destination_codes = classify_points(tree, geometries, dpa_codes, frame["destination_x"], frame["destination_y"])
        origin_match = origin_codes != None
        destination_match = destination_codes != None
        totals["origin_geometry_match"] += int(np.count_nonzero(origin_match))
        totals["destination_geometry_match"] += int(np.count_nonzero(destination_match))
        totals["both_geometry_match"] += int(np.count_nonzero(origin_match & destination_match))
        for role, raw_codes, dpa_assignment, matched in (
            ("origin", frame["origin_commune"].astype(str).to_numpy(), origin_codes, origin_match),
            ("destination", frame["destination_commune"].astype(str).to_numpy(), destination_codes, destination_match),
        ):
            dtpm_code_accumulator[role].update(zip(raw_codes[matched], dpa_assignment[matched]))
        matched = frame.loc[origin_match & destination_match, ["origin_zone", "destination_zone", "trip_weight", "is_intrazonal"]].copy()
        matched["origin_code"] = origin_codes[origin_match & destination_match]
        matched["destination_code"] = destination_codes[origin_match & destination_match]
        matched["trip_count"] = 1
        matched["intrazonal_trip_count"] = matched["is_intrazonal"].astype(np.int64)
        matched["intrazonal_expanded_mass"] = matched["trip_weight"] * matched["intrazonal_trip_count"]
        commune_grouped = matched.groupby(["origin_code", "destination_code"], sort=False, as_index=False)[
            ["trip_count", "trip_weight", "intrazonal_trip_count", "intrazonal_expanded_mass"]
        ].sum().rename(columns={"trip_weight": "expanded_mass"})
        zone_grouped = matched.groupby(["origin_code", "destination_code", "origin_zone", "destination_zone"], sort=False, as_index=False)[
            ["trip_count", "trip_weight", "intrazonal_trip_count", "intrazonal_expanded_mass"]
        ].sum().rename(columns={"trip_weight": "expanded_mass"})
        add_grouped(commune_accumulator, commune_grouped, ("origin_code", "destination_code"))
        add_grouped(zone_accumulator, zone_grouped, ("origin_code", "destination_code", "origin_zone", "destination_zone"))
    code_rows = []
    for role, counter in dtpm_code_accumulator.items():
        totals_by_dtpm = Counter()
        for (dtpm_code, _), count in counter.items():
            totals_by_dtpm[dtpm_code] += count
        for (dtpm_code, dpa_code), count in counter.items():
            code_rows.append(
                {
                    "endpoint_role": role,
                    "dtpm_commune_code": dtpm_code,
                    "dpa_cut_com": dpa_code,
                    "endpoint_count": count,
                    "endpoint_share_within_dtpm_code": count / totals_by_dtpm[dtpm_code],
                }
            )
    code_audit = pd.DataFrame(code_rows)
    if not code_audit.empty:
        code_audit["is_modal_mapping"] = code_audit.groupby(["endpoint_role", "dtpm_commune_code"])["endpoint_count"].transform("max") == code_audit["endpoint_count"]
    return (
        accumulator_dataframe(commune_accumulator, ("origin_code", "destination_code")),
        accumulator_dataframe(zone_accumulator, ("origin_code", "destination_code", "origin_zone", "destination_zone")),
        code_audit,
        totals,
    )


def activity_candidate(communes, commune_od):
    endpoint_mass = pd.concat(
        [
            commune_od[["origin_code", "expanded_mass"]].rename(columns={"origin_code": "code"}),
            commune_od[["destination_code", "expanded_mass"]].rename(columns={"destination_code": "code"}),
        ],
        ignore_index=True,
    ).groupby("code", as_index=False)["expanded_mass"].sum()
    total = endpoint_mass["expanded_mass"].sum()
    outside = endpoint_mass[~endpoint_mass["code"].isin(core_codes(communes))].copy()
    outside["share"] = outside["expanded_mass"] / total
    # The extended alternative includes a contiguous neighbour of the core only when
    # it accounts for at least 0.10% of expanded endpoint mass. This rule is fixed
    # before inspecting its comparative OD diagnostics.
    projected = communes.to_crs(32719)
    core_union = projected[projected["CUT_COM"].astype(str).isin(core_codes(communes))].geometry.unary_union
    adjacent = set(
        projected.loc[projected.geometry.boundary.intersects(core_union.boundary), "CUT_COM"].astype(str)
    ) - core_codes(communes)
    additions = set(outside.loc[(outside["code"].isin(adjacent)) & (outside["share"] >= 0.001), "code"])
    return core_codes(communes) | additions, endpoint_mass, sorted(additions)


def core_codes(communes):
    names = {normalized(value) for value in CORE_34}
    result = set(communes.loc[communes["canonical_name"].isin(names), "CUT_COM"].astype(str))
    if len(result) != 34:
        raise ValueError("La referencia núcleo urbano no se pudo mapear a 34 comunas DPA.")
    return result


def candidate_metrics(name, description, codes, commune_od, zone_od, total_trips, total_mass):
    internal_commune = commune_od[
        commune_od["origin_code"].isin(codes) & commune_od["destination_code"].isin(codes)
    ]
    internal_zone = zone_od[
        zone_od["origin_code"].isin(codes) & zone_od["destination_code"].isin(codes)
    ]
    origin_zones = set(internal_zone["origin_zone"].dropna())
    destination_zones = set(internal_zone["destination_zone"].dropna())
    pair_count = internal_zone[["origin_zone", "destination_zone"]].drop_duplicates().shape[0]
    trips = int(internal_commune["trip_count"].sum())
    mass = float(internal_commune["expanded_mass"].sum())
    return {
        "candidate_id": name,
        "description": description,
        "commune_count": len(codes),
        "internal_trip_count": trips,
        "internal_trip_share": trips / total_trips if total_trips else 0.0,
        "internal_expanded_mass": mass,
        "internal_mass_share": mass / total_mass if total_mass else 0.0,
        "active_origin_zones": len(origin_zones),
        "active_destination_zones": len(destination_zones),
        "observed_zone_od_pairs": pair_count,
        "zone_od_density": pair_count / (len(origin_zones) * len(destination_zones)) if origin_zones and destination_zones else 0.0,
        "intrazonal_trip_count": int(internal_commune["intrazonal_trip_count"].sum()),
        "intrazonal_expanded_mass": float(internal_commune["intrazonal_expanded_mass"].sum()),
    }, internal_zone


def render_report(metrics, expanded_additions, coverage, code_audit, total_trips, total_mass):
    modal_mapping = code_audit[code_audit["is_modal_mapping"]]
    minimum_mapping_purity = modal_mapping["endpoint_share_within_dtpm_code"].min()
    coverage_row = coverage.iloc[0]
    lines = [
        "# F2-D — Alternativas de delimitación territorial",
        "",
        "**Estado:** evidencia generada; la delimitación final permanece pendiente de decisión del investigador.",
        "",
        "## Regla evaluada",
        "",
        "Los campos comunales de DTPM contienen códigos, no nombres, y no son unívocos frente a los límites administrativos. F2-D clasifica directamente los dos extremos UTM de cada viaje primario contra los polígonos DPA en EPSG:32719. La regla propuesta para congelar el área exige ambos extremos dentro de las comunas seleccionadas.",
        "El {:.2%} de los viajes primarios tuvo ambos extremos contenidos por la DPA RM. La auditoría completa código DTPM–DPA confirma por qué esos códigos no se usaron para el recorte: su menor correspondencia modal fue {:.2%}.".format(coverage_row["both_geometry_match_share"], minimum_mapping_purity),
        "",
        "## Alternativas",
        "",
        "| Alternativa | Comunas | Viajes internos | Masa expandida interna | Pares OD zonales | Densidad OD zonal |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in metrics.to_dict("records"):
        lines.append(
            "| {candidate_id} | {commune_count:,} | {internal_trip_count:,} ({internal_trip_share:.2%}) | {internal_expanded_mass:,.2f} ({internal_mass_share:.2%}) | {observed_zone_od_pairs:,} | {zone_od_density:.4%} |".format(**row)
        )
    lines.extend([
        "",
        "El núcleo referencial contiene las 34 comunas urbanas tradicionalmente asociadas al Gran Santiago. La alternativa ampliada añade comunas vecinas al núcleo con al menos 0,10 % de la masa expandida de extremos; las adiciones calculadas fueron: {}.".format(", ".join(expanded_additions) if expanded_additions else "ninguna"
        ),
        "",
        "## Cobertura espacial completa",
        "",
        "| Viajes primarios | Origen dentro de DPA RM | Destino dentro de DPA RM | Ambos extremos dentro de DPA RM |",
        "|---:|---:|---:|---:|",
        "| {:,} | {:.2%} | {:.2%} | {:.2%} |".format(total_trips, coverage_row["origin_geometry_match_share"], coverage_row["destination_geometry_match_share"], coverage_row["both_geometry_match_share"]),
    ])
    lines.extend([
        "",
        "## Alcance de esta evidencia",
        "",
        "La cohorte de referencia contiene {:,} viajes primarios y {:,.2f} de masa expandida. Los archivos CSV vecinos contienen las métricas por comuna, por zona y la lista exacta de comunas de cada alternativa. Esta fase no selecciona una alternativa ni ejecuta H3: F2-E comienza después de aprobar la delimitación.".format(total_trips, total_mass),
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", type=Path, default=Path("deepgravity/data/santiago/interim/f2c_canonical"))
    parser.add_argument("--boundaries", type=Path, default=Path("deepgravity/data/santiago/reference/comunas_rm_dpa_2023.geojson"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/territorio/f2d"))
    parser.add_argument("--duckdb-dir", type=Path, default=None, help="Compatibilidad con la dependencia local de F2-B/F2-C.")
    parser.add_argument("--memory-limit", default="4GB")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--minimum-free-gib", type=float, default=10.0)
    parser.add_argument("--batch-size", type=int, default=200000)
    args = parser.parse_args()
    if args.batch_size < 2048:
        raise ValueError("--batch-size debe ser al menos 2048.")
    free_gib = available_memory_gib()
    if free_gib is not None and free_gib < args.minimum_free_gib:
        raise RuntimeError(
            "Memoria libre insuficiente: {:.2f} GiB; el preflight exige al menos {:.2f} GiB antes de procesar.".format(
                free_gib, args.minimum_free_gib
            )
        )
    if not args.canonical_root.is_dir() or not list(args.canonical_root.glob("service_date=*/canonical.parquet")):
        raise FileNotFoundError("No se encontraron las particiones canónicas F2-C.")
    communes, projected = validate_boundaries(args.boundaries)
    duckdb = import_duckdb(args.duckdb_dir)
    connection = duckdb.connect()
    connection.execute("SET threads={}".format(args.threads))
    connection.execute("SET memory_limit={}".format("'{}'".format(args.memory_limit)))
    source = parquet_source(args.canonical_root)
    try:
        commune_od, zone_od, code_audit, spatial_totals = spatial_aggregate(connection, source, projected, args.batch_size)
        total_trips = int(spatial_totals["primary_trips"])
        total_mass = float(spatial_totals["primary_expanded_mass"])
        if int(commune_od["trip_count"].sum()) != int(spatial_totals["both_geometry_match"]):
            raise RuntimeError("La agregación espacial no reconcilia los viajes con ambos extremos dentro de DPA RM.")
        coverage = pd.DataFrame([{
            "primary_trip_count": total_trips,
            "origin_geometry_match_count": int(spatial_totals["origin_geometry_match"]),
            "destination_geometry_match_count": int(spatial_totals["destination_geometry_match"]),
            "both_geometry_match_count": int(spatial_totals["both_geometry_match"]),
            "origin_geometry_match_share": spatial_totals["origin_geometry_match"] / total_trips,
            "destination_geometry_match_share": spatial_totals["destination_geometry_match"] / total_trips,
            "both_geometry_match_share": spatial_totals["both_geometry_match"] / total_trips,
        }])
        core = core_codes(communes)
        expanded, endpoint_mass, expanded_additions = activity_candidate(communes, commune_od)
        expanded_addition_names = communes.set_index(communes["CUT_COM"].astype(str)).loc[expanded_additions, "COMUNA"].tolist()
        candidates = {
            "nucleo_urbano_referencial_34": ("34 comunas urbanas referenciales del Gran Santiago.", core),
            "ampliada_contigua_actividad": ("Núcleo más comunas vecinas con al menos 0,10 % de la masa de extremos.", expanded),
            "region_metropolitana_completa_52": ("Las 52 comunas de la Región Metropolitana disponibles en DPA.", set(communes["CUT_COM"].astype(str))),
        }
        metric_rows, selected_communities = [], []
        for candidate_id, (description, codes) in candidates.items():
            metric, _ = candidate_metrics(candidate_id, description, codes, commune_od, zone_od, total_trips, total_mass)
            metric_rows.append(metric)
            selected_communities.extend({"candidate_id": candidate_id, "CUT_COM": code} for code in sorted(codes))
        metrics = pd.DataFrame(metric_rows)
        selection = pd.DataFrame(selected_communities).merge(
            communes.drop(columns="geometry")[["CUT_COM", "COMUNA", "PROVINCIA", "REGION", "area_km2_geometry"]], on="CUT_COM", how="left"
        )
        origin_stats = commune_od.groupby("origin_code", as_index=False)[["trip_count", "expanded_mass"]].sum().rename(columns={"origin_code": "CUT_COM", "trip_count": "origin_trip_count", "expanded_mass": "origin_expanded_mass"})
        destination_stats = commune_od.groupby("destination_code", as_index=False)[["trip_count", "expanded_mass"]].sum().rename(columns={"destination_code": "CUT_COM", "trip_count": "destination_trip_count", "expanded_mass": "destination_expanded_mass"})
        commune_stats = origin_stats.merge(destination_stats, on="CUT_COM", how="outer").fillna(0)
        commune_stats = communes.drop(columns="geometry").merge(commune_stats, on="CUT_COM", how="left").fillna(0)
        commune_stats["endpoint_expanded_mass_per_km2"] = (commune_stats["origin_expanded_mass"] + commune_stats["destination_expanded_mass"]) / commune_stats["area_km2_geometry"]
        origin_zones = zone_od.groupby("origin_zone", as_index=False)[["trip_count", "expanded_mass"]].sum().rename(columns={"origin_zone": "zone_id", "trip_count": "origin_trip_count", "expanded_mass": "origin_expanded_mass"})
        destination_zones = zone_od.groupby("destination_zone", as_index=False)[["trip_count", "expanded_mass"]].sum().rename(columns={"destination_zone": "zone_id", "trip_count": "destination_trip_count", "expanded_mass": "destination_expanded_mass"})
        zone_stats = origin_zones.merge(destination_zones, on="zone_id", how="outer").fillna(0)
    finally:
        connection.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output_dir / "F2-D_ALTERNATIVAS_TERRITORIALES.csv", index=False)
    selection.to_csv(args.output_dir / "F2-D_COMUNAS_POR_ALTERNATIVA.csv", index=False)
    commune_stats.sort_values("endpoint_expanded_mass_per_km2", ascending=False).to_csv(args.output_dir / "F2-D_METRICAS_COMUNA.csv", index=False)
    zone_stats.sort_values("origin_expanded_mass", ascending=False).to_csv(args.output_dir / "F2-D_METRICAS_ZONA.csv", index=False)
    coverage.to_csv(args.output_dir / "F2-D_COBERTURA_ESPACIAL.csv", index=False)
    code_audit.to_csv(args.output_dir / "F2-D_AUDITORIA_CODIGO_COMUNA_DTPM.csv", index=False)
    (args.output_dir / "F2-D_REPORTE_DELIMITACION.md").write_text(render_report(metrics, expanded_addition_names, coverage, code_audit, total_trips, total_mass), encoding="utf-8")
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_root": str(args.canonical_root),
        "canonical_partitions": len(list(args.canonical_root.glob("service_date=*/canonical.parquet"))),
        "boundary_file": str(args.boundaries),
        "boundary_sha256": hashlib.sha256(args.boundaries.read_bytes()).hexdigest(),
        "crs_analysis": "EPSG:32719",
        "cohort_class": PRIMARY,
        "inclusion_rule": "both endpoint coordinates must be contained in selected DPA communal polygons",
        "free_memory_gib_before_run": free_gib,
        "duckdb_version": duckdb.__version__,
        "batch_size": args.batch_size,
        "candidate_ids": list(candidates),
    }
    (args.output_dir / "F2-D_MANIFIESTO_EJECUCION.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("output={}".format(args.output_dir))
    print("candidates={}".format(len(metrics)))


if __name__ == "__main__":
    main()
