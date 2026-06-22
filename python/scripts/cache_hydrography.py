from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from pyproj import CRS


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.hydrography import (
    build_query_envelope,
    calculate_sha256,
    canonicalize_hydrography,
    query_arcgis_layer,
    write_hydrography_cache,
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


def epsg_code(crs_value: str) -> int:
    code = CRS.from_user_input(
        crs_value
    ).to_epsg()

    if code is None:
        raise ValueError(
            f"CRS does not resolve to an EPSG code: "
            f"{crs_value}"
        )

    return int(code)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Query and cache selected USGS 3DHP flowlines and "
            "waterbodies surrounding the deterministic property "
            "sample."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Replace an existing hydrography cache. The source "
            "service is never refreshed implicitly."
        ),
    )

    args = parser.parse_args()

    config_path = repository_path(args.config)
    config = load_yaml(config_path)

    hydrography_config = config.get(
        "hydrography"
    )

    if not isinstance(
        hydrography_config,
        dict,
    ):
        raise ValueError(
            "Configuration is missing hydrography."
        )

    cache_path = repository_path(
        hydrography_config["cache_path"]
    )

    manifest_path = repository_path(
        hydrography_config["manifest_path"]
    )

    if cache_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Hydrography cache already exists: {cache_path}\n"
            "Use --overwrite only for an intentional source refresh."
        )

    properties = load_property_points(
        config,
        refresh=False,
    )

    query_crs = hydrography_config[
        "query_crs"
    ]

    cache_crs = hydrography_config[
        "cache_crs"
    ]

    query_buffer_meters = float(
        hydrography_config[
            "query_buffer_meters"
        ]
    )

    envelope = build_query_envelope(
        properties=properties,
        query_crs=query_crs,
        buffer_meters=query_buffer_meters,
    )

    query_epsg = epsg_code(query_crs)
    cache_epsg = epsg_code(cache_crs)

    service_url = hydrography_config[
        "service_url"
    ]

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "CAPRM-Flood/0.2 "
                "(graduate geospatial research project)"
            )
        }
    )

    layer_outputs = {}
    layer_statistics = {}

    for feature_class in (
        "flowline",
        "waterbody",
    ):
        layer_config = hydrography_config[
            feature_class
        ]

        raw, query_statistics = (
            query_arcgis_layer(
                session=session,
                service_url=service_url,
                layer_id=int(
                    layer_config["layer_id"]
                ),
                included_feature_types=[
                    int(value)
                    for value in layer_config[
                        "included_feature_types"
                    ]
                ],
                envelope=envelope,
                query_crs_wkid=query_epsg,
                output_crs_wkid=cache_epsg,
            )
        )

        canonical, canonical_statistics = (
            canonicalize_hydrography(
                dataframe=raw,
                feature_class=feature_class,
                included_feature_types=[
                    int(value)
                    for value in layer_config[
                        "included_feature_types"
                    ]
                ],
            )
        )

        layer_outputs[feature_class] = canonical

        layer_statistics[feature_class] = {
            **query_statistics,
            **canonical_statistics,
        }

    write_hydrography_cache(
        flowlines=layer_outputs["flowline"],
        waterbodies=layer_outputs[
            "waterbody"
        ],
        output_path=cache_path,
    )

    manifest = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_name": hydrography_config[
            "source_name"
        ],
        "service_url": service_url,
        "source_is_dynamic": True,
        "property_cache": display_path(
            repository_path(
                config["property_points"][
                    "output_path"
                ]
            )
        ),
        "query_crs": query_crs,
        "cache_crs": cache_crs,
        "distance_crs": config["project"][
            "distance_crs"
        ],
        "query_buffer_meters": (
            query_buffer_meters
        ),
        "query_envelope": {
            "min_x": envelope[0],
            "min_y": envelope[1],
            "max_x": envelope[2],
            "max_y": envelope[3],
        },
        "query_completeness_condition": (
            "Every computed nearest-water distance must be "
            "strictly less than query_buffer_meters. Otherwise "
            "features outside the cached envelope may be closer."
        ),
        "cache_path": display_path(cache_path),
        "cache_size_bytes": (
            cache_path.stat().st_size
        ),
        "cache_sha256": calculate_sha256(
            cache_path
        ),
        "layers": layer_statistics,
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