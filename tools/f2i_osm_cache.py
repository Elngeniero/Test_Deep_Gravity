"""Extract tagged OSM geometry once, retaining tags, IDs and source hashes.

The native KeyFilter runs after location storage / area assembly, preserving
untagged nodes required by ways. The SQLite cache is public OSM data only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import shutil
import time
from collections import Counter
from pathlib import Path

import build_f2i_features as base
import osmium
from pyproj import Transformer
from shapely import from_wkb
from shapely.errors import GEOSException
from shapely.ops import transform

KEYS = ("landuse", "natural", "building", "leisure", "amenity", "healthcare",
        "shop", "public_transport", "railway", "aeroway", "highway", "office", "tourism")
SCHEMA = 1


def publish(partial, target):
    # Windows may briefly keep the closed SQLite file open for scanning.
    for attempt in range(10):
        try:
            partial.replace(target)
            return
        except PermissionError:
            if attempt == 9:
                # Some Windows file scanners hold a non-delete-sharing handle.
                # Copy a completed, verified database without deleting its source.
                if target.exists() and target.stat().st_size:
                    raise
                with partial.open('rb') as source, target.open('wb') as destination:
                    shutil.copyfileobj(source,destination,1024*1024)
                if base.sha256(partial) != base.sha256(target):
                    raise ValueError('OSM cache publication hash mismatch')
                return
            time.sleep(.5)


def input_bounds(config, config_file):
    forward = Transformer.from_crs(4326, config["analysis_crs"], always_xy=True)
    reverse = Transformer.from_crs(config["analysis_crs"], 4326, always_xy=True)
    bounds = []
    for branch, path in config["units"].items():
        ids = [r["unit_id"] for r in base.unit_rows(base.config_path(path, config_file))]
        if branch == "zona777":
            all_zones = base.zone_geometries(base.config_path(config["geometries"][branch], config_file), forward)
            geoms = [all_zones[i] for i in ids if i in all_zones]
        else:
            geoms = list(base.h3_geometries(ids, forward).values())
        bounds.extend(transform(reverse.transform, g).bounds for g in geoms)
    return [min(b[0] for b in bounds), min(b[1] for b in bounds),
            max(b[2] for b in bounds), max(b[3] for b in bounds)]


def extract(config_file, target):
    config = base.load_config(config_file)
    pbf = base.config_path(config["osm"]["raw_path"], config_file)
    signature = {"schema": SCHEMA, "pbf_sha256": base.sha256(pbf),
                 "bounds_wgs84": input_bounds(config, config_file), "keys": list(KEYS)}
    if target.exists() and target.stat().st_size:
        with sqlite3.connect(target) as con:
            metadata = json.loads(con.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
        if any(metadata.get(k) != v for k, v in signature.items()):
            raise ValueError("Existing OSM cache belongs to different source/bounds/schema")
        print("Verified complete OSM cache: " + str(target), flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    if partial.exists():
        with sqlite3.connect(partial) as check:
            row = check.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()
            integrity = check.execute('PRAGMA quick_check').fetchone()[0]
        check.close()
        if row and integrity == 'ok' and all(json.loads(row[0]).get(k)==v for k,v in signature.items()):
            publish(partial,target)
            print('OSM_CACHE_COMPLETE recovered completed extraction: '+str(target),flush=True)
            return
        raise FileExistsError("Incomplete extraction exists: " + str(partial))
    con = sqlite3.connect(partial)
    con.execute("CREATE TABLE objects (kind TEXT, osm_id INTEGER, tags TEXT, wkb BLOB, PRIMARY KEY(kind, osm_id))")
    con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    factory = osmium.geom.WKBFactory()
    processor = osmium.FileProcessor(str(pbf)).with_locations().with_areas()
    processor.with_filter(osmium.filter.KeyFilter(*KEYS))
    west, south, east, north = signature["bounds_wgs84"]
    counts, errors, error_examples = Counter(), Counter(), []
    started = last_report = time.monotonic()
    print("OSM extraction started, native tag filter, bbox=" + str(signature["bounds_wgs84"]), flush=True)
    for obj in processor:
        kind = obj.type_str()
        if kind not in ("n", "w", "a"):
            continue
        counts["visited_" + kind] += 1
        if time.monotonic() - last_report > 25:
            print(f"OSM {time.monotonic()-started:.0f}s: {dict(counts)}", flush=True)
            con.commit()
            last_report = time.monotonic()
        # Closed ways are represented by their assembled area only. Roads stay
        # lines unless area=yes explicitly declares a plaza or other surface.
        if kind == "w" and ("highway" not in obj.tags or obj.tags.get("area") == "yes"):
            continue
        try:
            if kind == "n":
                x, y = obj.location.lon, obj.location.lat
                if not west <= x <= east or not south <= y <= north:
                    continue
                geometry = from_wkb(factory.create_point(obj))
            elif kind == "w":
                geometry = from_wkb(factory.create_linestring(obj))
            else:
                geometry = from_wkb(factory.create_multipolygon(obj))
        except (RuntimeError, ValueError, GEOSException) as exc:
            errors[kind] += 1
            if len(error_examples) < 30:
                error_examples.append({"kind": kind, "id": obj.id, "error": str(exc)})
            continue
        if geometry.is_empty:
            errors["empty_"+kind] += 1
            continue
        x1, y1, x2, y2 = geometry.bounds
        if x2 < west or x1 > east or y2 < south or y1 > north:
            continue
        con.execute("INSERT INTO objects VALUES (?,?,?,?)",
                    (kind, obj.id, json.dumps(dict(obj.tags), ensure_ascii=False), geometry.wkb))
        counts["retained_"+kind] += 1
    header = processor.header
    metadata = dict(signature, created_at=base.utc_now(), counts=dict(counts),
                    geometry_errors=dict(errors), error_examples=error_examples,
                    duration_seconds=time.monotonic()-started,
                    pbf_timestamp=header.get("osmosis_replication_timestamp"),
                    generator=header.get("generator"), extractor_sha256=base.sha256(Path(__file__)))
    con.execute("INSERT INTO metadata VALUES ('manifest',?)", (json.dumps(metadata),))
    con.commit()
    con.close()
    publish(partial,target)
    print(json.dumps(metadata, indent=2), flush=True)
    print("OSM_CACHE_COMPLETE " + str(target), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=base.ROOT/"config/f2i_santiago.example.json")
    parser.add_argument("--output", type=Path, default=base.ROOT/"deepgravity/data/santiago/cache/f2i/osm_tagged_v1.sqlite")
    args = parser.parse_args()
    extract(args.config.resolve(), args.output.resolve())
