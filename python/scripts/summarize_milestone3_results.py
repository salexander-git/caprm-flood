from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.ingest import repository_path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_float(value: Any, digits: int = 3) -> str:
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


def build_summary(
    terrain_manifest: dict[str, Any],
    index_manifest: dict[str, Any],
) -> str:
    terrain_summary = terrain_manifest["summary"]
    index_summary = index_manifest["summary"]

    lines: list[str] = []

    lines.append("# Milestone 3 Results Summary")
    lines.append("")

    lines.append("## Generated Outputs")
    lines.append("")
    lines.append(
        markdown_table(
            ["Output", "Path", "SHA-256"],
            [
                [
                    "Terrain evidence",
                    terrain_manifest["output"],
                    terrain_manifest["output_sha256"],
                ],
                [
                    "Exposure index",
                    index_manifest["output"],
                    index_manifest["output_sha256"],
                ],
            ],
        )
    )
    lines.append("")

    lines.append("## Terrain Evidence")
    lines.append("")
    lines.append(
        markdown_table(
            ["Metric", "Value"],
            [
                ["Property count", terrain_summary["property_count"]],
                ["Unique property IDs", terrain_summary["unique_property_ids"]],
                ["Minimum elevation m", terrain_summary["minimum_elevation_m"]],
                ["Maximum elevation m", terrain_summary["maximum_elevation_m"]],
                ["Mean elevation m", terrain_summary["mean_elevation_m"]],
                ["Median elevation m", terrain_summary["median_elevation_m"]],
                [
                    "Minimum relative elevation m",
                    terrain_summary["minimum_relative_elevation_m"],
                ],
                [
                    "Maximum relative elevation m",
                    terrain_summary["maximum_relative_elevation_m"],
                ],
                [
                    "Mean relative elevation m",
                    terrain_summary["mean_relative_elevation_m"],
                ],
                [
                    "Median relative elevation m",
                    terrain_summary["median_relative_elevation_m"],
                ],
                ["Missing slope count", terrain_summary["missing_slope_count"]],
                ["Mean slope degrees", terrain_summary["mean_slope_degrees"]],
                ["Median slope degrees", terrain_summary["median_slope_degrees"]],
            ],
        )
    )
    lines.append("")

    lines.append("## Preliminary Exposure Index")
    lines.append("")
    lines.append(
        markdown_table(
            ["Metric", "Value"],
            [
                ["Property count", index_summary["property_count"]],
                ["Unique property IDs", index_summary["unique_property_ids"]],
                [
                    "Minimum exposure index",
                    index_summary["minimum_exposure_index"],
                ],
                [
                    "Maximum exposure index",
                    index_summary["maximum_exposure_index"],
                ],
                ["Mean exposure index", index_summary["mean_exposure_index"]],
                ["Median exposure index", index_summary["median_exposure_index"]],
                [
                    "Minimum exposure percentile",
                    index_summary["minimum_exposure_percentile"],
                ],
                [
                    "Maximum exposure percentile",
                    index_summary["maximum_exposure_percentile"],
                ],
                ["Mean FEMA component", index_summary["mean_fema_component"]],
                ["Mean water component", index_summary["mean_water_component"]],
                [
                    "Mean terrain component",
                    index_summary["mean_terrain_component"],
                ],
            ],
        )
    )
    lines.append("")

    lines.append("## Scoring Policy")
    lines.append("")
    lines.append(
        markdown_table(
            ["Component", "Weight"],
            [
                ["FEMA flood-zone evidence", index_manifest["weights"]["fema"]],
                ["Nearest-water evidence", index_manifest["weights"]["water"]],
                ["Terrain evidence", index_manifest["weights"]["terrain"]],
            ],
        )
    )
    lines.append("")

    lines.append("## Interpretation Boundary")
    lines.append("")
    lines.append(f"- Terrain: {terrain_manifest['interpretation']}")
    lines.append(f"- Exposure index: {index_manifest['interpretation']}")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a report-ready Markdown summary of Milestone 3 "
            "terrain and exposure-index outputs."
        )
    )

    parser.add_argument(
        "--terrain-manifest",
        default="outputs/validation/property_terrain_evidence_countywide_manifest.json",
    )

    parser.add_argument(
        "--index-manifest",
        default="outputs/validation/property_exposure_index_countywide_manifest.json",
    )

    parser.add_argument(
        "--output",
        default="outputs/validation/milestone3_results_summary.md",
    )

    args = parser.parse_args()

    terrain_manifest_path = repository_path(args.terrain_manifest)
    index_manifest_path = repository_path(args.index_manifest)
    output_path = repository_path(args.output)

    terrain_manifest = load_json(terrain_manifest_path)
    index_manifest = load_json(index_manifest_path)

    summary = build_summary(
        terrain_manifest=terrain_manifest,
        index_manifest=index_manifest,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")

    print(summary)


if __name__ == "__main__":
    main()