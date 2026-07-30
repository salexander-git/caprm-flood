"""Tests for caprm.split_gate.

The gate is the instrument C1 rests on, so each test constructs a case whose
answer is known by hand, including the two cases the design documents call out
as latent failures: the exact-boundary comparison and the Chebyshev minimum
taken over the wrong set.
"""

from __future__ import annotations

import numpy as np
import pytest

from caprm.spatial_split import SPLIT_TEST, SPLIT_TRAIN, SPLIT_VAL
from caprm.split_gate import (
    coordinate_label_ambiguity,
    measure_gate,
    min_chebyshev_to_train,
    nearest_neighbour_baseline,
    nearest_train_distance,
    random_split,
    summarise_seed_stability,
)


def test_chebyshev_minimum_is_over_all_train_blocks_not_the_nearest_point():
    """The trap: the metrically closest train point is in a further-away block.

    Train A sits at (0, 0) in block (0, 0). Train B sits at (2500, 0) in block
    (2, 0). The test point at (1200, 0) is in block (1, 0): metrically closer to
    A (1200 m) than to B (1300 m), but grid-adjacent to BOTH. Now move A far in
    the j direction so its block is (0, 5) while it stays metrically nearest.
    Taking the Chebyshev separation OF THE METRICALLY NEAREST POINT would report
    5; the minimum over all train blocks is 1.
    """
    x = np.array([0.0, 2500.0, 1200.0])
    y = np.array([5000.0, 0.0, 0.0])
    block_i = np.array([0, 2, 1], dtype=np.int64)
    block_j = np.array([5, 0, 0], dtype=np.int64)
    split = np.array([SPLIT_TRAIN, SPLIT_TRAIN, SPLIT_TEST], dtype=object)

    chebyshev = min_chebyshev_to_train(block_i, block_j, split, SPLIT_TEST)
    assert chebyshev.tolist() == [1]


def test_chebyshev_is_empty_when_a_side_is_empty():
    split = np.array([SPLIT_TRAIN, SPLIT_TRAIN], dtype=object)
    out = min_chebyshev_to_train(np.array([0, 1]), np.array([0, 0]), split, SPLIT_TEST)
    assert out.size == 0


def test_gate_passes_at_exactly_the_criterion():
    """>= and not >. Two points exactly s apart must PASS."""
    s = 1000.0
    x = np.array([0.0, s])
    y = np.array([0.0, 0.0])
    split = np.array([SPLIT_TRAIN, SPLIT_TEST], dtype=object)
    report = measure_gate(
        x, y, np.array([0, 1]), np.array([0, 0]), split, SPLIT_TEST,
        criterion_separation_m=s, block_size_m=1000.0, partition="exact_boundary",
    )
    assert report.min_distance_m == pytest.approx(s)
    assert report.n_metric_violations == 0
    assert report.passed is True


def test_gate_fails_just_inside_the_criterion():
    s = 1000.0
    x = np.array([0.0, s - 1e-6])
    y = np.array([0.0, 0.0])
    split = np.array([SPLIT_TRAIN, SPLIT_TEST], dtype=object)
    report = measure_gate(
        x, y, np.array([0, 0]), np.array([0, 0]), split, SPLIT_TEST,
        criterion_separation_m=s, block_size_m=1000.0, partition="just_inside",
    )
    assert report.n_metric_violations == 1
    assert report.passed is False


def test_gate_counts_violations_and_reports_the_distribution():
    x = np.array([0.0, 100.0, 5000.0, 20000.0])
    y = np.zeros(4)
    split = np.array([SPLIT_TRAIN, SPLIT_TEST, SPLIT_TEST, SPLIT_TEST], dtype=object)
    report = measure_gate(
        x, y, np.zeros(4, dtype=np.int64), np.zeros(4, dtype=np.int64), split,
        SPLIT_TEST, criterion_separation_m=1000.0, block_size_m=1000.0,
        partition="mixed",
    )
    assert report.n_holdout == 3
    assert report.n_metric_violations == 1
    assert report.fraction_metric_violations == pytest.approx(1 / 3)
    assert report.distance_percentiles_m["p0"] == pytest.approx(100.0)
    assert report.distance_percentiles_m["p100"] == pytest.approx(20000.0)


def test_gate_reports_failure_when_a_split_is_empty():
    x = np.array([0.0, 1.0])
    y = np.zeros(2)
    split = np.array([SPLIT_TRAIN, SPLIT_TRAIN], dtype=object)
    report = measure_gate(
        x, y, np.zeros(2, dtype=np.int64), np.zeros(2, dtype=np.int64), split,
        SPLIT_TEST, criterion_separation_m=100.0, block_size_m=1000.0, partition="empty",
    )
    assert report.n_holdout == 0
    assert report.passed is False  # an empty holdout is not a pass


