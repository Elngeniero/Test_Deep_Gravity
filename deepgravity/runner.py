"""Reproducible training/evaluation, with no test access during training."""
from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path
import platform
import random
import shutil
import time
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd
import torch

from .adapters import load_bundle, resolve_path
from .data_loader import FlowDataset, my_collate
from .metrics import cpc_components
from .models.deepgravity import NN_MultinomialRegression
from .preprocessing import digest


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def make_dataset(bundle, origins, config, training):
    dataset = FlowDataset(origins, bundle.tiles, bundle.flows, bundle.features, {},
                       bundle.centroids, dim_dests=config.get("destinations_per_origin", 512),
                       frac_true_dest=config.get("positive_destination_fraction", 0.0),
                       destination_scope=bundle.metadata.get("destination_scope", "global"),
                       training=training, seed=config.get("seed", 1234))
    dataset.source_outflow = bundle.source_outflow
    return dataset


def make_loader(dataset, batch_size):
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False,
                                      num_workers=0, collate_fn=my_collate)


def train_epoch(model, loader, optimizer, device):
    model.train()
    total_loss, origins = 0.0, 0
    for features, targets, ids in loader:
        optimizer.zero_grad()
        losses = [model.loss(model(x.to(device)), y.to(device)) for x, y in zip(features, targets)]
        loss = torch.stack(losses).sum()
        if not torch.isfinite(loss):
            raise FloatingPointError("Nonfinite training loss")
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu())
        origins += len(ids)
    if not origins:
        raise ValueError("Empty training split")
    return {"loss_per_origin": total_loss / origins, "origins": origins}


def evaluate(model, loader, device):
    dataset = loader.dataset
    if dataset.training:
        raise ValueError("Evaluation requires complete, unsampled destination support")
    was_training = model.training
    model.eval()
    rows = []
    try:
        with torch.no_grad():
            for features, targets, ids in loader:
                for x, _, origin_ids in zip(features, targets, ids):
                    origin = origin_ids[0]
                    candidates = dataset.candidates(origin)
                    # Float64 mass totals come from canonical OD, not float32 training targets.
                    observed = np.asarray([dataset.get_flow(origin, d) for d in candidates], dtype=np.float64)
                    scores = model(x.to(device)).squeeze(-1).double()
                    probabilities = torch.softmax(scores, dim=-1).cpu().numpy()[0]
                    predicted = probabilities * observed.sum()
                    numerator, observed_mass, predicted_mass = cpc_components(observed, predicted)
                    if not np.isclose(observed_mass, predicted_mass, rtol=1e-12, atol=1e-8):
                        raise AssertionError("Predicted outflow is not conserved")
                    denominator = observed_mass + predicted_mass
                    log_probs = torch.log_softmax(scores, dim=-1).cpu().numpy()[0]
                    rows.append({"origin": origin, "tile": dataset.oa2tile[origin],
                                 "cpc_numerator": numerator, "observed_mass": observed_mass,
                                 "predicted_mass": predicted_mass,
                                 "full_domain_observed_mass": dataset.source_outflow.get(
                                     origin, sum(dataset.o2d2flow.get(origin, {}).values())),
                                 "cpc": numerator / denominator if denominator else 0.0,
                                 "loss": float(-(observed * log_probs).sum()),
                                 "destination_count": len(candidates)})
    finally:
        model.train(was_training)
    if len(rows) != len(dataset) or len({row["origin"] for row in rows}) != len(rows):
        raise AssertionError("Evaluation failed to visit each origin exactly once")
    if not rows:
        raise ValueError("Empty evaluation split")
    origins = pd.DataFrame(rows)
    tiles = origins.groupby("tile", as_index=False).agg(
        cpc_numerator=("cpc_numerator", "sum"), observed_mass=("observed_mass", "sum"),
        predicted_mass=("predicted_mass", "sum"), origins=("origin", "size"))
    denominator = tiles.observed_mass + tiles.predicted_mass
    tiles["cpc"] = np.divide(tiles.cpc_numerator, denominator,
                             out=np.zeros(len(tiles)), where=denominator != 0)
    total_denominator = origins.observed_mass.sum() + origins.predicted_mass.sum()
    summary = {"cpc_global": float(origins.cpc_numerator.sum() / total_denominator) if total_denominator else 0.0,
               "cpc_mean_origin": float(origins.cpc.mean()),
               "cpc_mean_all_tiles": float(tiles.cpc.mean()),
               "cpc_mean_nonzero_tiles": float(tiles.loc[tiles.cpc > 0, "cpc"].mean()) if (tiles.cpc > 0).any() else None,
               "zero_cpc_tiles": int((tiles.cpc == 0).sum()), "tiles": len(tiles), "origins": len(origins),
               "observed_mass": float(origins.observed_mass.sum()),
               "predicted_mass": float(origins.predicted_mass.sum()),
               "full_domain_observed_mass": float(origins.full_domain_observed_mass.sum()),
               "loss_per_origin": float(origins.loss.mean()), "empty_cpc_convention": 0.0,
               "destination_scope": dataset.destination_scope, "sampled_evaluation": False}
    return summary, origins, tiles


