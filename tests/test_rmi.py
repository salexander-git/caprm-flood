"""Unit tests for the two-stage recursive model index (Milestone 4 B4)."""

from __future__ import annotations

import dataclasses
import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from caprm import rmi


def digest(keys: np.ndarray) -> str:
    return hashlib.sha256(keys.tobytes()).hexdigest()


def clustered_keys(seed: int, clusters: int, per_cluster: int,
                   width_bits: int) -> np.ndarray:
    generator = np.random.default_rng(seed)
    centres = generator.integers(0, 2**62, size=clusters, dtype=np.uint64)
    blocks = [
        centre
        + generator.integers(0, 2**width_bits, size=per_cluster, dtype=np.uint64)
        for centre in centres
    ]
    return np.sort(np.concatenate(blocks).astype(np.uint64))


def uniform_keys(seed: int, count: int) -> np.ndarray:
    generator = np.random.default_rng(seed)
    return np.sort(generator.integers(0, 2**64, size=count, dtype=np.uint64))


def with_duplicate_runs(keys: np.ndarray) -> np.ndarray:
    keys = keys.copy()
    keys[10:15] = keys[10]
    keys[500:502] = keys[500]
    keys[-3:] = keys[-3]
    return np.sort(keys)


# --------------------------------------------------------------------------
# Targets and the duplicate-key convention
# --------------------------------------------------------------------------
def test_targets_match_searchsorted_lower_bound():
    keys = with_duplicate_runs(uniform_keys(1, 5000))
    targets = rmi.lower_bound_targets(keys)
    expected = np.searchsorted(keys, keys, side="left")
    assert np.array_equal(targets, expected)


def test_targets_are_the_first_position_of_each_run():
    keys = np.array([5, 5, 5, 9, 9, 12], dtype=np.uint64)
    assert rmi.lower_bound_targets(keys).tolist() == [0, 0, 0, 3, 3, 5]


def test_targets_on_a_fully_duplicated_array():
    keys = np.full(64, 7, dtype=np.uint64)
    assert np.all(rmi.lower_bound_targets(keys) == 0)


# --------------------------------------------------------------------------
# Key array loading
# --------------------------------------------------------------------------
def test_load_key_array_round_trips(tmp_path: Path):
    keys = uniform_keys(2, 1000)
    path = tmp_path / "keys.bin"
    path.write_bytes(keys.tobytes())
    loaded, sha = rmi.load_key_array(path)
    assert np.array_equal(loaded, keys)
    assert sha == digest(keys)


def test_load_key_array_rejects_unsorted(tmp_path: Path):
    keys = np.array([3, 1, 2], dtype=np.uint64)
    path = tmp_path / "unsorted.bin"
    path.write_bytes(keys.tobytes())
    with pytest.raises(ValueError, match="not sorted"):
        rmi.load_key_array(path)


def test_load_key_array_rejects_partial_key(tmp_path: Path):
    path = tmp_path / "ragged.bin"
    path.write_bytes(b"\x00" * 12)
    with pytest.raises(ValueError, match="whole number"):
        rmi.load_key_array(path)


# --------------------------------------------------------------------------
# Normalization and the float contract
# --------------------------------------------------------------------------
def test_normalize_matches_the_documented_expression():
    keys = uniform_keys(3, 100)
    key_min, key_max = int(keys[0]), int(keys[-1])
    expected = (
        keys.astype(np.float64) - np.float64(np.uint64(key_min))
    ) * (
        np.float64(1.0)
        / (np.float64(np.uint64(key_max)) - np.float64(np.uint64(key_min)))
    )
    assert np.array_equal(rmi.normalize_keys(keys, key_min, key_max), expected)


def test_normalize_is_monotone_in_the_key():
    """The domain-bound argument rests on this, so it is tested, not assumed."""
    keys = uniform_keys(4, 20000)
    x = rmi.normalize_keys(keys, int(keys[0]), int(keys[-1]))
    assert np.all(np.diff(x) >= 0.0)


def test_normalize_rejects_a_degenerate_span():
    keys = np.full(8, 11, dtype=np.uint64)
    with pytest.raises(ValueError, match="not positive"):
        rmi.normalize_keys(keys, 11, 11)


