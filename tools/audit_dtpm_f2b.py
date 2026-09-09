#!/usr/bin/env python3
"""Run F2-B structural and semantic profiling without retaining raw identifiers.

The script reads one CSV at a time in bounded chunks. It writes aggregate,
non-identifying evidence to docs/auditoria and keeps resumable state in an
ignored intermediate directory. Candidate join keys are transformed with a
per-day in-memory keyed hash and the temporary SQLite database is deleted when
the daily audit completes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


TABLES = ("viajes", "etapas")
EMPTY_VALUES = {"", "-", "nan", "none", "null", "na", "n/a"}
VIAJES_COLUMNS = [
    "tipodia",
    "factor_expansion",
    "n_etapas",
    "tviaje",
    "tviaje2",
    "distancia_eucl",
    "distancia_ruta",
    "tiempo_inicio_viaje",
    "tiempo_fin_viaje",
    "periodo_inicio_viaje",
    "periodo_fin_viaje",
    "comuna_inicio_viaje",
    "comuna_fin_viaje",
    "zona_inicio_viaje",
    "zona_fin_viaje",
    "netapassinbajada",
    "ultimaetapaconbajada",
    "tipo_corte_etapa_viaje",
    "id_tarjeta",
    "id_viaje",
]
ETAPAS_COLUMNS = [
    "tipo_dia",
    "tipo_transporte",
    "fExpansionServicioPeriodoTS",
    "fExpansionZonaPeriodoTS",
    "tiene_bajada",
    "tiempo2",
    "tiempo_subida",
    "tiempo_bajada",
    "tiempo_etapa",
    "x_subida",
    "y_subida",
    "x_bajada",
    "y_bajada",
    "dist_ruta_paraderos",
    "dist_eucl_paraderos",
    "comuna_subida",
    "comuna_bajada",
    "zona_subida",
    "zona_bajada",
    "periodoSubida",
    "periodoBajada",
    "id_etapa",
    "correlativo_viajes",
]
NUMERIC_FIELDS = {
    "viajes": [
        "factor_expansion",
        "n_etapas",
        "tviaje",
        "tviaje2",
        "distancia_eucl",
        "distancia_ruta",
        "tiempo_inicio_viaje",
        "tiempo_fin_viaje",
        "netapassinbajada",
        "ultimaetapaconbajada",
    ],
    "etapas": [
        "fExpansionServicioPeriodoTS",
        "fExpansionZonaPeriodoTS",
        "tiempo2",
        "tiempo_subida",
        "tiempo_bajada",
        "tiempo_etapa",
        "x_subida",
        "y_subida",
        "x_bajada",
        "y_bajada",
        "dist_ruta_paraderos",
        "dist_eucl_paraderos",
    ],
}
CATEGORICAL_FIELDS = {
    "viajes": [
        "tipodia",
        "n_etapas",
        "netapassinbajada",
        "ultimaetapaconbajada",
        "periodo_inicio_viaje",
        "periodo_fin_viaje",
        "tipo_corte_etapa_viaje",
    ],
    "etapas": [
        "tipo_dia",
        "tiene_bajada",
        "tipo_transporte",
        "periodoSubida",
        "periodoBajada",
    ],
}
COVERAGE_FIELDS = {
    "viajes": [
        "comuna_inicio_viaje",
        "comuna_fin_viaje",
        "zona_inicio_viaje",
        "zona_fin_viaje",
    ],
    "etapas": [
        "comuna_subida",
        "comuna_bajada",
        "zona_subida",
        "zona_bajada",
    ],
}
KEY_FIELDS = {
    "viajes": ("id_tarjeta", "id_viaje"),
    "etapas": ("id_etapa", "correlativo_viajes"),
}


def read_local_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_data_root(config_path: Path) -> Path:
    if not config_path.is_file():
        raise FileNotFoundError("Local configuration not found: {}".format(config_path))
    root_value = read_local_env(config_path).get("DTPM_DATA_ROOT")
    if not root_value:
        raise ValueError("DTPM_DATA_ROOT is required in the local configuration.")
    root = Path(root_value)
    if not root.is_dir():
        raise NotADirectoryError("DTPM_DATA_ROOT is not a directory: {}".format(root))
    return root


def clean_series(series: pd.Series) -> pd.Series:
    values = series.astype("string").fillna("").str.strip()
    return values.mask(values.str.lower().isin(EMPTY_VALUES), "")


def day_class(service_date: str) -> str:
    weekday = date.fromisoformat(service_date).weekday()
    if weekday == 5:
        return "sabado"
    if weekday == 6:
        return "domingo"
    return "laboral"


class NumericStats:
    def __init__(self) -> None:
        self.valid = 0
        self.missing = 0
        self.invalid = 0
        self.zero = 0
        self.negative = 0
        self.minimum: Optional[float] = None
        self.maximum: Optional[float] = None
        self.sum_value = 0.0
        self.sum_squares = 0.0

    def update(self, source: pd.Series) -> None:
        values = clean_series(source)
        self.missing += int(values.eq("").sum())
        numeric = pd.to_numeric(values.mask(values.eq(""), pd.NA), errors="coerce")
        invalid_mask = values.ne("") & numeric.isna()
        self.invalid += int(invalid_mask.sum())
        valid = numeric.dropna()
        if valid.empty:
            return
        self.valid += int(valid.shape[0])
        self.zero += int(valid.eq(0).sum())
        self.negative += int(valid.lt(0).sum())
        current_min = float(valid.min())
        current_max = float(valid.max())
        self.minimum = current_min if self.minimum is None else min(self.minimum, current_min)
        self.maximum = current_max if self.maximum is None else max(self.maximum, current_max)
        self.sum_value += float(valid.sum())
        self.sum_squares += float((valid * valid).sum())

    def as_dict(self) -> Dict[str, Any]:
        mean = self.sum_value / self.valid if self.valid else None
        variance = (
            max(0.0, (self.sum_squares / self.valid) - (mean * mean))
            if self.valid and mean is not None
            else None
        )
        return {
            "valid": self.valid,
            "missing": self.missing,
            "invalid": self.invalid,
            "zero": self.zero,
            "negative": self.negative,
            "min": self.minimum,
            "max": self.maximum,
            "mean": mean,
            "std": math.sqrt(variance) if variance is not None else None,
        }


class TableProfiler:
    def __init__(self, table: str, columns: Sequence[str]) -> None:
        self.table = table
        self.columns = list(columns)
        self.rows = 0
        self.chunks = 0
        self.empty_by_field: Counter = Counter()
        self.dash_by_field: Counter = Counter()
        self.numeric = {field: NumericStats() for field in NUMERIC_FIELDS[table]}
        self.categories: Dict[str, Counter] = {
            field: Counter() for field in CATEGORICAL_FIELDS[table]
        }
        self.coverage: Dict[str, set] = {field: set() for field in COVERAGE_FIELDS[table]}
        self.coordinate_pairs: Dict[str, Counter] = (
            {"subida": Counter(), "bajada": Counter()} if table == "etapas" else {}
        )

    def update(self, chunk: pd.DataFrame) -> None:
        self.rows += int(chunk.shape[0])
        self.chunks += 1
        for field in self.columns:
            raw = chunk[field].astype("string").fillna("").str.strip()
            self.empty_by_field[field] += int(raw.eq("").sum())
            self.dash_by_field[field] += int(raw.eq("-").sum())
        for field, accumulator in self.numeric.items():
            accumulator.update(chunk[field])
        for field, counter in self.categories.items():
            values = clean_series(chunk[field])
            counter.update(
                {
                    str(value): int(count)
                    for value, count in values.loc[values.ne("")].value_counts().items()
                }
            )
        for field, values_set in self.coverage.items():
            values = clean_series(chunk[field])
            values_set.update(values.loc[values.ne("")].unique().tolist())
        if self.table == "etapas":
            self._update_coordinate_pair(chunk, "subida", "x_subida", "y_subida")
            self._update_coordinate_pair(chunk, "bajada", "x_bajada", "y_bajada")

    def _update_coordinate_pair(
        self, chunk: pd.DataFrame, label: str, x_field: str, y_field: str
    ) -> None:
        x = pd.to_numeric(clean_series(chunk[x_field]).replace("", pd.NA), errors="coerce")
        y = pd.to_numeric(clean_series(chunk[y_field]).replace("", pd.NA), errors="coerce")
        present = x.notna() & y.notna()
        valid = present & x.between(100000, 900000) & y.between(5000000, 10000000)
        pair = self.coordinate_pairs[label]
        pair["both_present"] += int(present.sum())
        pair["valid_epsg_32719_broad"] += int(valid.sum())
        pair["invalid_or_outside_broad_range"] += int((present & ~valid).sum())

    def as_dict(self) -> Dict[str, Any]:
        return {
            "table": self.table,
            "rows": self.rows,
            "chunks": self.chunks,
            "column_count_selected": len(self.columns),
            "empty_by_field": dict(self.empty_by_field),
            "dash_by_field": dict(self.dash_by_field),
            "numeric": {field: value.as_dict() for field, value in self.numeric.items()},
            "categories": {field: dict(value) for field, value in self.categories.items()},
            "coverage_cardinality": {
                field: len(value) for field, value in self.coverage.items()
            },
            "coordinate_pairs": {
                field: dict(value) for field, value in self.coordinate_pairs.items()
            },
        }


def csv_chunks(path: Path, columns: Sequence[str], chunk_size: int) -> Iterable[pd.DataFrame]:
    return pd.read_csv(
        path,
        sep="|",
        usecols=list(columns),
        dtype="string",
        encoding="utf-8-sig",
        keep_default_na=False,
        na_filter=False,
        chunksize=chunk_size,
    )


def hash_key_pairs(left: pd.Series, right: pd.Series, salt: bytes) -> Tuple[List[bytes], int]:
    left_clean = clean_series(left)
    right_clean = clean_series(right)
    keys: List[bytes] = []
    missing = 0
    for first, second in zip(left_clean.tolist(), right_clean.tolist()):
        if not first or not second:
            missing += 1
            continue
        digest = hashlib.blake2b(
            (str(first) + "\x1f" + str(second)).encode("utf-8"),
            digest_size=16,
            key=salt,
        ).digest()
        keys.append(digest)
    return keys, missing


def stage_counts(keys: List[bytes]) -> Iterable[Tuple[bytes, int]]:
    return Counter(keys).items()


def prepare_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute(
        "CREATE TABLE viajes_keys (key BLOB PRIMARY KEY, n_etapas INTEGER) WITHOUT ROWID"
    )
    connection.execute(
        "CREATE TABLE etapas_groups (key BLOB PRIMARY KEY, stage_rows INTEGER NOT NULL) WITHOUT ROWID"
    )
    return connection


def numeric_ints(source: pd.Series) -> List[Optional[int]]:
    numeric = pd.to_numeric(clean_series(source).replace("", pd.NA), errors="coerce")
    values: List[Optional[int]] = []
    for value in numeric.tolist():
        if pd.isna(value) or float(value) != int(float(value)):
            values.append(None)
        else:
            values.append(int(float(value)))
    return values


def profile_day(
    service_date: str,
    data_root: Path,
    work_dir: Path,
    chunk_size: int,
) -> Dict[str, Any]:
    db_path = work_dir / "join-{}.sqlite".format(service_date)
    if db_path.exists():
        db_path.unlink()
    connection = prepare_database(db_path)
    salt = os.urandom(32)
    paths = {
        "viajes": data_root / "viajes" / "{}.viajes.csv".format(service_date),
        "etapas": data_root / "etapas" / "{}.etapas.csv".format(service_date),
    }
    if not all(path.is_file() for path in paths.values()):
        raise FileNotFoundError("Both daily CSV files are required for {}".format(service_date))
    profilers = {
        "viajes": TableProfiler("viajes", VIAJES_COLUMNS),
        "etapas": TableProfiler("etapas", ETAPAS_COLUMNS),
    }
    keys = {
        "viajes": Counter(valid_rows=0, missing_rows=0),
        "etapas": Counter(valid_rows=0, missing_rows=0),
    }
    try:
        for chunk in csv_chunks(paths["viajes"], VIAJES_COLUMNS, chunk_size):
            profilers["viajes"].update(chunk)
            hashed, missing = hash_key_pairs(chunk["id_tarjeta"], chunk["id_viaje"], salt)
            stages = numeric_ints(chunk["n_etapas"])
            valid_indices = [
                index
                for index, (left, right) in enumerate(
                    zip(
                        clean_series(chunk["id_tarjeta"]).tolist(),
                        clean_series(chunk["id_viaje"]).tolist(),
                    )
                )
                if left and right
            ]
            keys["viajes"]["valid_rows"] += len(hashed)
            keys["viajes"]["missing_rows"] += missing
            connection.executemany(
                "INSERT OR IGNORE INTO viajes_keys(key, n_etapas) VALUES (?, ?)",
                [(key, stages[index]) for key, index in zip(hashed, valid_indices)],
            )
            connection.commit()

        for chunk in csv_chunks(paths["etapas"], ETAPAS_COLUMNS, chunk_size):
            profilers["etapas"].update(chunk)
            hashed, missing = hash_key_pairs(
                chunk["id_etapa"], chunk["correlativo_viajes"], salt
            )
            keys["etapas"]["valid_rows"] += len(hashed)
            keys["etapas"]["missing_rows"] += missing
            connection.executemany(
                "INSERT INTO etapas_groups(key, stage_rows) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET stage_rows = stage_rows + excluded.stage_rows",
                list(stage_counts(hashed)),
            )
            connection.commit()

        viajes_unique = connection.execute("SELECT COUNT(*) FROM viajes_keys").fetchone()[0]
        etapas_groups = connection.execute("SELECT COUNT(*) FROM etapas_groups").fetchone()[0]
        etapas_rows = connection.execute(
            "SELECT COALESCE(SUM(stage_rows), 0) FROM etapas_groups"
        ).fetchone()[0]
        matched = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(s.stage_rows), 0), "
            "COALESCE(SUM(CASE WHEN v.n_etapas = s.stage_rows THEN 1 ELSE 0 END), 0), "
            "COALESCE(SUM(CASE WHEN v.n_etapas IS NULL THEN 1 ELSE 0 END), 0) "
            "FROM etapas_groups AS s INNER JOIN viajes_keys AS v ON s.key = v.key"
        ).fetchone()
        union = {
            "candidate": "viajes.(id_tarjeta,id_viaje) <-> etapas.(id_etapa,correlativo_viajes)",
            "viajes_key_valid_rows": int(keys["viajes"]["valid_rows"]),
            "viajes_key_missing_rows": int(keys["viajes"]["missing_rows"]),
            "viajes_key_unique": int(viajes_unique),
            "viajes_key_duplicate_rows": int(keys["viajes"]["valid_rows"] - viajes_unique),
            "etapas_key_valid_rows": int(keys["etapas"]["valid_rows"]),
            "etapas_key_missing_rows": int(keys["etapas"]["missing_rows"]),
            "etapas_key_groups": int(etapas_groups),
            "etapas_rows_in_groups": int(etapas_rows),
            "matched_groups": int(matched[0]),
            "matched_stage_rows": int(matched[1]),
            "matched_groups_n_etapas_equal_stage_rows": int(matched[2]),
            "matched_groups_n_etapas_missing_or_invalid": int(matched[3]),
        }
        return {
            "service_date": service_date,
            "day_class": day_class(service_date),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "chunk_size": chunk_size,
            "tables": {table: profiler.as_dict() for table, profiler in profilers.items()},
            "union": union,
        }
    finally:
        connection.close()
        if db_path.exists():
            db_path.unlink()


def sql_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def duckdb_scan(path: Path) -> str:
    return (
        "read_csv_auto({}, delim='|', header=true, all_varchar=true, "
        "ignore_errors=false)".format(sql_literal(path.as_posix()))
    )


def load_duckdb(dependency_dir: Path) -> Any:
    if not dependency_dir.is_dir():
        raise NotADirectoryError(
            "DuckDB dependency directory not found: {}".format(dependency_dir)
        )
    sys.path.insert(0, str(dependency_dir))
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("DuckDB could not be imported from {}".format(dependency_dir)) from error
    return duckdb


def profile_table_duckdb(
    duckdb: Any, path: Path, table: str, columns: Sequence[str], chunk_size: int
) -> TableProfiler:
    profiler = TableProfiler(table, columns)
    connection = duckdb.connect()
    connection.execute("PRAGMA threads=4")
    query = "SELECT {} FROM {}".format(
        ", ".join(sql_identifier(column) for column in columns), duckdb_scan(path)
    )
    try:
        result = connection.execute(query)
        vectors_per_chunk = max(1, int(math.ceil(float(chunk_size) / 2048.0)))
        while True:
            frame = result.fetch_df_chunk(vectors_per_chunk=vectors_per_chunk)
            if frame is None or frame.empty:
                break
            profiler.update(frame)
    finally:
        connection.close()
    return profiler


def valid_sql_expression(field: str) -> str:
    source = "trim({})".format(sql_identifier(field))
    return (
        "CASE WHEN lower({source}) IN ('', '-', 'nan', 'none', 'null', 'na', 'n/a') "
        "THEN NULL ELSE {source} END"
    ).format(source=source)


def profile_day_duckdb(
    service_date: str,
    data_root: Path,
    chunk_size: int,
    duckdb: Any,
) -> Dict[str, Any]:
    paths = {
        "viajes": data_root / "viajes" / "{}.viajes.csv".format(service_date),
        "etapas": data_root / "etapas" / "{}.etapas.csv".format(service_date),
    }
    if not all(path.is_file() for path in paths.values()):
        raise FileNotFoundError("Both daily CSV files are required for {}".format(service_date))
    profilers = {
        "viajes": profile_table_duckdb(
            duckdb, paths["viajes"], "viajes", VIAJES_COLUMNS, chunk_size
        ),
        "etapas": profile_table_duckdb(
            duckdb, paths["etapas"], "etapas", ETAPAS_COLUMNS, chunk_size
        ),
    }
    connection = duckdb.connect()
    connection.execute("PRAGMA threads=4")
    try:
        viajes_first = valid_sql_expression("id_tarjeta")
        viajes_second = valid_sql_expression("id_viaje")
        etapas_first = valid_sql_expression("id_etapa")
        etapas_second = valid_sql_expression("correlativo_viajes")
        n_stages = "try_cast({} AS DOUBLE)".format(valid_sql_expression("n_etapas"))
        connection.execute(
            "CREATE TEMP TABLE viajes_key_rows AS "
            "SELECT {first} AS first_key, {second} AS second_key, {n_stages} AS n_etapas "
            "FROM {source} WHERE {first} IS NOT NULL AND {second} IS NOT NULL".format(
                first=viajes_first,
                second=viajes_second,
                n_stages=n_stages,
                source=duckdb_scan(paths["viajes"]),
            )
        )
        connection.execute(
            "CREATE TEMP TABLE viajes_keys AS "
            "SELECT first_key, second_key, min(n_etapas) AS n_etapas, count(*) AS row_count "
            "FROM viajes_key_rows GROUP BY first_key, second_key"
        )
        connection.execute(
            "CREATE TEMP TABLE etapas_groups AS "
            "SELECT {first} AS first_key, {second} AS second_key, count(*) AS stage_rows "
            "FROM {source} WHERE {first} IS NOT NULL AND {second} IS NOT NULL "
            "GROUP BY first_key, second_key".format(
                first=etapas_first,
                second=etapas_second,
                source=duckdb_scan(paths["etapas"]),
            )
        )
        viajes_valid = int(
            connection.execute("SELECT count(*) FROM viajes_key_rows").fetchone()[0]
        )
        viajes_unique = int(
            connection.execute("SELECT count(*) FROM viajes_keys").fetchone()[0]
        )
        etapas_valid = int(
            connection.execute("SELECT coalesce(sum(stage_rows), 0) FROM etapas_groups").fetchone()[0]
        )
        etapas_groups = int(
            connection.execute("SELECT count(*) FROM etapas_groups").fetchone()[0]
        )
        matched = connection.execute(
            "SELECT count(*), coalesce(sum(e.stage_rows), 0), "
            "coalesce(sum(CASE WHEN v.n_etapas = e.stage_rows THEN 1 ELSE 0 END), 0), "
            "coalesce(sum(CASE WHEN v.n_etapas IS NULL THEN 1 ELSE 0 END), 0) "
            "FROM etapas_groups AS e INNER JOIN viajes_keys AS v "
            "ON e.first_key = v.first_key AND e.second_key = v.second_key"
        ).fetchone()
        union = {
            "candidate": "viajes.(id_tarjeta,id_viaje) <-> etapas.(id_etapa,correlativo_viajes)",
            "viajes_key_valid_rows": viajes_valid,
            "viajes_key_missing_rows": int(profilers["viajes"].rows - viajes_valid),
            "viajes_key_unique": viajes_unique,
            "viajes_key_duplicate_rows": int(viajes_valid - viajes_unique),
            "etapas_key_valid_rows": etapas_valid,
            "etapas_key_missing_rows": int(profilers["etapas"].rows - etapas_valid),
            "etapas_key_groups": etapas_groups,
            "etapas_rows_in_groups": etapas_valid,
            "matched_groups": int(matched[0]),
            "matched_stage_rows": int(matched[1]),
            "matched_groups_n_etapas_equal_stage_rows": int(matched[2]),
            "matched_groups_n_etapas_missing_or_invalid": int(matched[3]),
        }
    finally:
        connection.close()
    return {
        "service_date": service_date,
        "day_class": day_class(service_date),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "chunk_size": chunk_size,
        "engine": "duckdb",
        "tables": {table: profiler.as_dict() for table, profiler in profilers.items()},
        "union": union,
    }


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_states(state_dir: Path, requested_dates: Sequence[str]) -> List[Dict[str, Any]]:
    states = []
    for service_date in requested_dates:
        path = state_dir / "{}.json".format(service_date)
        if not path.is_file():
            raise FileNotFoundError("Missing completed state for {}".format(service_date))
        states.append(json.loads(path.read_text(encoding="utf-8")))
    return states


def percentage(numerator: int, denominator: int) -> Optional[float]:
    return round(100.0 * numerator / denominator, 4) if denominator else None


def compile_outputs(states: Sequence[Dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_rows: List[Dict[str, Any]] = []
    field_rows: List[Dict[str, Any]] = []
    numeric_rows: List[Dict[str, Any]] = []
    category_rows: List[Dict[str, Any]] = []
    coverage_rows: List[Dict[str, Any]] = []
    union_rows: List[Dict[str, Any]] = []
    for state in states:
        service_date = state["service_date"]
        for table, profile in state["tables"].items():
            profile_rows.append(
                {
                    "service_date": service_date,
                    "day_class": state["day_class"],
                    "table": table,
                    "rows": profile["rows"],
                    "chunks": profile["chunks"],
                    "selected_columns": profile["column_count_selected"],
                }
            )
            for field, empty_count in profile["empty_by_field"].items():
                field_rows.append(
                    {
                        "service_date": service_date,
                        "day_class": state["day_class"],
                        "table": table,
                        "field": field,
                        "empty": empty_count,
                        "dash": profile["dash_by_field"].get(field, 0),
                    }
                )
            for field, metrics in profile["numeric"].items():
                numeric_rows.append(
                    {
                        "service_date": service_date,
                        "day_class": state["day_class"],
                        "table": table,
                        "field": field,
                        **metrics,
                    }
                )
            for field, counts in profile["categories"].items():
                for category, count in sorted(counts.items()):
                    category_rows.append(
                        {
                            "service_date": service_date,
                            "day_class": state["day_class"],
                            "table": table,
                            "field": field,
                            "category": category,
                            "count": count,
                        }
                    )
            for field, cardinality in profile["coverage_cardinality"].items():
                coverage_rows.append(
                    {
                        "service_date": service_date,
                        "day_class": state["day_class"],
                        "table": table,
                        "field": field,
                        "unique_nonempty_values": cardinality,
                    }
                )
            for pair, metrics in profile["coordinate_pairs"].items():
                coverage_rows.append(
                    {
                        "service_date": service_date,
                        "day_class": state["day_class"],
                        "table": table,
                        "field": "coordinates_{}".format(pair),
                        "unique_nonempty_values": "",
                        **metrics,
                    }
                )
        union = dict(state["union"])
        union_rows.append(
            {
                "service_date": service_date,
                "day_class": state["day_class"],
                **union,
                "matched_group_rate_pct": percentage(
                    union["matched_groups"], union["etapas_key_groups"]
                ),
                "matched_viajes_rate_pct": percentage(
                    union["matched_groups"], union["viajes_key_unique"]
                ),
                "stage_row_match_rate_pct": percentage(
                    union["matched_stage_rows"], union["etapas_key_valid_rows"]
                ),
                "n_etapas_exact_rate_pct": percentage(
                    union["matched_groups_n_etapas_equal_stage_rows"],
                    union["matched_groups"],
                ),
            }
        )
    write_csv(
        output_dir / "F2-B_PERFILES_DIARIOS_DTPM_NOV2024.csv",
        ["service_date", "day_class", "table", "rows", "chunks", "selected_columns"],
        profile_rows,
    )
    write_csv(
        output_dir / "F2-B_CAMPOS_DTPM_NOV2024.csv",
        ["service_date", "day_class", "table", "field", "empty", "dash"],
        field_rows,
    )
    write_csv(
        output_dir / "F2-B_NUMERICAS_DTPM_NOV2024.csv",
        [
            "service_date",
            "day_class",
            "table",
            "field",
            "valid",
            "missing",
            "invalid",
            "zero",
            "negative",
            "min",
            "max",
            "mean",
            "std",
        ],
        numeric_rows,
    )
    write_csv(
        output_dir / "F2-B_CATEGORIAS_DTPM_NOV2024.csv",
        ["service_date", "day_class", "table", "field", "category", "count"],
        category_rows,
    )
    write_csv(
        output_dir / "F2-B_COBERTURA_DTPM_NOV2024.csv",
        [
            "service_date",
            "day_class",
            "table",
            "field",
            "unique_nonempty_values",
            "both_present",
            "valid_epsg_32719_broad",
            "invalid_or_outside_broad_range",
        ],
        coverage_rows,
    )
    union_fields = [
        "service_date",
        "day_class",
        "candidate",
        "viajes_key_valid_rows",
        "viajes_key_missing_rows",
        "viajes_key_unique",
        "viajes_key_duplicate_rows",
        "etapas_key_valid_rows",
        "etapas_key_missing_rows",
        "etapas_key_groups",
        "etapas_rows_in_groups",
        "matched_groups",
        "matched_stage_rows",
        "matched_groups_n_etapas_equal_stage_rows",
        "matched_groups_n_etapas_missing_or_invalid",
        "matched_group_rate_pct",
        "matched_viajes_rate_pct",
        "stage_row_match_rate_pct",
        "n_etapas_exact_rate_pct",
    ]
    write_csv(output_dir / "F2-B_UNION_VIAJES_ETAPAS_NOV2024.csv", union_fields, union_rows)
    write_report(states, output_dir)


def write_report(states: Sequence[Dict[str, Any]], output_dir: Path) -> None:
    totals: Dict[str, int] = defaultdict(int)
    by_day_class: Dict[Tuple[str, str], int] = defaultdict(int)
    union_totals: Counter = Counter()
    coordinate_totals: Counter = Counter()
    for state in states:
        for table, profile in state["tables"].items():
            totals[table] += int(profile["rows"])
            by_day_class[(state["day_class"], table)] += int(profile["rows"])
            for pair, metrics in profile["coordinate_pairs"].items():
                coordinate_totals["{}_both_present".format(pair)] += int(
                    metrics.get("both_present", 0)
                )
                coordinate_totals["{}_valid".format(pair)] += int(
                    metrics.get("valid_epsg_32719_broad", 0)
                )
        union_totals.update(state["union"])
    union_totals.pop("candidate", None)
    lines = [
        "# F2-B — Auditoría estructural y semántica DTPM",
        "",
        "**Estado:** resultados generados automáticamente desde lecturas por lotes.",
        "",
        "## Cobertura procesada",
        "",
        "| Tabla | Filas procesadas |",
        "|---|---:|",
        "| viajes | {:,} |".format(totals["viajes"]),
        "| etapas | {:,} |".format(totals["etapas"]),
        "",
        "Se procesaron {} fechas: {}.".format(
            len(states), ", ".join(state["service_date"] for state in states)
        ),
        "",
        "## Unión candidata",
        "",
        "La prueba usa viajes.(id_tarjeta,id_viaje) y etapas.(id_etapa,correlativo_viajes). "
        "Solo se almacenaron hashes efímeros con una sal por fecha; las bases temporales se eliminaron.",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
        "| Claves únicas de viajes | {:,} |".format(union_totals["viajes_key_unique"]),
        "| Grupos de etapas | {:,} |".format(union_totals["etapas_key_groups"]),
        "| Grupos enlazados | {:,} |".format(union_totals["matched_groups"]),
        "| Cobertura de grupos de etapas | {} % |".format(
            percentage(union_totals["matched_groups"], union_totals["etapas_key_groups"])
        ),
        "| Coincidencia exacta n_etapas con número de etapas | {} % |".format(
            percentage(
                union_totals["matched_groups_n_etapas_equal_stage_rows"],
                union_totals["matched_groups"],
            )
        ),
        "",
        "Los resultados diarios y las métricas de campos, números, categorías y cobertura "
        "se guardan en los CSV vecinos de este reporte.",
        "",
        "## Coordenadas de etapas",
        "",
        "| Extremo | Pares completos | Dentro de rango UTM amplio EPSG:32719 |",
        "|---|---:|---:|",
        "| subida | {:,} | {:,} |".format(
            coordinate_totals["subida_both_present"], coordinate_totals["subida_valid"]
        ),
        "| bajada | {:,} | {:,} |".format(
            coordinate_totals["bajada_both_present"], coordinate_totals["bajada_valid"]
        ),
        "",
        "El rango UTM usado para este control es amplio (X 100.000–900.000; "
        "Y 5.000.000–10.000.000) y no constituye todavía la regla territorial final.",
        "",
        "## Límites de interpretación",
        "",
        "- Esta auditoría no construye la cohorte canónica ni decide pesos, exclusiones o área de estudio.",
        "- Los archivos del 30 de noviembre fueron entregados con errores; la cohorte se limita a los días 1–29 y no se imputará ese día.",
        "- La semántica definitiva de los factores de expansión se cerrará tras contrastar estas métricas con el diccionario y la documentación de origen.",
    ]
    (output_dir / "F2-B_REPORTE_AUDITORIA_DTPM_NOV2024.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def daily_dates(data_root: Path) -> List[str]:
    names = {
        path.name.split(".")[0]
        for path in (data_root / "viajes").glob("*.viajes.csv")
    }
    stage_names = {
        path.name.split(".")[0]
        for path in (data_root / "etapas").glob("*.etapas.csv")
    }
    return sorted(names & stage_names)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/dtpm.local.env"))
    parser.add_argument("--chunk-size", type=int, default=50000)
    parser.add_argument("--dates", help="Comma-separated service dates; default is all paired dates.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--engine", choices=("pandas", "duckdb"), default="pandas")
    parser.add_argument(
        "--duckdb-dir",
        type=Path,
        default=Path("deepgravity/data/santiago/interim/f2b_deps"),
        help="Ignored local directory containing DuckDB when --engine=duckdb.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("deepgravity/data/santiago/interim/f2b_audit_state"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("docs/auditoria"))
    args = parser.parse_args()
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size must be positive")
    data_root = resolve_data_root(args.config)
    duckdb = load_duckdb(args.duckdb_dir) if args.engine == "duckdb" else None
    all_dates = daily_dates(data_root)
    requested_dates = args.dates.split(",") if args.dates else all_dates
    missing = sorted(set(requested_dates) - set(all_dates))
    if missing:
        raise ValueError("Dates with no paired CSV: {}".format(", ".join(missing)))
    args.state_dir.mkdir(parents=True, exist_ok=True)
    completed = 0
    for service_date in requested_dates:
        state_path = args.state_dir / "{}.json".format(service_date)
        if args.resume and state_path.is_file():
            print("reused={}".format(service_date))
            completed += 1
            continue
        if args.engine == "duckdb":
            state = profile_day_duckdb(service_date, data_root, args.chunk_size, duckdb)
        else:
            state = profile_day(service_date, data_root, args.state_dir, args.chunk_size)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print("completed={}".format(service_date))
        completed += 1
    states = load_states(args.state_dir, requested_dates)
    compile_outputs(states, args.output_dir)
    print("dates_completed={}".format(completed))
    print("output_dir={}".format(args.output_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
