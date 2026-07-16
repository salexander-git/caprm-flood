from __future__ import annotations

import pandas as pd
import pytest

from caprm.scoring import (
    COMPOSITE_DECIMALS,
    DEFAULT_WEIGHTS,
    SCORING_POLICY_VERSION,
    build_exposure_index,
    fema_component_score,
    percentile_score,
    summarize_exposure_index,
    terrain_absolute_component_score,
    terrain_relative_component_score,
    validate_weights,
    water_component_score,
)


def evidence_frame() -> pd.DataFrame:
    """
    Five properties ordered from lowest to highest exposure on every input.

    Every field descends in severity order, so each component must produce
    a monotonically increasing score. That makes directionality testable
    without asserting specific percentile values.
    """
    return pd.DataFrame(
        {
            "property_id": ["A", "B", "C", "D", "E"],
            "matched_fema_polygon": [True, True, True, True, True],
            "fema_zone": ["X", "AO", "A", "AE", "VE"],
            "is_sfha": [False, True, True, True, True],
            "nearest_water_distance_m": [1000.0, 500.0, 250.0, 100.0, 0.0],
            "distance_crs": ["EPSG:26918"] * 5,
        }
    )


def terrain_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["A", "B", "C", "D", "E"],
            "terrain_elevation_m": [200.0, 175.0, 150.0, 100.0, 75.0],
            "terrain_relative_elevation_m": [10.0, 5.0, 0.0, -5.0, -10.0],
            "terrain_slope_degrees": [1.0, 2.0, 3.0, 4.0, 5.0],
            "terrain_crs": ["EPSG:26918"] * 5,
        }
    )


# ---------------------------------------------------------------- weights


def test_validate_weights_accepts_default_weights() -> None:
    assert validate_weights(DEFAULT_WEIGHTS) == DEFAULT_WEIGHTS


def test_default_weights_sum_to_one() -> None:
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_validate_weights_rejects_bad_sum() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_weights(
            {
                "fema": 0.4,
                "water": 0.4,
                "terrain_absolute": 0.4,
                "terrain_relative": 0.4,
            }
        )


def test_validate_weights_rejects_negative_weight() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        validate_weights(
            {
                "fema": 0.7,
                "water": 0.5,
                "terrain_absolute": -0.1,
                "terrain_relative": -0.1,
            }
        )


def test_validate_weights_rejects_retired_nested_key_set() -> None:
    """The nested terrain weight is gone; the old key set must not pass."""
    with pytest.raises(ValueError, match="must contain exactly"):
        validate_weights({"fema": 0.40, "water": 0.35, "terrain": 0.25})


# ------------------------------------------------------------- percentile


def test_percentile_score_reverses_low_values_when_requested() -> None:
    values = pd.Series([100.0, 50.0, 0.0])

    scores = percentile_score(
        values,
        higher_value_is_higher_exposure=False,
    )

    assert scores.tolist() == pytest.approx(
        [33.3333333333, 66.6666666667, 100.0]
    )


def test_percentile_score_returns_midpoint_for_constant_input() -> None:
    values = pd.Series([5.0, 5.0, 5.0])

    scores = percentile_score(values, higher_value_is_higher_exposure=True)

    assert scores.tolist() == [50.0, 50.0, 50.0]


def test_percentile_score_averages_ties() -> None:
    values = pd.Series([1.0, 2.0, 2.0, 3.0])

    scores = percentile_score(values, higher_value_is_higher_exposure=True)

    assert scores.iloc[1] == scores.iloc[2]


def test_percentile_score_rejects_nonfinite() -> None:
    values = pd.Series([1.0, float("nan"), 3.0])

    with pytest.raises(ValueError, match="nonfinite"):
        percentile_score(values, higher_value_is_higher_exposure=True)


# ------------------------------------------------------------------ FEMA


def test_fema_component_score_orders_every_mapped_zone() -> None:
    scores = fema_component_score(evidence_frame())

    assert scores.tolist() == [10.0, 80.0, 90.0, 95.0, 100.0]