# --------------------------------------------------------------------------
# ceil_log2
# --------------------------------------------------------------------------
def test_ceil_log2_matches_math_for_small_values():
    values = np.arange(1, 4097, dtype=np.int64)
    expected = np.array([math.ceil(math.log2(v)) for v in values])
    assert np.array_equal(rmi.ceil_log2(values), expected)


def test_ceil_log2_is_exact_at_powers_of_two():
    values = np.array([2**k for k in range(0, 40)], dtype=np.int64)
    assert np.array_equal(rmi.ceil_log2(values), np.arange(0, 40))


def test_ceil_log2_rejects_zero():
    with pytest.raises(ValueError):
        rmi.ceil_log2(np.array([0], dtype=np.int64))


# --------------------------------------------------------------------------
# The stored-key bound — the acceptance criterion
# --------------------------------------------------------------------------
@pytest.mark.parametrize("n_leaves", [1, 4, 64, 1024])
@pytest.mark.parametrize(
    "builder",
    [
        lambda: uniform_keys(5, 4000),
        lambda: with_duplicate_runs(uniform_keys(6, 4000)),
        lambda: clustered_keys(7, 40, 100, 30),
    ],
)
def test_bound_contains_the_true_position_for_every_key(builder, n_leaves):
    keys = builder()
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, n_leaves, digest(keys))
    report = rmi.verify_exhaustive(model, keys, targets)
    assert report["bound_holds_asymmetric"]
    assert report["bound_holds_symmetric"]
    assert report["keys_verified"] == keys.size


def test_bound_holds_after_a_disk_round_trip(tmp_path: Path):
    keys = clustered_keys(8, 60, 80, 32)
    targets = rmi.lower_bound_targets(keys)
    path = tmp_path / "model.bin"
    path.write_bytes(rmi.serialize(rmi.fit_rmi(keys, targets, 256, digest(keys))))
    reloaded = rmi.deserialize(path.read_bytes())
    assert rmi.verify_exhaustive(reloaded, keys, targets)["bound_holds_symmetric"]


def test_leaf_assignment_is_monotone_along_the_sorted_array():
    keys = clustered_keys(9, 50, 60, 30)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 512, digest(keys))
    leaf = model.route(rmi.normalize_keys(keys, model.key_min, model.key_max))
    assert np.all(np.diff(leaf) >= 0)


def test_empty_leaves_are_filled_with_their_boundary_rank():
    keys = clustered_keys(10, 8, 200, 26)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 4096, digest(keys))
    x = rmi.normalize_keys(keys, model.key_min, model.key_max)
    occupied = np.bincount(model.route(x), minlength=model.n_leaves) > 0
    empty = ~occupied
    assert empty.any()
    assert np.all(model.leaf_b[empty] == 0.0)
    assert np.all(model.leaf_a[empty] >= 0.0)
    assert np.all(model.leaf_a[empty] <= float(keys.size))
    assert np.all(np.diff(model.leaf_a[empty]) >= 0.0)


def test_fitting_is_deterministic():
    keys = with_duplicate_runs(uniform_keys(11, 3000))
    targets = rmi.lower_bound_targets(keys)
    first = rmi.serialize(rmi.fit_rmi(keys, targets, 128, digest(keys)))
    second = rmi.serialize(rmi.fit_rmi(keys, targets, 128, digest(keys)))
    assert first == second


def test_a_single_leaf_is_a_plain_linear_regression():
    keys = uniform_keys(12, 2000)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 1, digest(keys))
    x = rmi.normalize_keys(keys, model.key_min, model.key_max)
    slope, intercept = np.polyfit(x, targets.astype(np.float64), 1)
    assert model.leaf_b[0] == pytest.approx(slope, rel=1e-9)
    assert model.leaf_a[0] == pytest.approx(intercept, rel=1e-9, abs=1e-6)


def test_more_leaves_never_worsen_the_mean_absolute_error_on_uniform_keys():
    keys = uniform_keys(13, 20000)
    targets = rmi.lower_bound_targets(keys)
    errors = []
    for n_leaves in (16, 256, 4096):
        model = rmi.fit_rmi(keys, targets, n_leaves, digest(keys))
        report = rmi.verify_exhaustive(model, keys, targets)
        errors.append(report["per_key_absolute_error"]["mean"])
    assert errors[1] <= errors[0]
    assert errors[2] <= errors[1]


