"""Milestone 4, chunk B2 — entry-extent sweep for the segment-BVH index.

Sweeps the segment-BVH split cap, which is the index's entry-extent parameter,
under both phase-2 verification modes, and validates every point of the sweep
against the Python nearest-water reference before reporting any of it.

What this script does NOT do, deliberately:

  * It does not write to ``outputs/validation/water_cpp_benchmark_summary.json``.
    ``python/scripts/build_property_evidence.py`` asserts that summary's
    algorithm set equals ``{brute_force, feature_bvh}`` and raises otherwise, so
    adding ``segment_bvh`` to it would break the frozen Milestone 2/3 evidence
    build. The sweep writes to its own summary path and records the frozen
    summary's sha256 so an accidental modification would be visible.
  * It does not sweep run grouping. See ``grouping_scope_note`` in the emitted
    summary: the fewer-entries half of the entry-extent axis is UNMEASURED.

Usage (from the repository root, PowerShell or POSIX)::

    python python/scripts/sweep_segment_bvh_cap.py \
        --segment-bvh-executable cpp/spatial_core/build/water_distance_segment_bvh.exe \
        --properties outputs/cpp_input/water_properties_projected_countywide.csv \
        --features outputs/cpp_input/water_features_countywide.csv \
        --vertices outputs/cpp_input/water_vertices_countywide.csv \
        --python-reference outputs/baseline/python_nearest_water_countywide.csv \
        --caps 10 25 50 100 200 500 0 \
        --verification-modes original split

Exit code is 0 only if every point of the sweep agrees field-for-field with the
Python reference and every artefact check passes.
"""

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

from caprm.hydrography import calculate_sha256  # noqa: E402
from caprm.ingest import repository_path  # noqa: E402
from caprm.water_benchmark import (  # noqa: E402
    benchmark_segment_bvh_cap_sweep,
    cap_label,
)
from caprm.water_validate import compare_water_files  # noqa: E402

