"""Tests for caprm.surrogate.

The gradient test is the one that matters. Everything else in this module
checks plumbing; ``test_analytic_gradient_matches_central_difference`` checks
that the thing being plumbed is the derivative of the loss. It runs in float64
on a deliberately small network, because a central difference in float32 is
dominated by the step size rather than by the quantity it is estimating.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from caprm.surrogate import (
    Adam,
    CoordinateNormalizer,
    FourierConfig,
    MLPConfig,
    TrainConfig,
    backward,
    derived_seed,
    forward,
    fourier_features,
    init_parameters,
    load_model,
    regression_metrics,
    save_model,
    train_surrogate,
)

COUNTY = dict(x_min=256333.34038562785, x_max=307184.1620882016,
              y_min=4757539.408309271, y_max=4805761.972407171)


# ---------------------------------------------------------------------------
# seeds
# ---------------------------------------------------------------------------


def test_derived_seed_is_deterministic_and_namespaced():
    assert derived_seed("a:", 1, 2) == derived_seed("a:", 1, 2)
    assert derived_seed("a:", 1, 2) != derived_seed("b:", 1, 2)
    assert derived_seed("a:", 1, 2) != derived_seed("a:", 2, 1)
    assert 0 <= derived_seed("a:", 1) < 2**63


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------


def test_normalizer_is_isotropic_and_covers_the_box():
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    half_x = (COUNTY["x_max"] - COUNTY["x_min"]) / 2
    half_y = (COUNTY["y_max"] - COUNTY["y_min"]) / 2
    assert normalizer.scale_m == pytest.approx(max(half_x, half_y))

    corners_x = np.array([COUNTY["x_min"], COUNTY["x_max"], COUNTY["x_min"]])
    corners_y = np.array([COUNTY["y_min"], COUNTY["y_max"], COUNTY["y_max"]])
    normalized = normalizer.transform(corners_x, corners_y)
    assert np.abs(normalized).max() <= 1.0 + 1e-12
    # the wider axis reaches +/-1 exactly; the narrower one does not, which is
    # what isotropy costs and is deliberate
    assert normalized[:, 0].max() == pytest.approx(1.0)
    assert normalized[:, 1].max() < 1.0


def test_normalizer_rejects_degenerate_bounds():
    with pytest.raises(ValueError):
        CoordinateNormalizer.from_bounds(x_min=1.0, x_max=1.0, y_min=0.0, y_max=1.0)


def test_normalizer_reads_bounds_from_a_dataset_manifest(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"verification": COUNTY}), encoding="utf-8")
    assert CoordinateNormalizer.from_dataset_manifest(path) == (
        CoordinateNormalizer.from_bounds(**COUNTY)
    )


def test_quantisation_is_millimetres_at_float32_and_negligible_at_float64():
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    at32 = normalizer.quantisation_m(np.float32)
    at64 = normalizer.quantisation_m(np.float64)
    # the declared contract: float32 normalized input resolves position to
    # millimetres, far coarser than the 1e-9 m epsilon discipline and far finer
    # than the 2,125 m separation the error is measured at
    assert 1e-4 < at32 < 1e-1
    assert at64 < 1e-9
    assert at32 > at64


# ---------------------------------------------------------------------------
# fourier features
# ---------------------------------------------------------------------------


def test_fourier_feature_shape_and_determinism():
    config = FourierConfig(n_features=8, scale=4.0, include_raw=True)
    assert config.n_columns == 18
    first = config.draw(seed=5)
    assert first.shape == (2, 8)
    assert np.array_equal(first, config.draw(seed=5))
    assert not np.array_equal(first, config.draw(seed=6))

    coords = np.array([[0.0, 0.0], [0.5, -0.25]])
    features = fourier_features(coords, first, include_raw=True, dtype=np.float64)
    assert features.shape == (2, 18)
    assert np.array_equal(features[:, :2], coords)
    assert np.abs(features[:, 2:]).max() <= 1.0
    # at the origin every cosine is 1 and every sine is 0
    assert np.allclose(features[0, 2:10], 1.0)
    assert np.allclose(features[0, 10:], 0.0)


def test_fourier_features_reject_bad_shapes():
    with pytest.raises(ValueError):
        fourier_features(np.zeros((3,)), np.zeros((2, 2)), include_raw=False)


def test_fourier_scale_converts_to_a_metric_wavelength():
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    config = FourierConfig(n_features=4, scale=12.0)
    assert config.wavelength_m(normalizer) == pytest.approx(normalizer.scale_m / 12.0)
    # the sweep is legible against C1's variogram only if this lands in metres
    assert 1_000.0 < config.wavelength_m(normalizer) < 5_000.0


def test_fourier_config_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        FourierConfig(n_features=0)
    with pytest.raises(ValueError):
        FourierConfig(scale=0.0)


# ---------------------------------------------------------------------------
# the network
# ---------------------------------------------------------------------------


def test_init_parameters_shapes_dtype_and_determinism():
    config = MLPConfig(hidden=(7, 5), dtype="float32")
    parameters = init_parameters(4, config, seed=11)
    assert [w.shape for w, _ in parameters] == [(4, 7), (7, 5), (5, 1)]
    assert all(w.dtype == np.float32 and b.dtype == np.float32 for w, b in parameters)
    assert all(np.array_equal(b, np.zeros_like(b)) for _, b in parameters)
    again = init_parameters(4, config, seed=11)
    assert all(np.array_equal(a, b) for (a, _), (b, _) in zip(parameters, again))


def test_mlp_config_rejects_bad_configuration():
    with pytest.raises(ValueError):
        MLPConfig(hidden=())
    with pytest.raises(ValueError):
        MLPConfig(dtype="float16")


def test_forward_returns_one_value_per_row():
    parameters = init_parameters(3, MLPConfig(hidden=(4,), dtype="float64"), seed=2)
    features = np.random.default_rng(0).normal(size=(6, 3))
    prediction, activations = forward(features, parameters)
    assert prediction.shape == (6,)
    assert len(activations) == 2
    assert np.all(activations[1] >= 0.0)  # ReLU


def test_analytic_gradient_matches_central_difference():
    """The one test that checks calculus rather than plumbing."""
    rng = np.random.default_rng(20260731)
    config = MLPConfig(hidden=(5, 4), dtype="float64")
    parameters = init_parameters(3, config, seed=7)
    features = rng.normal(size=(11, 3))
    target = rng.normal(size=11)

    prediction, activations = forward(features, parameters)
    analytic = backward(activations, parameters, prediction, target)

    def loss() -> float:
        value, _ = forward(features, parameters)
        return float(np.mean((value - target) ** 2))

    step = 1e-6
    for depth, (weight, bias) in enumerate(parameters):
        for array, gradient in ((weight, analytic[depth][0]), (bias, analytic[depth][1])):
            flat = array.reshape(-1)
            flat_gradient = gradient.reshape(-1)
            for position in range(0, flat.size, max(1, flat.size // 4)):
                original = flat[position]
                flat[position] = original + step
                up = loss()
                flat[position] = original - step
                down = loss()
                flat[position] = original
                numerical = (up - down) / (2 * step)
                assert numerical == pytest.approx(flat_gradient[position], rel=1e-5, abs=1e-8)


def test_adam_reduces_a_quadratic_loss():
    parameters = init_parameters(2, MLPConfig(hidden=(8,), dtype="float64"), seed=3)
    optimizer = Adam(parameters, learning_rate=0.05)
    rng = np.random.default_rng(1)
    features = rng.normal(size=(64, 2))
    target = features[:, 0] * 2.0 - features[:, 1]

    losses = []
    for _ in range(60):
        prediction, activations = forward(features, parameters)
        losses.append(float(np.mean((prediction - target) ** 2)))
        optimizer.step(parameters, backward(activations, parameters, prediction, target))
    assert losses[-1] < losses[0] / 10.0


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


def test_regression_metrics_match_the_split_gate_definition():
    predicted = np.array([1.0, 2.0, 3.0, 4.0])
    actual = np.array([1.5, 1.5, 3.5, 3.5])
    metrics = regression_metrics(predicted, actual)
    error = predicted - actual
    assert metrics["rmse"] == pytest.approx(math.sqrt(np.mean(error**2)))
    assert metrics["mae"] == pytest.approx(np.mean(np.abs(error)))
    assert metrics["max_abs_error"] == pytest.approx(0.5)
    # r2 against the POPULATION variance of the holdout actuals, which is what
    # caprm.split_gate.nearest_neighbour_baseline uses to produce the floor
    assert metrics["r2"] == pytest.approx(1.0 - np.mean(error**2) / np.var(actual))


def test_regression_metrics_reject_mismatched_or_empty_input():
    with pytest.raises(ValueError):
        regression_metrics(np.zeros(3), np.zeros(4))
    with pytest.raises(ValueError):
        regression_metrics(np.zeros(0), np.zeros(0))


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------


def _smooth_problem(n: int = 1500, seed: int = 4):
    rng = np.random.default_rng(seed)
    x = rng.uniform(COUNTY["x_min"], COUNTY["x_max"], size=n)
    y = rng.uniform(COUNTY["y_min"], COUNTY["y_max"], size=n)
    normalizer = CoordinateNormalizer.from_bounds(**COUNTY)
    coords = normalizer.transform(x, y)
    target = 50.0 + 20.0 * np.sin(2.0 * coords[:, 0]) + 10.0 * coords[:, 1]
    index = rng.permutation(n)
    return x, y, target, normalizer, index[: n // 2], index[n // 2 : 3 * n // 4], index[3 * n // 4 :]


def test_training_learns_a_smooth_function():
    x, y, target, normalizer, train_index, val_index, test_index = _smooth_problem()
    model = train_surrogate(
        x, y, target, train_index, val_index, normalizer,
        fourier=FourierConfig(n_features=16, scale=1.0),
        mlp=MLPConfig(hidden=(32, 32), dtype="float32"),
        train_config=TrainConfig(max_epochs=60, patience=15, batch_size=256),
        seed=20260731,
    )
    metrics = regression_metrics(model.predict(x[test_index], y[test_index]), target[test_index])
    # the target has a 20-point amplitude; a model that has not learned it
    # scores near its standard deviation, so this threshold separates learning
    # from not learning rather than certifying accuracy
    assert metrics["rmse"] < 3.0
    assert metrics["r2"] > 0.95


def test_the_fourier_scale_moves_the_result_on_a_target_of_known_wavelength():
    """The sweep is not ceremony: the scale changes the answer, measurably.

    Nucleus 18.25 — a parameter is only worth sweeping once some setting of it
    has been shown to change something. This target varies on a wavelength of
    pi normalized units; a frequency draw an octave and two octaves above that
    fits it worse, monotonically, and this test is the positive control that
    says so before the countywide sweep is believed.
    """
    x, y, target, normalizer, train_index, val_index, test_index = _smooth_problem()
    scores = []
    for scale in (1.0, 2.0, 4.0):
        model = train_surrogate(
            x, y, target, train_index, val_index, normalizer,
            fourier=FourierConfig(n_features=16, scale=scale),
            mlp=MLPConfig(hidden=(32, 32), dtype="float32"),
            train_config=TrainConfig(max_epochs=60, patience=15, batch_size=256),
            seed=20260731,
        )
        scores.append(
            regression_metrics(
                model.predict(x[test_index], y[test_index]), target[test_index]
            )["rmse"]
        )
    assert scores[0] < scores[1] < scores[2]


def test_training_is_deterministic_under_a_recorded_seed():
    x, y, target, normalizer, train_index, val_index, _ = _smooth_problem(n=400)
    kwargs = dict(
        fourier=FourierConfig(n_features=8, scale=2.0),
        mlp=MLPConfig(hidden=(16,), dtype="float32"),
        train_config=TrainConfig(max_epochs=8, patience=8, batch_size=128),
    )
    first = train_surrogate(x, y, target, train_index, val_index, normalizer, seed=1, **kwargs)
    second = train_surrogate(x, y, target, train_index, val_index, normalizer, seed=1, **kwargs)
    third = train_surrogate(x, y, target, train_index, val_index, normalizer, seed=2, **kwargs)
    assert first.weights_sha256() == second.weights_sha256()
    assert first.weights_sha256() != third.weights_sha256()


def test_training_standardizes_the_target_on_training_rows_only():
    x, y, target, normalizer, train_index, val_index, _ = _smooth_problem(n=400)
    poisoned = target.copy()
    poisoned[val_index] += 1000.0
    kwargs = dict(
        fourier=FourierConfig(n_features=4, scale=2.0),
        mlp=MLPConfig(hidden=(8,), dtype="float32"),
        train_config=TrainConfig(max_epochs=3, patience=3, batch_size=128),
        seed=1,
    )
    clean = train_surrogate(x, y, target, train_index, val_index, normalizer, **kwargs)
    dirty = train_surrogate(x, y, poisoned, train_index, val_index, normalizer, **kwargs)
    assert clean.target_mean == pytest.approx(dirty.target_mean)
    assert clean.target_std == pytest.approx(dirty.target_std)


def test_training_rejects_an_empty_or_overlapping_validation_set():
    x, y, target, normalizer, train_index, val_index, _ = _smooth_problem(n=200)
    with pytest.raises(ValueError):
        train_surrogate(x, y, target, train_index, np.array([], dtype=np.int64), normalizer)
    with pytest.raises(ValueError):
        train_surrogate(x, y, target, train_index, train_index[:5], normalizer)


def test_prediction_depends_on_the_inference_batch_size_only_below_a_stated_bound():
    """float32 matrix multiply is not invariant to operand SHAPE.

    BLAS chooses blocking and accumulation order from the shapes it is given,
    so predicting in batches of 37 and of 10,000 does not produce bit-identical
    float32 output. Measured here at 3.87e-06 index points on the 0-100 scale,
    against a reported RMSE of order 10: it is recorded rather than asserted
    away, and the bound below is deliberately loose enough to hold on another
    BLAS rather than tight enough to pin this one.
    """
    x, y, target, normalizer, train_index, val_index, _ = _smooth_problem(n=400)
    model = train_surrogate(
        x, y, target, train_index, val_index, normalizer,
        fourier=FourierConfig(n_features=8, scale=2.0),
        mlp=MLPConfig(hidden=(16,), dtype="float32"),
        train_config=TrainConfig(max_epochs=4, patience=4, batch_size=128),
        seed=1,
    )
    deviation = np.abs(
        model.predict(x, y, batch_size=37) - model.predict(x, y, batch_size=10_000)
    ).max()
    assert deviation < 1e-3


def test_repeated_prediction_at_one_batch_size_is_bit_identical():
    """Fix the shape and the output is reproducible, which is what is reported."""
    x, y, target, normalizer, train_index, val_index, _ = _smooth_problem(n=400)
    model = train_surrogate(
        x, y, target, train_index, val_index, normalizer,
        fourier=FourierConfig(n_features=8, scale=2.0),
        mlp=MLPConfig(hidden=(16,), dtype="float32"),
        train_config=TrainConfig(max_epochs=4, patience=4, batch_size=128),
        seed=1,
    )
    assert np.array_equal(model.predict(x, y), model.predict(x, y))


# ---------------------------------------------------------------------------
# the model as an artifact (Nucleus 18.20)
# ---------------------------------------------------------------------------


def test_header_carries_everything_a_model_artifact_must_carry():
    x, y, target, normalizer, train_index, val_index, _ = _smooth_problem(n=300)
    model = train_surrogate(
        x, y, target, train_index, val_index, normalizer,
        fourier=FourierConfig(n_features=4, scale=2.0),
        mlp=MLPConfig(hidden=(8,), dtype="float32"),
        train_config=TrainConfig(max_epochs=3, patience=3, batch_size=128),
        seed=99,
        provenance={"split_manifest_sha256": "deadbeef"},
    )
    header = model.header()
    assert header["schema_version"] == "c2_surrogate_v1"
    assert header["crs"] == "EPSG:26918"
    assert header["architecture"]["training_dtype"] == "float32"
    assert header["architecture"]["n_parameters"] == model.n_parameters()
    assert header["seeds"]["seed"] == 99
    assert len(header["weights_sha256"]) == 64
    assert len(header["history"]["val_rmse_label_units"]) == 3
    assert header["provenance"]["split_manifest_sha256"] == "deadbeef"
    assert header["input_quantisation_m"] > 0.0


def test_saved_model_reloads_to_the_same_checksum_and_predictions(tmp_path):
    x, y, target, normalizer, train_index, val_index, _ = _smooth_problem(n=300)
    model = train_surrogate(
        x, y, target, train_index, val_index, normalizer,
        fourier=FourierConfig(n_features=8, scale=3.0),
        mlp=MLPConfig(hidden=(16, 8), dtype="float32"),
        train_config=TrainConfig(max_epochs=4, patience=4, batch_size=128),
        seed=5,
    )
    path = save_model(model, tmp_path / "model.npz")
    reloaded = load_model(path)
    # checked on the artifact AS RELOADED, which is the standard B4 established
    assert reloaded.weights_sha256() == model.weights_sha256()
    assert reloaded.header()["weights_sha256"] == model.header()["weights_sha256"]
    assert np.array_equal(reloaded.predict(x, y), model.predict(x, y))
