"""Measure the C1 leakage gate, its controls, and the nearest-neighbour floor.

``caprm.spatial_split`` BUILDS partitions. This module JUDGES them, and it
judges every partition with the same code path, because a gate applied only to
the partition it was designed for measures nothing (Nucleus 18.25).

The criterion, stated once
--------------------------
A partition PASSES at separation ``s`` metres when every surviving holdout
property lies at least ``s`` metres from every training property:

    min over holdout h, train t of  euclidean(h, t)  >=  s

``>=`` and not ``>``. Two points on the facing edges of an ``s``-wide gap are
exactly ``s`` apart, and an assertion written ``>`` turns that into a latent
failure that fires once, on a rerun, for no reason a reader can reconstruct.

The block-grid Chebyshev separation is measured and reported ALONGSIDE the
metric criterion, never as a second criterion. The two are not equivalent —
points in Chebyshev-adjacent blocks can be up to ``2*b*sqrt(2)`` apart, and
points ``s`` apart can still share a block edge — so reporting both and naming
the binding one is honest, while deriving one from the other would be a claim
the geometry does not support.

The Chebyshev figure is computed as the minimum over ALL training blocks, not
as the Chebyshev separation of the metrically nearest training property. Those
are different quantities: the metrically closest training property need not sit
in the grid-closest training block. Taking the second and calling it the first
is the defect shape of Nucleus 18.29 — a plausible number, no error raised.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from caprm.spatial_split import SPLIT_TEST, SPLIT_TRAIN, SPLIT_VAL

DISTANCE_PERCENTILES = (0, 1, 5, 25, 50, 75, 95, 100)


@dataclass(frozen=True)
class GateReport:
    partition: str
    holdout_label: str
    criterion_separation_m: float
    n_train: int
    n_holdout: int
    min_distance_m: float | None
    distance_percentiles_m: dict[str, float]
    n_metric_violations: int
    fraction_metric_violations: float
    min_chebyshev_blocks: int | None
    n_grid_violations: int
    block_size_m: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def min_chebyshev_to_train(
    block_i: np.ndarray,
    block_j: np.ndarray,
    split: np.ndarray,
    holdout_label: str,
) -> np.ndarray:
    """Per holdout property, the minimum Chebyshev block separation to ANY train.

    Reduced over distinct blocks first: the county holds a few hundred occupied
    blocks, so the exhaustive comparison is small and exact rather than
    approximated by a tree.
    """
    block_i = np.asarray(block_i, dtype=np.int64)
    block_j = np.asarray(block_j, dtype=np.int64)
    split = np.asarray(split, dtype=object)

    train_mask = split == SPLIT_TRAIN
    holdout_mask = split == holdout_label
    if not train_mask.any() or not holdout_mask.any():
        return np.empty(0, dtype=np.int64)

    train_blocks = np.unique(
        np.stack([block_i[train_mask], block_j[train_mask]], axis=1), axis=0
    )
    holdout_pairs = np.stack([block_i[holdout_mask], block_j[holdout_mask]], axis=1)
    holdout_blocks, inverse = np.unique(holdout_pairs, axis=0, return_inverse=True)
    inverse = inverse.reshape(-1)

    per_block = np.empty(len(holdout_blocks), dtype=np.int64)
    for k, (bi, bj) in enumerate(holdout_blocks):
        chebyshev = np.maximum(
            np.abs(train_blocks[:, 0] - bi), np.abs(train_blocks[:, 1] - bj)
        )
        per_block[k] = int(chebyshev.min())
    return per_block[inverse]


def nearest_train_distance(
    x: np.ndarray, y: np.ndarray, split: np.ndarray, holdout_label: str
) -> np.ndarray:
    """Per holdout property, the metric distance to the nearest training property."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    split = np.asarray(split, dtype=object)
    train_mask = split == SPLIT_TRAIN
    holdout_mask = split == holdout_label
    if not train_mask.any() or not holdout_mask.any():
        return np.empty(0)
    tree = cKDTree(np.column_stack([x[train_mask], y[train_mask]]))
    distances, _ = tree.query(np.column_stack([x[holdout_mask], y[holdout_mask]]), k=1)
    return distances


def measure_gate(
    x: np.ndarray,
    y: np.ndarray,
    block_i: np.ndarray,
    block_j: np.ndarray,
    split: np.ndarray,
    holdout_label: str,
    criterion_separation_m: float,
    block_size_m: float,
    partition: str,
) -> GateReport:
    """Run the identical gate on any partition and report what it measured."""
    split = np.asarray(split, dtype=object)
    distances = nearest_train_distance(x, y, split, holdout_label)
    chebyshev = min_chebyshev_to_train(block_i, block_j, split, holdout_label)

    n_holdout = int((split == holdout_label).sum())
    n_train = int((split == SPLIT_TRAIN).sum())

    if distances.size == 0:
        return GateReport(
            partition=partition,
            holdout_label=holdout_label,
            criterion_separation_m=float(criterion_separation_m),
            n_train=n_train,
            n_holdout=n_holdout,
            min_distance_m=None,
            distance_percentiles_m={},
            n_metric_violations=0,
            fraction_metric_violations=0.0,
            min_chebyshev_blocks=None,
            n_grid_violations=0,
            block_size_m=float(block_size_m),
            passed=False,
        )

    violations = int((distances < criterion_separation_m).sum())
    return GateReport(
        partition=partition,
        holdout_label=holdout_label,
        criterion_separation_m=float(criterion_separation_m),
        n_train=n_train,
        n_holdout=n_holdout,
        min_distance_m=float(distances.min()),
        distance_percentiles_m={
            f"p{p:g}": float(np.percentile(distances, p)) for p in DISTANCE_PERCENTILES
        },
        n_metric_violations=violations,
        fraction_metric_violations=float(violations / len(distances)),
        min_chebyshev_blocks=int(chebyshev.min()) if chebyshev.size else None,
        n_grid_violations=int((chebyshev <= 1).sum()) if chebyshev.size else 0,
        block_size_m=float(block_size_m),
        passed=bool(violations == 0),
    )


