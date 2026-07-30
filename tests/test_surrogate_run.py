"""Tests for caprm.surrogate_run.

The comparison logic is what these are mostly about. It decides whether C2 gets
to say it beat the floor, and the two statistics it reports — beating the floor
at every seed, and the ranges being disjoint — must not be allowed to collapse
into each other, because Nucleus 18.32 accepts only the second.
"""

from __future__ import annotations

import numpy as np
import pytest

from caprm.surrogate import CoordinateNormalizer, FourierConfig, MLPConfig, TrainConfig
from caprm.surrogate_data import EvaluationSplit, PartitionInputs
from caprm.surrogate_run import (
    RunConfig,
    compare_to_floor,
    fit_split,
    memorization_gap,
    run_seed,
    summarise_partition,
)

COUNTY = dict(x_min=256333.34038562785, x_max=307184.1620882016,
              y_min=4757539.408309271, y_max=4805761.972407171)
FAST = RunConfig(
    fourier=FourierConfig(n_features=8, scale=1.0),
    mlp=MLPConfig(hidden=(16, 16), dtype="float32"),
    train=TrainConfig(max_epochs=25, patience=10, batch_size=256, min_epochs=5),
)


def _inputs(n: int = 900, seed: int = 3) -> PartitionInputs:
    rng = np.random.default_rng(seed)
    x = rng.uniform(COUNTY["x_min"], COUNTY["x_max"], size=n)
    y = rng.uniform(COUNTY["y_min"], COUNTY["y_max"], size=n)
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    coords = normalizer.transform(x, y)
    target = 45.0 + 18.0 * np.sin(1.5 * coords[:, 0]) + 8.0 * coords[:, 1]
    return PartitionInputs(
        dataset_path="memory",  # type: ignore[arg-type]
        manifest_path="memory",  # type: ignore[arg-type]
        manifest={"operating_point": {"seeds": [1], "n_folds": 3, "buffer_m": 100.0}},
        property_id=np.array([f"{i:020d}" for i in range(n)], dtype=object),
        x=x,
        y=y,
        target=target,
    )


def _splits(n: int, n_folds: int = 3, seed: int = 1) -> list[EvaluationSplit]:
    rng = np.random.default_rng(0)
    order = rng.permutation(n)
    chunks = np.array_split(order, n_folds)
    splits = []
    for k in range(n_folds):
        test = np.sort(chunks[k])
        val = np.sort(chunks[(k + 1) % n_folds])
        train = np.sort(np.setdiff1d(np.arange(n), np.union1d(test, val)))
        splits.append(
            EvaluationSplit("blocked_kfold", seed, k, train, val, test)
        )
    return splits


# ---------------------------------------------------------------------------
# fitting
# ---------------------------------------------------------------------------


def test_fit_split_records_everything_the_fold_report_needs():
    inputs = _inputs()
    split = _splits(inputs.n_properties)[0]
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    model, predicted, record = fit_split(inputs, split, normalizer, FAST)
    assert predicted.shape == split.test_index.shape
    assert record["label"] == split.label
    assert record["counts"] == split.counts()
    assert record["test"]["n"] == split.test_index.size
    assert record["weights_sha256"] == model.weights_sha256()
    assert 0 <= record["best_epoch"] < record["epochs_run"]


def test_fit_split_seeds_differ_between_folds_and_repeat_within_one():
    inputs = _inputs()
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    splits = _splits(inputs.n_properties)
    first = fit_split(inputs, splits[0], normalizer, FAST)[2]
    again = fit_split(inputs, splits[0], normalizer, FAST)[2]
    other = fit_split(inputs, splits[1], normalizer, FAST)[2]
    assert first["weights_sha256"] == again["weights_sha256"]
    assert first["seeds"]["init_seed"] != other["seeds"]["init_seed"]


def test_fit_split_refuses_a_fold_with_no_surviving_test_rows():
    inputs = _inputs(n=300)
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    empty = EvaluationSplit(
        "blocked_kfold", 1, 0,
        np.arange(200), np.arange(200, 300), np.array([], dtype=np.int64),
    )
    with pytest.raises(ValueError, match="no surviving test rows"):
        fit_split(inputs, empty, normalizer, FAST)


