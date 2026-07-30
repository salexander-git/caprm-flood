"""Tests for caprm.spatial_kfold.

The properties asserted here are the ones the partition's defensibility rests
on: every block is tested exactly once, training rows are never dropped, the
test set is separated from BOTH other splits, the compact on-disk encoding is
lossless, and fold membership is not a relabelling of the train/val/test draw.
"""

from __future__ import annotations

import numpy as np
import pytest

from caprm.spatial_split import (
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_VAL,
    SplitConfig,
    assign_blocks,
    block_uniform,
)
from caprm.spatial_kfold import (
    SPLIT_DROPPED,
    KFoldConfig,
    assign_block_folds,
    block_fold,
    build_kfold,
    dropped_mask_codes,
    roles_for_fold,
    roles_from_codes,
)


def _grid(n_side: int, spacing: float, offset: float = 500_000.0):
    coords = offset + np.arange(n_side) * spacing
    xx, yy = np.meshgrid(coords, coords)
    x, y = xx.ravel(), yy.ravel()
    pid = np.array([f"P{i:06d}" for i in range(x.size)], dtype=object)
    target = (x - offset) / 1000.0 + (y - offset) / 2000.0
    return pid, x, y, target


def test_block_uniform_default_namespace_is_the_original_key():
    """Adding the namespace parameter must not move any existing assignment."""
    import hashlib

    key = f"{7}:{3}:{-4}".encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=8).digest()
    expected = (int.from_bytes(digest, "big") >> 11) / float(1 << 53)
    assert block_uniform(3, -4, 7) == expected


def test_block_fold_is_in_range_and_deterministic():
    for i in range(-5, 5):
        for j in range(-5, 5):
            a = block_fold(i, j, 20260722, 5)
            assert 0 <= a < 5
            assert a == block_fold(i, j, 20260722, 5)


def test_block_fold_is_independent_of_the_split_draw():
    """Different hash namespaces must not produce a correlated assignment."""
    folds = [block_fold(i, 0, 11, 5) for i in range(200)]
    split_like = [int(block_uniform(i, 0, 11) * 5) for i in range(200)]
    agreement = sum(a == b for a, b in zip(folds, split_like)) / len(folds)
    assert 0.10 < agreement < 0.30  # chance is 0.20 for K = 5


def test_block_fold_changes_with_the_seed():
    a = [block_fold(i, 0, 1, 5) for i in range(200)]
    b = [block_fold(i, 0, 2, 5) for i in range(200)]
    assert a != b


def test_roles_for_fold_assigns_test_val_and_train():
    fold = np.array([0, 1, 2, 3, 4])
    roles = roles_for_fold(fold, 0, 5)
    assert roles.tolist() == [SPLIT_TEST, SPLIT_VAL, SPLIT_TRAIN, SPLIT_TRAIN, SPLIT_TRAIN]


def test_roles_for_fold_wraps_validation_at_the_last_fold():
    fold = np.array([0, 1, 2, 3, 4])
    roles = roles_for_fold(fold, 4, 5)
    assert roles[4] == SPLIT_TEST
    assert roles[0] == SPLIT_VAL


def test_every_fold_is_test_exactly_once_across_the_cycle():
    fold = np.arange(5)
    counts = np.zeros(5, dtype=int)
    for k in range(5):
        counts += (roles_for_fold(fold, k, 5) == SPLIT_TEST).astype(int)
    assert counts.tolist() == [1, 1, 1, 1, 1]


def test_block_folds_are_shared_by_every_property_in_a_block():
    config = KFoldConfig(block_size_m=2000.0, n_folds=5, seed=3)
    x = np.array([500_100.0, 500_900.0, 502_100.0])
    y = np.array([600_100.0, 600_900.0, 600_100.0])
    block_i, block_j = assign_blocks(x, y, config.as_split_config())
    folds = assign_block_folds(block_i, block_j, config)
    assert folds[0] == folds[1]  # same 2 km cell
    assert block_i[2] != block_i[0]


def test_role_encoding_round_trips():
    fold = np.array([0, 1, 2, 0, 1])
    roles = np.empty((5, 3), dtype=object)
    for k in range(3):
        roles[:, k] = roles_for_fold(fold, k, 3)
    roles[0, 1] = SPLIT_DROPPED
    roles[3, 2] = SPLIT_DROPPED
    codes = dropped_mask_codes(roles, 3)
    assert codes.tolist() == [2, 0, 0, 4, 0]
    assert (roles_from_codes(fold, codes, 3) == roles).all()


