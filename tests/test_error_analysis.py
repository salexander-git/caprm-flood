"""Tests for C3's error-analysis primitives.

Two of these are positive controls rather than assertions of correctness
(Nucleus 18.25): ``test_verdict_can_be_confirmed`` and
``test_verdict_can_be_refuted`` exist because a verdict function that can only
return one answer is not a verdict, and ``test_cluster_bootstrap_is_wider_than
_row_bootstrap`` exists because a clustered interval that matches the naive one
is a clustered interval that is not clustering.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from caprm.error_analysis import (
    BootstrapConfig,
    ErrorAnalysisError,
    bin_residuals,
    boundary_distance_by_class,
    class_decomposition,
    cluster_bootstrap_mean_abs,
    competitor_ranking,
    distance_to_convex_hull,
    distance_to_nearest_training,
    evaluate_prediction,
    label_recovery,
    local_neighbourhood_range,
    majority_class,
    stratified_table,
)


# ---------------------------------------------------------------------------
# boundary proxy
# ---------------------------------------------------------------------------


def test_boundary_distance_is_the_distance_to_a_different_class():
    x = np.array([0.0, 1.0, 5.0, 6.0])
    y = np.zeros(4)
    klass = np.array([10.0, 10.0, 95.0, 95.0])
    d = boundary_distance_by_class(x, y, klass)
    # nearest different-class neighbour: 0->5 is 5, 1->5 is 4, 5->1 is 4, 6->5 is 5
    assert np.allclose(d, [5.0, 4.0, 4.0, 5.0])


def test_boundary_distance_ignores_same_class_neighbours_that_are_closer():
    """The point at x=1 has a same-class neighbour at distance 1 and a
    different-class neighbour at distance 4. The proxy must report 4."""
    x = np.array([0.0, 1.0, 5.0])
    y = np.zeros(3)
    d = boundary_distance_by_class(x, y, np.array([10.0, 10.0, 95.0]))
    assert d[1] == pytest.approx(4.0)


def test_boundary_distance_is_infinite_when_only_one_class_exists():
    d = boundary_distance_by_class(np.arange(5.0), np.zeros(5), np.full(5, 10.0))
    assert np.isinf(d).all()


def test_boundary_distance_rejects_mismatched_lengths():
    with pytest.raises(ErrorAnalysisError):
        boundary_distance_by_class(np.zeros(3), np.zeros(3), np.zeros(2))


# ---------------------------------------------------------------------------
# competitors
# ---------------------------------------------------------------------------


def test_local_neighbourhood_range_over_three_nearest():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.zeros(4)
    values = np.array([0.0, 10.0, 20.0, 30.0])
    r = local_neighbourhood_range(x, y, values, k=3)
    assert np.allclose(r, [20.0, 20.0, 20.0, 20.0])


def test_local_neighbourhood_range_is_zero_on_a_constant_field():
    x = np.linspace(0.0, 10.0, 20)
    r = local_neighbourhood_range(x, np.zeros(20), np.full(20, 7.0), k=5)
    assert np.allclose(r, 0.0)


def test_local_neighbourhood_range_clamps_k_to_the_point_count():
    r = local_neighbourhood_range(np.arange(3.0), np.zeros(3), np.array([1.0, 2.0, 9.0]), k=50)
    assert np.allclose(r, 8.0)


def test_distance_to_convex_hull_on_a_unit_square():
    x = np.array([0.0, 1.0, 1.0, 0.0, 0.5])
    y = np.array([0.0, 0.0, 1.0, 1.0, 0.5])
    d = distance_to_convex_hull(x, y)
    assert np.allclose(d[:4], 0.0)
    assert d[4] == pytest.approx(0.5)


def test_distance_to_nearest_training_uses_only_training_rows():
    x = np.array([0.0, 1.0, 10.0, 11.0])
    y = np.zeros(4)
    d = distance_to_nearest_training(x, y, np.array([0, 1]), np.array([2, 3]))
    assert np.allclose(d, [9.0, 10.0])


# ---------------------------------------------------------------------------
# residual statistics
# ---------------------------------------------------------------------------


def test_majority_class_is_measured_not_assumed():
    value, count, share = majority_class(np.array([10.0] * 8 + [95.0, 80.0]))
    assert (value, count) == (10.0, 8)
    assert share == pytest.approx(0.8)


def test_bin_residuals_reports_a_count_for_every_bin_including_empty_ones():
    distance = np.array([1.0, 2.0, 300.0])
    residual = np.array([1.0, -3.0, 5.0])
    actual = np.array([10.0, 20.0, 30.0])
    table = bin_residuals(distance, residual, actual, edges=[0.0, 10.0, 100.0, np.inf])
    assert list(table["n"]) == [2, 0, 1]
    assert table.loc[0, "mean_abs"] == pytest.approx(2.0)
    assert table.loc[0, "mean_signed"] == pytest.approx(-1.0)


def test_bin_residuals_separates_signed_from_absolute():
    """A symmetric ramp: signed mean is zero while absolute mean is not.

    This is the case the chunk brief warns about, and a signed-only analysis
    would read this bin as error-free.
    """
    table = bin_residuals(
        np.zeros(4), np.array([5.0, -5.0, 5.0, -5.0]), np.full(4, 50.0),
        edges=[0.0, 10.0, np.inf],
    )
    assert table.loc[0, "mean_signed"] == pytest.approx(0.0)
    assert table.loc[0, "mean_abs"] == pytest.approx(5.0)


def test_class_decomposition_shares_sum_to_one_and_expose_concentration():
    klass = np.array([10.0] * 9 + [95.0])
    residual = np.array([1.0] * 9 + [30.0])
    actual = np.full(10, 40.0)
    table = class_decomposition(klass, residual, actual)
    assert table["row_share"].sum() == pytest.approx(1.0)
    assert table["sse_share"].sum() == pytest.approx(1.0)
    minority = table[table["class_value"] == 95.0].iloc[0]
    assert minority["row_share"] == pytest.approx(0.1)
    assert minority["sse_share"] > 0.98  # 900 of 909


def test_class_decomposition_records_one_sided_error():
    """Every minority row under-predicted is the signature the ramp leaves when
    the minority level is one the network never reaches."""
    table = class_decomposition(
        np.array([10.0, 10.0, 95.0, 95.0]),
        np.array([1.0, -1.0, -30.0, -25.0]),
        np.full(4, 50.0),
    )
    minority = table[table["class_value"] == 95.0].iloc[0]
    assert minority["fraction_under_predicted"] == pytest.approx(1.0)
    assert minority["mean_signed"] == pytest.approx(-minority["mean_abs"])


def test_stratified_table_returns_aligned_means_and_counts():
    rng = np.random.default_rng(0)
    actual = rng.uniform(0.0, 100.0, 500)
    distance = rng.uniform(0.0, 2000.0, 500)
    residual = rng.normal(0.0, 1.0, 500)
    mean_abs, counts = stratified_table(distance, residual, actual, n_label_bins=5)
    assert mean_abs.shape == counts.shape
    assert int(counts.to_numpy().sum()) == 500


# ---------------------------------------------------------------------------
# competitor ranking
# ---------------------------------------------------------------------------


def _confounded_fixture(n: int = 8000):
    """A true driver, a label confounded with it, and pure noise.

    ``driver`` generates the residual outright; ``actual`` is correlated with
    ``driver`` but plays no causal role. This is the shape of the real problem:
    distance-to-boundary and label magnitude both track water proximity, and
    only one of them need be doing the work.
    """
    rng = np.random.default_rng(11)
    actual = rng.uniform(0.0, 100.0, n)
    driver = 0.7 * (actual / 100.0) + 0.3 * rng.uniform(0.0, 1.0, n)
    residual = driver * 20.0 * rng.choice([-1.0, 1.0], n)
    return actual, driver, residual, rng.uniform(0.0, 1.0, n)


def test_within_label_statistic_attenuates_a_confounded_label_proxy():
    """The check that the within-label statistic is doing what it claims.

    The label's MARGINAL correlation with |residual| is large because it is
    confounded with the true driver. Stratifying by the label removes most of
    it. The true driver survives untouched and pure noise scores near zero, so
    the statistic is discriminating rather than merely shrinking everything.
    """
    actual, driver, residual, noise = _confounded_fixture()
    ranking = competitor_ranking(
        {"label_magnitude": actual, "true_driver": driver, "noise": noise},
        residual, actual,
    )
    row = lambda name: ranking[ranking["candidate"] == name].iloc[0]
    label, true_driver, pure_noise = row("label_magnitude"), row("true_driver"), row("noise")
    assert abs(label["spearman_abs"]) > 0.8
    assert abs(label["spearman_within_label"]) < 0.4 * abs(label["spearman_abs"])
    assert abs(true_driver["spearman_within_label"]) > 0.9
    assert abs(pure_noise["spearman_within_label"]) < 0.1


def test_a_planted_within_stratum_driver_outranks_a_label_proxy():
    actual, driver, residual, _ = _confounded_fixture()
    ranking = competitor_ranking(
        {"label_magnitude": actual, "planted": driver}, residual, actual
    )
    assert ranking.loc[0, "candidate"] == "planted"


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------


def _bootstrap_fixture(n_clusters: int = 200, replicates: int = 5):
    rng = np.random.default_rng(3)
    cluster = np.repeat(np.arange(n_clusters), replicates)
    per_cluster = rng.normal(0.0, 5.0, n_clusters)
    residual = np.repeat(per_cluster, replicates)
    group = np.where(cluster < n_clusters // 2, "near", "far")
    return group, cluster, residual


def test_cluster_bootstrap_is_deterministic_under_its_seed():
    group, cluster, residual = _bootstrap_fixture()
    config = BootstrapConfig(n_resamples=40, seed=1234)
    a = cluster_bootstrap_mean_abs(group, cluster, residual, config)
    b = cluster_bootstrap_mean_abs(group, cluster, residual, config)
    pd.testing.assert_frame_equal(a, b)


def test_cluster_bootstrap_interval_brackets_the_observed_mean():
    group, cluster, residual = _bootstrap_fixture()
    out = cluster_bootstrap_mean_abs(group, cluster, residual, BootstrapConfig(n_resamples=100))
    assert (out["ci_low"] <= out["mean_abs"]).all()
    assert (out["mean_abs"] <= out["ci_high"]).all()
    assert int(out["n"].sum()) == residual.size


def test_cluster_bootstrap_is_wider_than_a_row_bootstrap_on_replicated_data():
    """Positive control. Each property is replicated five times, so a row
    bootstrap sees five times the independent information it has. If the two
    intervals matched, the clustering would not be happening."""
    group, cluster, residual = _bootstrap_fixture()
    clustered = cluster_bootstrap_mean_abs(
        group, cluster, residual, BootstrapConfig(n_resamples=200, seed=7)
    )
    naive = cluster_bootstrap_mean_abs(
        group, np.arange(residual.size), residual, BootstrapConfig(n_resamples=200, seed=7)
    )
    clustered_width = (clustered["ci_high"] - clustered["ci_low"]).to_numpy()
    naive_width = (naive["ci_high"] - naive["ci_low"]).to_numpy()
    assert (clustered_width > naive_width * 1.5).all()


# ---------------------------------------------------------------------------
# the verdict, in both directions
# ---------------------------------------------------------------------------


def _tables(far_value: float, boundary_rho: float, minority_rmse: float,
            rival_rho: float = 0.03):
    """Verdict fixtures, kept internally consistent: sse is derived from rmse
    and n rather than typed independently, so the fixture cannot describe a
    class decomposition that arithmetic forbids. ``rival_rho`` is a competing
    candidate, present so the "strongest candidate" condition is exercised."""
    majority_rmse, majority_n, minority_n = 9.0, 9800, 200
    majority_sse = majority_rmse**2 * majority_n
    minority_sse = minority_rmse**2 * minority_n
    total = majority_sse + minority_sse
    binned = pd.DataFrame(
        {
            "bin_index": [0, 1, 2],
            "lower_m": [0.0, 100.0, 3200.0],
            "upper_m": [100.0, 3200.0, np.inf],
            "n": [50, 5000, 200],
            "mean_abs": [20.0, 8.0, far_value],
        }
    )
    classes = pd.DataFrame(
        {
            "class_value": [10.0, 95.0],
            "n": [majority_n, minority_n],
            "row_share": [majority_n / 10000, minority_n / 10000],
            "sse": [majority_sse, minority_sse],
            "sse_share": [majority_sse / total, minority_sse / total],
            "rmse": [majority_rmse, minority_rmse],
        }
    )
    ranking = pd.DataFrame(
        {
            "candidate": ["fema_boundary_distance_m", "local_range__water_component_0_100",
                          "label_magnitude"],
            "spearman_within_label": [boundary_rho, rival_rho, 0.05],
        }
    ).reindex([0, 1, 2])
    ranking = ranking.reindex(
        ranking["spearman_within_label"].abs().sort_values(ascending=False).index
    ).reset_index(drop=True)
    return binned, classes, ranking


def test_verdict_can_be_confirmed():
    binned, classes, ranking = _tables(far_value=7.0, boundary_rho=-0.40, minority_rmse=45.0)
    out = evaluate_prediction(binned, classes, ranking, majority_value=10.0)
    assert out["verdict"] == "CONFIRMED"
    assert out["mechanism_confirmed"] and out["spatial_prediction_confirmed"]


def test_verdict_can_be_refuted_by_the_far_field_alone():
    binned, classes, ranking = _tables(far_value=18.0, boundary_rho=-0.40, minority_rmse=45.0)
    out = evaluate_prediction(binned, classes, ranking, majority_value=10.0)
    assert out["verdict"] == "REFUTED"
    assert out["mechanism_confirmed"] is True
    assert out["small_elsewhere"] is False


def test_proximity_fails_on_the_wrong_sign():
    """A positive rho means the residual GROWS with distance from a boundary,
    which is the opposite of the prediction and must not be scored as support
    merely because its magnitude is large."""
    binned, classes, ranking = _tables(far_value=7.0, boundary_rho=+0.40, minority_rmse=45.0)
    out = evaluate_prediction(binned, classes, ranking, majority_value=10.0)
    assert out["proximity_correct_sign"] is False
    assert out["proximity_effect"] is False
    assert out["verdict"] == "REFUTED"


def test_proximity_fails_below_the_declared_floor():
    binned, classes, ranking = _tables(far_value=7.0, boundary_rho=-0.04, minority_rmse=45.0)
    out = evaluate_prediction(binned, classes, ranking, majority_value=10.0)
    assert out["proximity_clears_floor"] is False
    assert out["proximity_effect"] is False


def test_proximity_fails_when_a_competitor_is_stronger():
    """Beating label magnitude is not enough. A boundary effect that loses to
    water-component roughness has not explained anything FEMA-specific."""
    binned, classes, ranking = _tables(
        far_value=7.0, boundary_rho=-0.15, minority_rmse=45.0, rival_rho=-0.30
    )
    out = evaluate_prediction(binned, classes, ranking, majority_value=10.0)
    assert out["strongest_candidate"] == "local_range__water_component_0_100"
    assert out["proximity_is_strongest_candidate"] is False
    assert out["proximity_effect"] is False


def test_verdict_requires_error_to_concentrate_in_the_minority():
    binned, classes, ranking = _tables(far_value=7.0, boundary_rho=-0.40, minority_rmse=3.0)
    out = evaluate_prediction(binned, classes, ranking, majority_value=10.0)
    assert out["mechanism_confirmed"] is False
    assert out["verdict"] == "REFUTED"


# ---------------------------------------------------------------------------
# label recovery and candidate spread, added at C3b
# ---------------------------------------------------------------------------


def test_mean_predicted_reconstructs_the_prediction_from_residual_and_actual():
    table = bin_residuals(
        np.array([1.0, 1.0]), np.array([5.0, -3.0]), np.array([40.0, 60.0]),
        edges=[0.0, 10.0, np.inf],
    )
    assert table.loc[0, "mean_predicted"] == pytest.approx((45.0 + 57.0) / 2.0)
    assert table.loc[0, "mean_label"] == pytest.approx(50.0)


def test_label_recovery_is_one_for_a_perfect_tracker():
    actual = np.array([10.0, 20.0, 30.0, 40.0])
    table = bin_residuals(
        np.array([1.0, 30.0, 300.0, 3000.0]), np.zeros(4), actual,
        edges=[0.0, 10.0, 100.0, 1000.0, np.inf],
    )
    out = label_recovery(table)
    assert out["recovery_ratio"] == pytest.approx(1.0)
    assert out["n_bins"] == 4


def test_label_recovery_is_zero_for_a_constant_predictor():
    """A model emitting one value everywhere: the residual curve still moves,
    the recovery ratio does not. This is the pair the statistic exists for."""
    actual = np.array([10.0, 20.0, 30.0, 40.0])
    residual = 25.0 - actual  # predicted == 25 in every bin
    table = bin_residuals(
        np.array([1.0, 30.0, 300.0, 3000.0]), residual, actual,
        edges=[0.0, 10.0, 100.0, 1000.0, np.inf],
    )
    out = label_recovery(table)
    assert out["predicted_span"] == pytest.approx(0.0)
    assert out["recovery_ratio"] == pytest.approx(0.0)
    assert out["label_span"] == pytest.approx(30.0)


def test_label_recovery_ignores_empty_bins():
    table = bin_residuals(
        np.array([1.0, 3000.0]), np.zeros(2), np.array([10.0, 40.0]),
        edges=[0.0, 10.0, 100.0, 1000.0, np.inf],
    )
    assert (table["n"] == 0).any()
    assert label_recovery(table)["n_bins"] == 2


def test_label_recovery_needs_two_occupied_bins():
    table = bin_residuals(np.array([1.0]), np.zeros(1), np.array([10.0]),
                          edges=[0.0, 10.0, np.inf])
    with pytest.raises(ErrorAnalysisError):
        label_recovery(table)


def test_competitor_ranking_reports_candidate_spread():
    """A range-compressed candidate must be visibly range-compressed: the
    blocked test set is >= 2,125 m from training by construction and a reader
    comparing its rank across partitions needs to see that."""
    actual, driver, residual, _ = _confounded_fixture()
    compressed = 2125.0 + driver  # one metre of spread above a hard floor
    ranking = competitor_ranking(
        {"label_magnitude": actual, "compressed": compressed}, residual, actual
    )
    row = ranking[ranking["candidate"] == "compressed"].iloc[0]
    assert row["candidate_min"] >= 2125.0
    assert row["candidate_max"] - row["candidate_min"] < 1.5
    assert row["candidate_p25"] < row["candidate_median"] < row["candidate_p75"]