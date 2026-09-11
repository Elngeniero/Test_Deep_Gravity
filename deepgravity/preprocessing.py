"""Raw legacy preprocessing; never invoked merely by importing a model."""
from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_FILES = ("tileid2oa2handmade_features.json", "oa_gdf.csv.gz",
               "flows_oa.csv.zip", "oa2features.pkl", "od2flow.pkl", "oa2centroid.pkl")
CACHE_VERSION = 2


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def raw_fingerprint(root):
    patterns = ("tessellation.*", "output_areas.*", "flows.csv", "features.csv")
    paths = sorted({path for pattern in patterns for path in Path(root).glob(pattern)
                    if path.is_file()})
    return {path.name: digest(path) for path in paths}


def is_cache_complete(root, cache_dir=None, options=None):
    cache = Path(cache_dir) if cache_dir else Path(root) / "processed"
    if not all((cache / name).is_file() for name in CACHE_FILES):
        return False
    manifest_path = cache / "cache_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["version"] != CACHE_VERSION:
                return False
            if options is not None and manifest.get("options") != options:
                return False
            if manifest["outputs"] != {name: digest(cache / name) for name in CACHE_FILES}:
                return False
            sources = raw_fingerprint(root)
            if sources and manifest["inputs"] != sources:
                return False
        except (ValueError, KeyError):
            return False
    return True


def write_support_files(cache, units, flows, features, tiles, centroids):
    """Write aggregated OD pairs, keeping zero and fractional weights."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    if flows[["residence", "workplace", "commuters"]].isna().any().any():
        raise ValueError("Flows cannot have missing IDs or weights")
    if not np.isfinite(flows.commuters).all() or (flows.commuters < 0).any():
        raise ValueError("Flows must be finite and nonnegative before aggregation")
    flows = flows.groupby(["residence", "workplace"], as_index=False).commuters.sum()
    if not np.isfinite(flows.commuters).all() or (flows.commuters < 0).any():
        raise ValueError("Flows must be finite and nonnegative")
    unit_ids = set(units.geo_code)
    if (set(flows.residence) | set(flows.workplace)) - unit_ids:
        raise ValueError("Flow references an unknown output area")
    od2flow = {(o, d): float(value) for o, d, value in
               flows[["residence", "workplace", "commuters"]].itertuples(index=False, name=None)}
    units.to_csv(cache / "oa_gdf.csv.gz", index=False)
    flows.to_csv(cache / "flows_oa.csv.zip", index=False)
    for name, value in (("od2flow.pkl", od2flow), ("oa2features.pkl", features),
                        ("oa2centroid.pkl", centroids)):
        with (cache / name).open("wb") as handle:
            pickle.dump(value, handle, protocol=4)
    (cache / "tileid2oa2handmade_features.json").write_text(
        json.dumps(tiles, sort_keys=True), encoding="utf-8")


def compute_support_files(db_dir, tile_id_column="tile_ID", tile_geometry="geometry",
                          oa_id_column="oa_ID", oa_geometry="geometry",
                          flow_origin_column="origin", flow_destination_column="destination",
                          flow_flows_column="flow", cache_dir=None, projected_crs=None):
    import geopandas as gpd

    root = Path(db_dir)
    cache = Path(cache_dir) if cache_dir else root / "processed"
    options = {"tile_id_column": tile_id_column, "tile_geometry": tile_geometry,
               "oa_id_column": oa_id_column, "oa_geometry": oa_geometry,
               "flow_origin_column": flow_origin_column,
               "flow_destination_column": flow_destination_column,
               "flow_flows_column": flow_flows_column, "projected_crs": projected_crs}

    def read_geometry(stem):
        path = next((root / (stem + ext) for ext in (".shp", ".geojson")
                     if (root / (stem + ext)).exists()), None)
        if path is None:
            raise FileNotFoundError("Missing raw geometry: " + stem)
        frame = gpd.read_file(path)
        if frame.crs is None:
            raise ValueError("Geometry CRS must be declared: " + stem)
        return frame

    areas, tiles = read_geometry("output_areas"), read_geometry("tessellation")
    areas[oa_id_column] = areas[oa_id_column].astype(str)
    tiles[tile_id_column] = tiles[tile_id_column].astype(str)
    if areas[oa_id_column].duplicated().any() or tiles[tile_id_column].duplicated().any():
        raise ValueError("Geometry IDs must be unique")
    projected_crs = projected_crs or areas.estimate_utm_crs()
    projected = areas.to_crs(projected_crs)
    centers = projected[oa_geometry].centroid
    centers_wgs = gpd.GeoSeries(centers, crs=projected.crs).to_crs(4326)
    projected_tiles = tiles.to_crs(projected.crs)
    mapping = {}
    for unit, point in zip(areas[oa_id_column], centers):
        matches = projected_tiles.loc[projected_tiles[tile_geometry].covers(point), tile_id_column].tolist()
        if len(matches) != 1:
            raise ValueError("Centroid must belong to exactly one tile: " + unit)
        mapping.setdefault(matches[0], {})[unit] = {}
    area_km2 = projected[oa_geometry].area.to_numpy() / 1e6
    if not np.isfinite(area_km2).all() or (area_km2 <= 0).any():
        raise ValueError("Output areas must have positive projected area")
    centroids = {unit: [point.y, point.x] for unit, point in zip(areas[oa_id_column], centers_wgs)}
    units = pd.DataFrame({"geo_code": areas[oa_id_column].tolist(),
                          "centroid": [json.dumps(centroids[u]) for u in areas[oa_id_column]],
                          "area_km2": area_km2})
    path = root / "features.csv"
    if path.exists():
        frame = pd.read_csv(path, dtype={oa_id_column: str})
        if oa_id_column not in frame or frame[oa_id_column].duplicated().any():
            raise ValueError("features.csv requires unique output area IDs")
        columns = [name for name in frame if name != oa_id_column]
        frame = frame.set_index(oa_id_column).reindex(units.geo_code)
        values = frame[columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Features require complete, finite numeric values")
        features = dict(zip(units.geo_code, values.tolist()))
    else:
        features = {unit: [] for unit in units.geo_code}
    flow_columns = [flow_origin_column, flow_destination_column, flow_flows_column]
    flows = pd.read_csv(root / "flows.csv", usecols=flow_columns,
                        dtype={flow_origin_column: str, flow_destination_column: str})
    flows = flows.rename(columns=dict(zip(flow_columns, ["residence", "workplace", "commuters"])))
    write_support_files(cache, units, flows, features, mapping, centroids)
    manifest = {"version": CACHE_VERSION, "centroid_order": "lat_lon",
                "projected_crs": str(projected.crs), "feature_transform": "as supplied in features.csv",
                "inputs": raw_fingerprint(root), "options": options,
                "outputs": {name: digest(cache / name) for name in CACHE_FILES}}
    (cache / "cache_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return cache
