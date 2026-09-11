"""Stable, bounded, without-replacement destination sampling."""
import numpy as np


def sample_destinations(origin, size, candidates, flows, fraction=0.0, rng=None):
    if not 0 <= fraction <= 1 or size < 1:
        raise ValueError("Require size >= 1 and fraction in [0, 1]")
    universe = sorted(set(candidates))
    if not universe:
        raise ValueError("Empty destination universe")
    size = min(size, len(universe))
    if size == len(universe):
        return universe
    rng = np.random if rng is None else rng
    positives = [d for d in universe if flows.get(origin, {}).get(d, 0) > 0]
    count = min(int(size * fraction), len(positives))
    selected = list(rng.choice(positives, size=count, replace=False)) if count else []
    selected_set = set(selected)
    remaining = [d for d in universe if d not in selected_set]
    # Remaining candidates may include unselected positives: fraction is a quota.
    selected.extend(rng.choice(remaining, size=size - count, replace=False).tolist())
    rng.shuffle(selected)
    return selected
