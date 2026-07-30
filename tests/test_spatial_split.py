"""Unit tests for caprm.spatial_split.

These run on synthetic property sets and prove the algorithm's guarantees
independent of the countywide data. The single most important test is
``test_buffer_guarantees_min_separation``: it constructs a dense grid so that
many holdout properties sit close to training properties, then asserts the
post-buffer min train<->test and train<->val separation is >= w.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from caprm.spatial_split import (  # noqa: E402
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_VAL,
    SplitConfig,
    assign_block_splits,
    assign_blocks,
    build_split,
    label_for_uniform,
    min_separation,
)


def _grid(n_side: int, spacing: float, offset: float = 500_000.0):
    """A regular grid of n_side x n_side points, UTM-scale coordinates."""
    coords = offset + np.arange(n_side) * spacing
    xx, yy = np.meshgrid(coords, coords)
    x = xx.ravel()
    y = yy.ravel()
    pid = np.array([f"P{i:06d}" for i in range(x.size)], dtype=object)
    return pid, x, y


def test_blocks_are_floor_of_scaled_coords():
    config = SplitConfig(block_size_m=1000.0, origin_x_m=0.0, origin_y_m=0.0)
    x = np.array([0.0, 999.0, 1000.0, 2500.0])
    y = np.array([0.0, 0.0, 0.0, 0.0])
    bi, bj = assign_blocks(x, y, config)
    assert bi.tolist() == [0, 0, 1, 2]
    assert bj.tolist() == [0, 0, 0, 0]


def test_label_for_uniform_boundaries():
    config = SplitConfig(train_fraction=0.70, val_fraction=0.15)
    assert label_for_uniform(0.0, config) == SPLIT_TRAIN
    assert label_for_uniform(0.6999, config) == SPLIT_TRAIN
    assert label_for_uniform(0.70, config) == SPLIT_VAL
    assert label_for_uniform(0.8499, config) == SPLIT_VAL
    assert label_for_uniform(0.85, config) == SPLIT_TEST
    assert label_for_uniform(0.999, config) == SPLIT_TEST


def test_block_assignment_is_order_independent():
    """Same property -> same block label regardless of input row order."""
    config = SplitConfig(block_size_m=2000.0, seed=123)
    pid, x, y = _grid(20, 300.0)

    bi, bj = assign_blocks(x, y, config)
    labels = assign_block_splits(bi, bj, config)

    order = np.random.default_rng(0).permutation(x.size)
    bi2, bj2 = assign_blocks(x[order], y[order], config)
    labels2 = assign_block_splits(bi2, bj2, config)

    # Undo the permutation and compare per property.
    inverse = np.empty_like(order)
    inverse[order] = np.arange(order.size)
    assert list(labels) == list(labels2[inverse])


def test_all_properties_in_a_block_share_pre_buffer_label():
    config = SplitConfig(block_size_m=2000.0, seed=7)
    # Two points guaranteed to share a block (same 2 km cell).
    x = np.array([500_100.0, 500_900.0])
    y = np.array([600_100.0, 600_900.0])
    bi, bj = assign_blocks(x, y, config)
    assert bi[0] == bi[1] and bj[0] == bj[1]
    labels = assign_block_splits(bi, bj, config)
    assert labels[0] == labels[1]


def test_buffer_guarantees_min_separation():
    """Core acceptance: post-buffer min holdout<->train distance >= w.

    Uses w = b/2 on a large grid so all three splits retain survivors and the
    guarantee is exercised for both val and test. The guarantee itself (survivors
    are >= w from train) holds for any w; see the w == b edge test below for the
    aggressive-buffer regime where a small holdout split can be fully consumed.
    """
    config = SplitConfig(block_size_m=2000.0, buffer_m=1000.0, seed=42)
    # 80x80 grid at 250 m spacing spans ~20 km -> 100 blocks (70/15/15).
    pid, x, y = _grid(80, 250.0)
    result = build_split(pid, x, y, config)

    mtt = result.stats["min_separation_m"]["test_train"]
    mvt = result.stats["min_separation_m"]["val_train"]
    assert mtt is not None and mtt >= config.buffer_m
    assert mvt is not None and mvt >= config.buffer_m

    # Independent re-measurement must agree with the construction.
    assert min_separation(x, y, result.split, SPLIT_TEST) >= config.buffer_m
    assert min_separation(x, y, result.split, SPLIT_VAL) >= config.buffer_m

    # The buffer must actually have removed something on this dense grid,
    # otherwise the test proves nothing about the drop path.
    assert result.stats["dropped"]["total"] > 0


def test_invariant_holds_even_when_holdout_fully_consumed():
    """Documents the w == b regime: a small holdout split can be fully consumed.

    With buffer width equal to block width, a holdout block bordered by training
    blocks loses its whole interior (a point at a block's center is only b/2 from
    each edge). The guarantee is unaffected: any *surviving* holdout property is
    still >= w from train. build_split must not raise, and must not report a
    separation below w for whatever survives.
    """
    config = SplitConfig(block_size_m=2000.0, buffer_m=2000.0, seed=42)
    pid, x, y = _grid(60, 200.0)
    result = build_split(pid, x, y, config)

    for label in (SPLIT_TEST, SPLIT_VAL):
        sep = result.stats["min_separation_m"][
            "test_train" if label == SPLIT_TEST else "val_train"
        ]
        # Either the split was fully consumed (None) or its survivors clear w.
        assert sep is None or sep >= config.buffer_m

    # Train is never dropped; heavy holdout attrition is expected here.
    assert result.stats["counts_final"]["train"] == 2900
    assert result.stats["dropped"]["total"] > 0


def test_counts_are_conserved():
    config = SplitConfig(block_size_m=2000.0, buffer_m=2000.0, seed=42)
    pid, x, y = _grid(50, 250.0)
    result = build_split(pid, x, y, config)
    c = result.stats["counts_final"]
    assert c["train"] + c["val"] + c["test"] + c["dropped"] == x.size
    # Train is never dropped: final train == pre-buffer train.
    assert c["train"] == result.stats["counts_pre_buffer"]["train"]


def test_full_reproducibility_from_seed():
    config = SplitConfig(block_size_m=2000.0, buffer_m=1500.0, seed=99)
    pid, x, y = _grid(40, 300.0)
    a = build_split(pid, x, y, config)
    b = build_split(pid, x, y, config)
    assert list(a.split) == list(b.split)


def test_different_seed_changes_assignment():
    pid, x, y = _grid(40, 500.0)
    a = build_split(pid, x, y, SplitConfig(seed=1))
    b = build_split(pid, x, y, SplitConfig(seed=2))
    # Not guaranteed different for every property, but the overall vectors
    # should differ for independent seeds on a grid of this size.
    assert list(a.split) != list(b.split)


def test_nonfinite_coordinates_raise():
    config = SplitConfig()
    x = np.array([1.0, np.nan])
    y = np.array([1.0, 2.0])
    try:
        assign_blocks(x, y, config)
    except ValueError:
        return
    raise AssertionError("Expected ValueError for non-finite coordinates.")


def test_duplicate_property_ids_raise():
    config = SplitConfig()
    pid = np.array(["A", "A"], dtype=object)
    x = np.array([500_000.0, 520_000.0])
    y = np.array([600_000.0, 620_000.0])
    try:
        build_split(pid, x, y, config)
    except ValueError:
        return
    raise AssertionError("Expected ValueError for duplicate property IDs.")


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)