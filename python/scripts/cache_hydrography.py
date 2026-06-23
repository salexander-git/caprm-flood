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

sys.path.insert(
    0,
    str(PYTHON_SOURCE_DIRECTORY),
)

from caprm.hydrography import (
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
from caprm.study_area import (
    build_buffered_study_area,
    filter_features_to_study_area,
    load_study_area_cache,
    query_county_boundary,
    study_area_envelope,
    study_area_statistics,
    validate_properties_within_county,
    write_study_area_cache,
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
            "CRS does not resolve to an EPSG code: "
            f"{crs_value}"
        )

    return int(code)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cache selected USGS 3DHP flowlines and "
            "waterbodies intersecting the official Monroe "
            "County boundary plus the configured metric buffer."
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
            "Replace the existing hydrography cache."
        ),
    )

    parser.add_argument(
        "--refresh-study-area",
        action="store_true",
        help=(
            "Refresh the official Census county-boundary "
            "cache before querying hydrography."
        ),
    )

    args = parser.parse_args()

    config_path = repository_path(args.config)
    config = load_yaml(config_path)

    study_area_config = config.get(
        "study_area"
    )

    hydrography_config = config.get(
        "hydrography"
    )

    if not isinstance(
        study_area_config,
        dict,
    ):
        raise ValueError(
            "Configuration is missing study_area."
        )

    if not isinstance(
        hydrography_config,
        dict,
    ):
        raise ValueError(
            "Configuration is missing hydrography."
        )

    hydrography_cache_path = repository_path(
        hydrography_config["cache_path"]
    )

    manifest_path = repository_path(
        hydrography_config["manifest_path"]
    )

    county_cache_path = repository_path(
        study_area_config["cache_path"]
    )

    if (
        hydrography_cache_path.exists()
        and not args.overwrite
    ):
        raise FileExistsError(
            "Hydrography cache already exists: "
            f"{hydrography_cache_path}\n"
            "Use --overwrite only for an intentional "
            "source refresh."
        )

    query_crs = hydrography_config[
        "query_crs"
    ]

    cache_crs = hydrography_config[
        "cache_crs"
    ]

    distance_crs = config["project"][
        "distance_crs"
    ]

    if query_crs != distance_crs:
        raise ValueError(
            "Hydrography query_crs and project "
            "distance_crs must match."
        )

    query_buffer_meters = float(
        hydrography_config[
            "query_buffer_meters"
        ]
    )

    query_epsg = epsg_code(query_crs)
    cache_epsg = epsg_code(cache_crs)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "CAPRM-Flood/0.2 "
                "(graduate geospatial research project)"
            )
        }
    )

    county_query_statistics = None

    if (
        args.refresh_study_area
        or not county_cache_path.exists()
    ):
        county, county_query_statistics = (
            query_county_boundary(
                session=session,
                service_url=(
                    study_area_config[
                        "service_url"
                    ]
                ),
                layer_id=int(
                    study_area_config[
                        "layer_id"
                    ]
                ),
                county_geoid=str(
                    study_area_config[
                        "county_geoid"
                    ]
                ),
                output_crs_wkid=epsg_code(
                    study_area_config[
                        "cache_crs"
                    ]
                ),
            )
        )

        write_study_area_cache(
            county,
            county_cache_path,
        )
    else:
        county = load_study_area_cache(
            county_cache_path,
            expected_geoid=str(
                study_area_config[
                    "county_geoid"
                ]
            ),
        )

    county_cache_checksum = calculate_sha256(
        county_cache_path
    )

    properties = load_property_points(
        config,
        refresh=False,
    )

    property_coverage = (
        validate_properties_within_county(
            properties,
            county,
        )
    )

    buffered_study_area = (
        build_buffered_study_area(
            county=county,
            distance_crs=query_crs,
            buffer_meters=(
                query_buffer_meters
            ),
        )
    )

    envelope = study_area_envelope(
        buffered_study_area
    )

    area_statistics = study_area_statistics(
        county,
        buffered_study_area,
    )

    service_url = hydrography_config[
        "service_url"
    ]

    layer_outputs = {}
    layer_statistics = {}

    for feature_class in (
        "flowline",
        "waterbody",
    ):
        layer_config = hydrography_config[
            feature_class
        ]

        included_feature_types = [
            int(value)
            for value in layer_config[
                "included_feature_types"
            ]
        ]

        raw, query_statistics = (
            query_arcgis_layer(
                session=session,
                service_url=service_url,
                layer_id=int(
                    layer_config["layer_id"]
                ),
                included_feature_types=(
                    included_feature_types
                ),
                envelope=envelope,
                query_crs_wkid=query_epsg,
                output_crs_wkid=cache_epsg,
            )
        )

        canonical, canonical_statistics = (
            canonicalize_hydrography(
                dataframe=raw,
                feature_class=feature_class,
                included_feature_types=(
                    included_feature_types
                ),
            )
        )

        retained, filter_statistics = (
            filter_features_to_study_area(
                canonical,
                buffered_study_area,
            )
        )

        layer_outputs[feature_class] = retained

        canonical_feature_count = int(
            canonical_statistics.pop(
                "feature_count"
            )
        )

        layer_statistics[feature_class] = {
            **query_statistics,
            "canonical_feature_count": (
                canonical_feature_count
            ),
            **canonical_statistics,
            **filter_statistics,
        }

    write_hydrography_cache(
        flowlines=layer_outputs["flowline"],
        waterbodies=layer_outputs[
            "waterbody"
        ],
        output_path=hydrography_cache_path,
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
        "study_area_basis": (
            "Official Monroe County boundary plus a "
            "metric outward buffer."
        ),
        "study_area": {
            "source_name": (
                study_area_config[
                    "source_name"
                ]
            ),
            "service_url": (
                study_area_config[
                    "service_url"
                ]
            ),
            "layer_id": int(
                study_area_config[
                    "layer_id"
                ]
            ),
            "county_geoid": str(
                study_area_config[
                    "county_geoid"
                ]
            ),
            "county_name": (
                study_area_config[
                    "county_name"
                ]
            ),
            "source_vintage": (
                study_area_config[
                    "source_vintage"
                ]
            ),
            "boundary_cache": display_path(
                county_cache_path
            ),
            "boundary_cache_size_bytes": (
                county_cache_path.stat().st_size
            ),
            "boundary_cache_sha256": (
                county_cache_checksum
            ),
            "boundary_query": (
                county_query_statistics
            ),
            **area_statistics,
        },
        "property_cache": display_path(
            repository_path(
                config["property_points"][
                    "output_path"
                ]
            )
        ),
        "property_coverage": (
            property_coverage
        ),
        "query_crs": query_crs,
        "cache_crs": cache_crs,
        "distance_crs": distance_crs,
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
            "All selected hydrography features intersecting "
            "the official county boundary plus the configured "
            "buffer are cached. For a property covered by the "
            "county polygon, a nearest distance strictly less "
            "than the buffer proves that no feature outside "
            "the cached study area can be closer."
        ),
        "cache_path": display_path(
            hydrography_cache_path
        ),
        "cache_size_bytes": (
            hydrography_cache_path.stat().st_size
        ),
        "cache_sha256": calculate_sha256(
            hydrography_cache_path
        ),
        "layers": layer_statistics,
    }

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            manifest,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()