def test_fema_component_score_is_monotonic_in_severity() -> None:
    scores = fema_component_score(evidence_frame())

    assert scores.is_monotonic_increasing


def test_fema_component_score_scores_unmatched_as_zero() -> None:
    evidence = evidence_frame()
    evidence.loc[0, "matched_fema_polygon"] = False
    evidence.loc[0, "fema_zone"] = None
    evidence.loc[0, "is_sfha"] = False

    scores = fema_component_score(evidence)

    assert scores.iloc[0] == 0.0


def test_fema_component_score_rejects_unrecognized_zone() -> None:
    """A zone absent from the table must raise, never default to 0.0."""
    evidence = evidence_frame()
    evidence.loc[0, "fema_zone"] = "AH"

    with pytest.raises(ValueError, match="absent from"):
        fema_component_score(evidence)


def test_fema_component_score_rejects_matched_row_without_zone() -> None:
    evidence = evidence_frame()
    evidence.loc[0, "fema_zone"] = None

    with pytest.raises(ValueError, match="absent from"):
        fema_component_score(evidence)


def test_fema_component_score_rejects_sfha_without_polygon_match() -> None:
    evidence = evidence_frame()
    evidence.loc[0, "matched_fema_polygon"] = False
    evidence.loc[0, "fema_zone"] = None
    evidence.loc[0, "is_sfha"] = True

    with pytest.raises(ValueError, match="SFHA"):
        fema_component_score(evidence)


def test_fema_component_score_normalizes_zone_case_and_whitespace() -> None:
    evidence = evidence_frame()
    evidence.loc[3, "fema_zone"] = "  ae  "

    scores = fema_component_score(evidence)

    assert scores.iloc[3] == 95.0


def test_fema_component_score_ignores_sfha_flag_value() -> None:
    """
    is_sfha is validated but must not change the score. Zone determines
    severity; scoring both would double-count one signal.
    """
    baseline = fema_component_score(evidence_frame())

    evidence = evidence_frame()
    evidence.loc[1, "is_sfha"] = False

    assert fema_component_score(evidence).tolist() == baseline.tolist()


# ----------------------------------------------------------------- water


def test_water_component_score_ranks_nearer_water_higher() -> None:
    scores = water_component_score(evidence_frame())

    assert scores.is_monotonic_increasing
    assert scores.iloc[-1] > scores.iloc[0]


def test_water_component_score_bounds() -> None:
    scores = water_component_score(evidence_frame())

    assert scores.gt(0.0).all()
    assert scores.le(100.0).all()


def test_water_component_score_rejects_negative_distance() -> None:
    evidence = evidence_frame()
    evidence.loc[0, "nearest_water_distance_m"] = -1.0

    with pytest.raises(ValueError, match="cannot be negative"):
        water_component_score(evidence)


def test_water_component_score_rejects_nonfinite_distance() -> None:
    evidence = evidence_frame()
    evidence.loc[0, "nearest_water_distance_m"] = float("inf")

    with pytest.raises(ValueError, match="must be finite"):
        water_component_score(evidence)


# --------------------------------------------------------------- terrain


def test_terrain_absolute_component_ranks_lower_elevation_higher() -> None:
    scores = terrain_absolute_component_score(terrain_frame())

    assert scores.is_monotonic_increasing
    assert scores.iloc[-1] > scores.iloc[0]


def test_terrain_relative_component_ranks_lower_relative_higher() -> None:
    scores = terrain_relative_component_score(terrain_frame())

    assert scores.is_monotonic_increasing
    assert scores.iloc[-1] > scores.iloc[0]


def test_terrain_components_are_independent() -> None:
    """
    Absolute and relative elevation must be scored separately. A property
    high in the county can sit low within its neighborhood.
    """
    terrain = terrain_frame()
    terrain["terrain_relative_elevation_m"] = [-10.0, -5.0, 0.0, 5.0, 10.0]

    absolute = terrain_absolute_component_score(terrain)
    relative = terrain_relative_component_score(terrain)

    assert absolute.tolist() != relative.tolist()


# ------------------------------------------------------------- composite


