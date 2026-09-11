from __future__ import annotations

import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

from deepgravity.adapters import FlowBundle, load_legacy, load_partitions, load_santiago
from deepgravity.data_loader import FlowDataset, my_collate
from deepgravity.geometry import earth_distance
from deepgravity.metrics import common_part_of_commuters, cpc_components
from deepgravity.models.deepgravity import NN_MultinomialRegression
from deepgravity.models.od_models import GLM_MultinomialRegression
from deepgravity.preprocessing import compute_support_files, is_cache_complete
from deepgravity.runner import create_run, evaluate, make_dataset, make_loader, run
from deepgravity.sampling import sample_destinations
from deepgravity.spatial import EndpointMapper, write_parquet
from deepgravity.utils import load_data


def fixture_bundle():
    ids = list("abcdef")
    tiles = {"tile0": {"a": {}, "b": {}}, "tile1": {"c": {}, "d": {}}, "tile2": {"e": {}, "f": {}}}
    flows = {"a": {"d": 3.5, "a": 0.5}, "b": {"e": 2.0}, "c": {"a": 6.0},
             "d": {"b": 0.0}, "e": {"f": 4.0}, "f": {"a": 2.0, "c": 2.0}}
    features = {unit: [float(i) / 10] for i, unit in enumerate(ids)}
    coords = {unit: [-33.4 + i / 1000, -70.6] for i, unit in enumerate(ids)}
    return FlowBundle(tiles, flows, features, coords,
                      {"train": ["a", "b"], "validation": ["c", "d"], "test": ["e", "f"]},
                      {"destination_scope": "global"}).validate()


def write_raw(root):
    root = Path(root)
    def polygon(x1, x2):
        return {"type": "Polygon", "coordinates": [[[x1, 6300000], [x2, 6300000],
                    [x2, 6301000], [x1, 6301000], [x1, 6300000]]]}
    def geojson(name, key, values):
        data = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32719"}},
                "features": [{"type": "Feature", "properties": {key: unit}, "geometry": geometry}
                             for unit, geometry in values]}
        (root / name).write_text(json.dumps(data), encoding="utf-8")
    geojson("tessellation.geojson", "tile_ID", [("01", polygon(330000, 332000)), ("02", polygon(332000, 334000))])
    geojson("output_areas.geojson", "oa_ID", [("001", polygon(330000, 331000)), ("002", polygon(333000, 334000))])
    pd.DataFrame({"origin": ["001", "001", "002"], "destination": ["002", "002", "001"],
                  "flow": [1.25, 2.5, 0.0]}).to_csv(root / "flows.csv", index=False)
    pd.DataFrame({"oa_ID": ["001", "002"], "feature": [3.0, 5.0]}).to_csv(root / "features.csv", index=False)
    return root


class MetricsTests(unittest.TestCase):
    def test_known_cpc_cases(self):
        for observed, predicted, expected in [
            ([2, 4], [2, 4], 1.0), ([2, 0], [0, 3], 0.0),
            ([0, 0], [0, 0], 0.0), ([4, 2], [1, 5], 0.5),
            ([8, 0], [2, 0], 0.4), ([0, 0], [4, 0], 0.0)]:
            with self.subTest(observed=observed, predicted=predicted):
                self.assertAlmostEqual(common_part_of_commuters(observed, predicted), expected)
                self.assertAlmostEqual(common_part_of_commuters(predicted, observed), expected)

    def test_numerator_is_twice_overlap(self):
        self.assertEqual(common_part_of_commuters([8, 0], [2, 0], True), 4.0)

    def test_invalid_support_and_weights(self):
        for observed, predicted in [([1], [1, 2]), ([-1], [2]), ([float("nan")], [1]), ([1], [float("inf")])]:
            with self.subTest(observed=observed):
                with self.assertRaises(ValueError):
                    cpc_components(observed, predicted)

    def test_geodesic_distance_and_coordinate_contract(self):
        self.assertAlmostEqual(earth_distance([0, 0], [0, 1]), 111.1951, places=3)
        self.assertEqual(earth_distance([-33.4, -70.6], [-33.4, -70.6]), 0.0)
        self.assertAlmostEqual(earth_distance([12, 42], [-12, -138]), np.pi * 6371.01, places=3)
        with self.assertRaises(ValueError):
            earth_distance([6300000, 330000], [0, 0])


