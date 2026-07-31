"""C4 item 2a. Assert the nesting, stage the scratch subsets, declare the boundary.

    python python/scripts/stage_c4_pipeline_inputs.py

Runs BEFORE any stage is timed and writes nothing outside
``outputs/scratch/c4/`` and one new manifest. If the nesting gate fails, the
subsetting design for the terrain and scoring stages is unsound and this script
raises rather than producing a subset that would silently measure a different
property set than the config-selected workloads do.

Writes
    outputs/scratch/c4/evidence_{10000,100000,countywide}.csv
    outputs/scratch/c4/terrain_{10000,100000,countywide}.csv
    outputs/validation/c4_pipeline_boundary.json

Commit the boundary manifest before running the timing harness. A boundary
declared after the numbers are in is not a declaration.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from caprm import pipeline_cost as pc  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage C4 pipeline-cost inputs and declare the timing boundary."
    )
    parser.add_argument(
        "--evidence", default="outputs/evidence/property_flood_evidence_countywide.csv"
    )
    parser.add_argument(
        "--terrain", default="outputs/evidence/property_terrain_evidence_countywide.csv"
    )
    parser.add_argument("--scratch", default=pc.SCRATCH_DIRECTORY)
    parser.add_argument("--output", default="outputs/validation/c4_pipeline_boundary.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    id_sets = {}
    sources = {}
    for workload in pc.WORKLOADS:
        path = REPOSITORY_ROOT / workload.property_points
        if not path.exists():
            raise SystemExit(f"property points missing for {workload.name}: {path}")
        print(f"reading {workload.property_points} ...")
        frame = gpd.read_file(path)
        ids = pc.property_ids(pd.DataFrame(frame.drop(columns="geometry")), workload.name)
        if len(ids) != workload.expected_rows:
            raise SystemExit(
                f"{workload.name} has {len(ids)} rows, expected {workload.expected_rows}"
            )
        id_sets[workload.name] = ids
        sources[workload.name] = {"path": workload.property_points, "rows": int(len(ids))}

    print("checking 100000 within countywide (the link that can fail) ...")
    nesting = pc.nesting_report(id_sets)
    print("  nested")
    print("checking 10000 within 100000 ...")
    print("  nested")

    evidence_path = REPOSITORY_ROOT / args.evidence
    terrain_path = REPOSITORY_ROOT / args.terrain
    scratch = REPOSITORY_ROOT / args.scratch

    print(f"subsetting {args.evidence} ...")
    evidence = pd.read_csv(evidence_path, dtype={pc.KEY_COLUMN: "string"})
    evidence_subsets = pc.write_subsets(evidence, id_sets, scratch, "evidence", args.evidence)

    print(f"subsetting {args.terrain} ...")
    terrain = pd.read_csv(terrain_path, dtype={pc.KEY_COLUMN: "string"})
    terrain_subsets = pc.write_subsets(terrain, id_sets, scratch, "terrain", args.terrain)

    manifest = pc.boundary_manifest(
        nesting=nesting,
        subsets={"evidence": evidence_subsets, "terrain": terrain_subsets},
        inputs={
            "property_points": sources,
            "evidence": {
                "path": args.evidence,
                "sha256": pc.sha256_file(evidence_path),
                "rows": int(len(evidence)),
            },
            "terrain": {
                "path": args.terrain,
                "sha256": pc.sha256_file(terrain_path),
                "rows": int(len(terrain)),
            },
        },
        generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    )

    output_path = REPOSITORY_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    for family, written in manifest["scratch_subsets"].items():
        for name, entry in written.items():
            print(f"  {family:9} {name:11} {entry['rows']:>7,} rows  {entry['path']}")
    print(f"wrote {output_path}")
    print("Commit this manifest BEFORE running the timing harness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())