def test_window_orientation_survives_a_biased_model():
    """A deliberately shifted model must still bracket the true position.

    ``error = predicted - true``, so the window is
    ``[predicted - err_max, predicted - err_min]``. Getting that sign backwards
    passes on symmetric error and fails here.
    """
    keys = uniform_keys(14, 2000)
    targets = rmi.lower_bound_targets(keys)
    fitted = rmi.fit_rmi(keys, targets, 8, digest(keys))
    shifted = dataclasses.replace(fitted, leaf_a=fitted.leaf_a + 37.0)
    remeasured = rmi.with_measured_bounds(shifted, keys, targets)
    assert rmi.verify_exhaustive(remeasured, keys, targets)[
        "bound_holds_asymmetric"
    ]

    # The model now over-predicts nearly everywhere, so the window is strongly
    # one-sided and the INVERTED window must fail. Without this the sign error
    # is invisible: on a symmetric error distribution both orientations pass.
    x = rmi.normalize_keys(keys, remeasured.key_min, remeasured.key_max)
    leaf, position = remeasured.predict(x)
    inverted_low = position + remeasured.err_min[leaf].astype(np.int64)
    inverted_high = position + remeasured.err_max[leaf].astype(np.int64)
    assert not np.all((targets >= inverted_low) & (targets <= inverted_high))


# --------------------------------------------------------------------------
# The domain (gap) bound — measured, then re-tested by brute force
# --------------------------------------------------------------------------
def small_domain_keys() -> np.ndarray:
    """Keys confined to a range small enough to enumerate every query key."""
    generator = np.random.default_rng(101)
    keys = np.sort(
        generator.integers(50, 3950, size=400, dtype=np.uint64)
    ).astype(np.uint64)
    keys[7:11] = keys[7]
    keys[300:302] = keys[300]
    return np.sort(keys)


@pytest.mark.parametrize("n_leaves", [1, 8, 64, 512])
def test_domain_bound_holds_for_every_key_in_a_small_domain(n_leaves):
    """Brute force over the entire query domain, not just the candidate set.

    This is the test that actually validates ``domain_candidate_keys``. If the
    candidate-set argument missed a breakpoint class, some key in this sweep
    would fall outside its leaf's recorded window.
    """
    keys = small_domain_keys()
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, n_leaves, digest(keys))

    every = np.arange(0, 4096, dtype=np.uint64)
    leaf, position = model.predict_keys(every)
    rank = np.searchsorted(keys, every, side="left")
    error = position - rank
    low = model.gap_err_min[leaf].astype(np.int64)
    high = model.gap_err_max[leaf].astype(np.int64)
    assert np.all((error >= low) & (error <= high))


def test_domain_bound_contains_the_stored_key_bound():
    keys = clustered_keys(15, 40, 120, 30)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 512, digest(keys))
    occupied = (
        np.bincount(
            model.route(
                rmi.normalize_keys(keys, model.key_min, model.key_max)
            ),
            minlength=model.n_leaves,
        )
        > 0
    )
    assert np.all(model.gap_err_min[occupied] <= model.err_min[occupied])
    assert np.all(model.gap_err_max[occupied] >= model.err_max[occupied])


def test_domain_bound_is_wider_than_the_stored_bound_somewhere():
    """If the two were always equal the gap bound would be doing nothing."""
    keys = clustered_keys(16, 30, 150, 30)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 256, digest(keys))
    widened = (model.gap_err_max - model.err_max) > 0
    narrowed = (model.gap_err_min - model.err_min) < 0
    assert bool(widened.any() or narrowed.any())


def test_spot_check_passes_on_random_keys():
    keys = clustered_keys(17, 50, 100, 32)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 1024, digest(keys))
    result = rmi.spot_check_gap_bound(model, keys, 200_000, 20260728)
    assert result["holds"]
    assert result["violations"] == 0


def test_spot_check_catches_a_deliberately_understated_bound():
    keys = clustered_keys(18, 40, 100, 30)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 256, digest(keys))
    crippled = dataclasses.replace(
        model,
        gap_err_min=np.zeros(model.n_leaves, np.int32),
        gap_err_max=np.zeros(model.n_leaves, np.int32),
    )
    assert not rmi.spot_check_gap_bound(crippled, keys, 50_000, 1)["holds"]


