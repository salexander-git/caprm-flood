"""Tests for caprm.surrogate_data.

These build a small partition with the REAL C1 code path — ``build_kfold``,
``dropped_mask_codes``, ``random_split`` — write it out in the same schema the
C1 CLI writes, and then read it back through the consumer. A fixture that
hand-wrote the split file would test the reader against a convention rather
than against the producer, and the two could drift without either test failing.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from caprm.spatial_kfold import KFoldConfig, build_kfold, dropped_mask_codes
from caprm.split_gate import random_split
from caprm.surrogate_data import (
    PARTITION_BLOCKED,
    PARTITION_RANDOM,
    FoldPredictions,
    PartitionVerificationError,
    blocked_splits,
    declared_floor,
    iter_splits,
    load_partition_inputs,
    random_control_split,
    sha256_file,
)

SEED = 20260722
N_FOLDS = 3
BLOCK_M = 1000.0
BUFFER_M = 120.0


def _write_fixture(tmp_path, corrupt: str | None = None):
    """A 3 x 3 block county, built and persisted exactly as the C1 CLI does."""
    step = 40.0
    grid = np.arange(0.0, 3000.0, step)
    xs, ys = np.meshgrid(grid, grid)
    x = xs.ravel() + 256000.0
    y = ys.ravel() + 4757000.0
    n = len(x)
    property_id = np.array([f"{i:020d}" for i in range(n)], dtype=object)
    rng = np.random.default_rng(0)
    target = 40.0 + 15.0 * np.sin(x / 700.0) + 5.0 * np.cos(y / 900.0) + rng.normal(0, 0.5, n)

    dataset = tmp_path / "supervised_dataset.csv"
    pd.DataFrame(
        {"property_id": property_id, "x": x, "y": y, "exposure_index_0_100": target}
    ).to_csv(dataset, index=False, lineterminator="\n", float_format="%.17g")

    config = KFoldConfig(
        block_size_m=BLOCK_M, buffer_m=BUFFER_M, n_folds=N_FOLDS, seed=SEED
    )
    result = build_kfold(property_id, x, y, target, config)
    codes = dropped_mask_codes(result.roles, N_FOLDS)

    split_dir = tmp_path / "splits"
    split_dir.mkdir()
    split_path = split_dir / f"spatial_kfold_countywide_seed{SEED}.csv"
    order = np.arange(n)
    if corrupt == "misaligned":
        order = np.roll(order, 1)
    pd.DataFrame(
        {
            "property_id": property_id[order],
            "block_i": result.block_i[order],
            "block_j": result.block_j[order],
            "block_id": [f"{int(i)}_{int(j)}" for i, j in zip(result.block_i[order], result.block_j[order])],
            "fold": result.fold[order],
            "dropped_mask": codes[order],
        }
    ).to_csv(split_path, index=False, lineterminator="\n")

    random_labels = random_split(n, seed=SEED)
    random_path = split_dir / "random_control_countywide.csv"
    pd.DataFrame({"property_id": property_id, "split": random_labels}).to_csv(
        random_path, index=False, lineterminator="\n"
    )

    manifest = {
        "task": "C1_blocked_kfold_partition",
        "schema_version": "c1_kfold_v1",
        "crs": "EPSG:26918",
        "operating_point": {
            "buffer_m": BUFFER_M,
            "block_size_m": BLOCK_M,
            "n_folds": N_FOLDS,
            "seeds": [SEED, SEED + 1],
            "isolate_test_from_val": True,
        },
        "inputs": {
            "dataset": str(dataset),
            "dataset_sha256": sha256_file(dataset),
            "rows": n,
        },
        "per_seed": [
            {
                "seed": SEED,
                "split_path": f"outputs\\splits\\{split_path.name}",
                "split_sha256": sha256_file(split_path),
                "deterministic_on_rerun": True,
                "stats": result.stats,
            }
        ],
        "controls": {
            "random": {
                "expected": "FAIL",
                "failed_as_expected": True,
                "baseline": {"rmse": 4.93, "r2": 0.86, "n_holdout": 100},
                "split_path": str(random_path),
                "split_sha256": sha256_file(random_path),
            }
        },
        "acceptance": {"blocked_gate_passed_every_fold_every_seed": True},
    }
    if corrupt == "schema":
        manifest["schema_version"] = "c1_kfold_v0"
    if corrupt == "gate":
        manifest["acceptance"]["blocked_gate_passed_every_fold_every_seed"] = False
    if corrupt == "digest":
        manifest["inputs"]["dataset_sha256"] = "0" * 64

    manifest_path = tmp_path / "c1_kfold_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dataset, manifest_path, split_dir, random_path, n


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------


def test_inputs_load_and_verify_against_the_manifest(tmp_path):
    dataset, manifest, _, _, n = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    assert inputs.n_properties == n
    assert inputs.seeds == [SEED, SEED + 1]
    assert inputs.n_folds == N_FOLDS
    assert inputs.buffer_m == BUFFER_M
    assert inputs.verification["dataset_sha256_matches_manifest"] is True


def test_a_modified_dataset_is_refused(tmp_path):
    dataset, manifest, _, _, _ = _write_fixture(tmp_path)
    with dataset.open("a", encoding="utf-8") as handle:
        handle.write("99999999999999999999,256000,4757000,50\n")
    with pytest.raises(PartitionVerificationError):
        load_partition_inputs(dataset, manifest)


def test_a_wrong_manifest_schema_is_refused(tmp_path):
    dataset, manifest, _, _, _ = _write_fixture(tmp_path, corrupt="schema")
    with pytest.raises(PartitionVerificationError):
        load_partition_inputs(dataset, manifest)


def test_a_partition_whose_gate_did_not_pass_is_refused(tmp_path):
    dataset, manifest, _, _, _ = _write_fixture(tmp_path, corrupt="gate")
    with pytest.raises(PartitionVerificationError):
        load_partition_inputs(dataset, manifest)


def test_a_split_file_not_aligned_to_the_dataset_is_refused(tmp_path):
    dataset, manifest, split_dir, _, _ = _write_fixture(tmp_path, corrupt="misaligned")
    inputs = load_partition_inputs(dataset, manifest)
    with pytest.raises(PartitionVerificationError, match="row for"):
        blocked_splits(inputs, SEED, split_dir)


def test_a_split_file_that_does_not_match_its_digest_is_refused(tmp_path):
    dataset, manifest, split_dir, _, _ = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    path = split_dir / f"spatial_kfold_countywide_seed{SEED}.csv"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("\n", "\n", 1) + "\n", encoding="utf-8")
    with pytest.raises(PartitionVerificationError, match="does not match the manifest"):
        blocked_splits(inputs, SEED, split_dir)


def test_an_unrecorded_seed_is_refused(tmp_path):
    dataset, manifest, split_dir, _, _ = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    with pytest.raises(PartitionVerificationError, match="not one of the recorded seeds"):
        blocked_splits(inputs, 12345, split_dir)


# ---------------------------------------------------------------------------
# the splits themselves
# ---------------------------------------------------------------------------


def test_blocked_splits_are_disjoint_and_cover_the_partition(tmp_path):
    dataset, manifest, split_dir, _, n = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    splits = blocked_splits(inputs, SEED, split_dir)
    assert len(splits) == N_FOLDS

    tested = []
    for split in splits:
        counts = split.counts()
        assert counts["train"] > 0 and counts["val"] > 0 and counts["test"] > 0
        assert sum(counts.values()) <= n  # the difference is the dropped buffer
        assert np.intersect1d(split.train_index, split.test_index).size == 0
        assert np.intersect1d(split.train_index, split.val_index).size == 0
        assert np.intersect1d(split.val_index, split.test_index).size == 0
        tested.append(split.test_index)
    union = np.concatenate(tested)
    # every property is test in at most one fold: the property build_kfold
    # enforces and the aggregate depends on
    assert union.size == np.unique(union).size


def test_split_labels_identify_partition_seed_and_fold(tmp_path):
    dataset, manifest, split_dir, _, _ = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    labels = [s.label for s in blocked_splits(inputs, SEED, split_dir)]
    assert labels[0] == f"{PARTITION_BLOCKED}_seed{SEED}_fold0"
    assert len(set(labels)) == N_FOLDS


def test_random_control_regenerates_the_persisted_file(tmp_path):
    dataset, manifest, _, random_path, n = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    split = random_control_split(inputs, SEED, random_path)
    assert split.partition == PARTITION_RANDOM
    assert split.train_index.size + split.val_index.size + split.test_index.size == n
    assert split.train_index.size > split.test_index.size


def test_a_redrawn_random_control_at_another_seed_is_not_compared_to_the_file(tmp_path):
    """C1 persisted the control at one seed; the others are redraws, not defects."""
    dataset, manifest, _, random_path, n = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    redrawn = random_control_split(inputs, SEED + 1, random_path)
    persisted = random_control_split(inputs, SEED, random_path)
    assert redrawn.train_index.size + redrawn.val_index.size + redrawn.test_index.size == n
    assert not np.array_equal(redrawn.test_index, persisted.test_index)


def test_a_random_control_that_does_not_reproduce_is_refused(tmp_path):
    dataset, manifest, _, random_path, _ = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    frame = pd.read_csv(random_path, dtype={"property_id": str})
    frame.loc[0, "split"] = "test" if frame.loc[0, "split"] != "test" else "train"
    frame.to_csv(random_path, index=False, lineterminator="\n")
    with pytest.raises(PartitionVerificationError, match="does not reproduce"):
        random_control_split(inputs, SEED, random_path)


def test_iter_splits_serves_both_partitions_and_rejects_unknown_ones(tmp_path):
    dataset, manifest, split_dir, random_path, _ = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    assert len(iter_splits(inputs, PARTITION_BLOCKED, SEED, split_dir)) == N_FOLDS
    assert len(iter_splits(inputs, PARTITION_RANDOM, SEED, split_dir, random_path)) == 1
    with pytest.raises(ValueError):
        iter_splits(inputs, "something_else", SEED, split_dir)


# ---------------------------------------------------------------------------
# the floor and the aggregate
# ---------------------------------------------------------------------------


def test_declared_floor_is_read_from_the_manifest(tmp_path):
    dataset, manifest, _, _, _ = _write_fixture(tmp_path)
    inputs = load_partition_inputs(dataset, manifest)
    floor = declared_floor(inputs)
    recorded = inputs.manifest["per_seed"][0]["stats"]["aggregate_baseline"]
    assert floor["blocked_kfold"]["rmse_min"] == pytest.approx(recorded["rmse"])
    assert floor["blocked_kfold"]["rmse_max"] == pytest.approx(recorded["rmse"])
    assert floor["random_control"]["rmse"] == pytest.approx(4.93)


def test_fold_predictions_refuse_to_test_a_property_twice():
    predictions = FoldPredictions.empty(10)
    predictions.add(np.array([0, 1, 2]), np.array([1.0, 2.0, 3.0]))
    predictions.add(np.array([3, 4]), np.array([4.0, 5.0]))
    assert predictions.coverage_fraction() == pytest.approx(0.5)
    with pytest.raises(RuntimeError, match="more than one fold"):
        predictions.add(np.array([4, 5]), np.array([9.0, 9.0]))


def test_fold_predictions_reject_mismatched_lengths():
    predictions = FoldPredictions.empty(4)
    with pytest.raises(ValueError):
        predictions.add(np.array([0, 1]), np.array([1.0]))
