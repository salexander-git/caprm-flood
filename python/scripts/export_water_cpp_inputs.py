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

from caprm.hydrography import calculate_sha256
from caprm.ingest import (
    load_property_points,
    load_yaml,
    repository_path,
)
from caprm.water_distance import (
    load_hydrography_cache,
    prepare_distance_properties,
)
from caprm.water_export import (
    export_water_feature_metadata,
    export_water_properties,
    export_water_vertices,
    prepare_water_features,
    validate_reference_alignment,
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
            "Export deterministic EPSG:26918 water geometry and "
            "property inputs for C++ nearest-water computation."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
    )

    parser.add_argument(
        "--reference",
        default="outputs/baseline/python_nearest_water.csv",
    )

    parser.add_argument(
        "--properties-output",
        default=(
            "outputs/cpp_input/"
            "water_properties_projected.csv"
        ),
    )

    parser.add_argument(
        "--features-output",
        default="outputs/cpp_input/water_features.csv",
    )

    parser.add_argument(
        "--vertices-output",
        default="outputs/cpp_input/water_vertices.csv",
    )

    parser.add_argument(
        "--manifest-output",
        default=(
            "outputs/validation/"
            "water_cpp_input_manifest.json"
        ),
    )

    args = parser.parse_args()

    config = load_yaml(args.config)
    hydrography_config = config["hydrography"]

    cache_path = repository_path(
        hydrography_config["cache_path"]
    )

    cache_manifest_path = repository_path(
        hydrography_config["manifest_path"]
    )

    reference_path = repository_path(
        args.reference
    )

    properties_output = repository_path(
        args.properties_output
    )

    features_output = repository_path(
        args.features_output
    )

    vertices_output = repository_path(
        args.vertices_output
    )

    manifest_output = repository_path(
        args.manifest_output
    )

    cache_manifest = json.loads(
        cache_manifest_path.read_text(
            encoding="utf-8"
        )
    )

    actual_cache_checksum = calculate_sha256(
        cache_path
    )

    if (
        actual_cache_checksum
        != cache_manifest["cache_sha256"]
    ):
        raise RuntimeError(
            "Hydrography cache checksum does not match its manifest."
        )

    distance_crs = config["project"][
        "distance_crs"
    ]

    properties = load_property_points(
        config,
        refresh=False,
    )

    projected_properties = prepare_distance_properties(
        properties,
        distance_crs,
    )

    hydrography = load_hydrography_cache(
        cache_path,
        distance_crs,
    )

    feature_table = prepare_water_features(
        hydrography
    )

    reference = pd.read_csv(
        reference_path,
        dtype={"property_id": "string"},
    )

    validate_reference_alignment(
        projected_properties,
        feature_table,
        reference,
    )

    property_statistics = export_water_properties(
        projected_properties,
        properties_output,
    )

    feature_statistics = (
        export_water_feature_metadata(
            feature_table,
            features_output,
        )
    )

    vertex_statistics = export_water_vertices(
        feature_table,
        vertices_output,
    )

    manifest = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "distance_crs": distance_crs,
        "hydrography_cache": display_path(
            cache_path
        ),
        "hydrography_cache_sha256": (
            actual_cache_checksum
        ),
        "python_reference": display_path(
            reference_path
        ),
        "python_reference_sha256": (
            calculate_sha256(reference_path)
        ),
        "properties_output": display_path(
            properties_output
        ),
        "features_output": display_path(
            features_output
        ),
        "vertices_output": display_path(
            vertices_output
        ),
        **property_statistics,
        **feature_statistics,
        **vertex_statistics,
    }

    manifest_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_output.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()