def test_build_exposure_index_outputs_expected_schema() -> None:
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    assert len(index) == 5
    assert index["property_id"].tolist() == ["A", "B", "C", "D", "E"]
    assert index["scoring_policy_version"].nunique() == 1
    assert index["scoring_policy_version"].iloc[0] == SCORING_POLICY_VERSION

    for column in [
        "fema_component_0_100",
        "water_component_0_100",
        "terrain_absolute_component_0_100",
        "terrain_relative_component_0_100",
        "exposure_index_0_100",
        "exposure_percentile",
    ]:
        assert index[column].between(0.0, 100.0).all()


def test_build_exposure_index_composite_values() -> None:
    """Hand-computed composite for the fixture under default weights."""
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    assert index["exposure_index_0_100"].tolist() == pytest.approx(
        [16.0, 56.0, 72.0, 86.0, 100.0]
    )


def test_flat_weights_reproduce_legacy_nested_policy() -> None:
    """
    The four-weight model must equal the retired policy, which applied
    0.25 to a terrain component split 0.60 absolute / 0.40 relative.

    This locks the flattening decision. If it ever fails, the flat weights
    have drifted from the behavior verified across the countywide workload.
    """
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    legacy_terrain = (
        0.60 * index["terrain_absolute_component_0_100"]
        + 0.40 * index["terrain_relative_component_0_100"]
    )

    legacy_index = (
        0.40 * index["fema_component_0_100"]
        + 0.35 * index["water_component_0_100"]
        + 0.25 * legacy_terrain
    )

    assert legacy_index.tolist() == pytest.approx(
        index["exposure_index_0_100"].tolist()
    )


def test_build_exposure_index_honors_non_default_weights() -> None:
    """Regression: the weights argument must actually reach the composite."""
    weights = {
        "fema": 1.0,
        "water": 0.0,
        "terrain_absolute": 0.0,
        "terrain_relative": 0.0,
    }

    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
        weights=weights,
    )

    assert index["exposure_index_0_100"].tolist() == pytest.approx(
        index["fema_component_0_100"].tolist()
    )


def test_build_exposure_index_weights_change_the_result() -> None:
    baseline = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    equal = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
        weights={
            "fema": 0.25,
            "water": 0.25,
            "terrain_absolute": 0.25,
            "terrain_relative": 0.25,
        },
    )

    assert (
        baseline["exposure_index_0_100"].tolist()
        != equal["exposure_index_0_100"].tolist()
    )


def test_build_exposure_index_is_deterministic() -> None:
    first = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )
    second = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    pd.testing.assert_frame_equal(first, second)


def test_build_exposure_index_ignores_input_row_order() -> None:
    ordered = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    shuffled = build_exposure_index(
        evidence=evidence_frame().iloc[::-1].reset_index(drop=True),
        terrain=terrain_frame().iloc[::-1].reset_index(drop=True),
    )

    pd.testing.assert_frame_equal(ordered, shuffled)


def test_build_exposure_index_does_not_require_slope() -> None:
    """Slope is terrain evidence, not a scoring input."""
    terrain = terrain_frame().drop(columns=["terrain_slope_degrees"])

    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain,
    )

    assert len(index) == 5


def test_exposure_index_is_rounded_to_the_declared_precision() -> None:
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    values = index["exposure_index_0_100"]

    assert values.round(COMPOSITE_DECIMALS).equals(values)


def test_percentile_reproduces_from_the_stored_index() -> None:
    """
    Regression: ranking the stored index must reproduce the stored
    percentile.

    The composite lies on a lattice, so distinct component-rank triples
    collide constantly. Ranking an unrounded composite lets float noise of
    around 1e-14 split properties that are tied in substance, imposing an
    ordering that comes from operation order rather than evidence. It also
    breaks reproducibility: the artifact could not be regenerated from
    itself.
    """
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    recomputed = percentile_score(
        index["exposure_index_0_100"],
        higher_value_is_higher_exposure=True,
    )

    assert recomputed.tolist() == pytest.approx(
        index["exposure_percentile"].tolist()
    )


