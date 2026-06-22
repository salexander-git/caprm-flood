from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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
    nearest_water_reference,
    prepare_distance_properties,
    summarize_nearest_water,
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
            "Compute the Python nearest-water reference for the "
            "deterministic CAPRM-Flood property sample."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
    )

    parser.add_argument(
        "--output",
        default=None,
    )

    parser.add_argument(
        "--summary-output",
        default=None,
    )

    parser.add_argument(
        "--tie-tolerance-meters",
        type=float,
        default=1e-6,
    )

    args = parser.parse_args()

    config_path = repository_path(args.config)
    config = load_yaml(config_path)

    hydrography_config = config["hydrography"]
    output_config = config["outputs"]

    cache_path = repository_path(
        hydrography_config["cache_path"]
    )

    manifest_path = repository_path(
        hydrography_config["manifest_path"]
    )

    output_path = repository_path(
        args.output
        or output_config[
            "python_nearest_water_csv"
        ]
    )

    summary_path = repository_path(
        args.summary_output
        or output_config[
            "python_nearest_water_summary"
        ]
    )

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Hydrography manifest does not exist: "
            f"{manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    expected_checksum = manifest.get(
        "cache_sha256"
    )

    actual_checksum = calculate_sha256(
        cache_path
    )

    if actual_checksum != expected_checksum:
        raise RuntimeError(
            "Hydrography cache checksum does not match its manifest."
        )

    distance_crs = config["project"][
        "distance_crs"
    ]

    if (
        manifest.get("distance_crs")
        != distance_crs
    ):
        raise RuntimeError(
            "Configured distance CRS differs from the hydrography "
            "cache manifest."
        )

    configured_buffer = float(
        hydrography_config[
            "query_buffer_meters"
        ]
    )

    manifest_buffer = float(
        manifest["query_buffer_meters"]
    )

    if configured_buffer != manifest_buffer:
        raise RuntimeError(
            "Configured hydrography buffer differs from the cache "
            "manifest."
        )

    properties = load_property_points(
        config,
        refresh=False,
    )

    properties_projected = (
        prepare_distance_properties(
            properties,
            distance_crs,
        )
    )

    hydrography = load_hydrography_cache(
        cache_path,
        distance_crs,
    )

    output = nearest_water_reference(
        properties=properties_projected,
        hydrography=hydrography,
        query_buffer_meters=configured_buffer,
        distance_crs=distance_crs,
        tie_tolerance_meters=(
            args.tie_tolerance_meters
        ),
    )

    summary = summarize_nearest_water(
        output
    )

    summary.update(
        {
            "distance_crs": distance_crs,
            "query_buffer_meters": (
                configured_buffer
            ),
            "tie_tolerance_meters": (
                args.tie_tolerance_meters
            ),
            "hydrography_feature_count": int(
                len(hydrography)
            ),
            "hydrography_cache": display_path(
                cache_path
            ),
            "hydrography_cache_sha256": (
                actual_checksum
            ),
            "property_cache": (
                config["property_points"][
                    "output_path"
                ]
            ),
            "output_csv": display_path(
                output_path
            ),
        }
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.to_csv(
        output_path,
        index=False,
        float_format="%.12f",
    )

    summary_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()