class SamplingTests(unittest.TestCase):
    def test_cross_tile_destinations_are_retained(self):
        bundle = fixture_bundle()
        dataset = make_dataset(bundle, ["a"], {}, False)
        self.assertEqual(dataset.destinations_for(0), list("abcdef"))
        self.assertEqual(dataset.get_flow("a", "d"), 3.5)
        self.assertEqual(dataset[0][1].sum().item(), 4.0)

    def test_legacy_scope_is_explicit(self):
        bundle = fixture_bundle()
        bundle.metadata["destination_scope"] = "origin_tile"
        dataset = make_dataset(bundle, ["a"], {}, False)
        self.assertEqual(dataset.destinations_for(0), ["a", "b"])
        self.assertEqual(dataset[0][1].sum().item(), 0.5)

    def test_positive_quota_is_in_scope_and_without_replacement(self):
        values = sample_destinations("a", 10, ["a", "b", "c"], {"a": {"outside": 20, "b": 1}}, 1.0)
        self.assertEqual(values, ["a", "b", "c"])
        values = sample_destinations("a", 2, ["a", "b", "c"], {"a": {"outside": 20, "b": 1}}, 0.5, np.random.default_rng(5))
        self.assertIn("b", values)
        self.assertEqual(len(set(values)), 2)
        self.assertNotIn("outside", values)

    def test_all_positive_or_all_zero_candidates(self):
        for flows in ({}, {"a": {"a": 2, "b": 2, "c": 1}}):
            result = sample_destinations("a", 2, ["a", "b", "c"], flows, 0.5, np.random.default_rng(1))
            self.assertEqual(len(set(result)), 2)

    def test_seed_epoch_and_hash_order(self):
        bundle = fixture_bundle()
        first = make_dataset(bundle, ["a", "b"], {"seed": 9, "destinations_per_origin": 3}, True)
        second = make_dataset(bundle, ["a", "b"], {"seed": 9, "destinations_per_origin": 3}, True)
        for epoch in range(4):
            first.set_epoch(epoch)
            second.set_epoch(epoch)
            self.assertEqual(first.destinations_for(0), second.destinations_for(0))
            self.assertEqual(first.destinations_for(1), second.destinations_for(1))
        code = ("from deepgravity.sampling import sample_destinations; import numpy as np; "
                "print(sample_destinations('a', 3, set('abcdef'), {}, rng=np.random.default_rng(4)))")
        results = []
        for value in ("1", "987"):
            env = dict(os.environ, PYTHONHASHSEED=value)
            results.append(subprocess.check_output([sys.executable, "-c", code], env=env, text=True))
        self.assertEqual(*results)

    def test_collate_handles_variable_candidate_counts(self):
        bundle = fixture_bundle()
        bundle.tiles = {"tile0": {"a": {}, "b": {}, "c": {}}, "tile1": {"d": {}}, "tile2": {"e": {}, "f": {}}}
        bundle.metadata["destination_scope"] = "origin_tile"
        data = make_dataset(bundle, ["a", "d", "e"], {}, False)
        batches = list(make_loader(data, 2))
        self.assertEqual([x.shape[1] for x in batches[0][0]], [3, 1])
        self.assertEqual(len(batches), 2)

    def test_numpy_features_are_concatenated(self):
        bundle = fixture_bundle()
        bundle.features = {k: np.asarray(v) for k, v in bundle.features.items()}
        data = make_dataset(bundle, ["a"], {}, False)
        self.assertEqual(len(data.get_features("a", "b")), 3)


