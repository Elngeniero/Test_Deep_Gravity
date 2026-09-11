"""Independent F2-G aggregate verification; exports only public aggregate evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import duckdb
import numpy as np
import pandas as pd

from deepgravity.adapters import load_santiago
from deepgravity.data_loader import FlowDataset
from deepgravity.preprocessing import digest
from deepgravity.runner import make_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--tile-schedule", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.data.resolve()
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    if len(manifest["dates"]) != 29:
        raise AssertionError("The monthly F2-G verification requires all 29 dates")
    for name, expected in manifest["outputs"].items():
        if digest(data / name) != expected:
            raise AssertionError("Artifact checksum differs: " + name)
    daily = pd.read_csv(data / "daily_conservation.csv")
    if daily.retained_trip_count.sum() != approval["retained_trips_reported_f2d"]:
        raise AssertionError("Daily counts do not reconcile with F2-D")
    np.testing.assert_allclose(daily.retained_expanded_mass.sum(),
                               approval["retained_expanded_mass_reported_f2d"], rtol=1e-12, atol=1e-4)
    partitions = pd.read_csv(data / "partitions.csv", dtype={"unit_id": str, "tile_id": str})
    schedule = pd.read_csv(args.tile_schedule, dtype={"tile_id": str}).set_index("tile_id").partition
    if partitions.duplicated(["representation", "unit_id"]).any():
        raise AssertionError("Duplicate unit assignments")
    if not partitions.partition.eq(partitions.tile_id.map(schedule)).all():
        raise AssertionError("The approved tile agenda changed")
    connection = duckdb.connect()
    reports = []
    for representation in ("zona777", "h3_r7", "h3_r8"):
        path = data / (representation + "_od.parquet")
        summary = connection.execute(
            "SELECT count(*),sum(trip_count),sum(expanded_mass),count(DISTINCT origin_unit_id),"
            "count(DISTINCT destination_unit_id) FROM read_parquet(?)", [str(path)]).fetchone()
        if summary[1] != approval["retained_trips_reported_f2d"]:
            raise AssertionError("Wrong OD trip count")
        np.testing.assert_allclose(summary[2], approval["retained_expanded_mass_reported_f2d"], rtol=1e-12, atol=1e-4)
        columns = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchdf().column_name.tolist()
        if columns != ["origin_unit_id", "destination_unit_id", "trip_count", "expanded_mass"]:
            raise AssertionError("Unexpected fields in model OD artefact")
        config = {"representation": representation, "units_path": str(data / (representation + "_units.csv")),
                  "partitions_path": str(data / "partitions.csv"), "od_path": str(path), "weight": "expanded_mass"}
        bundle = load_santiago(config, data, "technical_smoke")
        dataset = make_dataset(bundle, bundle.partitions["train"], {}, False)
        cross_origin = next(origin for origin in dataset.list_IDs if any(
            dataset.oa2tile[d] != dataset.oa2tile[origin] and flow > 0
            for d, flow in bundle.flows.get(origin, {}).items()))
        if len(dataset.candidates(cross_origin)) != len(bundle.features):
            raise AssertionError("Destination support is restricted")
        if not any(dataset.oa2tile[d] != dataset.oa2tile[cross_origin]
                   for d in dataset.candidates(cross_origin)):
            raise AssertionError("Cross-tile destinations have been dropped")
        # Reconcile every origin against independently aggregated daily work files.
        per_origin = connection.execute(
            "SELECT origin_unit_id,sum(trip_count) trip_count,sum(expanded_mass) expanded_mass "
            "FROM read_parquet(?) GROUP BY 1", [str(path)]).fetchdf().set_index("origin_unit_id")
        units = pd.read_csv(data / (representation + "_units.csv"), dtype={"unit_id": str}).set_index("unit_id")
        aligned = units.loc[per_origin.index]
        np.testing.assert_array_equal(per_origin.trip_count, aligned.origin_trip_count)
        np.testing.assert_allclose(per_origin.expanded_mass, aligned.origin_expanded_mass, rtol=1e-12, atol=1e-5)
        reports.append({"representation": representation, "od_pairs": int(summary[0]),
                        "trip_count": int(summary[1]), "expanded_mass": float(summary[2]),
                        "active_origins": int(summary[3]), "active_destinations": int(summary[4]),
                        "candidate_units": len(bundle.features),
                        "train_origins": len(bundle.partitions["train"]),
                        "validation_origins": len(bundle.partitions["validation"]),
                        "test_origins": len(bundle.partitions["test"]),
                        "cross_tile_destinations_verified": True})
    connection.close()
    args.output.mkdir(parents=True, exist_ok=True)
    for original, name in (("daily_conservation.csv", "F2-G_CONSERVACION_DIARIA.csv"),
                           ("cross_tile_summary.csv", "F2-G_FLUJOS_CRUZADOS.csv"),
                           ("partitions.csv", "F2-G_PARTICIONES_UNIDADES.csv"),
                           ("zona777_units.csv", "F2-G_UNIDADES_ZONA777.csv"),
                           ("h3_r7_units.csv", "F2-G_UNIDADES_H3_R7.csv"),
                           ("h3_r8_units.csv", "F2-G_UNIDADES_H3_R8.csv")):
        shutil.copyfile(data / original, args.output / name)
    pd.DataFrame(reports).to_csv(args.output / "F2-G_VERIFICACION_RAMA.csv", index=False)
    output = {"status": "verified", "dates": len(daily), "branches": reports,
              "materialization": manifest, "approved_tile_schedule_sha256": digest(args.tile_schedule),
              "approved_area_manifest_sha256": digest(args.approval),
              "tests_of_real_data": "loading, aggregation, geometry and partition checks; no Santiago model trained"}
    (args.output / "F2-G_VERIFICACION.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": output["status"], "branches": reports}, indent=2))


if __name__ == "__main__":
    main()

