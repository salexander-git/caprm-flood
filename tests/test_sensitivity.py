from __future__ import annotations

import pandas as pd
import pytest

from caprm.scoring import (
    COMPONENT_NAMES,
    DEFAULT_WEIGHTS,
    build_exposure_index,
)
from caprm.sensitivity import (
    BASELINE_SCENARIO_NAME,
    PLAUSIBLE_FAMILIES,
    REFERENCE_FAMILY,
    STABILITY_THRESHOLDS,
    build_scenarios,
    classify_stability,
    compare_to_baseline,
    composite_score,
    equal_weights,
    evaluate_scenarios,
    extract_components,
    extreme_properties,
    rescale,
    score_scenarios,
    single_component_weights,
    summarize_property_variability,
    tail_members,
)


def evidence_frame() -> pd.DataFrame:
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


def build_index() -> pd.DataFrame:
    return build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )


# ------------------------------------------------------------- weight math


def test_rescale_doubles_and_renormalizes() -> None:
    rescaled = rescale(DEFAULT_WEIGHTS, ["water"], 2.0)

    assert sum(rescaled.values()) == pytest.approx(1.0)
    assert rescaled["water"] > DEFAULT_WEIGHTS["water"]
    assert rescaled["fema"] < DEFAULT_WEIGHTS["fema"]


def test_rescale_preserves_relative_order_of_untouched_weights() -> None:
    rescaled = rescale(DEFAULT_WEIGHTS, ["water"], 0.5)

    assert (
        rescaled["fema"] / rescaled["terrain_absolute"]
        == pytest.approx(
            DEFAULT_WEIGHTS["fema"] / DEFAULT_WEIGHTS["terrain_absolute"]
        )
    )


def test_rescale_rejects_unknown_component() -> None:
    with pytest.raises(ValueError, match="Unknown component"):
        rescale(DEFAULT_WEIGHTS, ["precipitation"], 2.0)


def test_rescale_rejects_zero_total() -> None:
    with pytest.raises(ValueError, match="zero or negative"):
        rescale(DEFAULT_WEIGHTS, list(COMPONENT_NAMES), 0.0)


def test_equal_weights_sum_to_one() -> None:
    weights = equal_weights()

    assert sum(weights.values()) == pytest.approx(1.0)
    assert len(set(weights.values())) == 1


def test_single_component_weights_put_all_mass_on_one() -> None:
    weights = single_component_weights("fema")

    assert weights["fema"] == 1.0
    assert sum(weights.values()) == pytest.approx(1.0)
    assert all(
        weights[name] == 0.0 for name in COMPONENT_NAMES if name != "fema"
    )


# --------------------------------------------------------------- scenarios


def test_every_scenario_is_a_valid_weight_vector() -> None:
    for scenario in build_scenarios():
        assert set(scenario["weights"]) == set(COMPONENT_NAMES)
        assert sum(scenario["weights"].values()) == pytest.approx(1.0)
        assert all(value >= 0.0 for value in scenario["weights"].values())


def test_scenarios_include_baseline_first() -> None:
    scenarios = build_scenarios()

    assert scenarios[0]["name"] == BASELINE_SCENARIO_NAME
    assert scenarios[0]["weights"] == DEFAULT_WEIGHTS


def test_scenario_names_are_unique() -> None:
    names = [scenario["name"] for scenario in build_scenarios()]

    assert len(names) == len(set(names))


def test_scenarios_are_deterministic_for_a_seed() -> None:
    first = build_scenarios(seed=1234)
    second = build_scenarios(seed=1234)

    assert first == second


def test_scenario_seed_changes_the_perturbations() -> None:
    first = build_scenarios(seed=1)
    second = build_scenarios(seed=2)

    assert first != second


def test_perturbations_can_be_disabled() -> None:
    scenarios = build_scenarios(perturbation_count=0)

    assert not any(
        scenario["family"] == "perturbation" for scenario in scenarios
    )


def test_reference_corners_are_not_plausible() -> None:
    scenarios = build_scenarios()

    corners = [
        scenario
        for scenario in scenarios
        if scenario["family"] == REFERENCE_FAMILY
    ]

    assert len(corners) == len(COMPONENT_NAMES)
    assert all(
        corner["family"] not in PLAUSIBLE_FAMILIES for corner in corners
    )


def test_build_scenarios_rejects_bad_concentration() -> None:
    with pytest.raises(ValueError, match="concentration"):
        build_scenarios(concentration=0.0)


# ------------------------------------------------------------- components


def test_extract_components_returns_all_four() -> None:
    components = extract_components(build_index())

    assert list(components.columns) == list(COMPONENT_NAMES)
    assert components.index.name == "property_id"
    assert len(components) == 5


def test_extract_components_rejects_missing_columns() -> None:
    index = build_index().drop(columns=["water_component_0_100"])

    with pytest.raises(ValueError, match="missing component columns"):
        extract_components(index)


def test_composite_score_matches_the_generated_index() -> None:
    """
    Reweighting the extracted components must reproduce what
    build_exposure_index produced, or the sensitivity analysis is
    measuring something other than the shipped policy.
    """
    index = build_index()
    components = extract_components(index)

    composite = composite_score(components, DEFAULT_WEIGHTS)

    assert composite.tolist() == pytest.approx(
        index["exposure_index_0_100"].tolist()
    )


