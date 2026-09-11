from __future__ import annotations

import numpy as np
import torch

from .geometry import earth_distance
from .sampling import sample_destinations


def my_collate(batch):
    """Keep variable candidate counts; each tensor represents a single origin."""
    return tuple([item[index] for item in batch] for index in range(3))


class FlowDataset(torch.utils.data.Dataset):
    def __init__(self, list_IDs, tileid2oa2features2vals, o2d2flow,
                 oa2features, oa2pop, oa2centroid, dim_dests=512,
                 frac_true_dest=0.0, model="DG", *, destination_scope="global",
                 destination_ids=None, training=True, seed=1234):
        self.list_IDs = list(list_IDs)
        self.tileid2oa2features2vals = tileid2oa2features2vals
        self.o2d2flow = o2d2flow
        self.oa2features = {key: list(value) for key, value in oa2features.items()}
        # Legacy compatibility only: observed generation is not a census feature.
        self.oa2pop = oa2pop
        self.oa2centroid = oa2centroid
        self.source_outflow = {}
        self.dim_dests = dim_dests
        self.frac_true_dest = frac_true_dest
        self.model = model
        self.training = training
        self.seed = seed
        self.epoch = 0
        self.destination_scope = destination_scope
        self.oa2tile = {}
        for tile, units in tileid2oa2features2vals.items():
            for unit in units:
                if unit in self.oa2tile:
                    raise ValueError("Unit assigned to multiple tiles: " + unit)
                self.oa2tile[unit] = tile
        if destination_scope not in {"global", "origin_tile"}:
            raise ValueError("Unknown destination scope")
        self.destination_ids = sorted(oa2features if destination_ids is None else destination_ids)
        if len(set(self.list_IDs)) != len(self.list_IDs) or not self.destination_ids:
            raise ValueError("Duplicate origins or empty destinations")
        required = set(self.list_IDs) | set(self.destination_ids)
        if any(required - set(mapping) for mapping in
               (self.oa2features, self.oa2centroid)) or set(self.list_IDs) - set(self.oa2tile):
            raise ValueError("Units lack features, anchors or tile assignment")
        if dim_dests < 1 or not 0 <= frac_true_dest <= 1:
            raise ValueError("Invalid destination sampling parameters")

    def __len__(self):
        return len(self.list_IDs)

    def set_epoch(self, epoch):
        self.epoch = int(epoch)

    def get_features(self, origin, destination):
        return (self.oa2features[origin] + self.oa2features[destination] +
                [earth_distance(self.oa2centroid[origin], self.oa2centroid[destination])])

    def get_flow(self, origin, destination):
        return self.o2d2flow.get(origin, {}).get(destination, 0.0)

    def candidates(self, origin):
        if self.destination_scope == "global":
            return self.destination_ids
        tile = self.oa2tile[origin]
        return [unit for unit in self.destination_ids if self.oa2tile.get(unit) == tile]

    def get_destinations(self, origin, size_train_dest, all_locs_in_train_region, rng=None):
        return sample_destinations(origin, size_train_dest, all_locs_in_train_region,
                                   self.o2d2flow, self.frac_true_dest, rng)

    def destinations_for(self, index):
        origin = self.list_IDs[index]
        candidates = self.candidates(origin)
        if not self.training:
            return candidates
        # Independent of worker count, PYTHONHASHSEED and iteration order.
        rng = np.random.default_rng(np.random.SeedSequence([self.seed, self.epoch, index]))
        return self.get_destinations(origin, self.dim_dests, candidates, rng)

    def get_X_T(self, origins, destinations):
        features = [[self.get_features(o, d) for d in ds] for o, ds in zip(origins, destinations)]
        targets = [[self.get_flow(o, d) for d in ds] for o, ds in zip(origins, destinations)]
        return torch.tensor(features, dtype=torch.float32), torch.tensor(targets, dtype=torch.float32)

    def __getitem__(self, index):
        origin = self.list_IDs[index]
        features, targets = self.get_X_T([origin], [self.destinations_for(index)])
        return features, targets, [origin]
