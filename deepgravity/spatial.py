"""Materialize approved Santiago OD counts/mass, incrementally and without trip IDs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import h3
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import STRtree, points, prepare, contains_xy
from shapely.geometry import shape
from shapely.ops import transform

from .preprocessing import digest

REPRESENTATIONS = ("zona777", "h3_r7", "h3_r8")


def quote(path):
    return "'" + Path(path).as_posix().replace("'", "''") + "'"


def write_parquet(connection, frame, path):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    connection.register("f2g_output_frame", frame)
    try:
        connection.execute("COPY f2g_output_frame TO " + quote(path) + " (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        connection.unregister("f2g_output_frame")


class EndpointMapper:
    def __init__(self, area_path, approval_path):
        approval = json.loads(Path(approval_path).read_text(encoding="utf-8"))
        if digest(area_path) != approval["geometry_sha256"]:
            raise ValueError("Approved area hash mismatch")
        area = json.loads(Path(area_path).read_text(encoding="utf-8"))
        project = Transformer.from_crs(4326, 32719, always_xy=True)
        self.to_wgs = Transformer.from_crs(32719, 4326, always_xy=True)
        self.geometries = [transform(project.transform, shape(f["geometry"])) for f in area["features"]]
        prepare(self.geometries)
        self.tree = STRtree(self.geometries)
        self.cache = {}

    def map(self, xs, ys):
        xy = np.column_stack((xs, ys))
        unique, inverse = np.unique(xy, axis=0, return_inverse=True)
        keys = [tuple(value) for value in unique]
        missing = [key for key in keys if key not in self.cache]
        if missing:
            coords = np.asarray(missing)
            memberships = self.tree.query(points(coords[:, 0], coords[:, 1]))
            inside = np.zeros(len(missing), dtype=bool)
            if memberships.size:
                for geometry_index in np.unique(memberships[1]):
                    indices = memberships[0][memberships[1] == geometry_index]
                    inside[indices] |= contains_xy(self.geometries[geometry_index],
                                                   coords[indices, 0], coords[indices, 1])
            lon, lat = self.to_wgs.transform(coords[:, 0], coords[:, 1])
            for key, keep, longitude, latitude in zip(missing, inside, lon, lat):
                self.cache[key] = (bool(keep),
                                   h3.latlng_to_cell(latitude, longitude, 7) if keep else "",
                                   h3.latlng_to_cell(latitude, longitude, 8) if keep else "")
        values = [self.cache[key] for key in keys]
        result = [np.asarray([row[i] for row in values])[inverse] for i in range(3)]
        if len(self.cache) > 300000:
            self.cache.clear()
        return result


def normalize_zones(values):
    return pd.to_numeric(values, errors="raise").to_numpy(dtype=np.int64).astype(str)


def aggregate_batch(frame, mapper, accumulators, lookups):
    origin = mapper.map(frame.origin_x.to_numpy(), frame.origin_y.to_numpy())
    destination = mapper.map(frame.destination_x.to_numpy(), frame.destination_y.to_numpy())
    keep = origin[0] & destination[0]
    weights = frame.trip_weight.to_numpy(dtype=float)[keep]
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("Invalid canonical trip weights")
    assignments = {
        "zona777": (normalize_zones(frame.origin_zone[keep]), normalize_zones(frame.destination_zone[keep])),
        "h3_r7": (origin[1][keep], destination[1][keep]),
        "h3_r8": (origin[2][keep], destination[2][keep]),
    }
    for representation, (origins, destinations) in assignments.items():
        lookup = lookups[representation]
        unknown = (set(origins) | set(destinations)) - set(lookup)
        if unknown:
            if representation == "zona777":
                raise ValueError("Canonical zone outside F2-E support: " + repr(sorted(unknown)))
            # The approved operation is direct assignment at each resolution.
            # F2-E's r8-parent shortcut omitted some directly observed r7 cells.
            # Expand the work arrays; final units are checked against the frozen tile agenda.
            for unit in sorted(unknown):
                lookup[unit] = len(lookup)
            old_counts, old_masses = accumulators[representation]
            extra = len(lookup) - len(old_counts)
            accumulators[representation] = (np.pad(old_counts, ((0, extra), (0, extra))),
                                            np.pad(old_masses, ((0, extra), (0, extra))))
        oi = np.fromiter((lookup[value] for value in origins), dtype=np.int64, count=len(origins))
        di = np.fromiter((lookup[value] for value in destinations), dtype=np.int64, count=len(destinations))
        counts, masses = accumulators[representation]
        np.add.at(counts, (oi, di), 1)
        np.add.at(masses, (oi, di), weights)
    return int(keep.sum()), float(weights.sum())


def matrix_frame(counts, masses, units):
    oi, di = np.nonzero(counts)
    return pd.DataFrame({"origin_unit_id": np.asarray(units)[oi],
                         "destination_unit_id": np.asarray(units)[di],
                         "trip_count": counts[oi, di], "expanded_mass": masses[oi, di]})


def corrected_units(result, representation, reference, schedule):
    origins = result.groupby("origin_unit_id").agg(
        origin_trip_count=("trip_count", "sum"), origin_expanded_mass=("expanded_mass", "sum"))
    destinations = result.groupby("destination_unit_id").agg(
        destination_trip_count=("trip_count", "sum"), destination_expanded_mass=("expanded_mass", "sum"))
    units = origins.join(destinations, how="outer").fillna(0)
    units.index.name = "unit_id"
    units = units.reset_index()
    for column in ("origin_trip_count", "destination_trip_count"):
        units[column] = units[column].astype(np.int64)
    if representation == "zona777":
        geometry_columns = [column for column in reference if column not in units and column != "representation"]
        units = units.merge(reference[["unit_id"] + geometry_columns], on="unit_id", validate="one_to_one")
    else:
        transformer = Transformer.from_crs(4326, 32719, always_xy=True)
        centers = [h3.cell_to_latlng(cell) for cell in units.unit_id]
        xs, ys = transformer.transform([c[1] for c in centers], [c[0] for c in centers])
        units["unit_x_32719"], units["unit_y_32719"] = xs, ys
        units["unit_area_km2"] = [h3.cell_area(cell, unit="km^2") for cell in units.unit_id]
        spans = []
        for cell in units.unit_id:
            boundary = h3.cell_to_boundary(cell)
            bx, by = transformer.transform([p[1] for p in boundary], [p[0] for p in boundary])
            spans.append(max(max(bx) - min(bx), max(by) - min(by)))
        units["unit_bbox_span_m"] = spans
    units["representation"] = representation
    units["tile_id"] = ("E" + (units.unit_x_32719 // 15000).astype(int).astype(str)
                        + "_N" + (units.unit_y_32719 // 15000).astype(int).astype(str))
    units["partition"] = units.tile_id.map(schedule)
    if units.partition.isna().any():
        raise ValueError("Direct H3 assignment requires a tile outside the approved agenda")
    if (units.unit_bbox_span_m >= 15000).any():
        raise ValueError("A corrected unit is not smaller than its tile")
    return units


def materialize(config, config_dir):
    def path(key):
        value = Path(config[key])
        return value if value.is_absolute() else (config_dir / value).resolve()
    root, output = path("canonical_root"), path("output_root")
    partitions_path, area_path, approval_path = path("partitions"), path("area"), path("approval")
    output.mkdir(parents=True, exist_ok=True)
    assignments = pd.read_csv(partitions_path, dtype={"unit_id": str, "tile_id": str})
    unit_ids = {r: sorted(assignments.loc[assignments.representation == r, "unit_id"].tolist())
                for r in REPRESENTATIONS}
    lookups = {r: {unit: i for i, unit in enumerate(ids)} for r, ids in unit_ids.items()}
    mapper = EndpointMapper(area_path, approval_path)
    signature = {"version": 1, "assignment": "direct_latlng_to_cell_per_resolution",
                 "partitions_sha256": digest(partitions_path), "area_sha256": digest(area_path),
                 "h3_version": h3.__version__, "period": config.get("period", "all"),
                 "day_types": config.get("day_types", [])}
    connection = duckdb.connect()
    connection.execute("SET memory_limit='1GB'")
    connection.execute("SET threads=2")
    inputs = sorted(root.glob("service_date=*/canonical.parquet"))
    dates = config.get("service_dates", [])
    if dates:
        inputs = [p for p in inputs if p.parent.name.split("=", 1)[1] in dates]
    if not inputs:
        raise FileNotFoundError("No selected canonical partitions")
    daily = []
    for source in inputs:
        date = source.parent.name.split("=", 1)[1]
        folder = output / ("service_date=" + date)
        manifest_path = folder / "manifest.json"
        fingerprint = dict(signature, input_sha256=digest(source))
        if manifest_path.exists():
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            if saved["signature"] != fingerprint:
                raise ValueError("Existing daily output has different inputs: " + date)
            if any(digest(folder / name) != value for name, value in saved["outputs"].items()):
                raise ValueError("Existing daily output hash mismatch: " + date)
            daily.append(saved)
            print(json.dumps({"date": date, "status": "reused"}), flush=True)
            continue
        folder.mkdir(exist_ok=True)
        if any(folder.iterdir()):
            raise FileExistsError("Incomplete daily output; choose a new output_root: " + str(folder))
        accumulators = {r: (np.zeros((len(lookup), len(lookup)), dtype=np.int64),
                            np.zeros((len(lookup), len(lookup)), dtype=np.float64))
                        for r, lookup in lookups.items()}
        sql = ("SELECT origin_x,origin_y,destination_x,destination_y,origin_zone,destination_zone,trip_weight "
               "FROM read_parquet(" + quote(source) + ") WHERE cohort_class='primary'")
        params = []
        if config.get("period", "all") != "all":
            sql += " AND period=?"
            params.append(config["period"])
        if config.get("day_types"):
            sql += " AND day_type IN (" + ",".join("?" for _ in config["day_types"]) + ")"
            params.extend(config["day_types"])
        cursor = connection.execute(sql, params)
        count, mass, primary = 0, 0.0, 0
        while True:
            frame = cursor.fetch_df_chunk(vectors_per_chunk=25)
            if frame.empty:
                break
            primary += len(frame)
            kept, weight = aggregate_batch(frame, mapper, accumulators, lookups)
            count += kept
            mass += weight
        names = []
        for representation, (counts, masses) in accumulators.items():
            result = matrix_frame(counts, masses, list(lookups[representation]))
            if result.trip_count.sum() != count or not np.isclose(result.expanded_mass.sum(), mass, rtol=1e-12, atol=1e-5):
                raise ValueError("Daily conservation failed")
            name = representation + "_od.parquet"
            write_parquet(connection, result, folder / name)
            names.append(name)
        saved = {"date": date, "signature": fingerprint, "primary_trip_count": primary,
                 "retained_trip_count": count, "retained_expanded_mass": mass,
                 "outputs": {name: digest(folder / name) for name in names}}
        manifest_path.write_text(json.dumps(saved, indent=2), encoding="utf-8")
        daily.append(saved)
        print(json.dumps({"date": date, "status": "written", "retained_trips": count}), flush=True)
    total_count = sum(d["retained_trip_count"] for d in daily)
    total_mass = sum(d["retained_expanded_mass"] for d in daily)
    if len(inputs) == 29 and not dates and config.get("period", "all") == "all" and not config.get("day_types"):
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        if total_count != approval["retained_trips_reported_f2d"] or not np.isclose(
                total_mass, approval["retained_expanded_mass_reported_f2d"], rtol=1e-12, atol=1e-4):
            raise ValueError("Monthly mass differs from frozen F2-D")
    summary, corrected_assignments, comparisons = [], [], []
    units_root = path("units_root")
    tile_schedule = assignments.groupby("tile_id").partition.first().to_dict()
    for representation in REPRESENTATIONS:
        paths = [output / ("service_date=" + d["date"]) / (representation + "_od.parquet") for d in daily]
        relation = "read_parquet([" + ",".join(quote(p) for p in paths) + "])"
        result = connection.execute("SELECT origin_unit_id,destination_unit_id,CAST(sum(trip_count) AS BIGINT) trip_count,"
                                    "sum(expanded_mass) expanded_mass FROM " + relation +
                                    " GROUP BY 1,2 ORDER BY 1,2").fetchdf()
        target = output / (representation + "_od.parquet")
        if not target.exists():
            write_parquet(connection, result, target)
        else:
            existing = connection.execute("SELECT * FROM read_parquet(" + quote(target) + ") ORDER BY 1,2").fetchdf()
            pd.testing.assert_frame_equal(existing, result, rtol=1e-12, atol=1e-5)
        reference_name = "F2-E_UNIDADES_" + ("ZONA777" if representation == "zona777" else "H3_R" + representation[-1]) + ".csv"
        reference = pd.read_csv(units_root / reference_name, dtype={"unit_id": str})
        units = corrected_units(result, representation, reference, tile_schedule)
        units.to_csv(output / (representation + "_units.csv"), index=False)
        corrected_assignments.append(units[["representation", "unit_id", "tile_id", "partition",
                                            "origin_trip_count", "origin_expanded_mass",
                                            "destination_trip_count", "destination_expanded_mass", "unit_bbox_span_m"]])
        old_counts = reference.set_index("unit_id").origin_trip_count
        new_counts = units.set_index("unit_id").origin_trip_count
        comparison_ids = old_counts.index.union(new_counts.index)
        comparisons.append({"representation": representation, "previous_units": len(reference), "direct_units": len(units),
                            "added_units": sorted(set(units.unit_id) - set(reference.unit_id)),
                            "removed_units": sorted(set(reference.unit_id) - set(units.unit_id)),
                            "units_with_changed_origin_count": int((old_counts.reindex(comparison_ids, fill_value=0)
                                                                      != new_counts.reindex(comparison_ids, fill_value=0)).sum()),
                            "active_origins": int((units.origin_trip_count > 0).sum()),
                            "active_destinations": int((units.destination_trip_count > 0).sum()),
                            "od_pairs": len(result), "retained_trips": int(result.trip_count.sum()),
                            "expanded_mass": float(result.expanded_mass.sum())})
        lookup = units.set_index("unit_id")
        result["origin_tile"] = result.origin_unit_id.map(lookup.tile_id)
        result["destination_tile"] = result.destination_unit_id.map(lookup.tile_id)
        result["origin_partition"] = result.origin_unit_id.map(lookup.partition)
        result["destination_partition"] = result.destination_unit_id.map(lookup.partition)
        result["is_cross_tile"] = result.origin_tile != result.destination_tile
        grouped = result.groupby(["origin_partition", "destination_partition", "is_cross_tile"], as_index=False).agg(
            trip_count=("trip_count", "sum"), expanded_mass=("expanded_mass", "sum"))
        grouped.insert(0, "representation", representation)
        summary.append(grouped)
    pd.concat(summary, ignore_index=True).to_csv(output / "cross_tile_summary.csv", index=False)
    pd.concat(corrected_assignments, ignore_index=True).to_csv(output / "partitions.csv", index=False)
    pd.DataFrame([{k: d[k] for k in ("date", "primary_trip_count", "retained_trip_count", "retained_expanded_mass")}
                  for d in daily]).to_csv(output / "daily_conservation.csv", index=False)
    manifest = {"stage": "F2-G", "status": "materialized", "signature": signature,
                "dates": [d["date"] for d in daily], "retained_trip_count": total_count,
                "retained_expanded_mass": total_mass, "destination_scope": "global",
                "f2e_comparison": comparisons,
                "outputs": {name: digest(output / name) for name in
                            [r + "_od.parquet" for r in REPRESENTATIONS] +
                            [r + "_units.csv" for r in REPRESENTATIONS] +
                            ["partitions.csv", "cross_tile_summary.csv", "daily_conservation.csv"]}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    connection.close()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    print(json.dumps(materialize(json.loads(config_path.read_text(encoding="utf-8-sig")), config_path.parent), indent=2))


if __name__ == "__main__":
    main()