class CacheTests(unittest.TestCase):
    def test_raw_negative_and_missing_flows_are_not_hidden_by_grouping(self):
        for values in ([-1.0, 2.0, 0.0], [float("nan"), 2.0, 0.0]):
            with tempfile.TemporaryDirectory() as folder:
                root = write_raw(folder)
                frame = pd.read_csv(root / "flows.csv", dtype={"origin": str, "destination": str})
                frame["flow"] = values
                frame.to_csv(root / "flows.csv", index=False)
                with self.assertRaises(ValueError):
                    load_data(root)

    def test_parser_options_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = write_raw(folder)
            frame = pd.read_csv(root / "flows.csv", dtype={"origin": str, "destination": str})
            frame["other_weight"] = [5.0, 6.0, 0.0]
            frame.to_csv(root / "flows.csv", index=False)
            self.assertEqual(load_data(root)[5][("001", "002")], 3.75)
            self.assertEqual(load_data(root, flow_flows_column="other_weight")[5][("001", "002")], 11.0)

    def test_regeneration_serialization_and_fractional_flow(self):
        with tempfile.TemporaryDirectory() as folder:
            root = write_raw(folder)
            self.assertFalse(is_cache_complete(root))
            values = load_data(root)
            self.assertEqual(values[5], {("001", "002"): 3.75, ("002", "001"): 0.0})
            self.assertEqual(values[3]["002"], 0.0)
            self.assertEqual(set(values[4]), {"001", "002"})
            self.assertTrue(is_cache_complete(root))
            with patch("deepgravity.utils.compute_support_files", side_effect=AssertionError("Unexpected regeneration")):
                load_data(root)
            (root / "processed" / "od2flow.pkl").unlink()
            self.assertFalse(is_cache_complete(root))
            self.assertEqual(load_data(root)[5][("001", "002")], 3.75)

    def test_cache_detects_corruption_and_changed_raw_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = write_raw(folder)
            load_data(root)
            with (root / "processed" / "od2flow.pkl").open("wb") as handle:
                pickle.dump({"wrong": [1, 2]}, handle)
            self.assertFalse(is_cache_complete(root))
            load_data(root)
            frame = pd.read_csv(root / "flows.csv", dtype=str)
            frame.loc[0, "flow"] = "4"
            frame.to_csv(root / "flows.csv", index=False)
            self.assertFalse(is_cache_complete(root))
            self.assertEqual(load_data(root)[5][("001", "002")], 6.5)

    def test_missing_features_are_optional_but_malformed_features_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = write_raw(folder)
            (root / "features.csv").unlink()
            self.assertEqual(load_data(root)[4], {"001": [], "002": []})
        with tempfile.TemporaryDirectory() as folder:
            root = write_raw(folder)
            (root / "features.csv").write_text("bad,value\n001,nope\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_data(root)

    def test_projected_centroid_order_and_area(self):
        with tempfile.TemporaryDirectory() as folder:
            root = write_raw(folder)
            values = load_data(root)
            coords = values[-1]["001"]
            self.assertTrue(-34 < coords[0] < -33)
            self.assertTrue(-71 < coords[1] < -70)
            self.assertAlmostEqual(values[1].area_km2.iloc[0], 1.0, places=5)

    def test_legacy_mass_predictor_requires_audit_purpose(self):
        with tempfile.TemporaryDirectory() as folder:
            root = write_raw(folder)
            load_data(root)
            config = {"data_dir": str(root), "centroid_order": "lat_lon", "mass_feature": "legacy_observed_outflow"}
            with self.assertRaisesRegex(ValueError, "legacy auditing"):
                load_legacy(config, root, "scientific")


class PartitionTests(unittest.TestCase):
    def test_overlap_rejected(self):
        bundle = fixture_bundle()
        bundle.partitions["test"].append("a")
        with self.assertRaises(ValueError):
            bundle.validate()

    def test_tile_split_rejected(self):
        bundle = fixture_bundle()
        bundle.partitions = {"train": ["a"], "validation": ["b"], "test": ["e", "f"]}
        with self.assertRaisesRegex(ValueError, "tile crosses"):
            bundle.validate()

    def test_partition_ids_keep_leading_zeroes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parts.csv"
            path.write_text("unit_id,tile_id,partition\n001,01,train\n002,02,test\n", encoding="utf-8")
            tiles, partitions = load_partitions(path, "test", ["001", "002"])
            self.assertEqual(partitions["train"], ["001"])
            self.assertIn("01", tiles)

    def test_duplicate_or_missing_partition_unit_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parts.csv"
            path.write_text("unit_id,tile_id,partition\na,0,train\na,0,train\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_partitions(path, "test", ["a", "b"])


class ModelAndEvaluationTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)

    def test_architecture_and_dropout_modes(self):
        torch.manual_seed(1)
        model = NN_MultinomialRegression(3, 256, "deepgravity")
        widths = [layer.out_features for layer in model.modules() if isinstance(layer, torch.nn.Linear)]
        self.assertEqual(widths, [256] * 5 + [128] * 10 + [1])
        self.assertFalse(any(isinstance(layer, torch.nn.modules.batchnorm._BatchNorm) for layer in model.modules()))
        self.assertTrue(all(layer.p == 0 for layer in model.modules() if isinstance(layer, torch.nn.Dropout)))
        model = NN_MultinomialRegression(3, 8, "deepgravity", dropout_p=0.5)
        sample = torch.randn(1, 6, 3)
        model.eval()
        self.assertTrue(torch.equal(model(sample), model(sample)))
        model.train()
        self.assertFalse(torch.equal(model.dropout1(torch.ones(100)), model.dropout1(torch.ones(100))))

    def test_full_evaluation_batch_invariance_and_mass(self):
        bundle = fixture_bundle()
        dataset = make_dataset(bundle, list("abcdef"), {}, False)
        model = GLM_MultinomialRegression(3)
        with torch.no_grad():
            model.linear1.weight.zero_()
            model.linear1.bias.zero_()
        model.train()
        first, origins, tiles = evaluate(model, make_loader(dataset, 2), torch.device("cpu"))
        second = evaluate(model, make_loader(dataset, 4), torch.device("cpu"))[0]
        self.assertEqual(first, second)
        self.assertEqual(first["origins"], 6)
        self.assertEqual(first["tiles"], 3)
        self.assertAlmostEqual(first["observed_mass"], 20.0)
        self.assertAlmostEqual(first["predicted_mass"], 20.0)
        self.assertTrue(model.training)
        self.assertEqual(origins.loc[origins.origin == "d", "cpc"].iloc[0], 0)
        expected_num = sum(2 * sum(min(bundle.flows.get(o, {}).get(d, 0), sum(bundle.flows.get(o, {}).values()) / 6)
                                  for d in "abcdef") for o in "abcdef")
        self.assertAlmostEqual(first["cpc_global"], expected_num / 40)
        self.assertAlmostEqual(tiles.cpc_numerator.sum(), expected_num)

    def test_evaluation_rejects_sampling(self):
        dataset = make_dataset(fixture_bundle(), ["a"], {}, True)
        with self.assertRaisesRegex(ValueError, "unsampled"):
            evaluate(GLM_MultinomialRegression(3), make_loader(dataset, 1), torch.device("cpu"))

    def test_probability_normalization_conserves_each_origin(self):
        model = GLM_MultinomialRegression(3)
        x = torch.randn(2, 4, 3)
        targets = torch.tensor([[1.0, 2, 4, 8], [0.0, 0, 0, 0]])
        prediction = model.average_OD_model(x, targets)
        np.testing.assert_allclose(prediction.sum(axis=1), [15, 0], rtol=1e-6)

    def test_empty_target_loss_has_finite_gradients(self):
        model = GLM_MultinomialRegression(3)
        loss = model.loss(model(torch.zeros(1, 2, 3)), torch.zeros(1, 2))
        loss.backward()
        self.assertEqual(loss.item(), 0)
        self.assertTrue(torch.isfinite(model.linear1.weight.grad).all())


class RunTests(unittest.TestCase):
    def config(self, folder):
        return {"purpose": "technical_smoke", "mode": "train", "output_root": str(Path(folder) / "runs"),
                "evaluation_split": "validation", "device": "cpu", "model": {"dim_hidden": 8, "dropout_p": 0.0},
                "training": {"epochs": 2, "batch_size": 2, "evaluation_batch_size": 2,
                             "seed": 123, "destinations_per_origin": 4}}

    def test_complete_repeatable_run_checkpoint_and_test_separation(self):
        with tempfile.TemporaryDirectory() as folder:
            config = self.config(folder)
            first, metrics1 = run(config, folder, fixture_bundle())
            second, metrics2 = run(config, folder, fixture_bundle())
            self.assertNotEqual(first, second)
            self.assertEqual(metrics1, metrics2)
            first_state = torch.load(first / "checkpoint.pt")["model_state_dict"]
            second_state = torch.load(second / "checkpoint.pt")["model_state_dict"]
            self.assertTrue(all(torch.equal(first_state[k], second_state[k]) for k in first_state))
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "completed")
            self.assertFalse(manifest["test_evaluated"])
            self.assertEqual(set(pd.read_csv(first / "origin_metrics.csv").origin), {"c", "d"})
            self.assertTrue((first / "source" / "runner.py").exists())
            config.update(mode="evaluate", checkpoint=str(first / "checkpoint.pt"), evaluation_split="test")
            evaluated, _ = run(config, folder, fixture_bundle())
            self.assertEqual(set(pd.read_csv(evaluated / "origin_metrics.csv").origin), {"e", "f"})

    def test_test_is_reserved_during_training(self):
        with tempfile.TemporaryDirectory() as folder:
            config = self.config(folder)
            config["evaluation_split"] = "test"
            with self.assertRaisesRegex(ValueError, "never evaluates test"):
                run(config, folder, fixture_bundle())

    def test_no_run_overwrite_or_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            create_run(folder, "fixed")
            with self.assertRaises(FileExistsError):
                create_run(folder, "fixed")
            with self.assertRaises(ValueError):
                create_run(folder, "../escape")

    def test_import_from_other_working_directory_has_no_training_side_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            result = subprocess.run([sys.executable, "-c", "import deepgravity.main; import deepgravity.models.deepgravity"],
                                    cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(folder).iterdir()), [])


