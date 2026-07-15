from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.ingest import repository_path
from caprm.scoring import (
    DEFAULT_WEIGHTS,
    build_exposure_index,
    calculate_sha256,
    summarize_exposure_index,
)


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a preliminary property-level flood-exposure index "
            "from FEMA, nearest-water, and terrain evidence."
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
        "--output",
        default="outputs/index/property_exposure_index_countywide.csv",
    )

    parser.add_argument(
        "--manifest-output",
        default="outputs/validation/property_exposure_index_countywide_manifest.json",
    )

    parser.add_argument(
        "--distance-crs",
        default="EPSG:26918",
    )

    parser.add_argument(
        "--terrain-crs",
        default="EPSG:26918",
    )

    args = parser.parse_args()

    evidence_path = repository_path(args.evidence)
    terrain_path = repository_path(args.terrain)
    output_path = repository_path(args.output)
    manifest_path = repository_path(args.manifest_output)

    evidence = pd.read_csv(
        evidence_path,
        dtype={"property_id": "string"},
    )

    terrain = pd.read_csv(
        terrain_path,
        dtype={"property_id": "string"},
    )

    index = build_exposure_index(
        evidence=evidence,
        terrain=terrain,
        expected_distance_crs=args.distance_crs,
        expected_terrain_crs=args.terrain_crs,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    index.to_csv(
        output_path,
        index=False,
        float_format="%.12f",
    )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "preliminary_exposure_index_v1",
        "input_evidence": display_path(evidence_path),
        "input_evidence_sha256": calculate_sha256(evidence_path),
        "input_terrain": display_path(terrain_path),
        "input_terrain_sha256": calculate_sha256(terrain_path),
        "output": display_path(output_path),
        "output_sha256": calculate_sha256(output_path),
        "distance_crs": args.distance_crs,
        "terrain_crs": args.terrain_crs,
        "weights": DEFAULT_WEIGHTS,
        "summary": summarize_exposure_index(index),
        "interpretation": (
            "The exposure index is a preliminary relative ranking built from "
            "validated evidence components. It is not a flood-probability "
            "model, hydrologic simulation, actuarial model, insurance-pricing "
            "tool, or loss estimate."
        ),
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()