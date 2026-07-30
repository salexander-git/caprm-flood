"""Spatially-blocked train/validation/test split for the Phase C surrogate.

CAPRM-Flood Phase C, task C1. This module is READ-ONLY with respect to every
frozen product: it consumes the frozen projected coordinates and the frozen
exposure index and produces a split assignment. It never regenerates or mutates
evidence tables, the scoring layer, or the exposure index.

Coordinate reference system: EPSG:26918 (NAD83 / UTM zone 18N), meters. All
distances and block sizes are in meters. Degrees are never used.

The split is *blocked*, not random: whole square blocks of side ``b`` are assigned
to train/val/test, then a dead zone of width ``w`` is carved around the training
set by dropping any val/test property within ``w`` of any training property. This
guarantees a minimum train<->test (and train<->val) separation of ``w``, which
measures generalization to unseen regions rather than interpolation between
memorized neighbors.

Design choices (all reproducible from the recorded seed/params):

* Grid origin is fixed at (0, 0) in EPSG:26918, so a property's block identity
  does not depend on which other properties are present.
* Block -> split assignment is a per-block hash of ``f"{seed}:{i}:{j}"``, so it is
  independent of the order in which blocks are enumerated.
* The dead zone is enforced by construction (drop-below-``w``), then verified
  independently by re-measuring nearest-train distance with a fresh KD-tree.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

DISTANCE_CRS = "EPSG:26918"

# Split labels are fixed strings; the cumulative fractions below map a per-block
# uniform draw u in [0, 1) to a label.
SPLIT_TRAIN = "train"
SPLIT_VAL = "val"
SPLIT_TEST = "test"


@dataclass(frozen=True)
class SplitConfig:
    """Fully specifies a reproducible spatial split.

    ``train_fraction`` and ``val_fraction`` are cumulative-friendly fractions of
    *blocks* (not properties): a block's uniform draw ``u`` goes to train if
    ``u < train_fraction``, to val if ``u < train_fraction + val_fraction``, else
    to test. Test therefore receives ``1 - train_fraction - val_fraction``.
    """

    block_size_m: float = 2000.0
    buffer_m: float = 2000.0
    seed: int = 20260722
    train_fraction: float = 0.70
    val_fraction: float = 0.15
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0

    def __post_init__(self) -> None:
        if self.block_size_m <= 0:
            raise ValueError("block_size_m must be positive.")
        if self.buffer_m < 0:
            raise ValueError("buffer_m must be non-negative.")
        if not (0.0 < self.train_fraction < 1.0):
            raise ValueError("train_fraction must be in (0, 1).")
        if not (0.0 <= self.val_fraction < 1.0):
            raise ValueError("val_fraction must be in [0, 1).")
        if self.train_fraction + self.val_fraction >= 1.0:
            raise ValueError(
                "train_fraction + val_fraction must be < 1 so that the test "
                "split is non-empty."
            )

    @property
    def test_fraction(self) -> float:
        return 1.0 - self.train_fraction - self.val_fraction


def assign_blocks(
    x: np.ndarray,
    y: np.ndarray,
    config: SplitConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Return integer (block_i, block_j) for each property.

    ``block_i = floor((x - origin_x) / b)`` and likewise for ``block_j``. Inputs
    must be finite; non-finite coordinates are a hard error rather than a silent
    NaN block.
    """

    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    if x.shape != y.shape:
        raise ValueError("x and y must have the same shape.")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("Coordinates contain non-finite values.")

    block_i = np.floor(
        (x - config.origin_x_m) / config.block_size_m
    ).astype(np.int64)
    block_j = np.floor(
        (y - config.origin_y_m) / config.block_size_m
    ).astype(np.int64)
    return block_i, block_j


def block_uniform(
    block_i: int, block_j: int, seed: int, namespace: str = ""
) -> float:
    """Deterministic uniform draw in [0, 1) for one block.

    Order-independent: depends only on the block indices and the seed, not on how
    the set of blocks was enumerated. Uses blake2b over a canonical string key and
    the top 53 bits (double mantissa) for a clean [0, 1) mapping.

    ``namespace`` lets an independent consumer draw an UNCORRELATED value for the
    same block from the same seed. It is empty by default, which reproduces the
    original key format byte for byte, so adding it changes no existing
    assignment. ``caprm.spatial_kfold`` uses ``"fold:"`` so that fold membership
    is not a relabelling of the train/val/test draw.
    """

    key = f"{seed}:{namespace}{int(block_i)}:{int(block_j)}".encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    # Top 53 bits -> exact double in [0, 1).
    return (value >> 11) / float(1 << 53)


def _block_uniform(block_i: int, block_j: int, seed: int) -> float:
    """Backwards-compatible alias; retained so existing call sites are untouched."""
    return block_uniform(block_i, block_j, seed)


def label_for_uniform(u: float, config: SplitConfig) -> str:
    if u < config.train_fraction:
        return SPLIT_TRAIN
    if u < config.train_fraction + config.val_fraction:
        return SPLIT_VAL
    return SPLIT_TEST


def assign_block_splits(
    block_i: np.ndarray,
    block_j: np.ndarray,
    config: SplitConfig,
) -> np.ndarray:
    """Assign each property the split of its block (before the buffer drop).

    Every distinct block is hashed once; all properties in a block inherit the
    block's label. Returns a string array of shape ``block_i.shape``.
    """

    block_i = np.asarray(block_i, dtype=np.int64)
    block_j = np.asarray(block_j, dtype=np.int64)

    unique_blocks, inverse = np.unique(
        np.stack([block_i, block_j], axis=1),
        axis=0,
        return_inverse=True,
    )
    inverse = inverse.reshape(-1)

    block_labels = np.empty(len(unique_blocks), dtype=object)
    for index, (bi, bj) in enumerate(unique_blocks):
        u = _block_uniform(int(bi), int(bj), config.seed)
        block_labels[index] = label_for_uniform(u, config)

    return block_labels[inverse].astype(object)