def test_nearest_train_distance_matches_a_hand_computation():
    x = np.array([0.0, 3.0, 0.0])
    y = np.array([0.0, 4.0, 10.0])
    split = np.array([SPLIT_TRAIN, SPLIT_TEST, SPLIT_TRAIN], dtype=object)
    d = nearest_train_distance(x, y, split, SPLIT_TEST)
    assert d.tolist() == [pytest.approx(5.0)]


def test_random_split_is_deterministic_and_hits_its_proportions():
    a = random_split(100_000, seed=7)
    b = random_split(100_000, seed=7)
    assert np.array_equal(a, b)
    assert (a == SPLIT_TRAIN).mean() == pytest.approx(0.70, abs=0.01)
    assert (a == SPLIT_VAL).mean() == pytest.approx(0.15, abs=0.01)
    assert (a == SPLIT_TEST).mean() == pytest.approx(0.15, abs=0.01)


def test_random_split_changes_with_the_seed():
    assert not np.array_equal(random_split(10_000, seed=1), random_split(10_000, seed=2))


def test_baseline_is_exact_when_a_holdout_point_coincides_with_training():
    x = np.array([0.0, 100.0, 0.0])
    y = np.array([0.0, 0.0, 0.0])
    z = np.array([10.0, 20.0, 10.0])
    split = np.array([SPLIT_TRAIN, SPLIT_TRAIN, SPLIT_TEST], dtype=object)
    report = nearest_neighbour_baseline(x, y, z, split, SPLIT_TEST, "coincident")
    assert report.rmse == pytest.approx(0.0)
    assert report.max_abs_error == pytest.approx(0.0)


def test_baseline_r2_is_against_the_holdout_variance():
    x = np.array([0.0, 1000.0, 10.0, 1010.0])
    y = np.zeros(4)
    z = np.array([0.0, 100.0, 50.0, 50.0])
    split = np.array([SPLIT_TRAIN, SPLIT_TRAIN, SPLIT_TEST, SPLIT_TEST], dtype=object)
    report = nearest_neighbour_baseline(x, y, z, split, SPLIT_TEST, "r2")
    # predictions are 0 and 100 against actuals 50 and 50: MSE = 2500,
    # holdout variance = 0, so r2 is not finite and must be reported as nan
    assert report.rmse == pytest.approx(50.0)
    assert np.isnan(report.r2)


def test_baseline_returns_none_when_a_side_is_empty():
    x = np.array([0.0, 1.0])
    y = np.zeros(2)
    z = np.zeros(2)
    split = np.array([SPLIT_TRAIN, SPLIT_TRAIN], dtype=object)
    assert nearest_neighbour_baseline(x, y, z, split, SPLIT_TEST, "empty") is None


def test_label_ambiguity_detects_a_genuine_conflict():
    x = np.array([0.0, 0.0, 5.0])
    y = np.array([0.0, 0.0, 5.0])
    z = np.array([10.0, 20.0, 30.0])
    out = coordinate_label_ambiguity(x, y, z)
    assert out["coordinate_groups_with_multiple_properties"] == 1
    assert out["groups_with_differing_label"] == 1
    assert out["max_within_group_label_range"] == pytest.approx(10.0)
    assert out["irreducible_rmse"] == pytest.approx(np.sqrt(50.0 / 3.0))


def test_label_ambiguity_reports_zero_floor_when_duplicates_agree():
    x = np.array([0.0, 0.0, 5.0])
    y = np.array([0.0, 0.0, 5.0])
    z = np.array([10.0, 10.0, 30.0])
    out = coordinate_label_ambiguity(x, y, z)
    assert out["groups_with_differing_label"] == 0
    assert out["irreducible_rmse"] == pytest.approx(0.0)


def test_seed_stability_summary_arithmetic():
    records = [
        {"seed": 1, "rmse": 10.0, "r2": 0.5},
        {"seed": 2, "rmse": 20.0, "r2": 0.1},
    ]
    out = summarise_seed_stability(records)
    assert out["n_seeds"] == 2
    assert out["rmse"]["mean"] == pytest.approx(15.0)
    assert out["rmse"]["range"] == pytest.approx(10.0)
    assert out["rmse"]["std"] == pytest.approx(np.std([10.0, 20.0], ddof=1))
    assert out["r2"]["min"] == pytest.approx(0.1)


def test_seed_stability_rejects_an_empty_record_set():
    with pytest.raises(ValueError):
        summarise_seed_stability([])