# ---------------------------------------------------------------- scoring


def test_score_scenarios_returns_a_column_per_scenario() -> None:
    components = extract_components(build_index())
    scenarios = build_scenarios(perturbation_count=2)

    percentiles = score_scenarios(components, scenarios)

    assert list(percentiles.columns) == [
        scenario["name"] for scenario in scenarios
    ]
    assert len(percentiles) == 5


def test_scenario_percentiles_stay_in_range() -> None:
    components = extract_components(build_index())
    percentiles = score_scenarios(
        components, build_scenarios(perturbation_count=2)
    )

    assert percentiles.gt(0.0).all().all()
    assert percentiles.le(100.0).all().all()


def test_baseline_percentile_matches_the_index() -> None:
    index = build_index()
    components = extract_components(index)

    percentiles = score_scenarios(
        components, build_scenarios(perturbation_count=0)
    )

    assert percentiles[BASELINE_SCENARIO_NAME].tolist() == pytest.approx(
        index["exposure_percentile"].tolist()
    )


# ---------------------------------------------------------------- metrics


def test_tail_members_selects_the_top_fraction() -> None:
    """
    A real percentile vector for n=5 is 20/40/60/80/100, since percentile
    is rank/n*100. The top 20% is one property, the top 40% is two.
    """
    percentile = pd.Series(
        [20.0, 40.0, 60.0, 80.0, 100.0],
        index=["A", "B", "C", "D", "E"],
    )

    assert tail_members(percentile, 0.2) == {"E"}
    assert tail_members(percentile, 0.4) == {"D", "E"}
    assert tail_members(percentile, 0.6) == {"C", "D", "E"}


def test_tail_members_excludes_the_boundary_property() -> None:
    """
    The property at exactly the (1 - fraction) percentile sits at the top
    of the bottom share, not the bottom of the top share. Including it
    would return one property too many.
    """
    percentile = pd.Series(
        [20.0, 40.0, 60.0, 80.0, 100.0],
        index=["A", "B", "C", "D", "E"],
    )

    # Threshold is exactly 80.0, which property D holds.
    assert "D" not in tail_members(percentile, 0.2)
    assert len(tail_members(percentile, 0.2)) == 1


def test_tail_members_keeps_tie_groups_together() -> None:
    """Tied properties share an average rank, so a tie group is never split."""
    percentile = pd.Series(
        [20.0, 70.0, 70.0, 70.0, 100.0],
        index=["A", "B", "C", "D", "E"],
    )

    members = tail_members(percentile, 0.5)

    assert {"B", "C", "D"}.issubset(members)


def test_tail_members_rejects_invalid_fraction() -> None:
    percentile = pd.Series([50.0], index=["A"])

    with pytest.raises(ValueError, match="strictly between"):
        tail_members(percentile, 1.0)


def test_compare_to_baseline_reports_perfect_agreement() -> None:
    percentile = pd.Series(
        [20.0, 40.0, 60.0, 80.0, 100.0],
        index=["A", "B", "C", "D", "E"],
    )

    record = compare_to_baseline(percentile, percentile)

    assert record["spearman_with_baseline"] == pytest.approx(1.0)
    assert record["maximum_absolute_percentile_shift"] == 0.0
    assert record["median_absolute_percentile_shift"] == 0.0
    assert record["top_10pct_overlap_of_smaller"] == pytest.approx(1.0)
    assert record["properties_shifted_over_10_percentile"] == 0


def test_compare_to_baseline_detects_a_reversed_ranking() -> None:
    baseline = pd.Series(
        [20.0, 40.0, 60.0, 80.0, 100.0],
        index=["A", "B", "C", "D", "E"],
    )
    reversed_ranking = pd.Series(
        [100.0, 80.0, 60.0, 40.0, 20.0],
        index=["A", "B", "C", "D", "E"],
    )

    record = compare_to_baseline(baseline, reversed_ranking)

    assert record["spearman_with_baseline"] == pytest.approx(-1.0)
    assert record["maximum_absolute_percentile_shift"] == pytest.approx(80.0)


def test_evaluate_scenarios_reports_weights_and_metrics() -> None:
    components = extract_components(build_index())
    scenarios = build_scenarios(perturbation_count=2)

    evaluation = evaluate_scenarios(
        score_scenarios(components, scenarios), scenarios
    )

    assert len(evaluation) == len(scenarios)
    assert "spearman_with_baseline" in evaluation.columns

    for name in COMPONENT_NAMES:
        assert f"weight_{name}" in evaluation.columns

    baseline_row = evaluation[
        evaluation["scenario"].eq(BASELINE_SCENARIO_NAME)
    ].iloc[0]

    assert baseline_row["spearman_with_baseline"] == pytest.approx(1.0)
    assert baseline_row["maximum_absolute_percentile_shift"] == 0.0


# ----------------------------------------------------------- variability