def test_leaf_boundary_keys_are_the_first_key_of_each_leaf():
    keys = clustered_keys(19, 30, 100, 30)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 64, digest(keys))
    boundaries = rmi.leaf_boundary_keys(model)
    assert boundaries.size == model.n_leaves - 1
    assert np.all(np.diff(boundaries.astype(object)) >= 0)
    at = model.route(
        rmi.normalize_keys(boundaries, model.key_min, model.key_max)
    )
    before = model.route(
        rmi.normalize_keys(
            boundaries[boundaries > 0] - np.uint64(1),
            model.key_min,
            model.key_max,
        )
    )
    assert np.all(at >= np.arange(1, model.n_leaves))
    assert np.all(before < np.arange(1, model.n_leaves)[boundaries > 0])


# --------------------------------------------------------------------------
# Probe records
# --------------------------------------------------------------------------
def test_probe_records_round_trip_through_hex():
    keys = uniform_keys(20, 5000)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 64, digest(keys))
    for record in rmi.probe_records(model, keys):
        key = np.array([record["key"]], dtype=np.uint64)
        x = rmi.normalize_keys(key, model.key_min, model.key_max)
        assert float(x[0]).hex() == record["x_hex"]
        leaf, position = model.predict(x)
        assert int(leaf[0]) == record["leaf"]
        assert int(position[0]) == record["predicted_position"]


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------
def test_serialization_round_trip_is_exact():
    keys = clustered_keys(21, 30, 100, 28)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 64, digest(keys))
    reloaded = rmi.deserialize(rmi.serialize(model))
    assert reloaded.n_keys == model.n_keys
    assert reloaded.key_min == model.key_min
    assert reloaded.key_max == model.key_max
    assert reloaded.root_a == model.root_a
    assert reloaded.root_b == model.root_b
    assert reloaded.keys_sha256 == model.keys_sha256
    for field in ("leaf_a", "leaf_b", "err_min", "err_max",
                  "gap_err_min", "gap_err_max"):
        assert np.array_equal(getattr(reloaded, field), getattr(model, field))


def test_serialized_size_matches_the_declared_layout():
    keys = uniform_keys(22, 500)
    targets = rmi.lower_bound_targets(keys)
    model = rmi.fit_rmi(keys, targets, 37, digest(keys))
    payload = rmi.serialize(model)
    assert len(payload) == rmi.HEADER_BYTES + rmi.LEAF_STRIDE_BYTES * 37
    assert len(payload) == model.size_bytes
    assert payload[:8] == rmi.MODEL_MAGIC
    assert rmi.LEAF_DTYPE.itemsize == rmi.LEAF_STRIDE_BYTES


def test_deserialize_rejects_a_bad_magic():
    keys = uniform_keys(23, 200)
    targets = rmi.lower_bound_targets(keys)
    payload = bytearray(rmi.serialize(rmi.fit_rmi(keys, targets, 4, digest(keys))))
    payload[:8] = b"NOTAMODL"
    with pytest.raises(ValueError, match="Bad magic"):
        rmi.deserialize(bytes(payload))


def test_deserialize_rejects_a_truncated_file():
    keys = uniform_keys(24, 200)
    targets = rmi.lower_bound_targets(keys)
    payload = rmi.serialize(rmi.fit_rmi(keys, targets, 8, digest(keys)))
    with pytest.raises(ValueError, match="bytes; header implies"):
        rmi.deserialize(payload[:-8])


# --------------------------------------------------------------------------
# Equi-depth diagnostic
# --------------------------------------------------------------------------
def test_equidepth_reference_uses_every_leaf():
    keys = clustered_keys(25, 40, 100, 30)
    targets = rmi.lower_bound_targets(keys)
    reference = rmi.equidepth_reference(keys, targets, 256)
    assert reference["leaves_occupied"] == 256
    assert reference["max_error"] >= 0


def test_equidepth_reference_beats_the_linear_root_on_clustered_keys():
    """The diagnostic exists to separate routing cost from leaf-fit cost."""
    keys = clustered_keys(26, 30, 300, 28)
    targets = rmi.lower_bound_targets(keys)
    fitted = rmi.verify_exhaustive(
        rmi.fit_rmi(keys, targets, 1024, digest(keys)), keys, targets
    )
    reference = rmi.equidepth_reference(keys, targets, 1024)
    assert reference["max_error"] <= fitted["per_model_max_error"]["max"]