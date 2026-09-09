#!/usr/bin/env python3
"""Build reanudable F2-C: viajes canónicos DTPM sin identificadores directos."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path


EMPTY = ("", "-", "nan", "none", "null", "na", "n/a")
HASH_VERSION = "sha256-salted-v1"
RANGE = {"xmin": 100000, "xmax": 900000, "ymin": 5000000, "ymax": 10000000}


def local_env(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def data_root(config):
    root = Path(local_env(config).get("DTPM_DATA_ROOT", ""))
    if not root.is_dir():
        raise ValueError("DTPM_DATA_ROOT inválido en {}".format(config))
    return root


def dates(root):
    left = {p.name.split(".")[0] for p in (root / "viajes").glob("*.viajes.csv")}
    right = {p.name.split(".")[0] for p in (root / "etapas").glob("*.etapas.csv")}
    return sorted(left & right)


def calendar_type(service_date):
    weekday = date.fromisoformat(service_date).weekday()
    return "sabado" if weekday == 5 else "domingo" if weekday == 6 else "laboral"


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def ident(value):
    return '"' + value.replace('"', '""') + '"'


def clean(field):
    source = "trim(cast({} as varchar))".format(ident(field))
    return "case when lower({}) in ({}) then null else {} end".format(
        source, ", ".join(literal(value) for value in EMPTY), source
    )


def scan(path):
    return "read_csv_auto({}, delim='|', header=true, all_varchar=true, ignore_errors=false)".format(
        literal(path.as_posix())
    )


def load_duckdb(path):
    sys.path.insert(0, str(path))
    import duckdb
    return duckdb


def salt(path):
    if path.is_file():
        value = path.read_bytes()
        if len(value) < 32:
            raise ValueError("La sal F2-C debe tener al menos 32 bytes.")
        return value
    path.parent.mkdir(parents=True, exist_ok=True)
    value = os.urandom(32)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)
    return value


def setup(connection, temp_dir):
    connection.execute("PRAGMA threads=4")
    connection.execute("PRAGMA memory_limit='6GB'")
    connection.execute("PRAGMA temp_directory={}".format(literal(temp_dir.as_posix())))


def count_row(connection, query):
    cursor = connection.execute(query)
    names = [value[0] for value in cursor.description]
    row = cursor.fetchone()
    return dict(zip(names, row))


def build_day(duckdb, service_date, root, output, hash_salt, dry_run):
    viajes = root / "viajes" / "{}.viajes.csv".format(service_date)
    etapas = root / "etapas" / "{}.etapas.csv".format(service_date)
    if not viajes.is_file() or not etapas.is_file():
        raise FileNotFoundError("Falta un CSV para {}".format(service_date))
    scratch = Path(tempfile.mkdtemp(prefix="f2c-", dir=str(output.parent)))
    connection = duckdb.connect()
    try:
        setup(connection, scratch)
        connection.execute(
            """
            CREATE TEMP TABLE trips AS
            SELECT {card} card_key, {trip} trip_key,
                   try_cast({nstages} AS BIGINT) n_stages,
                   {source_day_type} source_day_type_code,
                   try_cast({weight} AS DOUBLE) trip_weight,
                   {start_time} start_time_source, {end_time} end_time_source,
                   {period} period, {origin_zone} origin_zone,
                   {destination_zone} destination_zone,
                   {origin_commune} origin_commune,
                   {destination_commune} destination_commune,
                   try_cast({last_flag} AS BIGINT) last_stage_alighting_flag
            FROM {source}
            WHERE {card} IS NOT NULL AND {trip} IS NOT NULL
            """.format(
                card=clean("id_tarjeta"), trip=clean("id_viaje"),
                nstages=clean("n_etapas"), source_day_type=clean("tipodia"),
                weight=clean("factor_expansion"), start_time=clean("tiempo_inicio_viaje"),
                end_time=clean("tiempo_fin_viaje"), period=clean("periodo_inicio_viaje"),
                origin_zone=clean("zona_inicio_viaje"), destination_zone=clean("zona_fin_viaje"),
                origin_commune=clean("comuna_inicio_viaje"),
                destination_commune=clean("comuna_fin_viaje"),
                last_flag=clean("ultimaetapaconbajada"), source=scan(viajes)
            )
        )
        connection.execute(
            """
            CREATE TEMP TABLE stages AS
            SELECT {card} card_key, {trip} trip_key,
                   try_cast({stage_order} AS BIGINT) stage_order,
                   try_cast({has_bajada} AS BIGINT) has_bajada,
                   try_cast({origin_x} AS DOUBLE) origin_x,
                   try_cast({origin_y} AS DOUBLE) origin_y,
                   try_cast({destination_x} AS DOUBLE) destination_x,
                   try_cast({destination_y} AS DOUBLE) destination_y
            FROM {source}
            WHERE {card} IS NOT NULL AND {trip} IS NOT NULL
            """.format(
                card=clean("id_etapa"), trip=clean("correlativo_viajes"),
                stage_order=clean("correlativo_etapas"), has_bajada=clean("tiene_bajada"),
                origin_x=clean("x_subida"), origin_y=clean("y_subida"),
                destination_x=clean("x_bajada"), destination_y=clean("y_bajada"),
                source=scan(etapas)
            )
        )
        connection.execute(
            """
            CREATE TEMP TABLE ranked AS
            WITH source AS (
                SELECT *,
                  CASE WHEN origin_x BETWEEN {xmin} AND {xmax}
                         AND origin_y BETWEEN {ymin} AND {ymax} THEN 1 ELSE 0 END origin_ok,
                  CASE WHEN has_bajada=1
                         AND destination_x BETWEEN {xmin} AND {xmax}
                         AND destination_y BETWEEN {ymin} AND {ymax} THEN 1 ELSE 0 END destination_ok
                FROM stages
            )
            SELECT *,
              row_number() OVER (PARTITION BY card_key,trip_key ORDER BY stage_order ASC NULLS LAST) first_rank,
              row_number() OVER (PARTITION BY card_key,trip_key ORDER BY stage_order DESC NULLS LAST) final_rank,
              row_number() OVER (
                PARTITION BY card_key,trip_key
                ORDER BY CASE WHEN destination_ok=1 THEN 0 ELSE 1 END, stage_order DESC NULLS LAST
              ) latest_destination_rank
            FROM source
            """.format(**RANGE)
        )
        connection.execute(
            """
            CREATE TEMP TABLE stage_groups AS
            SELECT card_key,trip_key,count(*) stage_rows,count(DISTINCT stage_order) distinct_orders,
              min(stage_order) first_order,max(stage_order) final_order,
              max(CASE WHEN first_rank=1 THEN origin_x END) origin_x,
              max(CASE WHEN first_rank=1 THEN origin_y END) origin_y,
              max(CASE WHEN first_rank=1 THEN origin_ok ELSE 0 END) origin_ok,
              max(CASE WHEN final_rank=1 THEN destination_x END) final_destination_x,
              max(CASE WHEN final_rank=1 THEN destination_y END) final_destination_y,
              max(CASE WHEN final_rank=1 THEN has_bajada ELSE 0 END) final_has_bajada,
              max(CASE WHEN final_rank=1 THEN destination_ok ELSE 0 END) final_destination_ok,
              max(CASE WHEN latest_destination_rank=1 AND destination_ok=1 THEN destination_x END) latest_destination_x,
              max(CASE WHEN latest_destination_rank=1 AND destination_ok=1 THEN destination_y END) latest_destination_y,
              max(CASE WHEN latest_destination_rank=1 AND destination_ok=1 THEN 1 ELSE 0 END) latest_destination_ok
            FROM ranked GROUP BY card_key,trip_key
            """
        )
        connection.execute(
            """
            CREATE TEMP TABLE canonical AS
            WITH joined AS (
              SELECT t.*,g.*,
                CASE WHEN t.n_stages>=1 AND g.stage_rows=t.n_stages
                           AND g.distinct_orders=t.n_stages AND g.first_order=1
                           AND g.final_order=t.n_stages THEN 1 ELSE 0 END sequence_ok,
                CASE WHEN t.origin_zone IS NOT NULL THEN 1 ELSE 0 END origin_zone_ok,
                CASE WHEN t.destination_zone IS NOT NULL THEN 1 ELSE 0 END destination_zone_ok,
                CASE WHEN t.trip_weight IS NOT NULL AND t.trip_weight>=0 THEN 1 ELSE 0 END weight_ok
              FROM trips t LEFT JOIN stage_groups g ON t.card_key=g.card_key AND t.trip_key=g.trip_key
            ), classified AS (
              SELECT *,
                CASE WHEN sequence_ok=1 AND origin_ok=1 AND final_has_bajada=1
                           AND final_destination_ok=1 AND last_stage_alighting_flag=1
                           AND origin_zone_ok=1 AND destination_zone_ok=1 AND weight_ok=1
                     THEN 'primary'
                     WHEN origin_ok=1 AND latest_destination_ok=1 AND weight_ok=1
                     THEN 'secondary_observed' ELSE 'excluded' END cohort_class,
                CASE WHEN final_has_bajada=1 AND final_destination_ok=1 THEN 'observed_final_stage'
                     WHEN latest_destination_ok=1 THEN 'observed_latest_valid_bajada'
                     ELSE 'no_observed_destination' END endpoint_quality,
                CASE WHEN sequence_ok=1 AND origin_ok=1 AND final_has_bajada=1
                                AND final_destination_ok=1 AND last_stage_alighting_flag=1
                                AND origin_zone_ok=1 AND destination_zone_ok=1 AND weight_ok=1
                     THEN 'primary_eligible'
                     WHEN n_stages IS NULL OR n_stages<1 THEN 'invalid_n_etapas'
                     WHEN stage_rows IS NULL OR stage_rows<>n_stages THEN 'n_etapas_mismatch'
                     WHEN sequence_ok=0 THEN 'stage_order_incoherent'
                     WHEN origin_ok=0 THEN 'invalid_origin_coordinate'
                     WHEN origin_zone_ok=0 THEN 'missing_origin_zone'
                     WHEN destination_zone_ok=0 THEN 'missing_destination_zone'
                     WHEN last_stage_alighting_flag<>1 THEN 'trip_without_final_bajada_flag'
                     WHEN final_has_bajada<>1 THEN 'final_stage_without_bajada'
                     WHEN final_destination_ok<>1 THEN 'invalid_final_destination_coordinate'
                     WHEN weight_ok=0 THEN 'invalid_factor_expansion'
                     ELSE 'not_primary_unclassified' END exclusion_reason
              FROM joined
            )
            SELECT sha256(concat({salt},chr(31),{service_date},chr(31),card_key,chr(31),trip_key)) trip_key_hash,
              {service_date} service_date,{day_type} day_type,source_day_type_code,
              try_cast(start_time_source AS TIMESTAMP) start_time,
              try_cast(end_time_source AS TIMESTAMP) end_time,period,
              origin_x,origin_y,
              CASE WHEN endpoint_quality='observed_final_stage' THEN final_destination_x ELSE latest_destination_x END destination_x,
              CASE WHEN endpoint_quality='observed_final_stage' THEN final_destination_y ELSE latest_destination_y END destination_y,
              origin_zone,destination_zone,origin_commune,destination_commune,
              trip_weight,1.0 unexpanded_weight,n_stages,stage_rows,first_order,final_order,
              CASE WHEN origin_zone IS NOT NULL AND origin_zone=destination_zone THEN 1 ELSE 0 END is_intrazonal,
              cohort_class,endpoint_quality,exclusion_reason
            FROM classified
            """.format(
                salt=literal(hash_salt.hex()), service_date=literal(service_date),
                day_type=literal(calendar_type(service_date))
            )
        )
        metrics = count_row(
            connection,
            """
            SELECT (SELECT count(*) FROM trips) valid_viajes_keys,
                   (SELECT count(*) FROM stages) valid_etapas_keys,
                   count(*) matched_trips,
                   count(*) FILTER (WHERE cohort_class='primary') primary_trips,
                   count(*) FILTER (WHERE cohort_class='secondary_observed') secondary_trips,
                   count(*) FILTER (WHERE cohort_class='excluded') excluded_trips,
                   count(*) FILTER (WHERE cohort_class='primary' AND trip_weight=0) primary_zero_weight_trips,
                   count(*) FILTER (WHERE cohort_class='primary' AND trip_weight>0) primary_positive_weight_trips,
                   coalesce(sum(trip_weight) FILTER (WHERE cohort_class='primary'),0) primary_expanded_mass,
                   count(*) FILTER (WHERE start_time IS NOT NULL) parseable_start_time,
                   count(*) FILTER (WHERE end_time IS NOT NULL) parseable_end_time
            FROM canonical
            """
        )
        metrics["reason_counts"] = {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT exclusion_reason,count(*) FROM canonical GROUP BY exclusion_reason"
            ).fetchall()
        }
        metrics["endpoint_counts"] = {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT endpoint_quality,count(*) FROM canonical GROUP BY endpoint_quality"
            ).fetchall()
        }
        if not dry_run:
            target = output / "service_date={}".format(service_date) / "canonical.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            pending = target.with_name("canonical.parquet.pending")
            if pending.exists():
                pending.unlink()
            connection.execute(
                "COPY (SELECT * FROM canonical ORDER BY trip_key_hash) TO {} (FORMAT PARQUET, COMPRESSION ZSTD)".format(
                    literal(pending.as_posix())
                )
            )
            if target.exists():
                target.unlink()
            pending.replace(target)
            metrics["output_bytes"] = target.stat().st_size
        metrics.update({
            "service_date": service_date, "day_type": calendar_type(service_date),
            "hash_version": HASH_VERSION, "created_utc": datetime.now(timezone.utc).isoformat()
        })
        return metrics
    finally:
        connection.close()
        shutil.rmtree(scratch, ignore_errors=True)


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compile_outputs(states, output):
    output.mkdir(parents=True, exist_ok=True)
    fields = ["service_date","day_type","valid_viajes_keys","valid_etapas_keys","matched_trips",
              "primary_trips","secondary_trips","excluded_trips","primary_zero_weight_trips",
              "primary_positive_weight_trips","primary_expanded_mass","parseable_start_time",
              "parseable_end_time","output_bytes"]
    write_csv(output / "F2-C_RECONCILIACION_DIARIA_DTPM_NOV2024.csv", fields,
              [{field: state.get(field, "") for field in fields} for state in states])
    reasons = []
    for state in states:
        reasons.extend({"service_date": state["service_date"], "day_type": state["day_type"],
                        "exclusion_reason": reason, "trip_count": count}
                       for reason, count in state["reason_counts"].items())
    write_csv(output / "F2-C_DESCARTES_DIARIOS_DTPM_NOV2024.csv",
              ["service_date","day_type","exclusion_reason","trip_count"], reasons)
    total = lambda name: sum(float(state.get(name, 0) or 0) for state in states)
    matched, primary, secondary, excluded = [int(total(name)) for name in
        ("matched_trips","primary_trips","secondary_trips","excluded_trips")]
    if matched != primary + secondary + excluded:
        raise RuntimeError("La reconciliación de cohortes F2-C falló.")
    reason_totals, endpoint_totals = Counter(), Counter()
    for state in states:
        reason_totals.update(state["reason_counts"])
        endpoint_totals.update(state["endpoint_counts"])
    pct = lambda value: "n/a" if not matched else "{:.4f}".format(100 * value / matched)
    lines = [
        "# F2-C — Contrato canónico y reconciliación DTPM", "",
        "**Estado:** particiones canónicas generadas desde lecturas diarias reanudables.", "",
        "## Cohorte", "", "| Métrica | Valor |", "|---|---:|",
        "| Fechas procesadas | {} |".format(len(states)),
        "| Viajes unidos | {:,} |".format(matched),
        "| Cohorte primaria | {:,} ({} %) |".format(primary, pct(primary)),
        "| Cohorte secundaria observada | {:,} ({} %) |".format(secondary, pct(secondary)),
        "| Excluidos | {:,} ({} %) |".format(excluded, pct(excluded)), "",
        "La primaria requiere secuencia completa, origen de la primera etapa, bajada válida en la etapa final, bandera ultimaetapaconbajada, zonas de viaje y peso no negativo. No incluye filtro territorial.", "",
        "## Masa primaria", "", "| Métrica | Valor |", "|---|---:|",
        "| Masa con factor_expansion | {:,.4f} |".format(total("primary_expanded_mass")),
        "| Conteo sin expansión | {:,.0f} |".format(total("primary_trips")),
        "| Viajes con peso positivo | {:,.0f} |".format(total("primary_positive_weight_trips")),
        "| Viajes con peso cero conservados | {:,.0f} |".format(total("primary_zero_weight_trips")), "",
        "factor_expansion es el peso expandido propuesto porque el diccionario lo define a nivel de matriz OD de zonas 777. Los factores de etapa no sustituyen un peso de viaje; cada fila conserva unexpanded_weight=1.0.", "",
        "## Causas exclusivas fuera de la primaria", "", "| Causa | Viajes |", "|---|---:|"
    ]
    lines.extend("| {} | {:,} |".format(reason, count) for reason, count in sorted(reason_totals.items()) if reason != "primary_eligible")
    lines.extend(["", "## Calidad de extremos", "", "| Calidad | Viajes |", "|---|---:|"])
    lines.extend("| {} | {:,} |".format(label, count) for label, count in sorted(endpoint_totals.items()))
    lines.extend(["", "## Trazabilidad", "",
                  "- Las particiones contienen solo trip_key_hash con sal local ignorada por Git; no contienen identificadores de tarjeta, viaje ni etapa.",
                  "- La cohorte secundaria se conserva por cobertura, pero no se usará para comparar Zona 777 y H3.",
                  "- F2-D decidirá el área y F2-E el tratamiento de viajes intrazonales o intracelda."])
    (output / "F2-C_REPORTE_CONTRATO_DTPM_NOV2024.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/dtpm.local.env"))
    parser.add_argument("--dates")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--duckdb-dir", type=Path, default=Path("deepgravity/data/santiago/interim/f2b_deps"))
    parser.add_argument("--output-dir", type=Path, default=Path("deepgravity/data/santiago/interim/f2c_canonical"))
    parser.add_argument("--state-dir", type=Path, default=Path("deepgravity/data/santiago/interim/f2c_state"))
    parser.add_argument("--summary-dir", type=Path, default=Path("docs/auditoria"))
    parser.add_argument("--salt-file", type=Path, default=Path("deepgravity/data/santiago/interim/f2c_trip_hash_salt.bin"))
    args = parser.parse_args()
    duckdb = load_duckdb(args.duckdb_dir)
    root = data_root(args.config)
    available = dates(root)
    requested = args.dates.split(",") if args.dates else available
    missing = sorted(set(requested) - set(available))
    if missing:
        raise ValueError("Fechas sin par de CSV: {}".format(", ".join(missing)))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    hash_salt = salt(args.salt_file)
    for service_date in requested:
        state = args.state_dir / "{}.json".format(service_date)
        parquet = args.output_dir / "service_date={}".format(service_date) / "canonical.parquet"
        if args.resume and state.is_file() and (args.dry_run or parquet.is_file()):
            print("reused={}".format(service_date))
            continue
        result = build_day(duckdb, service_date, root, args.output_dir, hash_salt, args.dry_run)
        if not args.dry_run:
            state.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("completed={}".format(service_date))
    if not args.dry_run:
        states = [json.loads((args.state_dir / "{}.json".format(value)).read_text(encoding="utf-8")) for value in requested]
        compile_outputs(states, args.summary_dir)
        print("dates_completed={}".format(len(states)))


if __name__ == "__main__":
    main()