def test_summarize_property_variability_reports_range() -> None:
    percentiles = pd.DataFrame(
        {
            BASELINE_SCENARIO_NAME: [20.0, 60.0],
            "equal": [30.0, 50.0],
        },
        index=pd.Index(["A", "B"], name="property_id"),
    )

    variability = summarize_property_variability(
        percentiles, [BASELINE_SCENARIO_NAME, "equal"]
    )

    assert variability.loc["A", "minimum_percentile"] == 20.0
    assert variability.loc["A", "maximum_percentile"] == 30.0
    assert variability.loc["A", "percentile_range"] == 10.0
    assert variability.loc["A", "baseline_percentile"] == 20.0


def test_summarize_property_variability_requires_baseline() -> None:
    percentiles = pd.DataFrame(
        {"equal": [30.0]},
        index=pd.Index(["A"], name="property_id"),
    )

    with pytest.raises(ValueError, match="no baseline column"):
        summarize_property_variability(percentiles, ["equal"])


def test_extreme_properties_finds_the_edges() -> None:
    variability = pd.DataFrame(
        {
            "baseline_percentile": [10.0, 50.0, 90.0],
            "minimum_percentile": [5.0, 20.0, 85.0],
            "maximum_percentile": [15.0, 80.0, 95.0],
            "mean_percentile": [10.0, 50.0, 90.0],
            "standard_deviation_percentile": [5.0, 30.0, 5.0],
            "percentile_range": [10.0, 60.0, 10.0],
        },
        index=pd.Index(["A", "B", "C"], name="property_id"),
    )

    extremes = extreme_properties(variability, count=1)

    assert extremes["most_unstable"][0]["property_id"] == "B"
    assert extremes["consistently_high"][0]["property_id"] == "C"
    assert extremes["consistently_low"][0]["property_id"] == "A"


# -------------------------------------------------------- classification


def synthetic_evaluation(
    spearman: float,
    overlap: float,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "scenario": BASELINE_SCENARIO_NAME,
                "family": "baseline",
                "spearman_with_baseline": 1.0,
                "top_10pct_overlap_of_smaller": 1.0,
                "maximum_absolute_percentile_shift": 0.0,
                "median_absolute_percentile_shift": 0.0,
            },
            {
                "scenario": "equal",
                "family": "structured",
                "spearman_with_baseline": spearman,
                "top_10pct_overlap_of_smaller": overlap,
                "maximum_absolute_percentile_shift": 20.0,
                "median_absolute_percentile_shift": 2.0,
            },
            {
                "scenario": "fema_only",
                "family": REFERENCE_FAMILY,
                "spearman_with_baseline": 0.2,
                "top_10pct_overlap_of_smaller": 0.1,
                "maximum_absolute_percentile_shift": 90.0,
                "median_absolute_percentile_shift": 40.0,
            },
        ]
    )


def test_classify_stability_calls_a_tight_family_stable() -> None:
    stability = classify_stability(synthetic_evaluation(0.99, 0.95))

    assert stability["verdict"] == "stable"


def test_classify_stability_calls_a_loose_family_moderate() -> None:
    stability = classify_stability(synthetic_evaluation(0.90, 0.70))

    assert stability["verdict"] == "moderately_sensitive"


def test_classify_stability_calls_a_volatile_family_highly_sensitive() -> None:
    stability = classify_stability(synthetic_evaluation(0.50, 0.30))

    assert stability["verdict"] == "highly_sensitive"


def test_classify_stability_requires_both_criteria() -> None:
    """High correlation with poor tail overlap is not stable."""
    stability = classify_stability(synthetic_evaluation(0.99, 0.30))

    assert stability["verdict"] == "highly_sensitive"


def test_classify_stability_excludes_reference_corners() -> None:
    """
    The corners are far worse than any plausible scenario. If they leaked
    into the verdict, nothing would ever be called stable.
    """
    stability = classify_stability(synthetic_evaluation(0.99, 0.95))

    assert stability["verdict"] == "stable"
    assert stability["plausible_scenario_count"] == 1
    assert stability["reference_calibration"][
        "minimum_reference_spearman"
    ] == pytest.approx(0.2)


def test_classify_stability_reports_the_worst_scenario() -> None:
    stability = classify_stability(synthetic_evaluation(0.90, 0.70))

    assert stability["worst_spearman_scenario"] == "equal"
    assert stability["minimum_spearman_with_baseline"] == pytest.approx(0.90)


def test_classify_stability_reports_declared_thresholds() -> None:
    stability = classify_stability(synthetic_evaluation(0.99, 0.95))

    assert stability["thresholds"] == STABILITY_THRESHOLDS


def test_classify_stability_rejects_an_empty_family() -> None:
    evaluation = pd.DataFrame(
        [
            {
                "scenario": BASELINE_SCENARIO_NAME,
                "family": "baseline",
                "spearman_with_baseline": 1.0,
                "top_10pct_overlap_of_smaller": 1.0,
                "maximum_absolute_percentile_shift": 0.0,
                "median_absolute_percentile_shift": 0.0,
            }
        ]
    )

    with pytest.raises(ValueError, match="No plausible scenarios"):
        classify_stability(evaluation)