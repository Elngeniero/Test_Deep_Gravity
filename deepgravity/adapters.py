"""A common model-data interface for legacy NY, Zona 777 and H3."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .geometry import earth_distance
from .utils import load_data


@dataclass
class FlowBundle:
    tiles: dict
    flows: dict
    features: dict
    centroids: dict
    partitions: dict
    metadata: dict = field(default_factory=dict)
    input_paths: list = field(default_factory=list)
    source_outflow: dict = field(default_factory=dict)

    def validate(self):
        universe = set(self.features)
        if not universe or set(self.centroids) != universe:
            raise ValueError("Features and anchors must cover exactly the same nonempty unit set")
        widths = {len(values) for values in self.features.values()}
        if len(widths) != 1 or not all(np.isfinite(values).all() for values in self.features.values()):
            raise ValueError("Inconsistent or nonfinite feature vectors")
        flattened = [unit for units in self.tiles.values() for unit in units]
        if len(flattened) != len(set(flattened)) or set(flattened) - universe:
            raise ValueError("Each unit must have exactly one tile")
        for coords in self.centroids.values():
            earth_distance(coords, coords)
        assigned = []
        tile_partitions = {}
        oa2tile = {unit: tile for tile, units in self.tiles.items() for unit in units}
        for partition, origins in self.partitions.items():
            if partition not in {"train", "validation", "test"}:
                raise ValueError("Unknown partition name")
            assigned.extend(origins)
            for origin in origins:
                if origin not in universe:
                    raise ValueError("Partition contains an unknown origin")
                if origin not in oa2tile:
                    raise ValueError("Partition origin lacks a tile")
                tile = oa2tile[origin]
                if tile in tile_partitions and tile_partitions[tile] != partition:
                    raise ValueError("A tile crosses origin partitions")
                tile_partitions[tile] = partition
        if len(assigned) != len(set(assigned)):
            raise ValueError("An origin appears more than once across partitions")
        for origin, destinations in self.flows.items():
            if origin not in universe or set(destinations) - universe:
                raise ValueError("Flows reference units outside the destination domain")
            if not all(np.isfinite(value) and value >= 0 for value in destinations.values()):
                raise ValueError("Flows must be finite and nonnegative")
        return self


def resolve_path(value, base):
    value = Path(value)
    return value.resolve() if value.is_absolute() else (Path(base) / value).resolve()


def load_partitions(path, representation, universe):
    assignments = pd.read_csv(path, dtype={"unit_id": str, "tile_id": str, "partition": str})
    if "representation" in assignments:
        assignments = assignments[assignments.representation == representation]
    if assignments.unit_id.duplicated().any() or set(assignments.unit_id) != set(universe):
        raise ValueError("Partition assignment must cover each unit exactly once")
    if assignments.partition.isna().any() or set(assignments.partition) - {"train", "validation", "test"}:
        raise ValueError("Missing or invalid partitions")
    if assignments.groupby("tile_id").partition.nunique().max() != 1:
        raise ValueError("A tile has conflicting partitions")
    tiles = {tile: {unit: {} for unit in frame.unit_id}
             for tile, frame in assignments.groupby("tile_id")}
    active = assignments
    if "origin_trip_count" in active:
        active = active[active.origin_trip_count > 0]
    partitions = {name: sorted(active.loc[active.partition == name, "unit_id"].tolist())
                  for name in ("train", "validation", "test")}
    return tiles, partitions


def load_external_features(config, base, units):
    path = resolve_path(config["features_path"], base)
    columns = config.get("feature_columns")
    if not isinstance(columns, list) or not columns or len(set(columns)) != len(columns):
        raise ValueError("Declare a nonempty, unique feature_columns list")
    # Input features and masses need independent provenance, resolved in F2-I.
    frame = pd.read_csv(path, dtype={"unit_id": str})
    if frame.unit_id.duplicated().any() or set(frame.unit_id) != set(units):
        raise ValueError("External features must cover every approved unit once")
    frame = frame.set_index("unit_id").loc[units]
    values = frame[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("External features contain missing/nonfinite values")
    return dict(zip(units, values.tolist())), path


def load_santiago(config, base, purpose):
    import duckdb
    from pyproj import Transformer

    representation = config["representation"]
    if representation not in {"zona777", "h3_r7", "h3_r8"}:
        raise ValueError("Unsupported approved Santiago representation")
    if config.get("destination_scope", "global") != "global":
        raise ValueError("Santiago requires metropolitan destinations")
    units_path = resolve_path(config["units_path"], base)
    od_path = resolve_path(config["od_path"], base)
    partition_path = resolve_path(config["partitions_path"], base)
    units = pd.read_csv(units_path, dtype={"unit_id": str})
    if units.unit_id.duplicated().any():
        raise ValueError("Duplicate spatial units")
    ids = sorted(units.unit_id)
    units = units.set_index("unit_id").loc[ids]
    transformer = Transformer.from_crs(32719, 4326, always_xy=True)
    lon, lat = transformer.transform(units.unit_x_32719.to_numpy(), units.unit_y_32719.to_numpy())
    anchors = {unit: [float(y), float(x)] for unit, x, y in zip(ids, lon, lat)}
    paths = [units_path, od_path, partition_path]
    if config.get("features_path"):
        features, feature_path = load_external_features(config, base, ids)
        paths.append(feature_path)
    elif purpose == "technical_smoke":
        features = {unit: [] for unit in ids}
    else:
        raise ValueError("Santiago model features await the explicit F2-I contract")
    if purpose != "technical_smoke" and "geometry_source" in units and (
            units.geometry_source != "official_shapezona777").any():
        raise ValueError("Endpoint-support anchors were approved for tiles only; resolve missing zone geometry before scientific training")
    tiles, partitions = load_partitions(partition_path, representation, ids)
    connection = duckdb.connect()
    try:
        od = connection.execute("SELECT * FROM read_parquet(?)", [str(od_path)]).fetchdf()
    finally:
        connection.close()
    weight = config.get("weight", "expanded_mass")
    if weight not in {"trip_count", "expanded_mass"}:
        raise ValueError("Weight must be trip_count or expanded_mass")
    if od.duplicated(["origin_unit_id", "destination_unit_id"]).any():
        raise ValueError("OD pairs must already be aggregated")
    flows = {}
    for origin, destination, value in od[["origin_unit_id", "destination_unit_id", weight]].itertuples(index=False, name=None):
        flows.setdefault(str(origin), {})[str(destination)] = float(value)
    return FlowBundle(tiles, flows, features, anchors, partitions,
                      {"representation": representation, "weight": weight,
                       "anchor_definition": "F2-E spatial representative, not necessarily geometric centroid",
                       "mass_feature": "none", "destination_scope": "global",
                       "features_status": "external" if config.get("features_path") else "technical_distance_only"},
                      paths).validate()


def load_legacy(config, base, purpose):
    root = resolve_path(config["data_dir"], base)
    cache = resolve_path(config["cache_dir"], base) if config.get("cache_dir") else root / "processed"
    columns = config.get("columns", {})
    tiles, units, frame, outflow, features, od, centroids = load_data(root, cache_dir=cache, **columns)
    cache_manifest = cache / "cache_manifest.json"
    if cache_manifest.exists():
        order = json.loads(cache_manifest.read_text(encoding="utf-8"))["centroid_order"]
    else:
        order = config.get("centroid_order")
    if order not in {"lat_lon", "lon_lat"}:
        raise ValueError("Declare centroid_order for an unversioned legacy cache")
    centroids = {str(unit): (json.loads(coords) if isinstance(coords, str) else list(coords))
                 for unit, coords in centroids.items()}
    if order == "lon_lat":
        centroids = {unit: [coords[1], coords[0]] for unit, coords in centroids.items()}
    features = {str(unit): list(values) for unit, values in features.items()}
    mass_feature = config.get("mass_feature", "none")
    if mass_feature == "legacy_observed_outflow":
        if purpose != "legacy_audit":
            raise ValueError("Observed outflow as predictor is restricted to explicit legacy auditing")
        features = {unit: [float(np.log(max(outflow.get(unit, 0), 1e-6)))] + values
                    for unit, values in features.items()}
    elif mass_feature != "none":
        raise ValueError("Use explicit external features instead of an implicit mass predictor")
    paths = list(cache.glob("*"))
    if config.get("partitions_path"):
        partition_path = resolve_path(config["partitions_path"], base)
        tiles, partitions = load_partitions(partition_path, config.get("representation", "new_york"), features)
        paths.append(partition_path)
    else:
        partitions = {}
        for name in ("train", "validation", "test"):
            path = cache / (name + "_tiles.csv")
            if not path.exists():
                partitions[name] = []
                continue
            tile_ids = pd.read_csv(path, header=None, dtype=str)[0].tolist()
            if len(tile_ids) != len(set(tile_ids)) or set(tile_ids) - set(tiles):
                raise ValueError("Invalid legacy tile split")
            partitions[name] = sorted(unit for tile in tile_ids for unit in tiles[tile])
    flows = {}
    outside_pairs, outside_mass = 0, 0.0
    for (origin, destination), value in od.items():
        if origin not in features or destination not in features:
            outside_pairs += 1
            outside_mass += float(value)
        else:
            flows.setdefault(str(origin), {})[str(destination)] = float(value)
    if outside_pairs and purpose == "scientific":
        raise ValueError("Legacy flows outside feature coverage require F2-H audit before scientific use")
    # Reconcile serialised OD against the independent flow table.
    reference = frame.groupby(["residence", "workplace"]).commuters.sum()
    if len(reference) != len(od) or any(not np.isclose(od.get(key, np.nan), value, rtol=1e-12, atol=1e-8)
                                        for key, value in reference.items()):
        raise ValueError("od2flow.pkl does not reconcile with flows_oa.csv.zip")
    return FlowBundle(tiles, flows, features, centroids, partitions,
                      {"representation": "legacy", "mass_feature": mass_feature,
                       "legacy_centroid_order": order, "model_centroid_order": "lat_lon",
                       "outside_feature_support_pairs": outside_pairs,
                       "outside_feature_support_mass": outside_mass,
                       "feature_units_without_tile": len(set(features) - {u for group in tiles.values() for u in group}),
                       "destination_scope": config.get("destination_scope", "origin_tile"),
                       "cache_provenance": "versioned" if cache_manifest.exists() else "legacy_unversioned"},
                      paths, outflow).validate()


def load_bundle(config, base, purpose):
    adapter = config["adapter"]
    if adapter == "santiago":
        return load_santiago(config, base, purpose)
    if adapter == "legacy":
        return load_legacy(config, base, purpose)
    raise ValueError("Unknown data adapter")
