"""Tests for caprm.spatial_correlation.

The variogram estimator is tested against fields whose semivariogram is known
in closed form, not against a snapshot of its own output.
"""

from __future__ import annotations

import numpy as np
import pytest

from caprm.spatial_correlation import (
    accumulate_bins,
    first_lag_at_ratio,
    fit_exponential,
    nearest_neighbour_spacing,
    polynomial_detrend,
    variogram_long_range,
    variogram_short_range,
)


def test_accumulate_bins_is_hand_checkable():
    sums = np.zeros(4)
    counts = np.zeros(4)
    distances = np.array([0.0, 10.0, 10.0, 25.0, 1000.0])
    squared = np.array([2.0, 4.0, 6.0, 8.0, 999.0])
    accumulate_bins(distances, squared, bin_width_m=10.0, n_bins=4, sums=sums, counts=counts)
    assert counts.tolist() == [1.0, 2.0, 1.0, 0.0]
    assert sums.tolist() == [2.0, 10.0, 8.0, 0.0]


def test_accumulate_bins_discards_out_of_range_rather_than_piling_them_up():
    sums = np.zeros(2)
    counts = np.zeros(2)
    accumulate_bins(
        np.array([0.0, 500.0]), np.array([1.0, 1.0]), 10.0, 2, sums, counts
    )
    assert counts.tolist() == [1.0, 0.0]


def test_accumulate_bins_rejects_non_finite():
    sums = np.zeros(2)
    counts = np.zeros(2)
    accumulate_bins(
        np.array([np.inf, 5.0]), np.array([1.0, 3.0]), 10.0, 2, sums, counts
    )
    assert counts.tolist() == [1.0, 0.0]
    assert sums.tolist() == [3.0, 0.0]


def test_accumulate_bins_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        accumulate_bins(np.zeros(3), np.zeros(2), 1.0, 2, np.zeros(2), np.zeros(2))


def test_linear_field_reproduces_closed_form_semivariance():
    """For z = x on a 1-D lattice, gamma(h) = h^2 / 2 exactly."""
    x = np.arange(0.0, 400.0, 10.0)
    y = np.zeros_like(x)
    z = x.copy()
    v = variogram_short_range(
        x, y, z, max_lag_m=100.0, bin_width_m=10.0, n_centres=len(x), seed=1
    )
    for k in (1, 2, 3, 4):
        h = (k + 0.5) * 10.0 - 5.0  # bin k holds exactly the separation 10k
        assert v.pair_count[k] > 0
        assert v.semivariance[k] == pytest.approx(h * h / 2.0, rel=1e-12)


def test_pure_nugget_field_reaches_the_sill_in_the_first_bin():
    rng = np.random.default_rng(7)
    x = rng.uniform(0, 5000, 4000)
    y = rng.uniform(0, 5000, 4000)
    z = rng.normal(0.0, 1.0, 4000)  # no spatial structure at all
    v = variogram_short_range(
        x, y, z, max_lag_m=1000.0, bin_width_m=100.0, n_centres=2000, seed=3
    )
    assert first_lag_at_ratio(v, 0.9) == pytest.approx(50.0)
    assert np.nanmax(np.abs(v.semivariance / v.sill - 1.0)) < 0.15


def test_correlated_field_does_not_reach_the_sill_immediately():
    """A smooth gradient must produce a rising, not flat, variogram."""
    rng = np.random.default_rng(11)
    x = rng.uniform(0, 10000, 6000)
    y = rng.uniform(0, 10000, 6000)
    z = x / 1000.0
    v = variogram_short_range(
        x, y, z, max_lag_m=3000.0, bin_width_m=100.0, n_centres=3000, seed=5
    )
    ratios = v.semivariance / v.sill
    assert ratios[0] < 0.05
    # for z = x/1000 with pair directions uniform on the circle,
    # E[(z_i - z_j)^2] = h^2 / (2 * 1e6), so gamma(h) = h^2 / 4e6
    for k in (10, 20, 29):
        h = v.lag_centre_m[k]  # the bin centre, not its lower edge
        assert v.semivariance[k] == pytest.approx(h * h / 4e6, rel=0.05)
    assert first_lag_at_ratio(v, 0.25) is not None
    assert first_lag_at_ratio(v, 0.25) > 2000.0


def test_first_lag_at_ratio_returns_none_when_never_reached():
    rng = np.random.default_rng(13)
    x = rng.uniform(0, 10000, 2000)
    y = rng.uniform(0, 10000, 2000)
    z = x / 1000.0
    v = variogram_short_range(
        x, y, z, max_lag_m=200.0, bin_width_m=50.0, n_centres=1000, seed=5
    )
    assert first_lag_at_ratio(v, 0.95) is None


