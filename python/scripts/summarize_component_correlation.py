from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.ingest import repository_path
from caprm.scoring import (
    COMPONENT_NAMES,
    DEFAULT_WEIGHTS,
    calculate_sha256,
    fema_component_score,
    terrain_absolute_component_score,
    terrain_relative_component_score,
    water_component_score,
)


COMPARISON_TOLERANCE = 1e-9

COMPONENT_SCORERS = {
    "fema": fema_component_score,
    "water": water_component_score,
    "terrain_absolute": terrain_absolute_component_score,
    "terrain_relative": terrain_relative_component_score,
}


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def build_component_frame(
    evidence: pd.DataFrame,
    terrain: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reconstruct the four scoring primitives on a shared property index.
    """
    merged = evidence.merge(
        terrain,
        on="property_id",
        how="inner",
        validate="one_to_one",
    )

    if len(merged) != len(evidence):
        raise ValueError("Component merge lost property rows.")

    components = pd.DataFrame(
        {name: COMPONENT_SCORERS[name](merged) for name in COMPONENT_NAMES}
    )

    components.index = pd.Index(merged["property_id"], name="property_id")

    return components


def verify_recomputed_composite(
    components: pd.DataFrame,
    index_path: Path | None,
) -> dict[str, Any]:
    """
    Confirm the components recompute the generated index.

    A regression check that the shipped artifact matches what the current
    scoring policy produces from the same evidence. A disagreement means
    the artifact is stale relative to the code.
    """
    recomputed = sum(
        DEFAULT_WEIGHTS[name] * components[name].to_numpy()
        for name in COMPONENT_NAMES
    )

    result: dict[str, Any] = {
        "description": (
            "The weighted sum of the four components must equal the "
            "generated exposure_index_0_100."
        ),
        "weights": DEFAULT_WEIGHTS,
        "weight_sum": float(sum(DEFAULT_WEIGHTS.values())),
        "tolerance": COMPARISON_TOLERANCE,
    }

    if index_path is None or not index_path.exists():
        result["compared_against_generated_index"] = False
        result["note"] = "Generated index not available; comparison skipped."
        return result

    generated = pd.read_csv(index_path, dtype={"property_id": "string"})
    generated = generated.set_index("property_id").reindex(components.index)

    if generated["exposure_index_0_100"].isna().any():
        raise ValueError(
            "Generated index does not cover every scored property."
        )

    difference = np.abs(
        recomputed - generated["exposure_index_0_100"].to_numpy()
    )

    result["compared_against_generated_index"] = True
    result["generated_index"] = display_path(index_path)
    result["maximum_absolute_difference"] = float(difference.max())
    result["agrees"] = bool(difference.max() <= COMPARISON_TOLERANCE)

    return result


def spearman_matrix(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    Rank correlation between every pair of columns.

    Spearman is used because the index is interpreted as a relative
    ranking, and because it is invariant under the monotone percentile
    transform already applied to three of the four components. Correlation
    between components therefore equals correlation between the raw
    evidence they came from.
    """
    matrix = frame.corr(method="spearman")

    return {
        str(row): {
            str(column): float(matrix.loc[row, column])
            for column in matrix.columns
        }
        for row in matrix.index
    }


def tail_overlap(
    frame: pd.DataFrame,
    fraction: float,
) -> dict[str, Any]:
    """
    Compare the highest-scoring properties selected by each component.

    Two components can be weakly correlated overall yet agree strongly on
    the high-exposure tail, which is the part that drives the ranking.

    Selection uses a quantile threshold with a >= comparison. Ties at the
    threshold are all retained, so a heavily tied component can select far
    more than the requested fraction. That is reported rather than broken
    arbitrarily, because an arbitrary tiebreak would invent a distinction
    the component does not make.
    """
    thresholds = {
        column: float(frame[column].quantile(1.0 - fraction))
        for column in frame.columns
    }

    selected = {
        column: set(frame.index[frame[column] >= thresholds[column]])
        for column in frame.columns
    }

    selection_records = {
        column: {
            "threshold": thresholds[column],
            "selected_count": int(len(selected[column])),
            "selected_fraction": float(len(selected[column]) / len(frame)),
            "requested_fraction": fraction,
            "tie_inflated": bool(
                len(selected[column]) > 1.5 * fraction * len(frame)
            ),
        }
        for column in frame.columns
    }

    pair_records: list[dict[str, Any]] = []
    columns = list(frame.columns)

    for left_position, left in enumerate(columns):
        for right in columns[left_position + 1:]:
            left_set = selected[left]
            right_set = selected[right]

            intersection = left_set & right_set
            union = left_set | right_set
            smaller = min(len(left_set), len(right_set))

            pair_records.append(
                {
                    "left": left,
                    "right": right,
                    "left_count": int(len(left_set)),
                    "right_count": int(len(right_set)),
                    "intersection_count": int(len(intersection)),
                    "jaccard": (
                        float(len(intersection) / len(union)) if union else None
                    ),
                    "overlap_of_smaller": (
                        float(len(intersection) / smaller) if smaller else None
                    ),
                }
            )

    return {
        "requested_fraction": fraction,
        "property_count": int(len(frame)),
        "selection": selection_records,
        "pairs": pair_records,
    }


def describe_component(series: pd.Series) -> dict[str, Any]:
    return {
        "minimum": float(series.min()),
        "maximum": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "standard_deviation": float(series.std()),
        "unique_value_count": int(series.nunique()),
        "tied_value_count": int(len(series) - series.nunique()),
    }


def build_summary(
    evidence_path: Path,
    terrain_path: Path,
    index_path: Path | None,
    tail_fractions: list[float],
) -> dict[str, Any]:
    evidence = pd.read_csv(evidence_path, dtype={"property_id": "string"})
    terrain = pd.read_csv(terrain_path, dtype={"property_id": "string"})

    components = build_component_frame(evidence, terrain)

    composite = pd.Series(
        sum(
            DEFAULT_WEIGHTS[name] * components[name].to_numpy()
            for name in COMPONENT_NAMES
        ),
        index=components.index,
        name="exposure_index",
    )

    with_composite = components.join(composite)

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "component_correlation_summary_v1",
        "purpose": (
            "Measure redundancy between the scoring components. Rank "
            "correlation and high-exposure tail overlap determine whether "
            "components carry independent information."
        ),
        "inputs": {
            "evidence": display_path(evidence_path),
            "evidence_sha256": calculate_sha256(evidence_path),
            "terrain": display_path(terrain_path),
            "terrain_sha256": calculate_sha256(terrain_path),
        },
        "property_count": int(len(components)),
        "arithmetic_checks": {
            "recomputed_composite": verify_recomputed_composite(
                components, index_path
            ),
        },
        "component_descriptions": {
            str(column): describe_component(components[column])
            for column in components.columns
        },
        "spearman_correlation": spearman_matrix(with_composite),
        "tail_overlap": [
            tail_overlap(components, fraction) for fraction in tail_fractions
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure rank correlation and tail overlap between the "
            "CAPRM-Flood scoring components. Read-only."
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
        "--index",
        default="outputs/index/property_exposure_index_countywide.csv",
        help=(
            "Generated index used to verify recomputation. Pass an empty "
            "string to skip the comparison."
        ),
    )

    parser.add_argument(
        "--tail-fraction",
        action="append",
        type=float,
        default=None,
        help="Tail fraction to compare. Repeatable. Defaults to 0.10 and 0.05.",
    )

    parser.add_argument(
        "--output",
        default="outputs/validation/component_correlation_summary.json",
    )

    args = parser.parse_args()

    index_path = repository_path(args.index) if args.index else None

    summary = build_summary(
        evidence_path=repository_path(args.evidence),
        terrain_path=repository_path(args.terrain),
        index_path=index_path,
        tail_fractions=args.tail_fraction or [0.10, 0.05],
    )

    output_path = repository_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()