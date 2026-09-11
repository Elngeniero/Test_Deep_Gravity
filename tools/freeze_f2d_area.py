#!/usr/bin/env python3
"""Materialize the F2-D area explicitly approved by the researcher on 2026-09-09."""

import csv
import hashlib
import json
from pathlib import Path

from shapely.geometry import shape


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "docs/territorio/f2d"
    source = root / "deepgravity/data/santiago/reference/comunas_rm_dpa_2023.geojson"
    selection = directory / "F2-D_COMUNAS_POR_ALTERNATIVA.csv"
    candidate = "nucleo_urbano_referencial_34"
    target = directory / "F2-D_AREA_APROBADA.geojson"
    manifest = directory / "F2-D_AREA_APROBADA.json"
    if target.exists() or manifest.exists():
        raise FileExistsError("El área ya está materializada; no se reemplaza una decisión aprobada.")
    with selection.open(encoding="utf-8", newline="") as handle:
        codes = {row["CUT_COM"] for row in csv.DictReader(handle) if row["candidate_id"] == candidate}
    document = json.loads(source.read_text(encoding="utf-8"))
    features = sorted(
        (feature for feature in document["features"] if feature["properties"]["CUT_COM"] in codes),
        key=lambda feature: feature["properties"]["CUT_COM"],
    )
    if len(codes) != 34 or len(features) != 34:
        raise ValueError("La selección debe contener exactamente 34 comunas únicas.")
    for feature in features:
        polygon = shape(feature["geometry"])
        if polygon.is_empty or not polygon.is_valid:
            raise ValueError("Geometría vacía o inválida en el área aprobada.")
    payload = json.dumps(
        {"type": "FeatureCollection", "name": candidate, "features": features},
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    record = {
        "status": "approved_by_researcher",
        "approval_date": "2026-09-09",
        "candidate_id": candidate,
        "geometry_file": target.name,
        "geometry_sha256": hashlib.sha256(payload).hexdigest(),
        "source_file": source.relative_to(root).as_posix(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "selection_file": selection.name,
        "selection_sha256": hashlib.sha256(selection.read_bytes()).hexdigest(),
        "commune_codes": sorted(codes),
        "commune_names": [feature["properties"]["COMUNA"] for feature in features],
        "stored_crs": "EPSG:4326",
        "analysis_crs": "EPSG:32719",
        "endpoint_inclusion": "Each endpoint must be strictly contained in at least one selected municipal polygon after projecting polygons to EPSG:32719.",
        "trip_inclusion": "Both endpoints must satisfy endpoint_inclusion.",
        "boundary_rule": "Use contains as in the F2-D analysis; points exactly on municipal boundaries are excluded. Preserve municipal polygons separately to reproduce this predicate.",
        "primary_trips_before_area": 60682293,
        "retained_trips_reported_f2d": 60513881,
        "excluded_trips_reported_f2d": 168412,
        "retained_expanded_mass_reported_f2d": 85777662.9386,
        "h3_border_treatment": "Pending F2-E; this approval fixes the trip domain only.",
    }
    target.write_bytes(payload)
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Area aprobada: 34 geometrías originales válidas; 168412 viajes fuera del área según F2-D.")
    print(target.relative_to(root).as_posix())
    print(manifest.relative_to(root).as_posix())


if __name__ == "__main__":
    main()