def test_short_range_variogram_is_deterministic_under_a_seed():
    rng = np.random.default_rng(17)
    x = rng.uniform(0, 5000, 3000)
    y = rng.uniform(0, 5000, 3000)
    z = rng.normal(size=3000) + x / 2000.0
    a = variogram_short_range(x, y, z, max_lag_m=1000.0, bin_width_m=100.0,
                              n_centres=1500, seed=99)
    b = variogram_short_range(x, y, z, max_lag_m=1000.0, bin_width_m=100.0,
                              n_centres=1500, seed=99)
    assert np.array_equal(a.pair_count, b.pair_count)
    assert np.array_equal(a.semivariance, b.semivariance)


def test_long_range_variogram_excludes_self_pairs():
    rng = np.random.default_rng(19)
    x = rng.uniform(0, 20000, 2000)
    y = rng.uniform(0, 20000, 2000)
    z = rng.normal(size=2000)
    v = variogram_long_range(x, y, z, max_lag_m=20000.0, bin_width_m=1000.0,
                             n_sample=2000, seed=23, chunk=500)
    # a self-pair contributes distance 0 and difference 0; with 2000 points the
    # first bin would be visibly deflated if they leaked in
    assert v.semivariance[0] / v.sill > 0.5


def test_long_and_short_passes_agree_where_they_overlap():
    rng = np.random.default_rng(29)
    x = rng.uniform(0, 20000, 8000)
    y = rng.uniform(0, 20000, 8000)
    z = x / 3000.0 + y / 5000.0
    s = variogram_short_range(x, y, z, max_lag_m=3000.0, bin_width_m=500.0,
                              n_centres=4000, seed=31)
    l = variogram_long_range(x, y, z, max_lag_m=3000.0, bin_width_m=500.0,
                             n_sample=8000, seed=31, chunk=1000)
    for k in range(1, 6):
        assert s.semivariance[k] == pytest.approx(l.semivariance[k], rel=0.05)


def test_polynomial_detrend_removes_an_exact_polynomial():
    rng = np.random.default_rng(37)
    x = rng.uniform(250000, 300000, 500)
    y = rng.uniform(4750000, 4800000, 500)
    xs = (x - x.mean()) / 1000.0
    ys = (y - y.mean()) / 1000.0
    z = 3.0 + 2.0 * xs - 1.5 * ys + 0.25 * xs * ys
    residual, r2 = polynomial_detrend(x, y, z, degree=2)
    assert r2 == pytest.approx(1.0, abs=1e-9)
    assert np.abs(residual).max() < 1e-6


def test_polynomial_detrend_leaves_white_noise_alone():
    rng = np.random.default_rng(41)
    x = rng.uniform(250000, 300000, 2000)
    y = rng.uniform(4750000, 4800000, 2000)
    z = rng.normal(size=2000)
    residual, r2 = polynomial_detrend(x, y, z, degree=3)
    assert r2 < 0.05
    assert np.var(residual) == pytest.approx(np.var(z), rel=0.05)


def test_exponential_fit_recovers_a_known_range():
    """Synthesise gamma(h) from a known model and fit it back."""
    from caprm.spatial_correlation import Variogram

    lags = np.arange(25.0, 3000.0, 25.0)
    true_a = 800.0
    gamma = 2.0 + 50.0 * (1.0 - np.exp(-lags / true_a))
    v = Variogram(
        lag_centre_m=lags,
        semivariance=gamma,
        pair_count=np.full(len(lags), 10_000),
        bin_width_m=25.0,
        sill=52.0,
        method="synthetic",
        seed=0,
        n_centres=0,
    )
    fit = fit_exponential(v, max_lag_m=3000.0)
    assert fit["range_parameter_a_m"] == pytest.approx(true_a, rel=1e-4)
    assert fit["nugget"] == pytest.approx(2.0, abs=1e-6)
    assert fit["r_squared"] == pytest.approx(1.0, abs=1e-9)


def test_nearest_neighbour_spacing_on_a_known_lattice():
    xs, ys = np.meshgrid(np.arange(10) * 100.0, np.arange(10) * 100.0)
    stats = nearest_neighbour_spacing(xs.ravel(), ys.ravel())
    assert stats["p50_m"] == pytest.approx(100.0)
    assert stats["zero_distance_rows"] == 0


def test_nearest_neighbour_spacing_counts_coincident_points():
    x = np.array([0.0, 0.0, 500.0])
    y = np.array([0.0, 0.0, 0.0])
    stats = nearest_neighbour_spacing(x, y)
    assert stats["zero_distance_rows"] == 2