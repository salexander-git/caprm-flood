from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from caprm.scoring import (
    COMPONENT_COLUMNS,
    COMPONENT_NAMES,
    COMPOSITE_DECIMALS,
    DEFAULT_WEIGHTS,
    percentile_score,
    spearman_correlation,
    validate_weights,
)


# Stability thresholds, declared before any result was measured.
#
# These are a judgement call and there is no external standard for them.
# They are fixed here rather than chosen after inspecting the output,
# because a threshold selected to fit the result it is meant to judge makes
# the verdict unfalsifiable.
#
# A scenario family is called stable only if EVERY plausible scenario stays
# above the threshold. The worst case is the claim, not the average.
STABILITY_THRESHOLDS = {
    "stable": {
        "minimum_spearman": 0.95,
        "minimum_top_decile_overlap": 0.80,
    },
    "moderately_sensitive": {
        "minimum_spearman": 0.85,
        "minimum_top_decile_overlap": 0.60,
    },
}

# A component is emphasized by doubling its weight and renormalizing, and
# deemphasized by halving it. This keeps every scenario on the simplex and
# expresses an interpretable question: what if we believed this component
# mattered twice as much?
DEFAULT_EMPHASIS_FACTOR = 2.0
DEFAULT_DEEMPHASIS_FACTOR = 0.5

# Dirichlet perturbations around the baseline. The Dirichlet distribution
# is the natural choice because its support is exactly the weight simplex,
# and its mean is the baseline when alpha is proportional to the baseline.
#
# Concentration controls how tight the cloud is. At 200 the marginal
# standard deviation of a weight near 0.40 is roughly 0.035, so fema ranges
# about 0.40 +/- 0.07. That is a small perturbation, not a redesign.
DEFAULT_PERTURBATION_COUNT = 24
DEFAULT_PERTURBATION_SEED = 20260716
DEFAULT_PERTURBATION_CONCENTRATION = 200.0

TAIL_FRACTIONS = (0.10, 0.05)

BASELINE_SCENARIO_NAME = "baseline"

# Scenarios that represent weightings a reasonable person might choose.
# Reference corners are excluded: they exist to calibrate the metrics, not
# to be defended as configurations.
PLAUSIBLE_FAMILIES = ("baseline", "structured", "perturbation")

REFERENCE_FAMILY = "reference_corner"


def rescale(
    baseline: dict[str, float],
    names: list[str],
    factor: float,
) -> dict[str, float]:
    """
    Scale selected weights by a factor and renormalize to sum 1.0.

    Renormalizing rather than clamping keeps the result on the weight
    simplex, so every scenario remains a valid configuration.
    """
    adjusted = dict(baseline)

    for name in names:
        if name not in adjusted:
            raise ValueError(f"Unknown component: {name}")

        adjusted[name] = adjusted[name] * factor

    total = sum(adjusted.values())

    if total <= 0:
        raise ValueError(
            "Rescaling produced a zero or negative weight total."
        )

    return {key: value / total for key, value in adjusted.items()}


def equal_weights() -> dict[str, float]:
    share = 1.0 / len(COMPONENT_NAMES)
    return {name: share for name in COMPONENT_NAMES}


def single_component_weights(name: str) -> dict[str, float]:
    if name not in COMPONENT_NAMES:
        raise ValueError(f"Unknown component: {name}")

    return {key: (1.0 if key == name else 0.0) for key in COMPONENT_NAMES}