def test_config_rejects_too_few_folds():
    with pytest.raises(ValueError, match="n_folds"):
        KFoldConfig(n_folds=2)


def test_config_rejects_a_negative_buffer():
    with pytest.raises(ValueError, match="buffer_m"):
        KFoldConfig(buffer_m=-1.0)


def test_build_kfold_enforces_the_separation_on_every_fold():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=500.0, n_folds=5, seed=42)
    pid, x, y, target = _grid(60, 400.0)
    result = build_kfold(pid, x, y, target, config)
    for fold_stat in result.stats["folds"]:
        for key in ("gate_test", "gate_val"):
            gate = fold_stat[key]
            if gate["n_holdout"]:
                assert gate["min_distance_m"] >= config.buffer_m
                assert gate["n_metric_violations"] == 0


def test_build_kfold_never_drops_a_training_property():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=500.0, n_folds=5, seed=42)
    pid, x, y, target = _grid(50, 400.0)
    result = build_kfold(pid, x, y, target, config)
    for k in range(config.n_folds):
        pre = roles_for_fold(result.fold, k, config.n_folds)
        post = result.roles[:, k]
        assert int((pre == SPLIT_TRAIN).sum()) == int((post == SPLIT_TRAIN).sum())


def test_build_kfold_isolates_test_from_validation():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=500.0, n_folds=5, seed=42)
    pid, x, y, target = _grid(50, 400.0)
    result = build_kfold(pid, x, y, target, config)
    for fold_stat in result.stats["folds"]:
        separation = fold_stat["min_test_to_val_separation_m"]
        if separation is not None:
            assert separation >= config.buffer_m


def test_build_kfold_leaves_test_beside_validation_when_isolation_is_off():
    """The isolation flag must actually change something, or it is decoration."""
    pid, x, y, target = _grid(50, 400.0)
    off = build_kfold(
        pid, x, y, target,
        KFoldConfig(block_size_m=4000.0, buffer_m=500.0, n_folds=5, seed=42,
                    isolate_test_from_val=False),
    )
    separations = [
        f["min_test_to_val_separation_m"] for f in off.stats["folds"]
        if f["min_test_to_val_separation_m"] is not None
    ]
    assert min(separations) < 500.0


def test_no_property_is_tested_in_more_than_one_fold():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=500.0, n_folds=5, seed=42)
    pid, x, y, target = _grid(50, 400.0)
    result = build_kfold(pid, x, y, target, config)
    tested = np.zeros(len(pid), dtype=int)
    for k in range(config.n_folds):
        tested += (result.roles[:, k] == SPLIT_TEST).astype(int)
    assert tested.max() <= 1
    assert result.stats["properties_tested_at_least_once"] == int(tested.sum())


def test_build_kfold_is_deterministic():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=500.0, n_folds=5, seed=99)
    pid, x, y, target = _grid(40, 500.0)
    a = build_kfold(pid, x, y, target, config)
    b = build_kfold(pid, x, y, target, config)
    assert np.array_equal(a.fold, b.fold)
    assert (a.roles == b.roles).all()


def test_build_kfold_rejects_duplicate_property_ids():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=0.0, n_folds=5)
    pid = np.array(["A", "A"], dtype=object)
    with pytest.raises(ValueError, match="unique"):
        build_kfold(pid, np.array([1.0, 2.0]), np.array([1.0, 2.0]),
                    np.array([1.0, 2.0]), config)


def test_build_kfold_rejects_mismatched_lengths():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=0.0, n_folds=5)
    with pytest.raises(ValueError, match="equal length"):
        build_kfold(np.array(["A", "B"], dtype=object), np.array([1.0, 2.0]),
                    np.array([1.0, 2.0]), np.array([1.0]), config)


def test_aggregate_baseline_covers_only_tested_properties():
    config = KFoldConfig(block_size_m=4000.0, buffer_m=500.0, n_folds=5, seed=42)
    pid, x, y, target = _grid(50, 400.0)
    result = build_kfold(pid, x, y, target, config)
    aggregate = result.stats["aggregate_baseline"]
    assert aggregate["n"] == result.stats["properties_tested_at_least_once"]
    assert 0 < aggregate["n"] < len(pid)