# Columns that must never be null in a segment-BVH artefact.
REQUIRED_NON_NULL_COLUMNS = [
    "property_id",
    "cpp_nearest_water_distance_m",
    "cpp_nearest_water_feature_id",
    "cpp_nearest_water_feature_class",
    "cpp_nearest_water_tie_count",
    "cpp_segment_checks",
    "distance_crs",
    "verification_mode",
    "algorithm",
]


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def check_artifact(
    output_path: Path,
    expected_property_count: int,
    expected_zero_count: int,
    zero_distance_class: str,
    maximum_distance_m: float,
    verification_mode: str,
) -> dict[str, Any]:
    """Structural checks on one segment-BVH output CSV.

    Returns a record whose ``failures`` list is empty when the artefact is
    acceptable. Nothing here duplicates the field-for-field comparison against
    the Python reference; these are the shape, range and counter-invariant
    checks that the comparison does not cover.
    """
    frame = pd.read_csv(
        output_path,
        dtype={
            "property_id": "string",
            "cpp_nearest_water_feature_id": "string",
            "cpp_nearest_water_source_id": "string",
            "cpp_nearest_water_feature_class": "string",
            "verification_mode": "string",
            "algorithm": "string",
            "distance_crs": "string",
        },
    )

    failures: list[str] = []

    row_count = int(len(frame))
    unique_property_ids = int(frame["property_id"].nunique())

    if row_count != expected_property_count:
        failures.append(
            f"row count {row_count} != {expected_property_count}"
        )

    if unique_property_ids != expected_property_count:
        failures.append(
            f"unique property_ids {unique_property_ids} "
            f"!= {expected_property_count}"
        )

    for column in REQUIRED_NON_NULL_COLUMNS:
        if column not in frame.columns:
            failures.append(f"missing required column {column}")
            continue

        null_count = int(frame[column].isna().sum())

        if null_count:
            failures.append(
                f"{null_count} nulls in required column {column}"
            )

    distances = pd.to_numeric(
        frame["cpp_nearest_water_distance_m"],
        errors="raise",
    )

    zero_mask = distances.eq(0.0)
    zero_count = int(zero_mask.sum())

    if zero_count != expected_zero_count:
        failures.append(
            f"exact-zero distances {zero_count} "
            f"!= {expected_zero_count}"
        )

    zero_classes = sorted(
        frame.loc[zero_mask, "cpp_nearest_water_feature_class"]
        .dropna()
        .unique()
        .tolist()
    )

    if zero_count and zero_classes != [zero_distance_class]:
        failures.append(
            f"exact-zero feature classes {zero_classes} "
            f"!= ['{zero_distance_class}']"
        )

    if bool((distances < 0.0).any()):
        failures.append("negative distance present")

    if bool((distances >= maximum_distance_m).any()):
        failures.append(
            f"distance >= {maximum_distance_m} m present"
        )

    nonzero = distances.loc[~zero_mask]

    # The number that settles the Option B boundary-epsilon hazard. The kernel
    # treats a point as on-boundary at <= 1e-9 m, and the split-geometry
    # perturbation is the same order, so the two modes could in principle
    # classify a point differently. If the minimum nonzero distance is orders of
    # magnitude larger than 1e-9, no property is anywhere near that band and the
    # hazard is vacuous on this data — with a measured number behind the claim.
    minimum_nonzero_distance_m = (
        float(nonzero.min()) if len(nonzero) else None
    )

    for column, label in (
        ("distance_crs", "distance_crs"),
        ("algorithm", "algorithm"),
        ("verification_mode", "verification_mode"),
    ):
        values = sorted(
            frame[column].dropna().unique().tolist()
        )

        if len(values) != 1:
            failures.append(
                f"{label} has {len(values)} distinct values: {values}"
            )

    observed_mode = (
        frame["verification_mode"].dropna().unique().tolist()
    )

    if observed_mode and observed_mode[0] != verification_mode:
        failures.append(
            f"verification_mode {observed_mode[0]!r} "
            f"!= requested {verification_mode!r}"
        )

    # Counter invariants. These are what make the verification decomposition
    # trustworthy rather than decorative.
    line_checks = pd.to_numeric(
        frame["cpp_line_segment_checks"], errors="raise"
    )
    polygon_checks = pd.to_numeric(
        frame["cpp_polygon_segment_checks"], errors="raise"
    )
    ring_checks = pd.to_numeric(
        frame["cpp_containment_ring_checks"], errors="raise"
    )
    segment_checks = pd.to_numeric(
        frame["cpp_segment_checks"], errors="raise"
    )

    if verification_mode == "original":
        if not bool(
            (line_checks + polygon_checks).eq(segment_checks).all()
        ):
            failures.append(
                "original mode: line + polygon checks != total "
                "segment checks"
            )

        if not bool(ring_checks.eq(0).all()):
            failures.append(
                "original mode: nonzero standalone containment "
                "ring checks"
            )
    else:
        if not bool(
            line_checks.eq(0).all()
            and polygon_checks.eq(0).all()
        ):
            failures.append(
                "split mode: distance work performed over feature "
                "geometry"
            )

        if not bool(ring_checks.eq(segment_checks).all()):
            failures.append(
                "split mode: segment checks != containment ring "
                "checks"
            )

    return {
        "output": display_path(output_path),
        "row_count": row_count,
        "unique_property_ids": unique_property_ids,
        "exact_zero_distances": zero_count,
        "exact_zero_feature_classes": zero_classes,
        "minimum_distance_m": float(distances.min()),
        "maximum_distance_m": float(distances.max()),
        "minimum_nonzero_distance_m": minimum_nonzero_distance_m,
        "minimum_tie_count": int(
            pd.to_numeric(
                frame["cpp_nearest_water_tie_count"],
                errors="raise",
            ).min()
        ),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep the segment-BVH entry-extent cap under both "
            "verification modes and validate every point."
        )
    )

    parser.add_argument(
        "--segment-bvh-executable",
        default=(
            "cpp/spatial_core/build/"
            "water_distance_segment_bvh.exe"
        ),
    )

    parser.add_argument(
        "--properties",
        default=(
            "outputs/cpp_input/"
            "water_properties_projected_countywide.csv"
        ),
    )

    parser.add_argument(
        "--features",
        default=(
            "outputs/cpp_input/water_features_countywide.csv"
        ),
    )

    parser.add_argument(
        "--vertices",
        default=(
            "outputs/cpp_input/water_vertices_countywide.csv"
        ),
    )

    parser.add_argument(
        "--python-reference",
        default=(
            "outputs/baseline/"
            "python_nearest_water_countywide.csv"
        ),
    )

    parser.add_argument(
        "--caps",
        type=float,
        nargs="+",
        default=[10.0, 25.0, 50.0, 100.0, 200.0, 500.0, 0.0],
        help=(
            "Entry-extent caps in metres. 0 disables splitting "
            "(unlimited extent)."
        ),
    )

    parser.add_argument(
        "--verification-modes",
        nargs="+",
        default=["original", "split"],
        choices=["original", "split"],
    )

    parser.add_argument(
        "--distance-crs",
        default="EPSG:26918",
    )

    parser.add_argument(
        "--repetitions",
        type=int,
        default=7,
    )

    parser.add_argument(
        "--warmups",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--expected-property-count",
        type=int,
        default=267362,
    )

    parser.add_argument(
        "--expected-zero-count",
        type=int,
        default=266,
    )

    parser.add_argument(
        "--zero-distance-class",
        default="waterbody",
    )

    parser.add_argument(
        "--maximum-distance-m",
        type=float,
        default=20000.0,
    )

    parser.add_argument(
        "--distance-tolerance-meters",
        type=float,
        default=1e-6,
        help=(
            "Passed to the comparison harness. The project default. "
            "Do not change without a documented reason."
        ),
    )

    parser.add_argument(
        "--runs-output",
        default=(
            "outputs/benchmark/"
            "water_segment_bvh_cap_sweep_runs.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        default=(
            "outputs/validation/"
            "water_segment_bvh_cap_sweep_summary.json"
        ),
    )

    parser.add_argument(
        "--agreement-directory",
        default="outputs/validation/segment_bvh_cap_sweep",
    )

    parser.add_argument(
        "--retained-output-directory",
        default="outputs/cpp/segment_bvh_cap_sweep",
    )

    parser.add_argument(
        "--temporary-output-directory",
        default=(
            "outputs/benchmark/"
            "temporary_segment_bvh_sweep_outputs"
        ),
    )

    parser.add_argument(
        "--frozen-benchmark-summary",
        default=(
            "outputs/validation/"
            "water_cpp_benchmark_summary.json"
        ),
        help=(
            "Recorded by sha256 only, never written. Present so an "
            "accidental modification of the frozen Milestone 2/3 "
            "summary would be visible in this sweep's provenance."
        ),
    )

    parser.add_argument(
        "--keep-agreement-detail",
        action="store_true",
        help=(
            "Also write the per-property agreement CSV for every "
            "sweep point. Off by default: that is 267k rows per "
            "point."
        ),
    )

    args = parser.parse_args()

    executable_path = repository_path(
        args.segment_bvh_executable
    )
    properties_path = repository_path(args.properties)
    features_path = repository_path(args.features)
    vertices_path = repository_path(args.vertices)
    python_reference_path = repository_path(
        args.python_reference
    )
    runs_output_path = repository_path(args.runs_output)
    summary_output_path = repository_path(args.summary_output)
    agreement_directory = repository_path(
        args.agreement_directory
    )
    retained_output_directory = repository_path(
        args.retained_output_directory
    )
    temporary_output_directory = repository_path(
        args.temporary_output_directory
    )
    frozen_summary_path = repository_path(
        args.frozen_benchmark_summary
    )

    for path in (
        executable_path,
        properties_path,
        features_path,
        vertices_path,
        python_reference_path,
    ):
        if not path.exists():
            raise SystemExit(f"Input does not exist: {path}")

    agreement_directory.mkdir(parents=True, exist_ok=True)
    retained_output_directory.mkdir(
        parents=True, exist_ok=True
    )

    runs, summary = benchmark_segment_bvh_cap_sweep(
        segment_bvh_executable=executable_path,
        properties_path=properties_path,
        features_path=features_path,
        vertices_path=vertices_path,
        temporary_output_directory=temporary_output_directory,
        caps_m=args.caps,
        verification_modes=args.verification_modes,
        distance_crs=args.distance_crs,
        repetitions=args.repetitions,
        warmups=args.warmups,
        retained_output_directory=retained_output_directory,
    )

    validations: list[dict[str, Any]] = []
    failures: list[str] = []

    for cap_meters in args.caps:
        label = cap_label(cap_meters)

        for verification_mode in args.verification_modes:
            retained_path = retained_output_directory / (
                "cpp_nearest_water_segment_bvh_"
                f"{label}_{verification_mode}.csv"
            )

            point_name = f"{label}/{verification_mode}"

            if not retained_path.exists():
                failures.append(
                    f"{point_name}: retained output missing"
                )
                continue

            artifact = check_artifact(
                output_path=retained_path,
                expected_property_count=(
                    args.expected_property_count
                ),
                expected_zero_count=args.expected_zero_count,
                zero_distance_class=args.zero_distance_class,
                maximum_distance_m=args.maximum_distance_m,
                verification_mode=verification_mode,
            )

            detail, agreement = compare_water_files(
                python_reference_path=python_reference_path,
                cpp_output_path=retained_path,
                distance_tolerance_meters=(
                    args.distance_tolerance_meters
                ),
                path_display_root=REPOSITORY_ROOT,
            )

            agreement_summary_path = (
                agreement_directory
                / (
                    "water_segment_bvh_"
                    f"{label}_{verification_mode}_summary.json"
                )
            )

            agreement_summary_path.write_text(
                json.dumps(agreement, indent=2),
                encoding="utf-8",
            )

            if args.keep_agreement_detail:
                detail.to_csv(
                    agreement_directory
                    / (
                        "water_segment_bvh_"
                        f"{label}_{verification_mode}"
                        "_agreement.csv"
                    ),
                    index=False,
                    float_format="%.12f",
                )

            agrees = int(agreement["all_fields_agree"])
            union_rows = int(agreement["total_union_rows"])

            if (
                agreement["missing_python_rows"] != 0
                or agreement["missing_cpp_rows"] != 0
                or agrees != union_rows
            ):
                failures.append(
                    f"{point_name}: all_fields_agree {agrees} "
                    f"of {union_rows}"
                )

            for failure in artifact["failures"]:
                failures.append(f"{point_name}: {failure}")

            validations.append(
                {
                    "cap_label": label,
                    "max_segment_length_cap_m": float(
                        cap_meters
                    ),
                    "verification_mode": verification_mode,
                    "artifact_checks": artifact,
                    "agreement_summary": display_path(
                        agreement_summary_path
                    ),
                    "total_union_rows": union_rows,
                    "all_fields_agree": agrees,
                    "distance_agreements": int(
                        agreement["distance_agreements"]
                    ),
                    "feature_id_agreements": int(
                        agreement["feature_id_agreements"]
                    ),
                    "tie_count_agreements": int(
                        agreement["tie_count_agreements"]
                    ),
                    "maximum_absolute_error_m": agreement.get(
                        "maximum_absolute_error_m"
                    ),
                    "mean_absolute_error_m": agreement.get(
                        "mean_absolute_error_m"
                    ),
                    "median_absolute_error_m": agreement.get(
                        "median_absolute_error_m"
                    ),
                }
            )

    summary.update(
        {
            "created_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "segment_bvh_executable": display_path(
                executable_path
            ),
            "segment_bvh_executable_sha256": calculate_sha256(
                executable_path
            ),
            "properties_input": display_path(properties_path),
            "properties_input_sha256": calculate_sha256(
                properties_path
            ),
            "features_input": display_path(features_path),
            "features_input_sha256": calculate_sha256(
                features_path
            ),
            "vertices_input": display_path(vertices_path),
            "vertices_input_sha256": calculate_sha256(
                vertices_path
            ),
            "python_reference": display_path(
                python_reference_path
            ),
            "python_reference_sha256": calculate_sha256(
                python_reference_path
            ),
            "distance_tolerance_meters": (
                args.distance_tolerance_meters
            ),
            "frozen_benchmark_summary": display_path(
                frozen_summary_path
            ),
            "frozen_benchmark_summary_sha256": (
                calculate_sha256(frozen_summary_path)
                if frozen_summary_path.exists()
                else None
            ),
            "frozen_benchmark_summary_note": (
                "Recorded, never written. This sweep must not add "
                "segment_bvh to the frozen Milestone 2/3 summary; "
                "build_property_evidence.py requires that file's "
                "algorithm set to equal {brute_force, feature_bvh}."
            ),
            "validations": validations,
            "acceptance_failures": failures,
            "accepted": not failures,
        }
    )

    runs_output_path.parent.mkdir(parents=True, exist_ok=True)
    runs.to_csv(
        runs_output_path,
        index=False,
        float_format="%.12f",
    )

    summary_output_path.parent.mkdir(
        parents=True, exist_ok=True
    )
    summary_output_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))

    if failures:
        print(
            "\nACCEPTANCE FAILED:\n  "
            + "\n  ".join(failures),
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()