class SpatialTests(unittest.TestCase):
    def test_prepared_membership_keeps_strict_municipal_boundaries(self):
        import h3
        from pyproj import Transformer
        from deepgravity.preprocessing import digest
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            geometry = {"type": "Polygon", "coordinates": [[[-70.61, -33.41], [-70.59, -33.41],
                        [-70.59, -33.39], [-70.61, -33.39], [-70.61, -33.41]]]}
            area = root / "area.geojson"
            area.write_text(json.dumps({"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": geometry, "properties": {}}]}))
            approval = root / "approval.json"
            approval.write_text(json.dumps({"geometry_sha256": digest(area)}))
            mapper = EndpointMapper(area, approval)
            trans = Transformer.from_crs(4326, 32719, always_xy=True)
            x, y = trans.transform(-70.6, -33.4)
            boundary_x, boundary_y = mapper.geometries[0].exterior.coords[0]
            actual = mapper.map(np.asarray([x, boundary_x, x + 100000]),
                                np.asarray([y, boundary_y, y]))
            self.assertEqual(actual[0].tolist(), [True, False, False])
            self.assertEqual(actual[1][0], h3.latlng_to_cell(-33.4, -70.6, 7))
            again = mapper.map(np.asarray([x]), np.asarray([y]))
            self.assertEqual(again[1][0], actual[1][0])

    def test_direct_r7_is_not_replaced_with_r8_parent(self):
        import h3
        from deepgravity.spatial import aggregate_batch
        cell = "87b2c551bffffff"
        class Mapper:
            def map(self, xs, ys):
                return [np.ones(len(xs), dtype=bool), np.asarray([cell] * len(xs)),
                        np.asarray(["88b2c551b1fffff"] * len(xs))]
        frame = pd.DataFrame({"origin_x": [1, 2], "origin_y": [1, 2],
                              "destination_x": [1, 2], "destination_y": [1, 2],
                              "origin_zone": ["1", "1"], "destination_zone": ["1", "1"],
                              "trip_weight": [1.25, 0.0]})
        lookups = {"zona777": {"1": 0}, "h3_r7": {"old_cell": 0},
                   "h3_r8": {"88b2c551b1fffff": 0}}
        arrays = {r: (np.zeros((1, 1), dtype=np.int64), np.zeros((1, 1))) for r in lookups}
        count, mass = aggregate_batch(frame, Mapper(), arrays, lookups)
        self.assertEqual(count, 2)
        self.assertEqual(mass, 1.25)
        self.assertIn(cell, lookups["h3_r7"])
        self.assertEqual(arrays["h3_r7"][0][1, 1], 2)
        self.assertEqual(arrays["h3_r7"][1][1, 1], 1.25)

    def test_corrected_cells_cannot_change_frozen_tile_agenda(self):
        from deepgravity.spatial import corrected_units
        cell = "87b2c551bffffff"
        od = pd.DataFrame({"origin_unit_id": [cell], "destination_unit_id": [cell],
                           "trip_count": [2], "expanded_mass": [3.5]})
        with self.assertRaisesRegex(ValueError, "outside the approved agenda"):
            corrected_units(od, "h3_r7", pd.DataFrame(), {})
        units = corrected_units(od, "h3_r7", pd.DataFrame(), {"E21_N419": "train"})
        self.assertEqual(units.partition.tolist(), ["train"])
        self.assertEqual(units.origin_trip_count.tolist(), [2])

    def test_parquet_writer_is_reversible_and_refuses_overwrite(self):
        import duckdb
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "flows.parquet"
            frame = pd.DataFrame({"origin_unit_id": ["001"], "destination_unit_id": ["002"],
                                  "trip_count": [3], "expanded_mass": [1.25]})
            connection = duckdb.connect()
            write_parquet(connection, frame, path)
            result = connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
            pd.testing.assert_frame_equal(result, frame)
            with self.assertRaises(FileExistsError):
                write_parquet(connection, frame, path)
            connection.close()