def build_scenarios(
    baseline: dict[str, float] | None = None,
    perturbation_count: int = DEFAULT_PERTURBATION_COUNT,
    seed: int = DEFAULT_PERTURBATION_SEED,
    concentration: float = DEFAULT_PERTURBATION_CONCENTRATION,
    emphasis_factor: float = DEFAULT_EMPHASIS_FACTOR,
    deemphasis_factor: float = DEFAULT_DEEMPHASIS_FACTOR,
) -> list[dict[str, Any]]:
    """
    Construct the weight scenarios to evaluate.

    The family is deliberately structured rather than a combinatorial
    search. Each scenario answers a question someone might actually ask,
    and the seeded perturbations make the result reproducible.
    """
    if perturbation_count < 0:
        raise ValueError("perturbation_count cannot be negative.")

    if concentration <= 0:
        raise ValueError("concentration must be greater than zero.")

    baseline_weights = validate_weights(baseline or DEFAULT_WEIGHTS)

    scenarios: list[dict[str, Any]] = [
        {
            "name": BASELINE_SCENARIO_NAME,
            "family": "baseline",
            "description": "The current default configuration.",
            "weights": baseline_weights,
        },
        {
            "name": "equal",
            "family": "structured",
            "description": "Every component weighted identically.",
            "weights": equal_weights(),
        },
    ]

    for name in COMPONENT_NAMES:
        scenarios.append(
            {
                "name": f"{name}_emphasized",
                "family": "structured",
                "description": (
                    f"{name} weight multiplied by {emphasis_factor}, "
                    "renormalized."
                ),
                "weights": rescale(baseline_weights, [name], emphasis_factor),
            }
        )
        scenarios.append(
            {
                "name": f"{name}_deemphasized",
                "family": "structured",
                "description": (
                    f"{name} weight multiplied by {deemphasis_factor}, "
                    "renormalized."
                ),
                "weights": rescale(
                    baseline_weights, [name], deemphasis_factor
                ),
            }
        )

    # The two terrain components share an evidence family, so a reviewer
    # may reasonably ask what happens if terrain as a whole matters more.
    terrain_names = [
        name for name in COMPONENT_NAMES if name.startswith("terrain_")
    ]

    if terrain_names:
        scenarios.append(
            {
                "name": "terrain_family_emphasized",
                "family": "structured",
                "description": (
                    "Both terrain component weights multiplied by "
                    f"{emphasis_factor}, renormalized."
                ),
                "weights": rescale(
                    baseline_weights, terrain_names, emphasis_factor
                ),
            }
        )
        scenarios.append(
            {
                "name": "terrain_family_deemphasized",
                "family": "structured",
                "description": (
                    "Both terrain component weights multiplied by "
                    f"{deemphasis_factor}, renormalized."
                ),
                "weights": rescale(
                    baseline_weights, terrain_names, deemphasis_factor
                ),
            }
        )

    if perturbation_count > 0:
        generator = np.random.default_rng(seed)

        alpha = concentration * np.array(
            [baseline_weights[name] for name in COMPONENT_NAMES],
            dtype="float64",
        )

        samples = generator.dirichlet(alpha, size=perturbation_count)

        for position, sample in enumerate(samples):
            scenarios.append(
                {
                    "name": f"perturbation_{position:03d}",
                    "family": "perturbation",
                    "description": (
                        "Dirichlet sample around the baseline at "
                        f"concentration {concentration}."
                    ),
                    "weights": {
                        name: float(value)
                        for name, value in zip(COMPONENT_NAMES, sample)
                    },
                }
            )

    # Reference corners. These are not plausible configurations. They exist
    # to calibrate the metrics: without knowing what a genuinely different
    # weighting does to rank correlation, a high correlation among plausible
    # scenarios cannot be interpreted.
    for name in COMPONENT_NAMES:
        scenarios.append(
            {
                "name": f"{name}_only",
                "family": REFERENCE_FAMILY,
                "description": (
                    f"All weight on {name}. Calibration reference, not a "
                    "proposed configuration."
                ),
                "weights": single_component_weights(name),
            }
        )

    return scenarios


def extract_components(index: pd.DataFrame) -> pd.DataFrame:
    """
    Pull the four component scores out of a generated index.

    Component values do not depend on the weights, so they are computed
    once and reused across every scenario. Only the weighted combination
    changes.
    """
    missing = [
        COMPONENT_COLUMNS[name]
        for name in COMPONENT_NAMES
        if COMPONENT_COLUMNS[name] not in index.columns
    ]

    if missing:
        raise ValueError(f"Index is missing component columns: {missing}")

    components = pd.DataFrame(
        {name: index[COMPONENT_COLUMNS[name]].to_numpy() for name in COMPONENT_NAMES},
        index=pd.Index(index["property_id"], name="property_id"),
    )

    return components


