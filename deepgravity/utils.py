"""Loading helpers. Raw preprocessing is isolated in preprocessing.py."""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .geometry import earth_distance
from .models.deepgravity import NN_MultinomialRegression
from .preprocessing import compute_support_files, is_cache_complete

_is_support_files_computed = is_cache_complete
_compute_support_files = compute_support_files


def load_data(db_dir, tile_id_column="tile_ID", tile_geometry="geometry",
              oa_id_column="oa_ID", oa_geometry="geometry",
              flow_origin_column="origin", flow_destination_column="destination",
              flow_flows_column="flow", *, cache_dir=None, projected_crs=None):
    options = {"tile_id_column": tile_id_column, "tile_geometry": tile_geometry,
               "oa_id_column": oa_id_column, "oa_geometry": oa_geometry,
               "flow_origin_column": flow_origin_column,
               "flow_destination_column": flow_destination_column,
               "flow_flows_column": flow_flows_column, "projected_crs": projected_crs}
    if not is_cache_complete(db_dir, cache_dir, options):
        compute_support_files(db_dir, tile_id_column, tile_geometry, oa_id_column,
                              oa_geometry, flow_origin_column, flow_destination_column,
                              flow_flows_column, cache_dir=cache_dir, projected_crs=projected_crs)
    cache = Path(cache_dir) if cache_dir else Path(db_dir) / "processed"
    tiles = json.loads((cache / "tileid2oa2handmade_features.json").read_text(encoding="utf-8"))
    units = pd.read_csv(cache / "oa_gdf.csv.gz", dtype={"geo_code": str})
    flows = pd.read_csv(cache / "flows_oa.csv.zip", dtype={"residence": str, "workplace": str})
    outflow = {unit: 0.0 for unit in units.geo_code}
    outflow.update(flows.groupby("residence").commuters.sum().to_dict())
    loaded = []
    for name in ("oa2features.pkl", "od2flow.pkl", "oa2centroid.pkl"):
        with (cache / name).open("rb") as handle:
            loaded.append(pickle.load(handle))
    features, od2flow, centroids = loaded
    if not all(isinstance(key, tuple) and len(key) == 2 and np.isscalar(value)
               for key, value in od2flow.items()):
        raise ValueError("Invalid od2flow.pkl: expected (origin, destination) -> numeric flow")
    return tiles, units, flows, outflow, features, od2flow, centroids


def instantiate_model(oa2centroid, oa2features, oa2pop, dim_input,
                      device=torch.device("cpu"), dim_hidden=256, lr=5e-6,
                      momentum=0.9, dropout_p=0.0, verbose=False):
    return NN_MultinomialRegression(dim_input, dim_hidden, "deepgravity",
                                    dropout_p=dropout_p, device=device).to(device)


def load_model(fname, oa2centroid, oa2features, oa2pop, device, dim_s=1,
               distances=None, dim_hidden=256, lr=5e-6, momentum=0.9,
               dropout_p=0.0, verbose=True):
    model = instantiate_model(oa2centroid, oa2features, oa2pop, dim_s,
                              device, dim_hidden, dropout_p=dropout_p)
    checkpoint = torch.load(fname, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model
