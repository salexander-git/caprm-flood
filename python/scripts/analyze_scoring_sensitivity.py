from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.ingest import repository_path
from caprm.scoring import (
    COMPONENT_NAMES,
    DEFAULT_WEIGHTS,
    SCORING_POLICY_VERSION,
    build_exposure_index,
    calculate_sha256,
    validate_weights,
)
from caprm.sensitivity import (
    BASELINE_SCENARIO_NAME,
    DEFAULT_PERTURBATION_CONCENTRATION,
    DEFAULT_PERTURBATION_COUNT,
    DEFAULT_PERTURBATION_SEED,
    PLAUSIBLE_FAMILIES,
    build_scenarios,
    classify_stability,
    evaluate_scenarios,
    extract_components,
    extreme_properties,
    score_scenarios,
    summarize_property_variability,
)


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def format_float(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"

    if isinstance(value, float):
        return f"{value:.{digits}f}"

    return str(value)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"

    body = [
        "| " + " | ".join(format_float(value) for value in row) + " |"
        for row in rows
    ]

    return "\n".join([header_line, separator, *body])


def build_markdown_summary(
    manifest: dict[str, Any],
    evaluation: pd.DataFrame,
) -> str:
    stability = manifest["stability"]
    calibration = stability["reference_calibration"]

    lines: list[str] = []

    lines.append("# Scoring Sensitivity Summary")
    lines.append("")
    lines.append(f"- Scoring policy: `{manifest['scoring_policy_version']}`")
    lines.append(f"- Properties: {manifest['property_count']}")
    lines.append(
        f"- Scenarios evaluated: {manifest['scenario_count']} "
        f"({stability['plausible_scenario_count']} plausible, "
        f"{manifest['reference_scenario_count']} reference corners)"
    )
    lines.append("")

    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{stability['verdict'].replace('_', ' ').upper()}**")
    lines.append("")
    lines.append(
        "The verdict is driven by the worst plausible scenario, not the "
        "average. An index that survives most reweightings but collapses "
        "under one plausible reweighting is not stable."
    )
    lines.append("")
    lines.append(
        markdown_table(
            ["Measure", "Value", "Scenario"],
            [
                [
                    "Minimum Spearman vs baseline",
                    stability["minimum_spearman_with_baseline"],
                    stability["worst_spearman_scenario"],
                ],
                [
                    "Median Spearman vs baseline",
                    stability["median_spearman_with_baseline"],
                    "",
                ],
                [
                    "Minimum top-decile overlap",
                    stability["minimum_top_decile_overlap"],
                    stability["worst_top_decile_overlap_scenario"],
                ],
                [
                    "Median top-decile overlap",
                    stability["median_top_decile_overlap"],
                    "",
                ],
                [
                    "Maximum percentile shift",
                    stability["maximum_percentile_shift"],
                    "",
                ],
                [
                    "Median of median percentile shift",
                    stability["median_of_median_percentile_shift"],
                    "",
                ],
            ],
        )
    )
    lines.append("")

    lines.append("## Declared thresholds")
    lines.append("")
    lines.append(stability["thresholds_note"])
    lines.append("")
    lines.append(
        markdown_table(
            ["Verdict", "Minimum Spearman", "Minimum top-decile overlap"],
            [
                [
                    name,
                    values["minimum_spearman"],
                    values["minimum_top_decile_overlap"],
                ]
                for name, values in stability["thresholds"].items()
            ],
        )
    )
    lines.append("")

    lines.append("## Metric calibration")
    lines.append("")
    lines.append(calibration["description"])
    lines.append("")
    lines.append(
        markdown_table(
            ["Measure", "Value"],
            [
                [
                    "Minimum reference-corner Spearman",
                    calibration["minimum_reference_spearman"],
                ],
                [
                    "Maximum reference-corner Spearman",
                    calibration["maximum_reference_spearman"],
                ],
                [
                    "Minimum reference-corner top-decile overlap",
                    calibration["minimum_reference_top_decile_overlap"],
                ],
            ],
        )
    )
    lines.append("")

    lines.append("## Scenarios")
    lines.append("")

    display = evaluation.sort_values(
        ["family", "scenario"],
        kind="stable",
    )

    lines.append(
        markdown_table(
            [
                "Scenario",
                "Family",
                *[f"w({name})" for name in COMPONENT_NAMES],
                "Spearman",
                "Top decile",
                "Top 5%",
                "Median shift",
                "Max shift",
            ],
            [
                [
                    row.scenario,
                    row.family,
                    *[
                        getattr(row, f"weight_{name}")
                        for name in COMPONENT_NAMES
                    ],
                    row.spearman_with_baseline,
                    row.top_10pct_overlap_of_smaller,
                    row.top_5pct_overlap_of_smaller,
                    row.median_absolute_percentile_shift,
                    row.maximum_absolute_percentile_shift,
                ]
                for row in display.itertuples(index=False)
            ],
        )
    )
    lines.append("")

    lines.append("## Interpretation boundary")
    lines.append("")
    lines.append(manifest["interpretation"])
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure how far the countywide exposure ranking moves under "
            "alternative component weights."
        )
    )

    parser.add_argument(
        "--evidence",
        default="outputs/evidence/property_flood_evidence_countywide.csv",
    )

    parser.add_argument(
        "--terrain",
        default="outputs/evidence/property_terrain_evidence_countywide.csv",
    )

    parser.add_argument(
        "--baseline-weights",
        default=None,
        help=(
            "JSON object of baseline component weights. Defaults to "
            "caprm.scoring.DEFAULT_WEIGHTS."
        ),
    )

    parser.add_argument(
        "--perturbation-count",
        type=int,
        default=DEFAULT_PERTURBATION_COUNT,
    )

    parser.add_argument(
        "--perturbation-seed",
        type=int,
        default=DEFAULT_PERTURBATION_SEED,
    )

    parser.add_argument(
        "--perturbation-concentration",
        type=float,
        default=DEFAULT_PERTURBATION_CONCENTRATION,
    )

    parser.add_argument(
        "--extreme-property-count",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--distance-crs",
        default="EPSG:26918",
    )

    parser.add_argument(
        "--terrain-crs",
        default="EPSG:26918",
    )

    parser.add_argument(
        "--summary-output",
        default="outputs/analysis/scoring_sensitivity_summary.csv",
    )

    parser.add_argument(
        "--property-shifts-output",
        default="outputs/analysis/scoring_sensitivity_property_shifts.csv",
    )

    parser.add_argument(
        "--manifest-output",
        default="outputs/validation/scoring_sensitivity_manifest.json",
    )

    parser.add_argument(
        "--markdown-output",
        default="outputs/validation/scoring_sensitivity_summary.md",
    )

    args = parser.parse_args()

    baseline_weights = validate_weights(
        json.loads(args.baseline_weights)
        if args.baseline_weights
        else DEFAULT_WEIGHTS
    )

    evidence_path = repository_path(args.evidence)
    terrain_path = repository_path(args.terrain)

    evidence = pd.read_csv(evidence_path, dtype={"property_id": "string"})
    terrain = pd.read_csv(terrain_path, dtype={"property_id": "string"})

    # Build the index once. Component scores do not depend on the weights,
    # so every scenario reweights the same four columns rather than
    # rerunning the pipeline. This also reuses the validation and CRS gates
    # in build_exposure_index rather than duplicating them.
    index = build_exposure_index(
        evidence=evidence,
        terrain=terrain,
        expected_distance_crs=args.distance_crs,
        expected_terrain_crs=args.terrain_crs,
        weights=baseline_weights,
    )

    components = extract_components(index)

    scenarios = build_scenarios(
        baseline=baseline_weights,
        perturbation_count=args.perturbation_count,
        seed=args.perturbation_seed,
        concentration=args.perturbation_concentration,
    )

    percentiles = score_scenarios(components, scenarios)

    evaluation = evaluate_scenarios(percentiles, scenarios)

    plausible_names = [
        scenario["name"]
        for scenario in scenarios
        if scenario["family"] in PLAUSIBLE_FAMILIES
    ]

    variability = summarize_property_variability(percentiles, plausible_names)

    stability = classify_stability(evaluation)

    summary_path = repository_path(args.summary_output)
    shifts_path = repository_path(args.property_shifts_output)
    manifest_path = repository_path(args.manifest_output)
    markdown_path = repository_path(args.markdown_output)

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    shifts_path.parent.mkdir(parents=True, exist_ok=True)

    evaluation.to_csv(summary_path, index=False, float_format="%.12f")
    variability.to_csv(shifts_path, float_format="%.12f")

    reference_count = int(
        len(scenarios) - len(plausible_names)
    )

    manifest: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "scoring_sensitivity_v1",
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "input_evidence": display_path(evidence_path),
        "input_evidence_sha256": calculate_sha256(evidence_path),
        "input_terrain": display_path(terrain_path),
        "input_terrain_sha256": calculate_sha256(terrain_path),
        "property_count": int(len(components)),
        "baseline_weights": baseline_weights,
        "baseline_scenario": BASELINE_SCENARIO_NAME,
        "scenario_count": int(len(scenarios)),
        "plausible_scenario_count": int(len(plausible_names)),
        "reference_scenario_count": reference_count,
        "perturbation": {
            "count": int(args.perturbation_count),
            "seed": int(args.perturbation_seed),
            "concentration": float(args.perturbation_concentration),
            "distribution": "dirichlet",
            "note": (
                "Alpha is concentration times the baseline weights, so the "
                "distribution is centered on the baseline and supported "
                "exactly on the weight simplex. The seed makes the scenario "
                "family reproducible."
            ),
        },
        "stability": stability,
        "property_variability": {
            "median_percentile_range": float(
                variability["percentile_range"].median()
            ),
            "mean_percentile_range": float(
                variability["percentile_range"].mean()
            ),
            "p95_percentile_range": float(
                variability["percentile_range"].quantile(0.95)
            ),
            "maximum_percentile_range": float(
                variability["percentile_range"].max()
            ),
            "properties_with_range_over_10": int(
                variability["percentile_range"].gt(10.0).sum()
            ),
            "properties_with_range_over_25": int(
                variability["percentile_range"].gt(25.0).sum()
            ),
            "note": (
                "Computed across plausible scenarios only. Reference corners "
                "are excluded because including implausible configurations "
                "would inflate the apparent instability of every property."
            ),
        },
        "extreme_properties": extreme_properties(
            variability,
            count=args.extreme_property_count,
        ),
        "outputs": {
            "scenario_summary": display_path(summary_path),
            "scenario_summary_sha256": calculate_sha256(summary_path),
            "property_shifts": display_path(shifts_path),
            "property_shifts_sha256": calculate_sha256(shifts_path),
        },
        "interpretation": (
            "Sensitivity measures how far the countywide ranking moves when "
            "component weights change. It does not establish that the "
            "weights are correct, that the components are the right "
            "components, or that the index estimates flood probability. A "
            "stable ranking under reweighting means the conclusion does not "
            "hinge on the weight choice, not that the conclusion is right."
        ),
    }

    markdown = build_markdown_summary(manifest, evaluation)

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()