def composite_score(
    components: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    return sum(
        weights[name] * components[name] for name in COMPONENT_NAMES
    )


def score_scenarios(
    components: pd.DataFrame,
    scenarios: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Compute the countywide percentile for every scenario.

    The composite is rounded before ranking, exactly as
    build_exposure_index does, so that properties tied in substance share a
    rank in every scenario rather than being ordered by float noise. A
    scenario ranking built on a different rule than the baseline's would
    not be comparable to it.

    Returns one column per scenario, indexed by property_id.
    """
    percentiles: dict[str, pd.Series] = {}

    for scenario in scenarios:
        composite = composite_score(
            components, scenario["weights"]
        ).round(COMPOSITE_DECIMALS)

        percentiles[scenario["name"]] = percentile_score(
            composite,
            higher_value_is_higher_exposure=True,
        )

    return pd.DataFrame(percentiles, index=components.index)


def tail_members(percentile: pd.Series, fraction: float) -> set:
    """
    The properties in the top fraction by percentile.

    The percentile column is itself the rank expressed on 0-100, so no
    quantile estimation is needed: the top decile is exactly
    percentile > 90.

    The comparison is strictly greater than, not >=. A property whose
    percentile is exactly (1 - fraction) * 100 sits at rank (1 - f) * n,
    which is the top of the bottom (1 - f) share, not the bottom of the
    top f share. Including it would return f * n + 1 properties whenever
    (1 - f) * n lands on an integer.

    Tied properties share an average rank, so a tie group is either
    entirely inside or entirely outside the tail. Ties are never split.
    """
    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must lie strictly between 0 and 1.")

    threshold = 100.0 * (1.0 - fraction)

    return set(percentile.index[percentile > threshold])


def compare_to_baseline(
    baseline: pd.Series,
    scenario: pd.Series,
    tail_fractions: tuple[float, ...] = TAIL_FRACTIONS,
) -> dict[str, Any]:
    """
    Measure how far a scenario's ranking moves from the baseline.

    Rank-based metrics are used because the index is interpreted as a
    relative ranking. A change in raw score that preserves order does not
    change any conclusion drawn from the index.
    """
    shift = (scenario - baseline).abs()

    record: dict[str, Any] = {
        "spearman_with_baseline": spearman_correlation(baseline, scenario),
        "median_absolute_percentile_shift": float(shift.median()),
        "mean_absolute_percentile_shift": float(shift.mean()),
        "p95_absolute_percentile_shift": float(shift.quantile(0.95)),
        "maximum_absolute_percentile_shift": float(shift.max()),
        "properties_shifted_over_10_percentile": int(shift.gt(10.0).sum()),
        "properties_shifted_over_25_percentile": int(shift.gt(25.0).sum()),
    }

    for fraction in tail_fractions:
        label = f"top_{int(round(fraction * 100))}pct"

        left = tail_members(baseline, fraction)
        right = tail_members(scenario, fraction)

        intersection = left & right
        union = left | right
        smaller = min(len(left), len(right))

        record[f"{label}_baseline_count"] = int(len(left))
        record[f"{label}_scenario_count"] = int(len(right))
        record[f"{label}_retained_count"] = int(len(intersection))
        record[f"{label}_jaccard"] = (
            float(len(intersection) / len(union)) if union else None
        )
        record[f"{label}_overlap_of_smaller"] = (
            float(len(intersection) / smaller) if smaller else None
        )

    return record


def evaluate_scenarios(
    percentiles: pd.DataFrame,
    scenarios: list[dict[str, Any]],
    tail_fractions: tuple[float, ...] = TAIL_FRACTIONS,
) -> pd.DataFrame:
    """
    One row per scenario: its weights and its distance from the baseline.
    """
    baseline = percentiles[BASELINE_SCENARIO_NAME]

    records: list[dict[str, Any]] = []

    for scenario in scenarios:
        record: dict[str, Any] = {
            "scenario": scenario["name"],
            "family": scenario["family"],
            "description": scenario["description"],
        }

        for name in COMPONENT_NAMES:
            record[f"weight_{name}"] = float(scenario["weights"][name])

        record.update(
            compare_to_baseline(
                baseline,
                percentiles[scenario["name"]],
                tail_fractions=tail_fractions,
            )
        )

        records.append(record)

    return pd.DataFrame.from_records(records)


def summarize_property_variability(
    percentiles: pd.DataFrame,
    scenario_names: list[str],
) -> pd.DataFrame:
    """
    Per-property rank variability across the plausible scenarios.

    Reference corners are excluded by the caller. Including implausible
    configurations would inflate the apparent instability of every
    property.
    """
    if BASELINE_SCENARIO_NAME not in percentiles.columns:
        raise ValueError("Percentile frame has no baseline column.")

    subset = percentiles[scenario_names]

    minimum = subset.min(axis=1)
    maximum = subset.max(axis=1)

    return pd.DataFrame(
        {
            "baseline_percentile": percentiles[BASELINE_SCENARIO_NAME],
            "minimum_percentile": minimum,
            "maximum_percentile": maximum,
            "mean_percentile": subset.mean(axis=1),
            "standard_deviation_percentile": subset.std(axis=1),
            "percentile_range": maximum - minimum,
        }
    )


def extreme_properties(
    variability: pd.DataFrame,
    count: int = 20,
) -> dict[str, list[dict[str, Any]]]:
    """
    Properties at the edges of the stability distribution.

    Ordering ties are broken by the property_id index, which is sorted, so
    the selection is deterministic.
    """

    def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {
                "property_id": str(property_id),
                **{
                    column: float(value)
                    for column, value in row.items()
                },
            }
            for property_id, row in frame.iterrows()
        ]

    return {
        "most_unstable": records(
            variability.nlargest(count, "percentile_range", keep="first")
        ),
        "consistently_high": records(
            variability.nlargest(count, "minimum_percentile", keep="first")
        ),
        "consistently_low": records(
            variability.nsmallest(count, "maximum_percentile", keep="first")
        ),
    }


def classify_stability(
    evaluation: pd.DataFrame,
    tail_label: str = "top_10pct",
) -> dict[str, Any]:
    """
    Reduce the measured scenarios to a single verdict.

    The verdict is driven by the WORST plausible scenario, not the average.
    An index that is stable under most reweightings but collapses under one
    plausible reweighting is not stable.
    """
    plausible = evaluation[
        evaluation["family"].isin(PLAUSIBLE_FAMILIES)
        & evaluation["scenario"].ne(BASELINE_SCENARIO_NAME)
    ]

    if plausible.empty:
        raise ValueError("No plausible scenarios to classify.")

    overlap_column = f"{tail_label}_overlap_of_smaller"

    spearman_values = plausible["spearman_with_baseline"].dropna()
    overlap_values = plausible[overlap_column].dropna()

    if spearman_values.empty or overlap_values.empty:
        raise ValueError("Stability metrics are unavailable.")

    minimum_spearman = float(spearman_values.min())
    minimum_overlap = float(overlap_values.min())

    stable = STABILITY_THRESHOLDS["stable"]
    moderate = STABILITY_THRESHOLDS["moderately_sensitive"]

    if (
        minimum_spearman >= stable["minimum_spearman"]
        and minimum_overlap >= stable["minimum_top_decile_overlap"]
    ):
        verdict = "stable"
    elif (
        minimum_spearman >= moderate["minimum_spearman"]
        and minimum_overlap >= moderate["minimum_top_decile_overlap"]
    ):
        verdict = "moderately_sensitive"
    else:
        verdict = "highly_sensitive"

    worst_spearman_scenario = plausible.loc[
        spearman_values.idxmin(), "scenario"
    ]
    worst_overlap_scenario = plausible.loc[overlap_values.idxmin(), "scenario"]

    reference = evaluation[evaluation["family"].eq(REFERENCE_FAMILY)]

    calibration: dict[str, Any] = {
        "description": (
            "Reference corners place all weight on one component. They are "
            "not proposed configurations. They establish what a genuinely "
            "different weighting does to these metrics, without which a "
            "high correlation among plausible scenarios cannot be "
            "interpreted."
        ),
        "minimum_reference_spearman": (
            float(reference["spearman_with_baseline"].min())
            if not reference.empty
            else None
        ),
        "maximum_reference_spearman": (
            float(reference["spearman_with_baseline"].max())
            if not reference.empty
            else None
        ),
        "minimum_reference_top_decile_overlap": (
            float(reference[overlap_column].min())
            if not reference.empty
            else None
        ),
    }

    return {
        "verdict": verdict,
        "thresholds": STABILITY_THRESHOLDS,
        "thresholds_note": (
            "Declared in caprm.sensitivity before any result was measured. "
            "They are a judgement call with no external standard."
        ),
        "plausible_scenario_count": int(len(plausible)),
        "minimum_spearman_with_baseline": minimum_spearman,
        "worst_spearman_scenario": str(worst_spearman_scenario),
        "median_spearman_with_baseline": float(spearman_values.median()),
        "minimum_top_decile_overlap": minimum_overlap,
        "worst_top_decile_overlap_scenario": str(worst_overlap_scenario),
        "median_top_decile_overlap": float(overlap_values.median()),
        "maximum_percentile_shift": float(
            plausible["maximum_absolute_percentile_shift"].max()
        ),
        "median_of_median_percentile_shift": float(
            plausible["median_absolute_percentile_shift"].median()
        ),
        "reference_calibration": calibration,
    }