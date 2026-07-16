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

from caprm.audit import (
    FAIL,
    MANIFEST_OUTPUT_KEYS,
    PASS,
    WARN,
    audit_checksum,
    audit_index_product,
    audit_manifest_conventions,
    audit_population_consistency,
    audit_terrain_product,
    load_manifest,
    manifest_field,
    overall_status,
    record,
    status_counts,
)
from caprm.ingest import repository_path


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def read_property_ids_from_csv(path: Path) -> set[str]:
    frame = pd.read_csv(
        path,
        usecols=["property_id"],
        dtype={"property_id": "string"},
    )

    return set(frame["property_id"].dropna().tolist())


def read_property_ids_from_geojson(path: Path) -> set[str]:
    # Imported lazily. The audit is otherwise a pandas-only module, and the
    # workload comparison is optional.
    import geopandas as gpd

    workload = gpd.read_file(path)

    if "property_id" not in workload.columns:
        raise ValueError(
            f"Workload has no property_id column: {sorted(workload.columns)}"
        )

    return set(workload["property_id"].astype("string").dropna().tolist())


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the Milestone 3 terrain and exposure-index products for "
            "structural completeness, provenance consistency, and "
            "population agreement across the product chain. Read-only."
        )
    )

    parser.add_argument(
        "--evidence",
        default="outputs/evidence/property_flood_evidence_countywide.csv",
    )

    parser.add_argument(
        "--evidence-manifest",
        default=(
            "outputs/validation/"
            "property_flood_evidence_countywide_manifest.json"
        ),
    )

    parser.add_argument(
        "--terrain",
        default="outputs/evidence/property_terrain_evidence_countywide.csv",
    )

    parser.add_argument(
        "--terrain-manifest",
        default=(
            "outputs/validation/"
            "property_terrain_evidence_countywide_manifest.json"
        ),
    )

    parser.add_argument(
        "--index",
        default="outputs/index/property_exposure_index_countywide.csv",
    )

    parser.add_argument(
        "--index-manifest",
        default=(
            "outputs/validation/"
            "property_exposure_index_countywide_manifest.json"
        ),
    )

    parser.add_argument(
        "--terrain-raster",
        default="data/raw/terrain/monroe_dem_utm18.tif",
    )

    parser.add_argument(
        "--workload",
        default="data/processed/monroe_property_points_countywide.geojson",
        help=(
            "Countywide property workload. Pass an empty string to skip the "
            "workload comparison."
        ),
    )

    parser.add_argument(
        "--output",
        default="outputs/validation/milestone3_audit.json",
    )

    args = parser.parse_args()

    evidence_path = repository_path(args.evidence)
    terrain_path = repository_path(args.terrain)
    index_path = repository_path(args.index)

    terrain_manifest = load_manifest(repository_path(args.terrain_manifest))
    index_manifest = load_manifest(repository_path(args.index_manifest))
    evidence_manifest = load_manifest(repository_path(args.evidence_manifest))

    terrain = pd.read_csv(terrain_path, dtype={"property_id": "string"})
    index = pd.read_csv(index_path, dtype={"property_id": "string"})

    checks: list[dict[str, Any]] = []

    checks.extend(
        audit_manifest_conventions(
            {
                "flood_evidence": evidence_manifest,
                "terrain_evidence": terrain_manifest,
                "exposure_index": index_manifest,
            }
        )
    )

    # Manifest checksums against the files on disk. This is the check that
    # catches an artifact regenerated without its manifest.
    for label, manifest, path in (
        ("flood_evidence", evidence_manifest, evidence_path),
        ("terrain_evidence", terrain_manifest, terrain_path),
        ("exposure_index", index_manifest, index_path),
    ):
        recorded_path, _ = manifest_field(
            manifest, MANIFEST_OUTPUT_KEYS, "output path"
        )

        checks.append(
            record(
                f"{label}_manifest_path_agreement",
                PASS if recorded_path == display_path(path) else WARN,
                (
                    f"Manifest records {recorded_path!r}; audited "
                    f"{display_path(path)!r}."
                ),
            )
        )

        checks.append(
            audit_checksum(path, manifest.get("output_sha256"), label)
        )

    # The index manifest records the checksums of the tables it consumed.
    # If those no longer match, the index describes inputs that have since
    # changed and must be regenerated.
    checks.append(
        audit_checksum(
            evidence_path,
            index_manifest.get("input_evidence_sha256"),
            "index_input_evidence",
        )
    )

    checks.append(
        audit_checksum(
            terrain_path,
            index_manifest.get("input_terrain_sha256"),
            "index_input_terrain",
        )
    )

    checks.append(
        audit_checksum(
            evidence_path,
            terrain_manifest.get("input_evidence_sha256"),
            "terrain_input_evidence",
        )
    )

    raster_path = (
        repository_path(args.terrain_raster) if args.terrain_raster else None
    )

    checks.extend(
        audit_terrain_product(
            terrain=terrain,
            manifest=terrain_manifest,
            raster_path=raster_path,
        )
    )

    checks.extend(
        audit_index_product(
            index=index,
            manifest=index_manifest,
        )
    )

    populations = {
        "flood_evidence": read_property_ids_from_csv(evidence_path),
        "terrain_evidence": set(terrain["property_id"].dropna().tolist()),
        "exposure_index": set(index["property_id"].dropna().tolist()),
    }

    workload_path = repository_path(args.workload) if args.workload else None

    if workload_path is not None and workload_path.exists():
        populations["property_workload"] = read_property_ids_from_geojson(
            workload_path
        )
        reference = "property_workload"
    else:
        reference = "flood_evidence"

        checks.append(
            record(
                "population_workload_available",
                WARN,
                (
                    "The countywide property workload was not read, so the "
                    "chain is compared against the flood evidence rather "
                    "than its true source."
                ),
                workload=str(workload_path) if workload_path else None,
            )
        )

    checks.extend(audit_population_consistency(populations, reference))

    counts = status_counts(checks)
    status = overall_status(checks)

    report: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "milestone3_audit_v1",
        "purpose": (
            "Audit the structural completeness and provenance consistency "
            "of the Milestone 3 products. Checks the stored artifacts "
            "rather than the code that produced them, so it catches drift "
            "the unit tests cannot see."
        ),
        "status": status,
        "status_counts": counts,
        "audited": {
            "flood_evidence": display_path(evidence_path),
            "terrain_evidence": display_path(terrain_path),
            "exposure_index": display_path(index_path),
            "terrain_raster": (
                display_path(raster_path) if raster_path else None
            ),
            "property_workload": (
                display_path(workload_path)
                if workload_path and workload_path.exists()
                else None
            ),
        },
        "population_reference": reference,
        "checks": checks,
        "interpretation": (
            "A pass means the artifacts are internally consistent, agree "
            "with their manifests, and describe the same property "
            "population. It does not mean the evidence is accurate or the "
            "scoring methodology is correct."
        ),
    }

    output_path = repository_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(f"Audit status: {status}")
    print(
        f"pass {counts[PASS]}  warn {counts[WARN]}  fail {counts[FAIL]}"
    )
    print(f"Wrote {display_path(output_path)}")

    for check in checks:
        if check["status"] == PASS:
            continue

        print(f"\n[{check['status'].upper()}] {check['check']}")
        print(f"  {check['detail']}")

    if status == FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()