# ---------------------------------------------------------------------------
# a seed
# ---------------------------------------------------------------------------


def test_run_seed_aggregates_over_the_union_of_folds(tmp_path):
    inputs = _inputs()
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    splits = _splits(inputs.n_properties)
    result = run_seed(inputs, splits, normalizer, FAST, model_dir=tmp_path)

    assert result["n_folds_run"] == 3
    assert result["aggregate"]["n"] == inputs.n_properties  # this fixture covers all
    assert result["test_coverage_fraction"] == pytest.approx(1.0)
    assert len(result["seed_weights_sha256"]) == 64
    # every fold model was written and reloaded to the same checksum
    for record in result["folds"]:
        assert record["weights_sha256_after_reload"] == record["weights_sha256"]
        assert (tmp_path / f"c2_surrogate_{record['label']}.npz").exists()


def test_run_seed_aggregate_is_not_an_average_of_fold_rmses():
    """The aggregate is computed over pooled rows, which is the floor's own units."""
    inputs = _inputs()
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    splits = _splits(inputs.n_properties)
    result = run_seed(inputs, splits, normalizer, FAST)
    pooled = result["aggregate"]["rmse"]
    per_fold = [r["test"]["rmse"] for r in result["folds"]]
    weights = [r["test"]["n"] for r in result["folds"]]
    expected = float(
        np.sqrt(np.average([v**2 for v in per_fold], weights=weights))
    )
    assert pooled == pytest.approx(expected, rel=1e-9)
    # the unweighted mean is a different number, and is the one not to report
    assert pooled != pytest.approx(float(np.mean(per_fold)), rel=1e-12)


def test_run_seed_rejects_an_empty_split_list():
    inputs = _inputs(n=100)
    with pytest.raises(ValueError):
        run_seed(inputs, [], CoordinateNormalizer.from_bounds(**COUNTY), FAST)


# ---------------------------------------------------------------------------
# summaries and comparisons
# ---------------------------------------------------------------------------


def _seed_result(seed: int, rmse: float, r2: float, constant: float = 13.2) -> dict:
    return {
        "partition": "blocked_kfold",
        "seed": seed,
        "aggregate": {"rmse": rmse, "r2": r2, "n": 1000},
        "constant_aggregate": {"rmse": constant, "r2": -0.02, "n": 1000},
        "test_coverage_fraction": 0.4,
        "seed_weights_sha256": "0" * 64,
    }


FLOOR = {
    "source": "outputs/validation/c1_kfold_manifest.json",
    "predictor": "nearest training neighbour",
    "blocked_kfold": {
        "per_seed": {
            "20260722": {"rmse": 15.386, "r2": -0.3646, "n": 89344},
            "20260723": {"rmse": 15.429, "r2": -0.4343, "n": 100257},
        },
        "rmse_min": 15.386,
        "rmse_max": 15.429,
        "r2_min": -0.4343,
        "r2_max": -0.3646,
    },
    "random_control": {"rmse": 4.9329, "r2": 0.8586, "n": 40205},
}


def test_summarise_partition_reports_a_range_not_a_point():
    summary = summarise_partition(
        [_seed_result(20260722, 12.0, 0.1), _seed_result(20260723, 14.0, -0.1)]
    )
    assert summary["n_seeds"] == 2
    assert summary["rmse_min"] == 12.0
    assert summary["rmse_max"] == 14.0
    assert summary["rmse_range"] == pytest.approx(2.0)
    assert set(summary["per_seed"]) == {"20260722", "20260723"}


def test_summarise_partition_rejects_an_empty_result_set():
    with pytest.raises(ValueError):
        summarise_partition([])


def test_disjoint_ranges_are_required_to_claim_the_floor_is_beaten():
    summary = summarise_partition(
        [_seed_result(20260722, 12.0, 0.1), _seed_result(20260723, 13.0, 0.0)]
    )
    verdict = compare_to_floor(summary, FLOOR)
    assert verdict["beats_floor_per_seed"] is True
    assert verdict["ranges_are_disjoint"] is True
    assert "beats the declared floor" in verdict["verdict"]


