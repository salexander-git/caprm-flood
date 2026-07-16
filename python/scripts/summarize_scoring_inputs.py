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
    EVIDENCE_REQUIRED_COLUMNS,
    TERRAIN_REQUIRED_COLUMNS,
    calculate_sha256,
    normalize_string,
    strict_bool,
)


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def manifest_key_structure(path: Path) -> dict[str, Any]:
    """Report a manifest's key layout without assuming a schema."""
    if not path.exists():
        return {"path": display_path(path), "exists": False}

    manifest = json.loads(path.read_text(encoding="utf-8"))
    summary = manifest.get("summary")

    return {
        "path": display_path(path),
        "exists": True,
        "top_level_keys": sorted(manifest),
        "has_summary_block": isinstance(summary, dict),
        "summary_keys": sorted(summary) if isinstance(summary, dict) else None,
    }


def column_presence(
    dataframe: pd.DataFrame,
    required: set[str],
) -> dict[str, Any]:
    return {
        "present_columns": sorted(dataframe.columns),
        "required_columns": sorted(required),
        "missing_required_columns": sorted(required - set(dataframe.columns)),
    }


def numeric_domain(series: pd.Series) -> dict[str, Any]:
    """Describe the observed range of one numeric scoring input."""
    numeric = pd.to_numeric(series, errors="coerce")
    nonnull = numeric.dropna()

    return {
        "row_count": int(len(numeric)),
        "null_count": int(numeric.isna().sum()),
        "unique_value_count": int(nonnull.nunique()),
        "minimum": float(nonnull.min()) if len(nonnull) else None,
        "maximum": float(nonnull.max()) if len(nonnull) else None,
        "mean": float(nonnull.mean()) if len(nonnull) else None,
        "median": float(nonnull.median()) if len(nonnull) else None,
        "zero_value_count": int(nonnull.eq(0.0).sum()),
    }


def fema_domain(evidence: pd.DataFrame) -> dict[str, Any]:
    """Report FEMA inputs exactly as fema_component_score parses them."""
    zones = normalize_string(evidence["fema_zone"]).str.upper()
    matched = strict_bool(evidence["matched_fema_polygon"], "matched_fema_polygon")
    is_sfha = strict_bool(evidence["is_sfha"], "is_sfha")

    frame = pd.DataFrame(
        {
            "matched_fema_polygon": matched,
            "fema_zone": zones.fillna("<missing>"),
            "is_sfha": is_sfha,
        }
    )

    counts = (
        frame.groupby(
            ["matched_fema_polygon", "fema_zone", "is_sfha"],
            dropna=False,
        )
        .size()
        .reset_index(name="property_count")
        .sort_values(
            ["property_count", "fema_zone"],
            ascending=[False, True],
            kind="stable",
        )
    )

    return {
        "distinct_normalized_zone_values": sorted(
            frame["fema_zone"].unique().tolist()
        ),
        "matched_property_count": int(matched.sum()),
        "unmatched_property_count": int((~matched).sum()),
        "sfha_property_count": int(is_sfha.sum()),
        "matched_zone_sfha_counts": [
            {
                "matched_fema_polygon": bool(row.matched_fema_polygon),
                "fema_zone": str(row.fema_zone),
                "is_sfha": bool(row.is_sfha),
                "property_count": int(row.property_count),
            }
            for row in counts.itertuples(index=False)
        ],
    }


def build_summary(
    evidence_path: Path,
    terrain_path: Path,
    manifest_paths: list[Path],
) -> dict[str, Any]:
    evidence = pd.read_csv(evidence_path, dtype={"property_id": "string"})
    terrain = pd.read_csv(terrain_path, dtype={"property_id": "string"})

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "scoring_inputs_summary_v1",
        "purpose": (
            "Read-only description of the evidence and terrain inputs "
            "consumed by caprm.scoring, used to document current scoring "
            "behavior against measured values rather than assumptions."
        ),
        "inputs": {
            "evidence": display_path(evidence_path),
            "evidence_sha256": calculate_sha256(evidence_path),
            "terrain": display_path(terrain_path),
            "terrain_sha256": calculate_sha256(terrain_path),
        },
        "evidence_table": {
            "row_count": int(len(evidence)),
            "unique_property_ids": int(evidence["property_id"].nunique()),
            "columns": column_presence(evidence, EVIDENCE_REQUIRED_COLUMNS),
            "distance_crs_values": sorted(
                normalize_string(evidence["distance_crs"]).dropna().unique().tolist()
            ),
            "fema": fema_domain(evidence),
            "nearest_water_distance_m": numeric_domain(
                evidence["nearest_water_distance_m"]
            ),
        },
        "terrain_table": {
            "row_count": int(len(terrain)),
            "unique_property_ids": int(terrain["property_id"].nunique()),
            "columns": column_presence(terrain, TERRAIN_REQUIRED_COLUMNS),
            "terrain_crs_values": sorted(
                normalize_string(terrain["terrain_crs"]).dropna().unique().tolist()
            ),
            "terrain_elevation_m": numeric_domain(terrain["terrain_elevation_m"]),
            "terrain_relative_elevation_m": numeric_domain(
                terrain["terrain_relative_elevation_m"]
            ),
            "terrain_slope_degrees": numeric_domain(terrain["terrain_slope_degrees"]),
        },
        "manifest_structure": [
            manifest_key_structure(path) for path in manifest_paths
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize the evidence and terrain inputs consumed by the "
            "CAPRM-Flood scoring layer. Read-only."
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
        "--manifest",
        action="append",
        default=None,
        help="Manifest to describe. Repeatable.",
    )

    parser.add_argument(
        "--output",
        default="outputs/validation/scoring_inputs_summary.json",
    )

    args = parser.parse_args()

    default_manifests = [
        "outputs/validation/property_flood_evidence_countywide_manifest.json",
        "outputs/validation/property_terrain_evidence_countywide_manifest.json",
        "outputs/validation/property_exposure_index_countywide_manifest.json",
    ]

    manifest_paths = [
        repository_path(path)
        for path in (args.manifest or default_manifests)
    ]

    summary = build_summary(
        evidence_path=repository_path(args.evidence),
        terrain_path=repository_path(args.terrain),
        manifest_paths=manifest_paths,
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