class AdapterIntegrationTests(unittest.TestCase):
    def test_zona_and_h3_share_contract_and_keep_cross_partition_flows(self):
        import duckdb
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            units = pd.DataFrame({"unit_id": ["a", "b", "c"], "unit_x_32719": [330000, 340000, 350000],
                                  "unit_y_32719": [6300000] * 3,
                                  "geometry_source": ["official_shapezona777"] * 3})
            units.to_csv(root / "units.csv", index=False)
            pd.DataFrame({"unit_id": ["a", "b", "c"], "tile_id": ["t0", "t1", "t2"],
                          "partition": ["train", "validation", "test"], "origin_trip_count": [2, 1, 1]}
                         ).to_csv(root / "parts.csv", index=False)
            pd.DataFrame({"unit_id": ["a", "b", "c"], "land_use": [1, 2, 3]}).to_csv(root / "features.csv", index=False)
            od = pd.DataFrame({"origin_unit_id": ["a", "b", "c"], "destination_unit_id": ["c", "a", "b"],
                               "trip_count": [2, 1, 1], "expanded_mass": [1.25, 2.0, 0.0]})
            connection = duckdb.connect()
            write_parquet(connection, od, root / "od.parquet")
            connection.close()
            config = {"units_path": "units.csv", "partitions_path": "parts.csv", "od_path": "od.parquet",
                      "features_path": "features.csv", "feature_columns": ["land_use"], "weight": "expanded_mass"}
            for representation in ("zona777", "h3_r7", "h3_r8"):
                with self.subTest(representation=representation):
                    config["representation"] = representation
                    bundle = load_santiago(config, root, "scientific")
                    self.assertEqual(bundle.flows["a"]["c"], 1.25)
                    dataset = make_dataset(bundle, ["a"], {}, False)
                    self.assertEqual(dataset.destinations_for(0), ["a", "b", "c"])
                    self.assertEqual(dataset[0][1].sum().item(), 1.25)
            config["destination_scope"] = "origin_tile"
            with self.assertRaisesRegex(ValueError, "metropolitan"):
                load_santiago(config, root, "scientific")

    def test_absolute_launcher_and_relative_config_paths_from_other_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root / "raw"
            raw.mkdir()
            write_raw(raw)
            load_data(raw)
            (raw / "processed" / "train_tiles.csv").write_text("01\n")
            (raw / "processed" / "validation_tiles.csv").write_text("02\n")
            config = {"purpose": "technical_smoke", "mode": "train", "output_root": "runs",
                      "data": {"adapter": "legacy", "data_dir": "raw", "centroid_order": "lat_lon",
                               "destination_scope": "global", "mass_feature": "none"},
                      "model": {"dim_hidden": 8}, "training": {"epochs": 1, "seed": 1}}
            path = root / "config.json"
            path.write_text(json.dumps(config))
            launcher = Path(__file__).resolve().parents[1] / "run_deepgravity.py"
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            result = subprocess.run([sys.executable, str(launcher), "--config", str(path)],
                                    cwd=elsewhere, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = next((root / "runs").iterdir())
            self.assertEqual(json.loads((output / "manifest.json").read_text())["status"], "completed")
            self.assertEqual(list(elsewhere.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