def apply_buffer(
    x: np.ndarray,
    y: np.ndarray,
    split: np.ndarray,
    config: SplitConfig,
) -> np.ndarray:
    """Carve the dead zone: drop val/test properties within ``w`` of any train.

    Returns a copy of ``split`` where dropped properties are relabeled
    ``"dropped"``. Train labels are never changed. If there are no training
    properties, this is a hard error (a split with an empty train set is invalid).
    """

    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    split = np.asarray(split, dtype=object).copy()

    train_mask = split == SPLIT_TRAIN
    if not train_mask.any():
        raise ValueError("No training properties; cannot build a dead zone.")

    train_xy = np.column_stack([x[train_mask], y[train_mask]])
    tree = cKDTree(train_xy)

    holdout_mask = (split == SPLIT_VAL) | (split == SPLIT_TEST)
    if holdout_mask.any():
        holdout_xy = np.column_stack([x[holdout_mask], y[holdout_mask]])
        nearest_train_dist, _ = tree.query(holdout_xy, k=1)

        drop_local = nearest_train_dist < config.buffer_m
        holdout_indices = np.nonzero(holdout_mask)[0]
        drop_indices = holdout_indices[drop_local]
        split[drop_indices] = "dropped"

    return split


def min_separation(
    x: np.ndarray,
    y: np.ndarray,
    split: np.ndarray,
    holdout_label: str,
) -> float | None:
    """Independently measured minimum distance from a holdout split to train.

    Builds a fresh KD-tree on the *final* train coordinates and queries every
    surviving property of ``holdout_label``. Returns ``None`` if either side is
    empty.
    """

    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    split = np.asarray(split, dtype=object)

    train_mask = split == SPLIT_TRAIN
    holdout_mask = split == holdout_label
    if not train_mask.any() or not holdout_mask.any():
        return None

    tree = cKDTree(np.column_stack([x[train_mask], y[train_mask]]))
    dist, _ = tree.query(
        np.column_stack([x[holdout_mask], y[holdout_mask]]), k=1
    )
    return float(np.min(dist))


@dataclass
class SplitResult:
    property_id: np.ndarray
    block_i: np.ndarray
    block_j: np.ndarray
    split_pre_buffer: np.ndarray
    split: np.ndarray
    config: SplitConfig
    stats: dict = field(default_factory=dict)


def build_split(
    property_id: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    config: SplitConfig,
) -> SplitResult:
    """End-to-end split for one property set. Pure; does no file IO.

    Enforces: unique, non-null property IDs; finite coordinates; matching lengths.
    Verifies the min train<->test and train<->val separation after the buffer and
    raises if either falls below ``w`` (the construction should make this
    impossible; the check guards against a logic regression).
    """

    property_id = np.asarray(property_id, dtype=object)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    n = len(property_id)
    if not (len(x) == len(y) == n):
        raise ValueError("property_id, x, y must have equal length.")
    if n == 0:
        raise ValueError("Empty property set.")
    if len({str(v) for v in property_id}) != n:
        raise ValueError("property_id values are not unique.")
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in property_id):
        raise ValueError("property_id contains null values.")

    block_i, block_j = assign_blocks(x, y, config)
    split_pre = assign_block_splits(block_i, block_j, config)
    split = apply_buffer(x, y, split_pre, config)

    min_test_train = min_separation(x, y, split, SPLIT_TEST)
    min_val_train = min_separation(x, y, split, SPLIT_VAL)

    for label, value in (("test", min_test_train), ("val", min_val_train)):
        if value is not None and value < config.buffer_m:
            raise RuntimeError(
                f"Buffer invariant violated: min {label}<->train separation "
                f"{value:.6f} m < w={config.buffer_m} m."
            )

    def _count(label: str) -> int:
        return int(np.sum(split == label))

    def _pre_count(label: str) -> int:
        return int(np.sum(split_pre == label))

    def _blocks(label: str) -> int:
        mask = split_pre == label
        if not mask.any():
            return 0
        return len(np.unique(np.stack([block_i[mask], block_j[mask]], axis=1), axis=0))

    stats = {
        "n_properties": n,
        "n_blocks_total": len(
            np.unique(np.stack([block_i, block_j], axis=1), axis=0)
        ),
        "counts_pre_buffer": {
            "train": _pre_count(SPLIT_TRAIN),
            "val": _pre_count(SPLIT_VAL),
            "test": _pre_count(SPLIT_TEST),
        },
        "counts_final": {
            "train": _count(SPLIT_TRAIN),
            "val": _count(SPLIT_VAL),
            "test": _count(SPLIT_TEST),
            "dropped": _count("dropped"),
        },
        "dropped": {
            "val": _pre_count(SPLIT_VAL) - _count(SPLIT_VAL),
            "test": _pre_count(SPLIT_TEST) - _count(SPLIT_TEST),
            "total": _pre_count(SPLIT_VAL)
            - _count(SPLIT_VAL)
            + _pre_count(SPLIT_TEST)
            - _count(SPLIT_TEST),
        },
        "blocks_per_split": {
            "train": _blocks(SPLIT_TRAIN),
            "val": _blocks(SPLIT_VAL),
            "test": _blocks(SPLIT_TEST),
        },
        "min_separation_m": {
            "test_train": min_test_train,
            "val_train": min_val_train,
        },
    }

    return SplitResult(
        property_id=property_id,
        block_i=block_i,
        block_j=block_j,
        split_pre_buffer=split_pre,
        split=split,
        config=config,
        stats=stats,
    )