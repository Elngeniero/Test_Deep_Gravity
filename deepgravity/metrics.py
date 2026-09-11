"""CPC components are additive across origins and spatial tiles."""
import numpy as np


def cpc_components(observed, predicted):
    observed = np.asarray(observed, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    if observed.shape != predicted.shape:
        raise ValueError("Observed and predicted flows must have identical support")
    if (not np.isfinite(observed).all() or not np.isfinite(predicted).all()
            or (observed < 0).any() or (predicted < 0).any()):
        raise ValueError("CPC requires finite nonnegative flows")
    return (float(2 * np.minimum(observed, predicted).sum()),
            float(observed.sum()), float(predicted.sum()))


def common_part_of_commuters(values1, values2, numerator_only=False):
    numerator, observed, predicted = cpc_components(values1, values2)
    if numerator_only:
        return numerator
    denominator = observed + predicted
    # Explicit convention, consistent with historical reports: empty/empty = 0.
    return numerator / denominator if denominator else 0.0
