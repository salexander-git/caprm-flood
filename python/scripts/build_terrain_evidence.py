from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT/ "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.ingest import repository_path
from caprm.terrain import (
    build_terrain_evidence,
    calculate_sha256,
    summarize_terrain_evidence,
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
            "Build property-level elevation and terrain evidence from a projected DEM raster"
        )
    )

    parser.add_argument(
        "--evidence",
        default="outputs/evidence/property_flood_evidence_countywide.csv",
    )

    parser.add_argument(
        "--terrain-raster",
        default="data/raw/terrain/monroe_dem_utm18.tif",
    )

    parser.add_argument(
        "--terrain-crs",
        default="EPSG:26918",
    )

    parser.add_argument(
        "--sample-radius-meters",
        type=float,
        default=90.0,
    )

    parser.add_argument(
        "--output",
        default="outputs/evidence/property_terrain_evidence_countywide.csv",
    )

    parser.add_argument(
        "--manifest-output",
        default=(
            "outputs/validation/"
            "property_terrain_evidence_countywide_manifest.json"
        ),
    )

    args = parser.parse_args()

    evidence_path = repository_path(args.evidence)
    raster_path = repository_path(args.terrain_raster)
    output_path = repository_path(args.output)
    manifest_path = repository_path(args.manifest_output)

    evidence = pd.read_csv(
        evidence_path,
        dtype={"property_id": "string"}, 
    )

    terrain = build_terrain_evidence(
        evidence=evidence,
        raster_path=raster_path,
        terrain_crs=args.terrain_crs,
        sample_radius_meters=args.sample_radius_meters,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    terrain.to_csv(
        output_path,
        index=False,
        float_format="%.12f"
    )

    summary = summarize_terrain_evidence(terrain)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "terrain_evidence_v1",
        "input_evidence": display_path(evidence_path),
        "input_evidence_sha256": calculate_sha256(evidence_path),
        "terrain_raster": display_path(raster_path),
        "terrain_raster_sha256": calculate_sha256(raster_path),
        "output": display_path(output_path),
        "output_sha256": calculate_sha256(output_path),
        "terrain_crs": args.terrain_crs,
        "sample_radius_meters": float(args.sample_radius_meters),
        "summary": summary,
        "interpretation": (
            "Terrain evidence is property-centroid evidence derived from a "
            "projected DEM. It is not a hydrologic simulation, finished flood "
            "probability estimate, or loss model."
        ),
    }

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()