def random_split(
    n: int, seed: int, train_fraction: float = 0.70, val_fraction: float = 0.15
) -> np.ndarray:
    """The positive control: an i.i.d. per-property split, ignoring geometry.

    Kept deliberately. C2 reports the memorization gap between this and the
    blocked partition, and that gap is what the discipline bought.
    """
    rng = np.random.default_rng(seed)
    draws = rng.random(n)
    labels = np.full(n, SPLIT_TEST, dtype=object)
    labels[draws < train_fraction + val_fraction] = SPLIT_VAL
    labels[draws < train_fraction] = SPLIT_TRAIN
    return labels


@dataclass(frozen=True)
class BaselineReport:
    partition: str
    holdout_label: str
    n_train: int
    n_holdout: int
    rmse: float
    mae: float
    max_abs_error: float
    r2: float
    mean_nearest_train_distance_m: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def nearest_neighbour_baseline(
    x: np.ndarray,
    y: np.ndarray,
    target: np.ndarray,
    split: np.ndarray,
    holdout_label: str,
    partition: str,
) -> BaselineReport | None:
    """Copy the label of the geometrically closest training property.

    Declared before any model exists. On a target this autocorrelated it scores
    well, and it is the honest floor: a surrogate that does not beat it has
    learned the neighbourhood rather than the function.

    ``r2`` is computed against the variance of the HOLDOUT target, so it answers
    "better than predicting this holdout's own mean", not "better than
    predicting the training mean".
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    target = np.asarray(target, float)
    split = np.asarray(split, dtype=object)

    train_mask = split == SPLIT_TRAIN
    holdout_mask = split == holdout_label
    if not train_mask.any() or not holdout_mask.any():
        return None

    tree = cKDTree(np.column_stack([x[train_mask], y[train_mask]]))
    distances, indices = tree.query(
        np.column_stack([x[holdout_mask], y[holdout_mask]]), k=1
    )
    predicted = target[train_mask][indices]
    actual = target[holdout_mask]
    error = predicted - actual
    denominator = float(np.var(actual))
    return BaselineReport(
        partition=partition,
        holdout_label=holdout_label,
        n_train=int(train_mask.sum()),
        n_holdout=int(holdout_mask.sum()),
        rmse=float(np.sqrt(np.mean(error**2))),
        mae=float(np.mean(np.abs(error))),
        max_abs_error=float(np.max(np.abs(error))),
        r2=float(1.0 - np.mean(error**2) / denominator) if denominator > 0 else float("nan"),
        mean_nearest_train_distance_m=float(distances.mean()),
    )


def summarise_seed_stability(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Spread of a per-seed measurement across repeated splits of one geometry.

    A single blocked holdout reports an error that is partly a statement about
    WHICH blocks the seed happened to draw. Sweeping the seed converts that from
    a worry into a measured quantity, the way B6 swept the seed window: if the
    spread across seeds is comparable to the effect C2 wants to report, a single
    split cannot carry the claim and blocked K-fold is required instead.
    """
    if not records:
        raise ValueError("no records to summarise")
    keys = [k for k in records[0] if isinstance(records[0][k], (int, float))]
    summary: dict[str, Any] = {"n_seeds": len(records)}
    for key in keys:
        values = np.array([float(r[key]) for r in records], dtype=float)
        summary[key] = {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "min": float(values.min()),
            "max": float(values.max()),
            "range": float(values.max() - values.min()),
        }
    return summary


def coordinate_label_ambiguity(
    x: np.ndarray, y: np.ndarray, target: np.ndarray
) -> dict[str, Any]:
    """The irreducible error floor of ANY function of (x, y) on this workload.

    If two properties share a coordinate and carry different labels, the target
    is not a well-defined function of the input and no coordinate-only surrogate
    can drive its error to zero. C2 needs this number to know whether its
    residuals are model error or target ambiguity.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    target = np.asarray(target, float)

    keys = np.stack([x, y], axis=1)
    _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.reshape(-1)
    group_sum = np.bincount(inverse, weights=target)
    group_mean = group_sum / np.bincount(inverse)
    residual = target - group_mean[inverse]
    group_max = np.full(len(counts), -np.inf)
    group_min = np.full(len(counts), np.inf)
    np.maximum.at(group_max, inverse, target)
    np.minimum.at(group_min, inverse, target)
    spread = group_max - group_min
    multi = counts > 1
    return {
        "distinct_coordinates": int(len(counts)),
        "coordinate_groups_with_multiple_properties": int(multi.sum()),
        "rows_in_those_groups": int(counts[multi].sum()),
        "groups_with_differing_label": int((spread[multi] > 0).sum()),
        "max_within_group_label_range": float(spread[multi].max()) if multi.any() else 0.0,
        "irreducible_mse": float(np.mean(residual**2)),
        "irreducible_rmse": float(np.sqrt(np.mean(residual**2))),
        "target_variance": float(np.var(target)),
    }