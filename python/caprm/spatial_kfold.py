"""Spatially-blocked K-fold partition for the Phase C surrogate (task C1).

Why K-fold rather than one holdout
----------------------------------
C1-a held the separation fixed and varied only the seed. Across ten seeds the
test set's own mean label moved by up to one population sigma and the
nearest-neighbour baseline RMSE moved by more than the RMSE itself. A single
blocked holdout therefore reports an error that is partly a statement about
WHICH blocks the hash drew (Nucleus 18.32). Blocked K-fold removes that
leverage by construction: every occupied block serves as test exactly once and
as validation exactly once, so no block selection is left for a seed to make.
The seed still decides which blocks share a fold; it no longer decides which
blocks are tested.

Structure
---------
One grid, edge ``b``, origin recorded. Each occupied block draws a fold in
``[0, K)`` from a namespaced hash of ``(seed, i, j)``. For fold ``k``:

    test  = fold k
    val   = fold (k + 1) mod K
    train = the remaining K - 2 folds

The buffer is then carved by ``caprm.spatial_split.apply_buffer``, unchanged:
holdout properties within ``w`` of ANY training property are relabelled
``dropped``. Training rows are never dropped, so the cost of separation falls
entirely on the holdout sets, where it is affordable.

What this partition is, and is not
----------------------------------
A property survives as test only if it is at least ``w`` from every training
property, so the surviving test set is deliberately the subset FAR from
training data. Error measured on it is error at separation >= ``w``, not
countywide error, and C2/C4 must say so. The compensating property is that
every block contributes its own interior, so the aggregate test set is spread
over the whole county rather than concentrated in whichever blocks a seed drew.

No partition of a 51 x 48 km county decorrelates this field: the variogram is
still climbing at 8 km. The defensible claim is the measured one — test and
training properties are separated by at least ``w`` metres, at which the field
retains a stated fraction of its sill — not "we used a spatially blocked
split".
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict, field
from typing import Any

import numpy as np

from caprm.spatial_split import (
    DISTANCE_CRS,
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_VAL,
    SplitConfig,
    apply_buffer,
    assign_blocks,
)
from caprm.split_gate import (
    measure_gate,
    nearest_neighbour_baseline,
    nearest_train_distance,
)

SPLIT_DROPPED = "dropped"
FOLD_NAMESPACE = "fold:"


@dataclass(frozen=True)
class KFoldConfig:
    """Fully specifies a reproducible blocked K-fold partition."""

    block_size_m: float = 8000.0
    buffer_m: float = 2125.0
    n_folds: int = 5
    seed: int = 20260722
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0
    isolate_test_from_val: bool = True

    def __post_init__(self) -> None:
        if self.block_size_m <= 0:
            raise ValueError("block_size_m must be positive.")
        if self.buffer_m < 0:
            raise ValueError("buffer_m must be non-negative.")
        if self.n_folds < 3:
            raise ValueError(
                "n_folds must be at least 3: fold k is test, fold k+1 is "
                "validation, and at least one fold must remain for training."
            )
        if self.buffer_m >= self.block_size_m / 2.0:
            # Not a hard error: it is legal and sometimes desired. But a block
            # eroded by w on every side has no interior once w >= b/2, so the
            # caller should know it is asking for a near-empty test set.
            pass

    def as_split_config(self) -> SplitConfig:
        """The equivalent SplitConfig, so apply_buffer is reused unchanged."""
        return SplitConfig(
            block_size_m=self.block_size_m,
            buffer_m=self.buffer_m,
            seed=self.seed,
            train_fraction=0.70,
            val_fraction=0.15,
            origin_x_m=self.origin_x_m,
            origin_y_m=self.origin_y_m,
        )


def block_fold(block_i: int, block_j: int, seed: int, n_folds: int) -> int:
    """Deterministic fold index in [0, n_folds) for one block.

    Uses its own hash namespace so fold membership is statistically independent
    of the train/val/test draw ``caprm.spatial_split`` makes from the same seed.
    Order-independent: depends only on the block indices, the seed and the
    namespace.
    """
    key = f"{seed}:{FOLD_NAMESPACE}{int(block_i)}:{int(block_j)}".encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(digest, "big") % int(n_folds)


def assign_block_folds(
    block_i: np.ndarray, block_j: np.ndarray, config: KFoldConfig
) -> np.ndarray:
    """Per property, the fold index of its block. Every distinct block hashed once."""
    block_i = np.asarray(block_i, dtype=np.int64)
    block_j = np.asarray(block_j, dtype=np.int64)
    unique_blocks, inverse = np.unique(
        np.stack([block_i, block_j], axis=1), axis=0, return_inverse=True
    )
    inverse = inverse.reshape(-1)
    folds = np.array(
        [block_fold(int(bi), int(bj), config.seed, config.n_folds)
         for bi, bj in unique_blocks],
        dtype=np.int64,
    )
    return folds[inverse]


def roles_for_fold(fold_of_property: np.ndarray, k: int, n_folds: int) -> np.ndarray:
    """Pre-buffer train/val/test labels when fold ``k`` is the test fold."""
    fold_of_property = np.asarray(fold_of_property, dtype=np.int64)
    roles = np.full(len(fold_of_property), SPLIT_TRAIN, dtype=object)
    roles[fold_of_property == (k + 1) % n_folds] = SPLIT_VAL
    roles[fold_of_property == k] = SPLIT_TEST
    return roles


@dataclass
class KFoldResult:
    property_id: np.ndarray
    block_i: np.ndarray
    block_j: np.ndarray
    fold: np.ndarray
    roles: np.ndarray  # shape (n_properties, n_folds), post-buffer
    config: KFoldConfig
    stats: dict = field(default_factory=dict)


def build_kfold(
    property_id: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    target: np.ndarray,
    config: KFoldConfig,
) -> KFoldResult:
    """Build every fold, measure the gate on each, and aggregate.

    The gate is measured, not asserted, and a violation raises rather than being
    recorded and passed over: an artifact that fails its own acceptance must not
    be written to disk looking like one that passed.
    """
    property_id = np.asarray(property_id, dtype=object)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)

    n = len(property_id)
    if not (len(x) == len(y) == len(target) == n):
        raise ValueError("property_id, x, y, target must have equal length.")
    if n == 0:
        raise ValueError("Empty property set.")
    if len({str(v) for v in property_id}) != n:
        raise ValueError("property_id values are not unique.")

    split_config = config.as_split_config()
    block_i, block_j = assign_blocks(x, y, split_config)
    fold = assign_block_folds(block_i, block_j, config)

    roles = np.empty((n, config.n_folds), dtype=object)
    fold_stats = []
    tested_once = np.zeros(n, dtype=bool)
    predictions = np.full(n, np.nan)

    for k in range(config.n_folds):
        pre = roles_for_fold(fold, k, config.n_folds)
        if config.buffer_m == 0.0:
            post = pre.copy()
        else:
            # 1. the gate the Roadmap requires: holdout at least w from train.
            post = apply_buffer(x, y, pre, split_config)
            if config.isolate_test_from_val:
                # 2. test at least w from VALIDATION too. Validation is seen
                #    during model selection, so a test property beside a
                #    validation property is a selection leak. It is second
                #    order, but it is measurable, and a measured leak left in
                #    place is worse than an unmeasured one. Relabelling val as
                #    train reuses apply_buffer rather than restating its rule.
                merged = pre.copy()
                merged[merged == SPLIT_VAL] = SPLIT_TRAIN
                against_both = apply_buffer(x, y, merged, split_config)
                leaked = (post == SPLIT_TEST) & (against_both != SPLIT_TEST)
                post[leaked] = SPLIT_DROPPED
        roles[:, k] = post

        criterion = config.buffer_m if config.buffer_m > 0 else float("inf")
        gate_test = measure_gate(
            x, y, block_i, block_j, post, SPLIT_TEST,
            criterion_separation_m=config.buffer_m,
            block_size_m=config.block_size_m,
            partition=f"kfold_{k}",
        )
        gate_val = measure_gate(
            x, y, block_i, block_j, post, SPLIT_VAL,
            criterion_separation_m=config.buffer_m,
            block_size_m=config.block_size_m,
            partition=f"kfold_{k}",
        )
        if config.buffer_m > 0:
            for report in (gate_test, gate_val):
                if report.n_holdout and not report.passed:
                    raise RuntimeError(
                        f"gate failed on fold {k} for {report.holdout_label}: "
                        f"{report.n_metric_violations} properties inside "
                        f"{config.buffer_m} m of training data"
                    )

        test_mask = post == SPLIT_TEST
        if test_mask.any():
            if (tested_once & test_mask).any():
                raise RuntimeError(
                    "a property was assigned to test in more than one fold; "
                    "fold membership is not a partition"
                )
            tested_once |= test_mask
            train_mask = post == SPLIT_TRAIN
            from scipy.spatial import cKDTree

            tree = cKDTree(np.column_stack([x[train_mask], y[train_mask]]))
            _, nearest = tree.query(np.column_stack([x[test_mask], y[test_mask]]), k=1)
            predictions[test_mask] = target[train_mask][nearest]

        baseline = nearest_neighbour_baseline(
            x, y, target, post, SPLIT_TEST, f"kfold_{k}"
        )
        test_to_val = _cross_holdout_separation(x, y, post)
        fold_stats.append(
            {
                "fold": k,
                "counts": {
                    "train": int((post == SPLIT_TRAIN).sum()),
                    "val": int((post == SPLIT_VAL).sum()),
                    "test": int((post == SPLIT_TEST).sum()),
                    "dropped": int((post == SPLIT_DROPPED).sum()),
                },
                "counts_pre_buffer": {
                    "train": int((pre == SPLIT_TRAIN).sum()),
                    "val": int((pre == SPLIT_VAL).sum()),
                    "test": int((pre == SPLIT_TEST).sum()),
                },
                "test_blocks": _count_blocks(block_i, block_j, fold == k),
                "gate_test": gate_test.to_dict(),
                "gate_val": gate_val.to_dict(),
                "min_test_to_val_separation_m": test_to_val,
                "baseline": baseline.to_dict() if baseline else None,
            }
        )

    aggregate = _aggregate_baseline(target, predictions, tested_once)
    block_pairs = np.unique(np.stack([block_i, block_j], axis=1), axis=0)
    blocks_per_fold = {}
    for k in range(config.n_folds):
        mask = fold == k
        blocks_per_fold[str(k)] = (
            0 if not mask.any()
            else int(len(np.unique(np.stack([block_i[mask], block_j[mask]], axis=1), axis=0)))
        )

    stats = {
        "n_properties": n,
        "n_blocks_total": int(len(block_pairs)),
        "blocks_per_fold": blocks_per_fold,
        "properties_tested_at_least_once": int(tested_once.sum()),
        "test_coverage_fraction": float(tested_once.sum() / n),
        "folds": fold_stats,
        "aggregate_baseline": aggregate,
        "crs": DISTANCE_CRS,
    }
    return KFoldResult(
        property_id=property_id,
        block_i=block_i,
        block_j=block_j,
        fold=fold,
        roles=roles,
        config=config,
        stats=stats,
    )


def _count_blocks(block_i: np.ndarray, block_j: np.ndarray, mask: np.ndarray) -> int:
    """Distinct occupied blocks under a boolean property mask."""
    if not mask.any():
        return 0
    return int(len(np.unique(np.stack([block_i[mask], block_j[mask]], axis=1), axis=0)))


def dropped_mask_codes(roles: np.ndarray, n_folds: int) -> np.ndarray:
    """Encode the per-fold drop decisions as one integer per property.

    ``roles`` is fully recoverable from ``(fold, code)``: a property is test in
    its own fold, validation in the next fold, and training otherwise, unless
    bit ``k`` of ``code`` marks it dropped in fold ``k``. Persisting the code
    instead of K label columns keeps the split file small without losing
    anything, and ``roles_from_codes`` is tested to reproduce ``roles`` exactly.
    """
    roles = np.asarray(roles, dtype=object)
    codes = np.zeros(roles.shape[0], dtype=np.int64)
    for k in range(n_folds):
        codes |= (roles[:, k] == SPLIT_DROPPED).astype(np.int64) << k
    return codes


def roles_from_codes(
    fold: np.ndarray, codes: np.ndarray, n_folds: int
) -> np.ndarray:
    """Inverse of :func:`dropped_mask_codes`; rebuilds the full roles matrix."""
    fold = np.asarray(fold, dtype=np.int64)
    codes = np.asarray(codes, dtype=np.int64)
    roles = np.empty((len(fold), n_folds), dtype=object)
    for k in range(n_folds):
        column = roles_for_fold(fold, k, n_folds)
        column[(codes >> k) & 1 == 1] = SPLIT_DROPPED
        roles[:, k] = column
    return roles


def _cross_holdout_separation(
    x: np.ndarray, y: np.ndarray, roles: np.ndarray
) -> float | None:
    """Minimum test-to-validation distance, reported as a diagnostic.

    The gate constrains holdout against TRAIN, which is what the Roadmap
    requires. Test and validation may still sit close, which would bias model
    selection rather than the final measurement. It is measured and published
    rather than assumed away or silently enforced.
    """
    roles = np.asarray(roles, dtype=object)
    test_mask = roles == SPLIT_TEST
    val_mask = roles == SPLIT_VAL
    if not test_mask.any() or not val_mask.any():
        return None
    from scipy.spatial import cKDTree

    tree = cKDTree(np.column_stack([x[val_mask], y[val_mask]]))
    distances, _ = tree.query(np.column_stack([x[test_mask], y[test_mask]]), k=1)
    return float(distances.min())


def _aggregate_baseline(
    target: np.ndarray, predictions: np.ndarray, tested: np.ndarray
) -> dict[str, Any]:
    """Nearest-training-neighbour error over the union of all folds' test sets.

    Each property is tested at most once, so the union is a clean sample and the
    aggregate is not an average of averages over unequal folds.
    """
    if not tested.any():
        return {"n": 0}
    error = predictions[tested] - target[tested]
    actual = target[tested]
    denominator = float(np.var(actual))
    return {
        "n": int(tested.sum()),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mae": float(np.mean(np.abs(error))),
        "max_abs_error": float(np.max(np.abs(error))),
        "r2": float(1.0 - np.mean(error**2) / denominator) if denominator > 0 else float("nan"),
        "test_mean_label": float(actual.mean()),
        "test_std_label": float(actual.std(ddof=1)),
    }