"""Summarize the B3b inflation cost and the box-vs-disk gate from Hilbert
countywide outputs.

Reads the per-property counter columns of one or two Hilbert CSVs (the
disk_bbox operating run, and optionally the disk-region run) and writes a single
provenance-carrying JSON summary.

Example (PowerShell):

    .\\.venv\\Scripts\\python.exe python\\scripts\\summarize_hilbert_inflation.py `
        --disk-bbox-csv outputs/cpp/cpp_nearest_water_hilbert_countywide_bbox.csv `
        --disk-csv outputs/cpp/cpp_nearest_water_hilbert_countywide_disk.csv `
        --manifest outputs/validation/water_hilbert_countywide_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.ingest import repository_path
from caprm.hilbert_inflation import (
    box_vs_disk_gate,
    inflation_by_distance_decile,
    summarize_counters,
)


CSV_DTYPES = {
    "property_id": "string",
    "region_mode": "string",
    "seed_mode": "string",
    "verification_mode": "string",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Hilbert output does not exist: {path}")
    return pd.read_csv(path, dtype=CSV_DTYPES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk-bbox-csv", required=True)
    parser.add_argument("--disk-csv", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument(
        "--summary-output",
        default="outputs/validation/water_hilbert_inflation_summary.json",
    )
    parser.add_argument(
        "--decile-output",
        default="outputs/analysis/water_hilbert_inflation_by_decile.csv",
    )
    arguments = parser.parse_args()

    disk_bbox_path = repository_path(arguments.disk_bbox_csv)
    disk_bbox = load(disk_bbox_path)
    disk_bbox_summary = summarize_counters(disk_bbox, "disk_bbox")

    if disk_bbox_summary["region_mode"] != "disk_bbox":
        raise ValueError(
            "--disk-bbox-csv is not a disk_bbox run: region_mode is "
            f"{disk_bbox_summary['region_mode']}"
        )

    inputs = [{
        "path": display_path(disk_bbox_path),
        "sha256": sha256(disk_bbox_path),
        "rows": int(len(disk_bbox)),
    }]

    disk_summary = None
    if arguments.disk_csv:
        disk_path = repository_path(arguments.disk_csv)
        disk = load(disk_path)
        disk_summary = summarize_counters(disk, "disk")
        if disk_summary["region_mode"] != "disk":
            raise ValueError(
                "--disk-csv is not a disk run: region_mode is "
                f"{disk_summary['region_mode']}"
            )
        inputs.append({
            "path": display_path(disk_path),
            "sha256": sha256(disk_path),
            "rows": int(len(disk)),
        })

        # The disk counters are exact counts over disk(R) and must therefore be
        # identical across region predicates. Cross-checking the two runs tests
        # both predicates against each other.
        merged = disk_bbox.merge(
            disk, on="property_id", suffixes=("_bbox", "_disk")
        )
        if len(merged) != len(disk_bbox):
            raise ValueError(
                "disk_bbox and disk runs do not cover the same properties."
            )
        invariance = {
            column: int(
                (merged[f"{column}_bbox"] != merged[f"{column}_disk"]).sum()
            )
            for column in ("cpp_n_disk_r", "cpp_n_true_r", "cpp_n_disk_infl")
        }
        invariance["cpp_entries_scanned_disk_gt_bbox"] = int(
            (
                merged["cpp_entries_scanned_disk"]
                > merged["cpp_entries_scanned_bbox"]
            ).sum()
        )
        disk_summary["region_invariance_violations"] = invariance
        disk_summary["region_invariance_holds"] = all(
            value == 0 for value in invariance.values()
        )

    manifest = None
    if arguments.manifest:
        manifest_path = repository_path(arguments.manifest)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        inputs.append({
            "path": display_path(manifest_path),
            "sha256": sha256(manifest_path),
        })

    gate = box_vs_disk_gate(disk_bbox_summary, disk_summary)
    deciles = inflation_by_distance_decile(disk_bbox)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "chunk": "B3b",
        "inputs": inputs,
        "index_manifest": manifest,
        "disk_bbox": disk_bbox_summary,
        "disk": disk_summary,
        "box_vs_disk_gate": gate,
        "distance_deciles": deciles,
    }

    summary_path = repository_path(arguments.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    decile_path = repository_path(arguments.decile_output)
    decile_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(deciles).to_csv(decile_path, index=False)

    print(json.dumps(summary, indent=2))
    print(f"\nWrote {display_path(summary_path)}")
    print(f"Wrote {display_path(decile_path)}")

    failures = []
    if not disk_bbox_summary["ordering_holds"]:
        failures.append("disk_bbox ordering violated")
    if disk_summary is not None:
        if not disk_summary["ordering_holds"]:
            failures.append("disk ordering violated")
        if not disk_summary["region_invariance_holds"]:
            failures.append("region invariance violated")
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()