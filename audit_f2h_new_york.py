"""Audit the frozen NY cache and independently replay CPC; no input mutation.

Run inventory while the separate 20-epoch training runs, then finalize.
The legacy-axis diagnostic is intentionally confined to this audit script.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from importlib import metadata
import json
from pathlib import Path
import pickle
import platform
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import torch

from deepgravity.models.deepgravity import NN_MultinomialRegression
from deepgravity.runner import run, write_json

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "deepgravity/data/new_york"
OUT = ROOT / "docs/experimentos/f2h"
TRAIN = ROOT / "runs/f2h_new_york/f2h_train_20ep_20260912"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_cache():
    cache = DATA / "processed"
    values = []
    for name in ("oa2features.pkl", "od2flow.pkl", "oa2centroid.pkl"):
        with (cache / name).open("rb") as stream:
            values.append(pickle.load(stream))
    tiles = json.loads((cache / "tileid2oa2handmade_features.json").read_text())
    splits = {p: pd.read_csv(cache / (p + "_tiles.csv"), header=None, dtype=str)[0].tolist()
              for p in ("train", "test")}
    flows = pd.read_csv(cache / "flows_oa.csv.zip", dtype={"residence": str, "workplace": str})
    return (*values, tiles, splits, flows)


def independent_replay(checkpoint_path, legacy_axes=False):
    """Direct cache inputs, vectorized spherical distances and L1 CPC identity.

    This does not call FlowDataset, geometry.earth_distance, evaluate or metrics.
    Each test origin uses every destination in its assigned tile, including self.
    """
    features, od, centroids, tiles, splits, flows = read_cache()
    outgoing = flows.groupby("residence").commuters.sum().to_dict()
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model = NN_MultinomialRegression(39, 256, "deepgravity", 0.0, torch.device("cpu"))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    rows = []
    with torch.no_grad():
        for tile in splits["test"]:
            ids = sorted(tiles[tile])
            if not ids:
                continue
            geo = np.asarray([centroids[u] for u in ids], dtype=float)
            # Cached order is lon, lat. The historical caller interpreted it as lat, lon.
            if not legacy_axes:
                geo = geo[:, ::-1]
            radians = np.radians(geo)
            attrs = np.asarray([[np.log(max(outgoing.get(u, 0), 1e-6))] + list(features[u])
                                for u in ids], dtype=float)
            for index, origin in enumerate(ids):
                delta = radians - radians[index]
                hav = np.sin(delta[:, 0] / 2)**2 + np.cos(radians[:, 0]) * np.cos(radians[index, 0]) * np.sin(delta[:, 1] / 2)**2
                dist = 2 * 6371.01 * np.arcsin(np.sqrt(np.clip(hav, 0, 1)))
                x = np.concatenate([np.repeat(attrs[index:index + 1], len(ids), axis=0), attrs, dist[:, None]], axis=1)
                score = model(torch.tensor(x, dtype=torch.float32)).flatten().double().numpy()
                weights = np.exp(score - score.max())
                probs = weights / weights.sum()
                y = np.asarray([od.get((origin, dest), 0.0) for dest in ids], dtype=np.float64)
                predicted = probs * y.sum()
                denominator = float(y.sum() + predicted.sum())
                l1 = float(np.abs(y - predicted).sum())
                overlap = float(2 * np.minimum(y, predicted).sum())
                cpc = 1 - l1 / denominator if denominator else 0.0
                assert np.isclose(overlap / denominator if denominator else 0, cpc, atol=1e-12)
                assert np.isclose(y.sum(), predicted.sum(), rtol=1e-12, atol=1e-8)
                rows.append(dict(origin=origin, tile=tile, cpc=cpc, cpc_numerator=overlap,
                                 observed_mass=float(y.sum()), predicted_mass=float(predicted.sum()),
                                 full_domain_observed_mass=float(outgoing.get(origin, 0)),
                                 destination_count=len(ids), l1_error=l1))
    return pd.DataFrame(rows)


def summarize(origins, prefix):
    _, _, _, mapping, splits, _ = read_cache()
    grouped = origins.groupby("tile").agg(
        cpc_numerator=("cpc_numerator", "sum"), observed_mass=("observed_mass", "sum"),
        predicted_mass=("predicted_mass", "sum"), full_domain_observed_mass=("full_domain_observed_mass", "sum"),
        origins=("origin", "size"))
    tiles = grouped.reindex(splits["test"], fill_value=0).reset_index()
    tiles["empty_assigned_tile"] = [not bool(mapping[t]) for t in tiles.tile]
    den = tiles.observed_mass + tiles.predicted_mass
    tiles["cpc"] = np.divide(tiles.cpc_numerator, den, out=np.zeros(len(tiles)), where=den != 0)
    full_den = 2 * tiles.full_domain_observed_mass
    tiles["legacy_mixed_support_ratio"] = np.divide(tiles.cpc_numerator, full_den, out=np.zeros(len(tiles)), where=full_den != 0)
    origins.to_csv(OUT / (prefix + "_origins.csv"), index=False)
    tiles.to_csv(OUT / (prefix + "_tiles.csv"), index=False)
    mass = float(origins.observed_mass.sum())
    pred = float(origins.predicted_mass.sum())
    full = float(origins.full_domain_observed_mass.sum())
    nonempty = ~tiles.empty_assigned_tile
    result = dict(cpc_global=float(origins.cpc_numerator.sum() / (mass + pred)),
                  cpc_mean_assigned_tiles=float(tiles.cpc.mean()),
                  cpc_mean_nonempty_tiles=float(tiles.loc[nonempty, "cpc"].mean()),
                  cpc_mean_positive_tiles=float(tiles.loc[tiles.cpc > 0, "cpc"].mean()),
                  cpc_mean_origin=float(origins.cpc.mean()), assigned_tiles=len(tiles),
                  nonempty_tiles=int(nonempty.sum()), positive_cpc_tiles=int((tiles.cpc > 0).sum()),
                  zero_mass_nonempty_tiles=int((nonempty & (tiles.observed_mass == 0)).sum()),
                  zero_mass_tiles_with_external_outflow=int((nonempty & (tiles.observed_mass == 0) & (tiles.full_domain_observed_mass > 0)).sum()),
                  origins=len(origins), evaluated_pairs=int(origins.destination_count.sum()),
                  within_tile_mass=mass, predicted_mass=pred, full_origin_outflow=full,
                  within_tile_fraction_of_full_outflow=mass / full,
                  excluded_outflow=full - mass,
                  max_origin_mass_error=float((origins.observed_mass - origins.predicted_mass).abs().max()),
                  empty_cpc_convention=0.0)
    write_json(OUT / (prefix + "_metrics.json"), result)
    return result, tiles


def inventory():
    OUT.mkdir(parents=True, exist_ok=True)
    features, od, centroids, tiles, splits, flows = read_cache()
    tracked = subprocess.check_output(["git", "-c", "safe.directory=" + ROOT.as_posix(), "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    inputs = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(DATA.rglob("*")) if p.is_file()}
    old_checkpoint = ROOT / "deepgravity/results/model_DG_new_york.pt"
    old_csv = ROOT / "deepgravity/results/tile2cpc_DG_new_york.csv"
    for p in (old_checkpoint, old_csv):
        inputs[p.relative_to(ROOT).as_posix()] = sha(p)
    checkpoint = torch.load(old_checkpoint, map_location="cpu")
    steps = sorted({int(v["step"]) for v in checkpoint["optimizer_state_dict"]["state"].values()})
    assert set(splits["train"]).isdisjoint(splits["test"])
    tile_rows = [{"tile": tile, "partition": name, "origins": len(tiles[tile])}
                 for name, ids in splits.items() for tile in ids]
    pd.DataFrame(tile_rows).to_csv(OUT / "partitions_tiles.csv", index=False)
    assignment = {u: t for t, units in tiles.items() for u in units}
    raw_features = pd.read_csv(DATA / "features.csv", dtype={"GEOID": str}).set_index("GEOID")
    attrs = raw_features[[str(i) for i in range(18)]]
    differences = np.abs(attrs.to_numpy() - np.asarray([features[u] for u in attrs.index]))
    reference = flows.groupby(["residence", "workplace"]).commuters.sum()
    assert len(reference) == len(od)
    assert all(float(od[pair]) == float(v) for pair, v in reference.items())
    outside = [(o, d, v) for (o, d), v in od.items() if o not in features or d not in features]
    import geopandas as gpd
    shape = gpd.read_file(DATA / "output_areas.shp").set_index("GEOID")
    areas = pd.read_csv(DATA / "processed/oa_gdf.csv.gz", dtype={"geo_code": str}).set_index("geo_code")
    metric = shape.to_crs(5070).area / 1e6
    area_check = pd.DataFrame({"cached_area_km2": areas.area_km2, "area_epsg5070_km2": metric})
    area_check["cached_over_projected"] = area_check.cached_area_km2 / area_check.area_epsg5070_km2
    area_check.to_csv(OUT / "area_audit.csv", index_label="origin")
    old = pd.read_csv(old_csv, dtype={"tile": str})
    result = dict(git_commit=tracked, python=platform.python_version(), platform=platform.platform(),
                  versions={n: metadata.version(n) for n in ("torch", "numpy", "pandas", "geopandas", "shapely", "pyproj")},
                  input_sha256=inputs, cache_provenance="legacy_unversioned", raw_flows_present=(DATA / "flows.csv").exists(),
                  feature_units=len(features), assigned_units=len(assignment), unassigned_feature_units=sorted(set(features) - set(assignment)),
                  raw_feature_rows=len(attrs), raw_feature_columns=list(attrs.columns), raw_cached_max_abs_difference=float(differences.max()),
                  tile_count=len(tiles), nonempty_tile_count=sum(bool(v) for v in tiles.values()),
                  splits={name: dict(assigned_tiles=len(ids), nonempty_tiles=sum(bool(tiles[t]) for t in ids),
                                     origins=sum(len(tiles[t]) for t in ids), empty_tiles=[t for t in ids if not tiles[t]]) for name, ids in splits.items()},
                  tiles_not_in_splits=sorted(set(tiles) - set(splits["train"]) - set(splits["test"])),
                  validation_present=(DATA / "processed/validation_tiles.csv").exists(),
                  flow_rows=len(flows), od_pairs=len(od), od_mass=float(flows.commuters.sum()),
                  outside_feature_pairs=len(outside), outside_feature_mass=float(sum(v for _, _, v in outside)),
                  raw_cached_od_exact_match=True, shape_crs=str(shape.crs), shape_units=len(shape),
                  cached_over_projected_area_median=float(area_check.cached_over_projected.median()),
                  historical_checkpoint_keys=list(checkpoint), historical_optimizer_steps=steps,
                  historical_epoch_inference="50620 steps / 2531 origins = 20, conditional on batch size 1; seed/configuration not stored",
                  historical_csv=dict(tiles=len(old), zero_cpc_tiles=int((old.cpc == 0).sum()),
                                      mean_all=float(old.cpc.mean()), mean_positive=float(old.loc[old.cpc > 0, "cpc"].mean())))
    write_json(OUT / "inventory.json", result)
    for legacy, label in ((True, "historical_legacy_axes"), (False, "historical_corrected_axes")):
        print("Replaying", label, flush=True)
        summary, tile_frame = summarize(independent_replay(old_checkpoint, legacy), label)
        if legacy:
            match = old.merge(tile_frame[["tile", "legacy_mixed_support_ratio"]], on="tile", validate="one_to_one")
            assert len(match) == len(old)
            delta = float((match.cpc - match.legacy_mixed_support_ratio).abs().max())
            result["historical_csv_replay_max_abs_difference"] = delta
            assert delta < 1e-5, ("Historical CSV cannot be reproduced", delta)
            write_json(OUT / "inventory.json", result)
        print(label, json.dumps(summary), flush=True)


def finalize():
    inventory_data = json.loads((OUT / "inventory.json").read_text())
    for relative, expected in inventory_data["input_sha256"].items():
        assert sha(ROOT / relative) == expected, ("Input changed", relative)
    manifest = json.loads((TRAIN / "manifest.json").read_text())
    assert manifest["status"] == "completed" and not manifest["test_evaluated"]
    checkpoint = torch.load(TRAIN / "checkpoint.pt", map_location="cpu")
    history = [json.loads(line) for line in (TRAIN / "metrics.jsonl").read_text().splitlines()]
    assert checkpoint["epoch"] == 20 and [r["epoch"] for r in history] == list(range(1, 21))
    assert all(r["train"]["origins"] == 2531 and set(r) == {"epoch", "train"} for r in history)
    assert all(np.isfinite(r["train"]["loss_per_origin"]) for r in history)
    assert checkpoint["config"] == json.loads((TRAIN / "config.json").read_text())
    for name, expected in manifest["outputs"].items():
        assert sha(TRAIN / name) == expected, ("Training artifact changed", name)
    assert {int(v["step"]) for v in checkpoint["optimizer_state_dict"]["state"].values()} == {50620}
    for relative, expected in manifest["source_sha256"].items():
        assert sha(ROOT / "deepgravity" / relative) == expected, ("Code changed during training", relative)
    config = copy.deepcopy(checkpoint["config"])
    config.update(mode="evaluate", evaluation_split="test", run_id="f2h_test_20ep_20260912",
                  checkpoint="../runs/f2h_new_york/f2h_train_20ep_20260912/checkpoint.pt")
    config_path = ROOT / "config/f2h_new_york_evaluate.example.json"
    write_json(config_path, config)
    evaluation, runner_metrics = run(config, ROOT / "config")
    replay = independent_replay(TRAIN / "checkpoint.pt")
    summary, _ = summarize(replay, "fresh_20ep")
    observed = pd.read_csv(evaluation / "origin_metrics.csv", dtype={"origin": str, "tile": str})
    merged = replay.merge(observed, on="origin", suffixes=("_audit", "_runner"), validate="one_to_one")
    assert len(merged) == 2836 and set(replay.origin) == set(observed.origin)
    assert (merged.tile_audit == merged.tile_runner).all()
    assert (merged.destination_count_audit == merged.destination_count_runner).all()
    error = float((merged.cpc_audit - merged.cpc_runner).abs().max())
    assert error < 1e-6, error
    assert np.isclose(summary["cpc_global"], runner_metrics["cpc_global"], atol=1e-7, rtol=0)
    for directory, prefix in ((TRAIN, "training"), (evaluation, "evaluation")):
        for name in ("manifest.json", "config.json", "metrics.jsonl", "metrics.json", "partitions.csv"):
            if (directory / name).exists():
                shutil.copyfile(directory / name, OUT / (prefix + "_" + name))
    result = dict(status="completed", scope="F2-H technical legacy audit; scientific equivalence to paper not established",
                  epochs=20, optimizer_steps=50620, test_evaluations_for_fresh_checkpoint=1,
                  independent_replay_max_origin_cpc_error=error, inputs_unchanged=True,
                  core_source_unchanged=True, training_run=TRAIN.relative_to(ROOT).as_posix(),
                  evaluation_run=evaluation.relative_to(ROOT).as_posix(), checkpoint_sha256=sha(TRAIN / "checkpoint.pt"),
                  metrics=summary, audit_script_sha256=sha(__file__))
    result["evidence_sha256"] = {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "verification.json"}
    write_json(OUT / "verification.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("inventory", "finalize"))
    args = parser.parse_args()
    torch.set_num_threads(2)
    {"inventory": inventory, "finalize": finalize}[args.stage]()