def test_beating_the_floor_at_every_seed_is_not_enough_when_the_ranges_overlap():
    """The distinction Nucleus 18.32 exists to enforce, as a test."""
    summary = summarise_partition(
        [_seed_result(20260722, 15.30, 0.0), _seed_result(20260723, 15.40, 0.0)]
    )
    verdict = compare_to_floor(summary, FLOOR)
    assert verdict["beats_floor_per_seed"] is True   # 15.30 < 15.386, 15.40 < 15.429
    assert verdict["ranges_are_disjoint"] is False   # 15.40 > 15.386
    assert "does not beat the declared floor as a range" in verdict["verdict"]


def test_a_surrogate_worse_than_the_floor_is_reported_as_such():
    summary = summarise_partition(
        [_seed_result(20260722, 18.0, -0.9), _seed_result(20260723, 19.0, -1.0)]
    )
    verdict = compare_to_floor(summary, FLOOR)
    assert verdict["beats_floor_per_seed"] is False
    assert verdict["ranges_are_disjoint"] is False
    assert verdict["verdict"] == "does not beat the declared floor"


def test_run_seed_scores_the_constant_rung_on_the_identical_rows():
    inputs = _inputs()
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    splits = _splits(inputs.n_properties)
    result = run_seed(inputs, splits, normalizer, FAST)
    assert result["constant_aggregate"]["n"] == result["aggregate"]["n"]
    # a constant predictor cannot explain variance, so its R^2 is at or below 0
    assert result["constant_aggregate"]["r2"] <= 1e-9
    # every fold recorded the training mean it predicted
    assert all("train_mean" in record for record in result["folds"])


def test_summarise_partition_can_reduce_either_rung():
    results = [
        _seed_result(20260722, 12.0, 0.1, constant=13.1),
        _seed_result(20260723, 14.0, -0.1, constant=13.4),
    ]
    surrogate = summarise_partition(results)
    constant = summarise_partition(results, key="constant_aggregate")
    assert surrogate["rmse_min"] == 12.0
    assert constant["rmse_min"] == 13.1
    assert constant["rmse_max"] == 13.4


def test_the_constant_rung_is_reported_beside_the_floor_it_beats():
    """The measured fact from the C1 manifest, encoded so a run cannot hide it."""
    results = [
        _seed_result(20260722, 12.0, 0.1, constant=13.30),
        _seed_result(20260723, 12.5, 0.05, constant=13.55),
    ]
    verdict = compare_to_floor(
        summarise_partition(results),
        FLOOR,
        summarise_partition(results, key="constant_aggregate"),
    )
    constant_block = verdict["constant_baseline"]
    # 13.55 < 15.386: the constant clears the declared floor as a range
    assert constant_block["constant_beats_declared_floor_as_a_range"] is True
    # 12.5 < 13.30: this surrogate also clears the constant, which is the claim
    # that actually means something
    assert constant_block["surrogate_beats_constant_as_a_range"] is True
    assert verdict["rmse_rungs"]["rung_2_surrogate"] == [12.0, 12.5]


def test_a_surrogate_that_only_beats_the_floor_does_not_beat_the_constant():
    results = [
        _seed_result(20260722, 13.9, -0.1, constant=13.30),
        _seed_result(20260723, 14.0, -0.1, constant=13.55),
    ]
    verdict = compare_to_floor(
        summarise_partition(results),
        FLOOR,
        summarise_partition(results, key="constant_aggregate"),
    )
    assert verdict["ranges_are_disjoint"] is True  # it does beat the floor
    assert verdict["constant_baseline"]["surrogate_beats_constant_as_a_range"] is False


def test_memorization_gap_reports_both_predictors():
    blocked = summarise_partition(
        [_seed_result(20260722, 15.0, -0.3), _seed_result(20260723, 16.0, -0.4)]
    )
    random_control = summarise_partition(
        [_seed_result(20260722, 5.0, 0.85), _seed_result(20260723, 5.2, 0.84)]
    )
    gap = memorization_gap(blocked, random_control, FLOOR)
    assert gap["surrogate"]["r2_gap_min"] == pytest.approx(0.84 - (-0.3))
    assert gap["surrogate"]["rmse_ratio_max"] == pytest.approx(16.0 / 5.0)
    assert gap["nearest_training_neighbour"]["random_r2"] == pytest.approx(0.8586)
