#!/usr/bin/env python3
"""Create a metadata-only manifest for the daily DTPM CSV files.

The script reads only each file header. It never reads data rows or stores
card, trip, or stage identifiers. The raw-data root comes from a local
configuration file or the DTPM_DATA_ROOT environment variable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


FILE_NAME = re.compile(r"^(?P<service_date>\d{4}-\d{2}-\d{2})\.(?P<table>viajes|etapas)\.csv$")
TABLES = ("viajes", "etapas")


def read_local_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_data_root(config_path: Optional[Path]) -> Path:
    data_root = os.environ.get("DTPM_DATA_ROOT")
    if config_path is not None:
        if not config_path.is_file():
            raise FileNotFoundError(f"Local configuration not found: {config_path}")
        data_root = read_local_env(config_path).get("DTPM_DATA_ROOT", data_root)
    if not data_root:
        raise ValueError("Set DTPM_DATA_ROOT or provide --config with that value.")
    root = Path(data_root)
    if not root.is_dir():
        raise NotADirectoryError(f"DTPM_DATA_ROOT is not a directory: {root}")
    return root


def header_metadata(path: Path) -> Dict[str, object]:
    with path.open("rb") as handle:
        raw_header = handle.readline()
    if not raw_header:
        raise ValueError("empty file")
    decoded = raw_header.decode("utf-8-sig").rstrip("\r\n")
    columns = next(csv.reader([decoded], delimiter="|"))
    trailing_empty_columns = 0
    while columns and not columns[-1].strip():
        columns.pop()
        trailing_empty_columns += 1
    return {
        "separator": "|",
        "header_sha256": hashlib.sha256(raw_header).hexdigest(),
        "raw_header_column_count": len(columns) + trailing_empty_columns,
        "schema_column_count": len(columns),
        "trailing_empty_columns": trailing_empty_columns,
        "schema": "|".join(columns),
    }


def expected_dates(november: int) -> Set[str]:
    current = date(november, 11, 1)
    result: Set[str] = set()
    while current.month == 11:
        result.add(current.isoformat())
        current += timedelta(days=1)
    return result


def build_manifest(data_root: Path, output: Path) -> Tuple[int, Dict[str, List[str]]]:
    rows: List[Dict[str, object]] = []
    discovered: Dict[str, Set[str]] = {table: set() for table in TABLES}

    for table in TABLES:
        folder = data_root / table
        if not folder.is_dir():
            raise NotADirectoryError(f"Expected directory not found: {folder}")
        for path in sorted(folder.glob("*.csv")):
            match = FILE_NAME.match(path.name)
            if not match or match.group("table") != table:
                continue
            stat = path.stat()
            row: Dict[str, object] = {
                "service_date": match.group("service_date"),
                "table": table,
                "relative_path": path.relative_to(data_root).as_posix(),
                "size_bytes": stat.st_size,
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "read_status": "header_ok",
                "error": "",
            }
            try:
                row.update(header_metadata(path))
            except (OSError, UnicodeError, csv.Error, ValueError) as error:
                row.update(
                    {
                        "separator": "",
                        "header_sha256": "",
                        "raw_header_column_count": "",
                        "schema_column_count": "",
                        "trailing_empty_columns": "",
                        "schema": "",
                        "read_status": "header_error",
                        "error": type(error).__name__,
                    }
                )
            rows.append(row)
            discovered[table].add(match.group("service_date"))

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "service_date",
        "table",
        "relative_path",
        "size_bytes",
        "modified_utc",
        "separator",
        "raw_header_column_count",
        "schema_column_count",
        "trailing_empty_columns",
        "header_sha256",
        "schema",
        "read_status",
        "error",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    months = {int(value[:4]) for dates in discovered.values() for value in dates}
    if len(months) != 1:
        missing = {table: [] for table in TABLES}
    else:
        expected = expected_dates(months.pop())
        missing = {table: sorted(expected - dates) for table, dates in discovered.items()}
    return len(rows), missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Ignored local env file with DTPM_DATA_ROOT")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/preflight/MANIFIESTO_DTPM_NOV2024.csv"),
        help="Metadata-only CSV to create",
    )
    args = parser.parse_args()
    data_root = resolve_data_root(args.config)
    count, missing = build_manifest(data_root, args.output)
    print(f"manifest_rows={count}")
    for table in TABLES:
        print(f"missing_{table}={','.join(missing[table]) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
