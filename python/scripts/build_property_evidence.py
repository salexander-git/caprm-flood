from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(
    0,
    str(PYTHON_SOURCE_DIRECTORY),
)

from caprm.evidence import (
    build_property_evidence,
    calculate_sha256,
    prepare_property_coordinates,
    require_full_agreement_summary,
    summarize_property_evidence,
)
from caprm.ingest import (
    load_property_points,
    load_yaml,
    repository_path,
)


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(
            REPOSITORY_ROOT
        ).as_posix()
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the integrated CAPRM-Flood FEMA and "
            "nearest-water evidence dataset."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
    )

    parser.add_argument(
        "--fema-baseline",
        default=None,
    )

    parser.add_argument(
        "--water-baseline",
        default=None,
    )

    parser.add_argument(
        "--fema-validation",
        default=(
            "outputs/validation/"
            "fema_export_refresh_summary.json"
        ),
    )

    parser.add_argument(
        "--water-validation",
        default=(
            "outputs/validation/"
            "water_indexed_summary.json"
        ),
    )

    parser.add_argument(
        "--benchmark-summary",
        default=(
            "outputs/validation/"
            "water_cpp_benchmark_summary.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=None,
    )

    parser.add_argument(
        "--manifest-output",
        default=None,
    )

    args = parser.parse_args()

    config = load_yaml(
        repository_path(args.config)
    )

    outputs = config["outputs"]
    hydrography = config["hydrography"]

    fema_baseline_path = repository_path(
        args.fema_baseline
        or outputs["python_baseline_csv"]
    )

    water_baseline_path = repository_path(
        args.water_baseline
        or outputs["python_nearest_water_csv"]
    )

    fema_validation_path = repository_path(
        args.fema_validation
    )

    water_validation_path = repository_path(
        args.water_validation
    )

    benchmark_summary_path = repository_path(
        args.benchmark_summary
    )

    output_path = repository_path(
        args.output
        or outputs[
            "integrated_property_evidence_csv"
        ]
    )

    manifest_path = repository_path(
        args.manifest_output
        or outputs[
            "integrated_property_evidence_manifest"
        ]
    )

    for required_path in (
        fema_baseline_path,
        water_baseline_path,
        benchmark_summary_path,
    ):
        if not required_path.exists():
            raise FileNotFoundError(
                f"Required input does not exist: "
                f"{required_path}"
            )

    fema_validation = (
        require_full_agreement_summary(
            fema_validation_path,
            "FEMA Python/C++ validation",
        )
    )

    water_validation = (
        require_full_agreement_summary(
            water_validation_path,
            "Water Python/C++ validation",
        )
    )

    benchmark_summary = json.loads(
        benchmark_summary_path.read_text(
            encoding="utf-8"
        )
    )

    expected_algorithms = {
        "brute_force",
        "feature_bvh",
    }

    observed_algorithms = set(
        benchmark_summary.get(
            "algorithms",
            {},
        )
    )

    if observed_algorithms != expected_algorithms:
        raise ValueError(
            "Benchmark summary must contain brute_force "
            "and feature_bvh results."
        )

    fema_baseline = pd.read_csv(
        fema_baseline_path,
        dtype={
            "property_id": "string",
        },
    )

    water_baseline = pd.read_csv(
        water_baseline_path,
        dtype={
            "property_id": "string",
            "nearest_water_feature_id": "string",
            "nearest_water_source_id": "string",
        },
    )

    properties = load_property_points(
        config,
        refresh=False,
    )

    distance_crs = config["project"][
        "distance_crs"
    ]

    fema_project_crs = config["project"][
        "project_crs"
    ]

    property_coordinates = (
        prepare_property_coordinates(
            properties,
            distance_crs,
        )
    )

    evidence = build_property_evidence(
        property_coordinates=property_coordinates,
        fema_baseline=fema_baseline,
        water_baseline=water_baseline,
        fema_project_crs=fema_project_crs,
        distance_crs=distance_crs,
        query_buffer_meters=float(
            hydrography[
                "query_buffer_meters"
            ]
        ),
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    evidence.to_csv(
        output_path,
        index=False,
        float_format="%.12f",
    )

    evidence_summary = (
        summarize_property_evidence(
            evidence
        )
    )

    manifest = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "schema_version": (
            "milestone_2_fema_water_evidence_v1"
        ),
        "description": (
            "Integrated property-level FEMA flood-zone and "
            "nearest-water evidence. No composite score or "
            "flood-loss prediction is included."
        ),
        "scoring_included": False,
        "property_cache": config[
            "property_points"
        ]["output_path"],
        "fema_baseline": display_path(
            fema_baseline_path
        ),
        "fema_baseline_sha256": (
            calculate_sha256(
                fema_baseline_path
            )
        ),
        "water_baseline": display_path(
            water_baseline_path
        ),
        "water_baseline_sha256": (
            calculate_sha256(
                water_baseline_path
            )
        ),
        "fema_project_crs": (
            fema_project_crs
        ),
        "distance_crs": distance_crs,
        "hydrography_query_buffer_meters": (
            float(
                hydrography[
                    "query_buffer_meters"
                ]
            )
        ),
        "fema_validation": {
            "summary_path": display_path(
                fema_validation_path
            ),
            "summary_sha256": calculate_sha256(
                fema_validation_path
            ),
            "validated_rows": int(
                fema_validation[
                    "total_union_rows"
                ]
            ),
            "all_fields_agree": int(
                fema_validation[
                    "all_fields_agree"
                ]
            ),
        },
        "water_validation": {
            "summary_path": display_path(
                water_validation_path
            ),
            "summary_sha256": calculate_sha256(
                water_validation_path
            ),
            "algorithm": water_validation.get(
                "algorithm"
            ),
            "validated_rows": int(
                water_validation[
                    "total_union_rows"
                ]
            ),
            "all_fields_agree": int(
                water_validation[
                    "all_fields_agree"
                ]
            ),
            "maximum_absolute_error_m": (
                water_validation.get(
                    "maximum_absolute_error_m"
                )
            ),
        },
        "water_benchmark": {
            "summary_path": display_path(
                benchmark_summary_path
            ),
            "summary_sha256": calculate_sha256(
                benchmark_summary_path
            ),
            "repetitions": (
                benchmark_summary.get(
                    "repetitions"
                )
            ),
            "warmups_per_algorithm": (
                benchmark_summary.get(
                    "warmups_per_algorithm"
                )
            ),
            "comparison": (
                benchmark_summary[
                    "comparison"
                ]
            ),
        },
        "evidence_summary": evidence_summary,
        "output_csv": display_path(
            output_path
        ),
        "output_size_bytes": (
            output_path.stat().st_size
        ),
        "output_sha256": (
            calculate_sha256(output_path)
        ),
        "columns": evidence.columns.tolist(),
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