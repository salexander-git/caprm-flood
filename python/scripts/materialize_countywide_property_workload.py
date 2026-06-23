from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = REPOSITORY_ROOT / "python"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from caprm.ingest import (  # noqa: E402
    DEFAULT_REQUEST_MAX_ATTEMPTS,
    DEFAULT_REQUEST_RETRY_BACKOFF_SECONDS,
    load_yaml,
    prepare_property_cache,
    repository_path,
    request_json_with_retries,
)


DEFAULT_CONFIG_PATH = (
    REPOSITORY_ROOT
    / "configs"
    / "monroe_fema_spike_100000.yaml"
)

DEFAULT_PREFIX_CACHE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "monroe_property_points_sample_100000.geojson"
)

DEFAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "monroe_property_points_countywide.geojson"
)

DEFAULT_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "validation"
    / "property_cache_countywide_manifest.json"
)


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(
            REPOSITORY_ROOT
        ).as_posix()
    except ValueError:
        return str(resolved)


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_geojson_atomic(
    properties: gpd.GeoDataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        f"{output_path.stem}.tmp{output_path.suffix}"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    properties.to_file(
        temporary_path,
        driver="GeoJSON",
    )

    temporary_path.replace(output_path)


def write_json_atomic(
    payload: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        f"{output_path.stem}.tmp{output_path.suffix}"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    temporary_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    temporary_path.replace(output_path)


def ensure_output_is_safe(
    output_path: Path,
    prefix_cache_path: Path,
    overwrite: bool,
) -> None:
    if output_path.resolve() == prefix_cache_path.resolve():
        raise ValueError(
            "The countywide output must not overwrite the "
            "validated prefix cache."
        )

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Countywide property cache already exists: "
            f"{output_path}\n"
            "Rerun with --overwrite only when replacement "
            "is intended."
        )


def validate_geojson_point_feature(
    feature: dict[str, Any],
    object_id: int,
) -> None:
    geometry = feature.get("geometry")

    if not isinstance(geometry, dict):
        raise RuntimeError(
            "ArcGIS feature has no usable geometry for "
            f"object ID {object_id}."
        )

    if geometry.get("type") != "Point":
        raise RuntimeError(
            "ArcGIS feature is not a Point for object ID "
            f"{object_id}: {geometry.get('type')!r}"
        )

    coordinates = geometry.get("coordinates")

    if (
        not isinstance(coordinates, (list, tuple))
        or len(coordinates) < 2
    ):
        raise RuntimeError(
            "ArcGIS Point geometry has invalid coordinates "
            f"for object ID {object_id}."
        )

    try:
        x = float(coordinates[0])
        y = float(coordinates[1])
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "ArcGIS Point geometry has nonnumeric coordinates "
            f"for object ID {object_id}."
        ) from error

    if not math.isfinite(x) or not math.isfinite(y):
        raise RuntimeError(
            "ArcGIS Point geometry has nonfinite coordinates "
            f"for object ID {object_id}."
        )