def test_rounding_ties_properties_with_equal_composites() -> None:
    """
    Two properties whose components differ but combine to the same value
    must share a rank.
    """
    evidence = evidence_frame()
    terrain = terrain_frame()

    index = build_exposure_index(evidence=evidence, terrain=terrain)

    composites = index["exposure_index_0_100"]
    percentiles = index["exposure_percentile"]

    for left in range(len(index)):
        for right in range(left + 1, len(index)):
            if composites.iloc[left] == composites.iloc[right]:
                assert percentiles.iloc[left] == percentiles.iloc[right]


def test_build_exposure_index_rejects_crs_mismatch() -> None:
    evidence = evidence_frame()
    evidence.loc[0, "distance_crs"] = "EPSG:3857"

    with pytest.raises(ValueError, match="Evidence distance CRS mismatch"):
        build_exposure_index(
            evidence=evidence,
            terrain=terrain_frame(),
        )


def test_build_exposure_index_rejects_terrain_crs_mismatch() -> None:
    terrain = terrain_frame()
    terrain.loc[0, "terrain_crs"] = "EPSG:4326"

    with pytest.raises(ValueError, match="Terrain CRS mismatch"):
        build_exposure_index(
            evidence=evidence_frame(),
            terrain=terrain,
        )


def test_build_exposure_index_rejects_lost_rows() -> None:
    terrain = terrain_frame().iloc[:2].copy()

    with pytest.raises(ValueError, match="lost property rows"):
        build_exposure_index(
            evidence=evidence_frame(),
            terrain=terrain,
        )


def test_build_exposure_index_rejects_duplicate_property_ids() -> None:
    evidence = evidence_frame()
    evidence.loc[1, "property_id"] = "A"

    with pytest.raises(ValueError, match="duplicate property IDs"):
        build_exposure_index(
            evidence=evidence,
            terrain=terrain_frame(),
        )


# --------------------------------------------------------------- summary


def test_summarize_exposure_index_reports_supplied_weights() -> None:
    """
    Regression: the summary must report the weights actually used, not
    DEFAULT_WEIGHTS. Reporting defaults regardless of input would make
    every sensitivity scenario claim the baseline configuration.
    """
    weights = {
        "fema": 0.25,
        "water": 0.25,
        "terrain_absolute": 0.25,
        "terrain_relative": 0.25,
    }

    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
        weights=weights,
    )

    summary = summarize_exposure_index(index, weights)

    assert summary["weights"] == weights
    assert summary["weights"] != DEFAULT_WEIGHTS


def test_summarize_exposure_index_validates_weights() -> None:
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    with pytest.raises(ValueError, match="sum to 1.0"):
        summarize_exposure_index(
            index,
            {
                "fema": 0.1,
                "water": 0.1,
                "terrain_absolute": 0.1,
                "terrain_relative": 0.1,
            },
        )


def test_summarize_exposure_index_reports_component_means() -> None:
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    summary = summarize_exposure_index(index, DEFAULT_WEIGHTS)

    assert set(summary["component_means"]) == set(DEFAULT_WEIGHTS)
    assert summary["property_count"] == 5
    assert summary["unique_property_ids"] == 5
    assert summary["scoring_policy_version"] == SCORING_POLICY_VERSION


def test_component_influence_shares_sum_to_one() -> None:
    """
    The variance decomposition is exact by linearity of covariance, so the
    shares must sum to 1.0 without assuming the components are orthogonal.
    """
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    summary = summarize_exposure_index(index, DEFAULT_WEIGHTS)
    components = summary["component_influence"]["components"]

    shares = [components[name]["variance_share"] for name in DEFAULT_WEIGHTS]

    assert sum(shares) == pytest.approx(1.0)


def test_component_influence_reports_zero_share_for_zero_weight() -> None:
    weights = {
        "fema": 1.0,
        "water": 0.0,
        "terrain_absolute": 0.0,
        "terrain_relative": 0.0,
    }

    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
        weights=weights,
    )

    summary = summarize_exposure_index(index, weights)
    components = summary["component_influence"]["components"]

    assert components["fema"]["variance_share"] == pytest.approx(1.0)
    assert components["water"]["variance_share"] == pytest.approx(0.0)