def create_run(output_root, run_id=None):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex[:10]
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("run_id must be a single directory name")
    folder = output_root / run_id
    folder.mkdir(exist_ok=False)
    return folder


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def run(config, config_dir, bundle=None):
    config = json.loads(json.dumps(config))
    mode = config.get("mode", "train")
    if mode not in {"train", "evaluate"}:
        raise ValueError("mode must be train or evaluate")
    purpose = config.get("purpose", "scientific")
    if purpose not in {"scientific", "technical_smoke", "legacy_audit"}:
        raise ValueError("Unknown run purpose")
    training = config.setdefault("training", {})
    for key, value in {"seed": 1234, "epochs": 15, "batch_size": 1,
                       "evaluation_batch_size": 1, "lr": 5e-6, "momentum": 0.9,
                       "cpu_threads": 2, "destinations_per_origin": 512,
                       "positive_destination_fraction": 0.0}.items():
        training.setdefault(key, value)
    config.setdefault("model", {}).setdefault("dim_hidden", 256)
    config["model"].setdefault("dropout_p", 0.0)
    seed = training.get("seed", 1234)
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    epochs = training.get("epochs", 15)
    batch_size = training.get("batch_size", 1)
    test_batch_size = training.get("evaluation_batch_size", 1)
    if epochs < 1 or batch_size < 1 or test_batch_size < 1:
        raise ValueError("Epochs and batch sizes must be positive")
    evaluation_split = config.get("evaluation_split", "validation")
    if evaluation_split not in {"validation", "test"}:
        raise ValueError("Evaluation split must be validation or test")
    if mode == "train" and evaluation_split == "test":
        raise ValueError("Training never evaluates test; use a separate checkpoint evaluation")
    device = torch.device(config.get("device", "cpu"))
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested CUDA is unavailable")
    torch.set_num_threads(training.get("cpu_threads", 2))
    seed_everything(seed)
    bundle = bundle or load_bundle(config["data"], config_dir, purpose)
    bundle.validate()
    if mode == "train" and not bundle.partitions.get("train"):
        raise ValueError("No training origins")
    if mode == "evaluate" and not bundle.partitions.get(evaluation_split):
        raise ValueError("Requested evaluation partition is empty")
    output = create_run(resolve_path(config["output_root"], config_dir), config.get("run_id"))
    write_json(output / "config.json", config)
    manifest = {"status": "running", "purpose": purpose, "mode": mode,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(), "device": str(device), "seed": seed,
                "data_contract": bundle.metadata, "loss": "sum of count-weighted multinomial negative log-likelihood",
                "versions": {name: metadata.version(name) for name in ("torch", "numpy", "pandas")},
                "inputs": {str(path): digest(path) for path in bundle.input_paths if Path(path).is_file()}}
    source = Path(__file__).parent
    manifest["source_sha256"] = {}
    for path in sorted(source.rglob("*.py")):
        relative = path.relative_to(source)
        destination = output / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        manifest["source_sha256"][relative.as_posix()] = digest(path)
    oa2tile = {unit: tile for tile, units in bundle.tiles.items() for unit in units}
    pd.DataFrame([{"origin": origin, "tile": oa2tile[origin], "partition": partition}
                  for partition, origins in bundle.partitions.items() for origin in origins]).to_csv(
                      output / "partitions.csv", index=False)
    write_json(output / "manifest.json", manifest)
    started = time.perf_counter()
    try:
        width = len(next(iter(bundle.features.values()))) * 2 + 1
        model_config = config.get("model", {})
        hidden = model_config.get("dim_hidden", 256)
        dropout = model_config.get("dropout_p", 0.0)
        if hidden < 2 or not 0 <= dropout < 1:
            raise ValueError("Invalid model dimensions or dropout")
        model = NN_MultinomialRegression(width, hidden, "deepgravity", dropout, device).to(device)
        manifest["architecture"] = {"input_dimension": width, "hidden_widths": [hidden] * 5 + [hidden // 2] * 10,
                                    "batch_norm": False, "dropout_p": dropout, "activation": "LeakyReLU"}
        optimizer = torch.optim.RMSprop(model.parameters(), lr=training.get("lr", 5e-6),
                                         momentum=training.get("momentum", 0.9))
        eval_origins = bundle.partitions.get(evaluation_split, [])
        eval_loader = make_loader(make_dataset(bundle, eval_origins, training, False), test_batch_size) if eval_origins else None
        history = []
        if mode == "train":
            train_dataset = make_dataset(bundle, bundle.partitions["train"], training, True)
            train_loader = make_loader(train_dataset, batch_size)
            for epoch in range(1, epochs + 1):
                seed_everything(seed + epoch)
                train_dataset.set_epoch(epoch)
                metrics = train_epoch(model, train_loader, optimizer, device)
                record = {"epoch": epoch, "train": metrics}
                if eval_loader is not None:
                    record["validation"] = evaluate(model, eval_loader, device)[0]
                history.append(record)
                with (output / "metrics.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, allow_nan=False) + "\n")
                print(json.dumps({"run": output.name, **record}, allow_nan=False), flush=True)
            torch.save({"model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(),
                        "epoch": epochs, "config": config, "architecture": manifest["architecture"]},
                       output / "checkpoint.pt")
        else:
            checkpoint_path = resolve_path(config["checkpoint"], config_dir)
            manifest["checkpoint_input"] = {"path": str(checkpoint_path), "sha256": digest(checkpoint_path)}
            checkpoint = torch.load(checkpoint_path, map_location=device)
            model.load_state_dict(checkpoint["model_state_dict"])
            shutil.copyfile(checkpoint_path, output / "checkpoint.pt")
        summary = {}
        if eval_loader is not None:
            summary, origins, tiles = evaluate(model, eval_loader, device)
            origins.to_csv(output / "origin_metrics.csv", index=False)
            tiles.to_csv(output / "tile_metrics.csv", index=False)
            write_json(output / "metrics.json", summary)
        manifest.update(status="completed", elapsed_seconds=time.perf_counter() - started,
                        evaluation_split=evaluation_split if eval_loader is not None else None,
                        test_evaluated=mode == "evaluate" and evaluation_split == "test",
                        outputs={path.name: digest(path) for path in output.iterdir()
                                 if path.is_file() and path.name != "manifest.json"})
        write_json(output / "manifest.json", manifest)
        return output, summary
    except Exception as error:
        manifest.update(status="failed", error=str(error), elapsed_seconds=time.perf_counter() - started)
        write_json(output / "manifest.json", manifest)
        (output / "error.log").write_text(str(error) + "\n", encoding="utf-8")
        raise