def fetch_all_unique_property_points(
    config: dict[str, Any],
    timeout_seconds: int,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    """
    Fetch every Monroe County source row in ascending ArcGIS
    object-ID order and retain the first nonmissing occurrence
    of each canonical property ID.
    """
    property_config = config.get("property_points")

    if not isinstance(property_config, dict):
        raise ValueError(
            "Configuration is missing property_points."
        )

    canonical_id_field = property_config.get(
        "canonical_id_field"
    )

    if not canonical_id_field:
        raise ValueError(
            "property_points.canonical_id_field must be "
            "configured."
        )

    canonical_id_field = str(canonical_id_field)

    query_url = str(
        property_config["source_url"]
    )

    layer_url = query_url.removesuffix(
        "/query"
    )

    request_max_attempts = int(
        property_config.get(
            "request_max_attempts",
            DEFAULT_REQUEST_MAX_ATTEMPTS,
        )
    )

    retry_backoff_seconds = float(
        property_config.get(
            "request_retry_backoff_seconds",
            DEFAULT_REQUEST_RETRY_BACKOFF_SECONDS,
        )
    )

    layer_metadata = request_json_with_retries(
        "GET",
        layer_url,
        params={
            "f": "json",
        },
        timeout_seconds=timeout_seconds,
        max_attempts=request_max_attempts,
        retry_backoff_seconds=(
            retry_backoff_seconds
        ),
    )

    object_id_field = layer_metadata.get(
        "objectIdField"
    )

    if not object_id_field:
        raise RuntimeError(
            "ArcGIS service metadata did not provide "
            "objectIdField."
        )

    object_id_field = str(
        object_id_field
    )

    county_value = str(
        property_config["county_value"]
    ).replace(
        "'",
        "''",
    )

    where_clause = (
        f"{property_config['county_field']} = "
        f"'{county_value}'"
    )

    ids_payload = request_json_with_retries(
        "GET",
        query_url,
        params={
            "where": where_clause,
            "returnIdsOnly": "true",
            "f": "json",
        },
        timeout_seconds=timeout_seconds,
        max_attempts=request_max_attempts,
        retry_backoff_seconds=(
            retry_backoff_seconds
        ),
    )

    object_ids = ids_payload.get(
        "objectIds"
    )

    if not isinstance(object_ids, list):
        raise RuntimeError(
            "ArcGIS object-ID response did not contain "
            f"objectIds: {json.dumps(ids_payload)[:500]}"
        )

    try:
        ordered_object_ids = sorted(
            int(value)
            for value in object_ids
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "ArcGIS objectIds contained a non-integer "
            "value."
        ) from error

    if not ordered_object_ids:
        raise RuntimeError(
            "The county filter returned no ArcGIS "
            "object IDs."
        )

    if (
        len(set(ordered_object_ids))
        != len(ordered_object_ids)
    ):
        raise RuntimeError(
            "ArcGIS object-ID response contained "
            "duplicate IDs."
        )

    service_limit = int(
        layer_metadata.get(
            "maxRecordCount",
            1000,
        )
    )

    configured_batch_size = int(
        property_config.get(
            "object_id_batch_size",
            500,
        )
    )

    batch_size = min(
        service_limit,
        configured_batch_size,
    )

    if batch_size <= 0:
        raise ValueError(
            "property_points.object_id_batch_size "
            "must be positive."
        )

    selected_features: list[
        dict[str, Any]
    ] = []

    selected_object_ids: list[int] = []

    seen_property_ids: set[str] = set()
    seen_response_object_ids: set[int] = set()

    candidate_rows_examined = 0
    excluded_missing_property_id_count = 0
    excluded_duplicate_property_id_count = 0
    feature_request_count = 0

    total_batches = (
        len(ordered_object_ids)
        + batch_size
        - 1
    ) // batch_size

    for batch_number, start in enumerate(
        range(
            0,
            len(ordered_object_ids),
            batch_size,
        ),
        start=1,
    ):
        batch = ordered_object_ids[
            start : start + batch_size
        ]

        feature_request_count += 1

        payload = request_json_with_retries(
            "POST",
            query_url,
            data={
                "objectIds": ",".join(
                    str(value)
                    for value in batch
                ),
                "outFields": (
                    f"{object_id_field},"
                    f"{canonical_id_field}"
                ),
                "f": "geojson",
                "returnGeometry": "true",
                "outSR": 4326,
            },
            timeout_seconds=timeout_seconds,
            max_attempts=request_max_attempts,
            retry_backoff_seconds=(
                retry_backoff_seconds
            ),
        )

        page_features = payload.get(
            "features"
        )

        if not isinstance(
            page_features,
            list,
        ):
            raise RuntimeError(
                "Unexpected ArcGIS feature response: "
                f"{json.dumps(payload)[:500]}"
            )

        features_by_object_id: dict[
            int,
            dict[str, Any],
        ] = {}

        for feature in page_features:
            if not isinstance(feature, dict):
                raise RuntimeError(
                    "ArcGIS response contained a "
                    "non-object feature."
                )

            feature_properties = feature.get(
                "properties"
            )

            if not isinstance(
                feature_properties,
                dict,
            ):
                raise RuntimeError(
                    "ArcGIS response omitted feature "
                    "properties."
                )

            if (
                object_id_field
                not in feature_properties
            ):
                raise RuntimeError(
                    "ArcGIS response omitted object-ID "
                    f"field {object_id_field}."
                )

            try:
                response_object_id = int(
                    feature_properties[
                        object_id_field
                    ]
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise RuntimeError(
                    "ArcGIS response contained a "
                    "non-integer object ID."
                ) from error

            if response_object_id not in batch:
                raise RuntimeError(
                    "ArcGIS response contained an object "
                    "ID outside the requested batch: "
                    f"{response_object_id}"
                )

            if (
                response_object_id
                in seen_response_object_ids
            ):
                raise RuntimeError(
                    "ArcGIS response contained a "
                    "duplicate object ID: "
                    f"{response_object_id}"
                )

            if (
                response_object_id
                in features_by_object_id
            ):
                raise RuntimeError(
                    "ArcGIS response repeated an object "
                    "ID within one batch: "
                    f"{response_object_id}"
                )

            seen_response_object_ids.add(
                response_object_id
            )

            features_by_object_id[
                response_object_id
            ] = feature

        missing_object_ids = [
            object_id
            for object_id in batch
            if object_id
            not in features_by_object_id
        ]

        if missing_object_ids:
            raise RuntimeError(
                "ArcGIS response omitted requested "
                "object IDs: "
                f"{missing_object_ids[:10]}"
            )

        for object_id in batch:
            feature = features_by_object_id[
                object_id
            ]

            feature_properties = feature[
                "properties"
            ]

            candidate_rows_examined += 1

            if (
                canonical_id_field
                not in feature_properties
            ):
                raise RuntimeError(
                    "ArcGIS response omitted canonical "
                    "property-ID field "
                    f"{canonical_id_field}."
                )

            raw_property_id = feature_properties[
                canonical_id_field
            ]

            if (
                raw_property_id is None
                or bool(pd.isna(raw_property_id))
            ):
                excluded_missing_property_id_count += 1
                continue

            property_id = str(
                raw_property_id
            ).strip()

            if not property_id:
                excluded_missing_property_id_count += 1
                continue

            if property_id in seen_property_ids:
                excluded_duplicate_property_id_count += 1
                continue

            validate_geojson_point_feature(
                feature,
                object_id,
            )

            seen_property_ids.add(
                property_id
            )

            selected_features.append(
                feature
            )

            selected_object_ids.append(
                object_id
            )

        if (
            batch_number % 25 == 0
            or batch_number == total_batches
        ):
            print(
                "Fetched "
                f"{batch_number}/{total_batches} "
                "batches; "
                f"{len(selected_features)} unique "
                "properties retained."
            )

    if not selected_features:
        raise RuntimeError(
            "No usable property features were "
            "selected."
        )

    remote = (
        gpd.GeoDataFrame.from_features(
            selected_features,
            crs="EPSG:4326",
        )
    )

    remote["property_id"] = (
        remote[canonical_id_field]
        .astype("string")
        .str.strip()
    )

    remote["sample_order"] = range(
        len(remote)
    )

    remote["cache_origin"] = (
        "arcgis_countywide_object_id_ordered"
    )

    remote = prepare_property_cache(
        remote
    )

    metadata = {
        "source_name": property_config.get(
            "source_name"
        ),
        "source_url": query_url,
        "source_layer_url": layer_url,
        "county_field": property_config[
            "county_field"
        ],
        "county_value": property_config[
            "county_value"
        ],
        "where_clause": where_clause,
        "selection_method": (
            "all_sorted_arcgis_object_ids_with_"
            "unique_canonical_property_ids"
        ),
        "source_object_id_field": (
            object_id_field
        ),
        "source_ordering": (
            f"{object_id_field} ASC"
        ),
        "property_id_field": (
            canonical_id_field
        ),
        "property_id_selection_rule": (
            "Scan every matching source row in "
            "ascending object-ID order; retain the "
            "first nonmissing occurrence of each "
            "canonical property ID and skip later "
            "duplicates."
        ),
        "geometry_selection_rule": (
            "Require every retained canonical "
            "property record to have a finite "
            "GeoJSON Point geometry in EPSG:4326."
        ),
        "source_matching_object_id_count": (
            len(ordered_object_ids)
        ),
        "candidate_rows_examined_count": (
            candidate_rows_examined
        ),
        "selected_unique_property_count": (
            len(remote)
        ),
        "selected_first_object_id": (
            selected_object_ids[0]
        ),
        "selected_last_object_id": (
            selected_object_ids[-1]
        ),
        "excluded_missing_property_id_count": (
            excluded_missing_property_id_count
        ),
        "excluded_duplicate_property_id_count": (
            excluded_duplicate_property_id_count
        ),
        "service_max_record_count": (
            service_limit
        ),
        "object_id_batch_size": (
            batch_size
        ),
        "object_id_request_method": (
            "GET"
        ),
        "feature_request_method": (
            "POST"
        ),
        "feature_request_count": (
            feature_request_count
        ),
        "request_timeout_seconds": (
            timeout_seconds
        ),
        "request_max_attempts": (
            request_max_attempts
        ),
        "request_retry_backoff_seconds": (
            retry_backoff_seconds
        ),
        "source_current_version": (
            layer_metadata.get(
                "currentVersion"
            )
        ),
        "source_last_edit_epoch_ms": (
            (
                layer_metadata.get(
                    "editingInfo"
                )
                or {}
            ).get(
                "lastEditDate"
            )
        ),
    }

    return remote, metadata


def compare_prefix_with_current_source(
    prefix: gpd.GeoDataFrame,
    remote: gpd.GeoDataFrame,
    coordinate_tolerance_degrees: float,
) -> dict[str, Any]:
    if coordinate_tolerance_degrees < 0.0:
        raise ValueError(
            "coordinate tolerance must be "
            "nonnegative."
        )

    prefix_cache = prepare_property_cache(
        prefix
    )

    remote_cache = prepare_property_cache(
        remote,
        default_cache_origin=(
            "arcgis_countywide_object_id_ordered"
        ),
    )

    prefix_ids = set(
        prefix_cache[
            "property_id"
        ].astype(str)
    )

    remote_ids = set(
        remote_cache[
            "property_id"
        ].astype(str)
    )

    absent_prefix_ids = sorted(
        prefix_ids - remote_ids
    )

    joined = prefix_cache[
        [
            "property_id",
            "latitude",
            "longitude",
        ]
    ].merge(
        remote_cache[
            [
                "property_id",
                "latitude",
                "longitude",
            ]
        ],
        on="property_id",
        how="inner",
        suffixes=(
            "_prefix",
            "_remote",
        ),
        validate="one_to_one",
    )

    latitude_difference = (
        joined["latitude_prefix"]
        - joined["latitude_remote"]
    ).abs()

    longitude_difference = (
        joined["longitude_prefix"]
        - joined["longitude_remote"]
    ).abs()

    coordinate_match = (
        latitude_difference
        <= coordinate_tolerance_degrees
    ) & (
        longitude_difference
        <= coordinate_tolerance_degrees
    )

    mismatch_ids = joined.loc[
        ~coordinate_match,
        "property_id",
    ].astype(str).tolist()

    return {
        "prefix_property_count": int(
            len(prefix_cache)
        ),
        "prefix_ids_found_in_current_source": int(
            len(prefix_ids & remote_ids)
        ),
        "prefix_ids_absent_from_current_source": int(
            len(absent_prefix_ids)
        ),
        "prefix_absent_id_examples": (
            absent_prefix_ids[:10]
        ),
        "coordinate_tolerance_degrees": (
            coordinate_tolerance_degrees
        ),
        "coordinate_matches_within_tolerance": int(
            coordinate_match.sum()
        ),
        "coordinate_mismatches": int(
            (~coordinate_match).sum()
        ),
        "coordinate_mismatch_id_examples": (
            mismatch_ids[:10]
        ),
        "max_absolute_latitude_difference_degrees": (
            float(
                latitude_difference.max()
            )
            if not joined.empty
            else None
        ),
        "max_absolute_longitude_difference_degrees": (
            float(
                longitude_difference.max()
            )
            if not joined.empty
            else None
        ),
    }


def build_countywide_nested_cache(
    prefix: gpd.GeoDataFrame,
    remote: gpd.GeoDataFrame,
    coordinate_tolerance_degrees: float,
    allow_prefix_source_drift: bool,
) -> tuple[
    gpd.GeoDataFrame,
    dict[str, Any],
    dict[str, Any],
]:
    """
    Preserve the validated 100K workload exactly as the prefix,
    then append every remaining unique current-source property.
    """
    prefix_cache = prepare_property_cache(
        prefix
    )

    remote_cache = prepare_property_cache(
        remote,
        default_cache_origin=(
            "arcgis_countywide_object_id_ordered"
        ),
    )

    source_comparison = (
        compare_prefix_with_current_source(
            prefix=prefix_cache,
            remote=remote_cache,
            coordinate_tolerance_degrees=(
                coordinate_tolerance_degrees
            ),
        )
    )

    source_drift_detected = (
        source_comparison[
            "prefix_ids_absent_from_current_source"
        ]
        != 0
        or source_comparison[
            "coordinate_mismatches"
        ]
        != 0
    )

    if (
        source_drift_detected
        and not allow_prefix_source_drift
    ):
        raise RuntimeError(
            "The current ArcGIS source no longer "
            "exactly contains the validated prefix "
            "cache. Review the source-comparison "
            "diagnostics before allowing source drift. "
            "Absent IDs: "
            f"{source_comparison['prefix_ids_absent_from_current_source']}; "
            "coordinate mismatches: "
            f"{source_comparison['coordinate_mismatches']}."
        )

    prefix_ids = set(
        prefix_cache[
            "property_id"
        ].astype(str)
    )

    remote_ids = set(
        remote_cache[
            "property_id"
        ].astype(str)
    )

    remote_extension = remote_cache.loc[
        ~remote_cache[
            "property_id"
        ].astype(str).isin(
            prefix_ids
        )
    ].copy()

    remote_extension["cache_origin"] = (
        "arcgis_countywide_object_id_ordered_"
        "extension"
    )

    combined = gpd.GeoDataFrame(
        pd.concat(
            [
                prefix_cache,
                remote_extension,
            ],
            ignore_index=True,
        ),
        geometry="geometry",
        crs="EPSG:4326",
    )

    combined["sample_order"] = range(
        len(combined)
    )

    combined = prepare_property_cache(
        combined
    )

    prefix_count = len(
        prefix_cache
    )

    observed_prefix = combined.iloc[
        :prefix_count
    ].reset_index(
        drop=True
    )

    exact_prefix_ids = (
        observed_prefix[
            "property_id"
        ].astype(str).tolist()
        ==
        prefix_cache[
            "property_id"
        ].astype(str).tolist()
    )

    exact_prefix_order = (
        observed_prefix[
            "sample_order"
        ].astype(int).tolist()
        ==
        prefix_cache[
            "sample_order"
        ].astype(int).tolist()
    )

    exact_prefix_origin = (
        observed_prefix[
            "cache_origin"
        ].astype(str).tolist()
        ==
        prefix_cache[
            "cache_origin"
        ].astype(str).tolist()
    )

    exact_prefix_coordinates = bool(
        (
            observed_prefix.geometry.x.to_numpy()
            ==
            prefix_cache.geometry.x.to_numpy()
        ).all()
        and
        (
            observed_prefix.geometry.y.to_numpy()
            ==
            prefix_cache.geometry.y.to_numpy()
        ).all()
    )

    if not (
        exact_prefix_ids
        and exact_prefix_order
        and exact_prefix_origin
        and exact_prefix_coordinates
    ):
        raise RuntimeError(
            "The countywide cache did not preserve "
            "the validated prefix cache exactly."
        )

    combined_ids = set(
        combined[
            "property_id"
        ].astype(str)
    )

    missing_remote_ids = (
        remote_ids
        - combined_ids
    )

    if missing_remote_ids:
        raise RuntimeError(
            "Countywide cache omitted current-source "
            "property IDs: "
            f"{sorted(missing_remote_ids)[:10]}"
        )

    contract = {
        "row_count": int(
            len(combined)
        ),
        "unique_property_ids": int(
            combined[
                "property_id"
            ].nunique()
        ),
        "cache_crs": str(
            combined.crs
        ),
        "geometry_type_counts": {
            str(key): int(value)
            for key, value
            in (
                combined.geometry.geom_type
                .value_counts()
                .items()
            )
        },
        "first_sample_order": int(
            combined[
                "sample_order"
            ].min()
        ),
        "last_sample_order": int(
            combined[
                "sample_order"
            ].max()
        ),
        "validated_prefix_property_count": int(
            prefix_count
        ),
        "validated_prefix_preserved_exactly": (
            True
        ),
        "current_source_unique_property_count": int(
            len(remote_cache)
        ),
        "current_source_ids_present_in_cache": int(
            len(
                remote_ids
                & combined_ids
            )
        ),
        "current_source_is_subset_of_cache": (
            remote_ids.issubset(
                combined_ids
            )
        ),
        "cache_matches_current_source_id_set": (
            combined_ids
            == remote_ids
        ),
        "prefix_ids_absent_from_current_source": int(
            len(
                prefix_ids
                - remote_ids
            )
        ),
        "countywide_extension_property_count": int(
            len(remote_extension)
        ),
        "source_drift_allowed": bool(
            allow_prefix_source_drift
        ),
    }

    return (
        combined,
        contract,
        source_comparison,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a deterministic countywide Monroe "
            "County property cache by scanning every "
            "matching ArcGIS object ID, deduplicating "
            "canonical property IDs, preserving the "
            "validated 100K workload as the exact prefix, "
            "and appending every remaining current-source "
            "property."
        )
    )

    parser.add_argument(
        "--config",
        default=str(
            DEFAULT_CONFIG_PATH
        ),
        help=(
            "Existing CAPRM-Flood configuration used "
            "for source connection settings."
        ),
    )

    parser.add_argument(
        "--prefix-cache",
        default=str(
            DEFAULT_PREFIX_CACHE_PATH
        ),
        help=(
            "Validated workload cache that must remain "
            "the exact ordered prefix. Defaults to the "
            "completed 100K cache."
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            DEFAULT_OUTPUT_PATH
        ),
        help=(
            "Countywide GeoJSON output path."
        ),
    )

    parser.add_argument(
        "--manifest-output",
        default=str(
            DEFAULT_MANIFEST_PATH
        ),
        help=(
            "Countywide cache manifest output path."
        ),
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help=(
            "HTTP timeout for each ArcGIS request."
        ),
    )

    parser.add_argument(
        "--coordinate-tolerance-degrees",
        type=float,
        default=1e-9,
        help=(
            "Tolerance for checking validated-prefix "
            "coordinates against the current ArcGIS "
            "source."
        ),
    )

    parser.add_argument(
        "--allow-prefix-source-drift",
        action="store_true",
        help=(
            "Permit prefix IDs absent from the current "
            "source or prefix/source coordinate "
            "mismatches. Omit this flag for the normal "
            "strict countywide run."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Replace an existing countywide cache and "
            "manifest."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.timeout_seconds <= 0:
        raise ValueError(
            "--timeout-seconds must be positive."
        )

    config_path = repository_path(
        args.config
    )

    prefix_cache_path = repository_path(
        args.prefix_cache
    )

    output_path = repository_path(
        args.output
    )

    manifest_path = repository_path(
        args.manifest_output
    )

    ensure_output_is_safe(
        output_path=output_path,
        prefix_cache_path=prefix_cache_path,
        overwrite=args.overwrite,
    )

    if (
        manifest_path.exists()
        and not args.overwrite
    ):
        raise FileExistsError(
            "Countywide property-cache manifest "
            "already exists: "
            f"{manifest_path}\n"
            "Rerun with --overwrite only when "
            "replacement is intended."
        )

    if not prefix_cache_path.exists():
        raise FileNotFoundError(
            "Validated prefix cache does not exist: "
            f"{prefix_cache_path}"
        )

    config = load_yaml(
        config_path
    )

    prefix = gpd.read_file(
        prefix_cache_path
    )

    prefix = prepare_property_cache(
        prefix
    )

    remote, source_metadata = (
        fetch_all_unique_property_points(
            config=config,
            timeout_seconds=(
                args.timeout_seconds
            ),
        )
    )

    (
        countywide,
        contract,
        source_comparison,
    ) = build_countywide_nested_cache(
        prefix=prefix,
        remote=remote,
        coordinate_tolerance_degrees=(
            args.coordinate_tolerance_degrees
        ),
        allow_prefix_source_drift=(
            args.allow_prefix_source_drift
        ),
    )

    write_geojson_atomic(
        countywide,
        output_path,
    )

    manifest = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "cache_origin": (
            "validated_100k_prefix_plus_all_"
            "remaining_unique_county_arcgis_"
            "properties"
        ),
        "stable_ordering_rule": (
            "Preserve the validated prefix cache "
            "exactly in its existing sample_order, "
            "then append every current-source canonical "
            "property ID not already in that prefix, "
            "using the first nonmissing occurrence "
            "encountered while scanning all matching "
            "ArcGIS object IDs in ascending order."
        ),
        "config": display_path(
            config_path
        ),
        "config_sha256": calculate_sha256(
            config_path
        ),
        "canonical_property_id_field": str(
            config[
                "property_points"
            ][
                "canonical_id_field"
            ]
        ),
        "property_cache": display_path(
            output_path
        ),
        "property_cache_sha256": (
            calculate_sha256(
                output_path
            )
        ),
        "property_cache_size_bytes": int(
            output_path.stat().st_size
        ),
        **contract,
        "validated_prefix_cache": display_path(
            prefix_cache_path
        ),
        "validated_prefix_cache_sha256": (
            calculate_sha256(
                prefix_cache_path
            )
        ),
        "source": source_metadata,
        "prefix_current_source_comparison": (
            source_comparison
        ),
    }

    write_json_atomic(
        manifest,
        manifest_path,
    )

    print(
        json.dumps(
            manifest,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()