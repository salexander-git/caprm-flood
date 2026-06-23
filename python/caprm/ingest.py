from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_REQUEST_MAX_ATTEMPTS = 4
DEFAULT_REQUEST_RETRY_BACKOFF_SECONDS = 2.0
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}


def request_json_with_retries(
    method: str,
    url: str,
    *,
    timeout_seconds: int,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    max_attempts: int = DEFAULT_REQUEST_MAX_ATTEMPTS,
    retry_backoff_seconds: float = (
        DEFAULT_REQUEST_RETRY_BACKOFF_SECONDS
    ),
) -> dict[str, Any]:
    """Execute an idempotent ArcGIS request with bounded retries."""
    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be greater than zero."
        )

    if max_attempts <= 0:
        raise ValueError(
            "max_attempts must be greater than zero."
        )

    if retry_backoff_seconds < 0:
        raise ValueError(
            "retry_backoff_seconds cannot be negative."
        )

    normalized_method = method.upper()

    if normalized_method == "GET":
        request_function = requests.get
    elif normalized_method == "POST":
        request_function = requests.post
    else:
        raise ValueError(
            f"Unsupported HTTP method: {method}"
        )

    for attempt in range(1, max_attempts + 1):
        try:
            request_kwargs: dict[str, Any] = {
                "timeout": timeout_seconds,
            }

            if params is not None:
                request_kwargs["params"] = params

            if data is not None:
                request_kwargs["data"] = data

            response = request_function(
                url,
                **request_kwargs,
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                raise RuntimeError(
                    "ArcGIS response was not a JSON object."
                )

            return payload
        except requests.RequestException as error:
            status_code = getattr(
                getattr(error, "response", None),
                "status_code",
                None,
            )

            retryable = (
                isinstance(
                    error,
                    (
                        requests.Timeout,
                        requests.ConnectionError,
                    ),
                )
                or status_code
                in RETRYABLE_HTTP_STATUS_CODES
            )

            if not retryable or attempt == max_attempts:
                raise

            delay_seconds = (
                retry_backoff_seconds
                * (2 ** (attempt - 1))
            )

            print(
                "ArcGIS request failed "
                f"({normalized_method}, attempt "
                f"{attempt}/{max_attempts}): {error}. "
                f"Retrying in {delay_seconds:.1f} seconds."
            )

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    raise RuntimeError(
        "ArcGIS request retry loop exited unexpectedly."
    )


def repository_path(value: str | Path) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return REPOSITORY_ROOT / path


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved_path = repository_path(path)

    with resolved_path.open(
        "r",
        encoding="utf-8-sig",
    ) as input_file:
        config = yaml.safe_load(input_file)

    if not isinstance(config, dict):
        raise ValueError(
            f"Expected a YAML mapping at the root of {resolved_path}."
        )

    return config


def select_unique_identifier(
    dataframe: pd.DataFrame,
    candidates: list[str],
    label: str,
) -> str:
    diagnostics: list[str] = []

    for candidate in candidates:
        if candidate not in dataframe.columns:
            diagnostics.append(f"{candidate}: absent")
            continue

        values = (
            dataframe[candidate]
            .astype("string")
            .str.strip()
        )

        missing = values.isna() | values.eq("")
        duplicate = values.duplicated(keep=False) & ~missing

        if missing.any():
            diagnostics.append(
                f"{candidate}: {int(missing.sum())} missing"
            )
            continue

        if duplicate.any():
            diagnostics.append(
                f"{candidate}: "
                f"{int(values.nunique(dropna=True))} unique values "
                f"for {len(values)} rows"
            )
            continue

        return candidate

    raise ValueError(
        f"No complete unique {label} field was found. "
        + "; ".join(diagnostics)
    )

def select_existing_field(
    dataframe: pd.DataFrame,
    candidates: list[str],
    label: str,
) -> str:
    for candidate in candidates:
        if candidate in dataframe.columns:
            return candidate

    raise ValueError(
        f"No {label} field was found from candidates: {candidates}"
    )


def add_canonical_fema_fields(
    fema: gpd.GeoDataFrame,
    fema_config: dict[str, Any],
) -> gpd.GeoDataFrame:
    zone_field = select_existing_field(
        fema,
        fema_config["zone_field_candidates"],
        "FEMA zone",
    )

    sfha_field = select_existing_field(
        fema,
        fema_config["sfha_field_candidates"],
        "SFHA flag",
    )

    prepared = fema.copy()

    prepared["fema_zone"] = (
        prepared[zone_field]
        .astype("string")
        .str.strip()
        .mask(lambda values: values.eq(""))
    )

    prepared["sfha_flag"] = (
        prepared[sfha_field]
        .astype("string")
        .str.strip()
        .mask(lambda values: values.eq(""))
    )

    return prepared


def validate_property_points(
    properties: gpd.GeoDataFrame,
    expected_limit: int | None = None,
) -> gpd.GeoDataFrame:
    if properties.empty:
        raise ValueError("Property point dataset is empty.")

    if properties.crs is None:
        raise ValueError("Property point dataset has no CRS.")

    required_columns = {
        "property_id",
        "geometry",
    }

    missing_columns = sorted(
        required_columns - set(properties.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Property dataset is missing columns: {missing_columns}"
        )

    prepared = properties.copy()

    prepared["property_id"] = (
        prepared["property_id"]
        .astype("string")
        .str.strip()
    )

    missing_ids = (
        prepared["property_id"].isna()
        | prepared["property_id"].eq("")
    )

    if missing_ids.any():
        rows = prepared.index[missing_ids].tolist()[:10]
        raise ValueError(
            f"Property dataset has missing IDs at rows: {rows}"
        )

    duplicates = prepared.loc[
        prepared["property_id"].duplicated(keep=False),
        "property_id",
    ]

    if not duplicates.empty:
        raise ValueError(
            "Property dataset has duplicate IDs: "
            f"{duplicates.unique()[:10].tolist()}"
        )

    null_geometry = prepared.geometry.isna()
    empty_geometry = prepared.geometry.is_empty
    invalid_geometry = ~prepared.geometry.is_valid
    nonpoint_geometry = ~prepared.geometry.geom_type.eq("Point")

    if null_geometry.any():
        raise ValueError(
            "Property dataset contains null geometries."
        )

    if empty_geometry.any():
        raise ValueError(
            "Property dataset contains empty geometries."
        )

    if invalid_geometry.any():
        raise ValueError(
            "Property dataset contains invalid geometries."
        )

    if nonpoint_geometry.any():
        raise ValueError(
            "Property dataset contains non-Point geometries."
        )

    if expected_limit is not None and len(prepared) != expected_limit:
        raise ValueError(
            f"Expected {expected_limit} property rows, "
            f"but found {len(prepared)}."
        )

    if "sample_order" in prepared.columns:
        prepared["sample_order"] = pd.to_numeric(
            prepared["sample_order"],
            errors="raise",
        )

        if prepared["sample_order"].duplicated().any():
            raise ValueError(
                "Property dataset contains duplicate sample_order values."
            )

        prepared = prepared.sort_values(
            "sample_order",
            kind="stable",
        )

    return prepared.reset_index(drop=True)


def load_cached_property_points(
    config: dict[str, Any],
) -> gpd.GeoDataFrame:
    property_config = config.get("property_points")

    if not isinstance(property_config, dict):
        raise ValueError(
            "Configuration is missing property_points."
        )

    cache_value = property_config.get("output_path")

    if not cache_value:
        raise ValueError(
            "property_points.output_path is missing."
        )

    cache_path = repository_path(cache_value)

    if not cache_path.exists():
        raise FileNotFoundError(
            f"Property cache does not exist: {cache_path}\n"
            "Create it before running the baseline or explicitly refresh "
            "the remote source."
        )

    properties = gpd.read_file(cache_path)

    properties = validate_property_points(
        properties,
        expected_limit=property_config.get("sample_limit"),
    )

    if properties.crs != "EPSG:4326":
        properties = properties.to_crs("EPSG:4326")

    return properties


def prepare_property_cache(
    properties: gpd.GeoDataFrame,
    default_cache_origin: str | None = None,
) -> gpd.GeoDataFrame:
    """Return the minimal, ordered schema used by property cache files."""
    prepared = validate_property_points(properties)

    if prepared.crs != "EPSG:4326":
        prepared = prepared.to_crs("EPSG:4326")

    if "sample_order" not in prepared.columns:
        prepared["sample_order"] = range(len(prepared))

    if "cache_origin" not in prepared.columns:
        if default_cache_origin is None:
            raise ValueError(
                "Property dataset has no cache_origin and no default was supplied."
            )
        prepared["cache_origin"] = default_cache_origin

    cache = gpd.GeoDataFrame(
        {
            "sample_order": pd.to_numeric(
                prepared["sample_order"],
                errors="raise",
            ).astype("int64"),
            "property_id": (
                prepared["property_id"]
                .astype("string")
                .str.strip()
            ),
            "latitude": prepared.geometry.y.astype(float),
            "longitude": prepared.geometry.x.astype(float),
            "cache_origin": (
                prepared["cache_origin"]
                .astype("string")
                .str.strip()
            ),
        },
        geometry=prepared.geometry.copy(),
        crs="EPSG:4326",
    )

    cache = validate_property_points(cache)

    expected_order = list(range(len(cache)))
    actual_order = cache["sample_order"].astype(int).tolist()

    if actual_order != expected_order:
        raise ValueError(
            "Property cache sample_order must be consecutive from 0 "
            f"through {len(cache) - 1}."
        )

    return cache


def build_nested_property_sample(
    regression_properties: gpd.GeoDataFrame,
    remote_properties: gpd.GeoDataFrame,
    target_count: int,
) -> gpd.GeoDataFrame:
    """Build a larger deterministic workload containing the regression sample."""
    if target_count <= 0:
        raise ValueError("target_count must be positive.")

    regression = prepare_property_cache(regression_properties)
    remote = prepare_property_cache(
        remote_properties,
        default_cache_origin="arcgis_object_id_ordered_extension",
    )

    if target_count < len(regression):
        raise ValueError(
            f"target_count {target_count} is smaller than regression "
            f"count {len(regression)}."
        )

    regression_ids = set(regression["property_id"].astype(str))
    remote_extension = remote.loc[
        ~remote["property_id"].astype(str).isin(regression_ids)
    ].copy()

    required_extension_count = target_count - len(regression)

    if len(remote_extension) < required_extension_count:
        raise ValueError(
            "Remote property selection does not contain enough unique "
            "non-regression properties. "
            f"Required {required_extension_count}, found "
            f"{len(remote_extension)}."
        )

    remote_extension = remote_extension.head(
        required_extension_count
    ).copy()
    remote_extension["cache_origin"] = (
        "arcgis_object_id_ordered_extension"
    )

    combined = gpd.GeoDataFrame(
        pd.concat(
            [regression, remote_extension],
            ignore_index=True,
        ),
        geometry="geometry",
        crs="EPSG:4326",
    )
    combined["sample_order"] = range(len(combined))

    return validate_property_points(
        combined,
        expected_limit=target_count,
    )


def fetch_property_points_with_metadata(
    config: dict[str, Any],
    timeout_seconds: int = 120,
    sample_limit_override: int | None = None,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    """Fetch a deterministic property sample using sorted ArcGIS object IDs."""
    property_config = config.get("property_points")

    if not isinstance(property_config, dict):
        raise ValueError(
            "Configuration is missing property_points."
        )

    query_url = str(property_config["source_url"])
    layer_url = query_url.removesuffix("/query")

    request_max_attempts = int(
        property_config.get(
            "request_max_attempts",
            DEFAULT_REQUEST_MAX_ATTEMPTS,
        )
    )
    request_retry_backoff_seconds = float(
        property_config.get(
            "request_retry_backoff_seconds",
            DEFAULT_REQUEST_RETRY_BACKOFF_SECONDS,
        )
    )

    layer_metadata = request_json_with_retries(
        "GET",
        layer_url,
        params={"f": "json"},
        timeout_seconds=timeout_seconds,
        max_attempts=request_max_attempts,
        retry_backoff_seconds=(
            request_retry_backoff_seconds
        ),
    )

    object_id_field = layer_metadata.get("objectIdField")

    if not object_id_field:
        raise RuntimeError(
            "ArcGIS service metadata did not provide objectIdField."
        )

    sample_limit = int(
        sample_limit_override
        if sample_limit_override is not None
        else property_config.get("sample_limit", 1000)
    )

    if sample_limit <= 0:
        raise ValueError("Property sample limit must be positive.")

    county_value = str(
        property_config["county_value"]
    ).replace("'", "''")

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
            request_retry_backoff_seconds
        ),
    )

    object_ids = ids_payload.get("objectIds")

    if not isinstance(object_ids, list):
        raise RuntimeError(
            "ArcGIS object-ID response did not contain objectIds: "
            f"{json.dumps(ids_payload)[:500]}"
        )

    try:
        ordered_object_ids = sorted(int(value) for value in object_ids)
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "ArcGIS objectIds contained a non-integer value."
        ) from error

    if len(ordered_object_ids) < sample_limit:
        raise RuntimeError(
            f"Requested {sample_limit} properties but the county filter "
            f"matched only {len(ordered_object_ids)} object IDs."
        )

    service_limit = int(
        layer_metadata.get("maxRecordCount", 1000)
    )
    configured_batch_size = int(
        property_config.get("object_id_batch_size", 500)
    )
    batch_size = min(service_limit, configured_batch_size)

    if batch_size <= 0:
        raise ValueError(
            "property_points.object_id_batch_size must be positive."
        )

    canonical_id_field = property_config.get(
        "canonical_id_field"
    )

    selected_features: list[dict[str, Any]] = []
    selected_object_ids: list[int] = []
    seen_property_ids: set[str] = set()
    seen_response_object_ids: set[int] = set()

    requested_object_id_count = 0
    candidate_rows_examined = 0
    excluded_missing_property_id_count = 0
    excluded_duplicate_property_id_count = 0
    feature_request_count = 0
    last_requested_object_id: int | None = None

    for start in range(0, len(ordered_object_ids), batch_size):
        if len(selected_features) >= sample_limit:
            break

        batch = ordered_object_ids[start : start + batch_size]
        requested_object_id_count += len(batch)
        last_requested_object_id = batch[-1]
        feature_request_count += 1

        payload = request_json_with_retries(
            "POST",
            query_url,
            data={
                "objectIds": ",".join(str(value) for value in batch),
                "outFields": "*",
                "f": "geojson",
                "returnGeometry": "true",
                "outSR": 4326,
            },
            timeout_seconds=timeout_seconds,
            max_attempts=request_max_attempts,
            retry_backoff_seconds=(
                request_retry_backoff_seconds
            ),
        )

        page_features = payload.get("features")

        if not isinstance(page_features, list):
            raise RuntimeError(
                "Unexpected ArcGIS feature response: "
                f"{json.dumps(payload)[:500]}"
            )

        features_by_object_id: dict[int, dict[str, Any]] = {}

        for feature in page_features:
            if not isinstance(feature, dict):
                raise RuntimeError(
                    "ArcGIS feature response contained a non-object feature."
                )

            feature_properties = feature.get("properties")

            if not isinstance(feature_properties, dict):
                raise RuntimeError(
                    "ArcGIS feature response omitted feature properties."
                )

            if object_id_field not in feature_properties:
                raise RuntimeError(
                    "ArcGIS response omitted object-ID field "
                    f"{object_id_field}."
                )

            try:
                response_object_id = int(
                    feature_properties[object_id_field]
                )
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    "ArcGIS response contained a non-integer object ID."
                ) from error

            if response_object_id not in batch:
                raise RuntimeError(
                    "ArcGIS response contained an object ID outside the "
                    f"requested batch: {response_object_id}"
                )

            if response_object_id in seen_response_object_ids:
                raise RuntimeError(
                    "ArcGIS response contained a duplicate object ID: "
                    f"{response_object_id}"
                )

            seen_response_object_ids.add(response_object_id)
            features_by_object_id[response_object_id] = feature

        missing_object_ids = [
            object_id
            for object_id in batch
            if object_id not in features_by_object_id
        ]

        if missing_object_ids:
            raise RuntimeError(
                "ArcGIS response omitted requested object IDs: "
                f"{missing_object_ids[:10]}"
            )

        for object_id in batch:
            if len(selected_features) >= sample_limit:
                break

            feature = features_by_object_id[object_id]
            feature_properties = feature["properties"]
            candidate_rows_examined += 1

            if canonical_id_field:
                canonical_name = str(canonical_id_field)

                if canonical_name not in feature_properties:
                    raise RuntimeError(
                        "ArcGIS response omitted canonical property-ID "
                        f"field {canonical_name}."
                    )

                raw_property_id = feature_properties[canonical_name]

                if raw_property_id is None or bool(
                    pd.isna(raw_property_id)
                ):
                    excluded_missing_property_id_count += 1
                    continue

                property_id = str(raw_property_id).strip()

                if not property_id:
                    excluded_missing_property_id_count += 1
                    continue

                if property_id in seen_property_ids:
                    excluded_duplicate_property_id_count += 1
                    continue

                seen_property_ids.add(property_id)

            selected_features.append(feature)
            selected_object_ids.append(object_id)

    if len(selected_features) != sample_limit:
        raise RuntimeError(
            f"Requested {sample_limit} unique properties but only "
            f"{len(selected_features)} could be selected from "
            f"{len(ordered_object_ids)} ordered source rows."
        )

    properties = gpd.GeoDataFrame.from_features(
        selected_features,
        crs="EPSG:4326",
    )

    if canonical_id_field:
        id_field = select_unique_identifier(
            properties,
            [str(canonical_id_field)],
            "property identifier",
        )
    else:
        id_field = select_unique_identifier(
            properties,
            property_config["id_field_candidates"],
            "property identifier",
        )

    properties["property_id"] = (
        properties[id_field]
        .astype("string")
        .str.strip()
    )
    properties["sample_order"] = range(len(properties))
    properties["cache_origin"] = "arcgis_object_id_ordered"

    properties = validate_property_points(
        properties,
        expected_limit=sample_limit,
    )

    fetch_metadata = {
        "source_name": property_config.get("source_name"),
        "source_url": query_url,
        "source_layer_url": layer_url,
        "county_field": property_config["county_field"],
        "county_value": property_config["county_value"],
        "where_clause": where_clause,
        "selection_method": "sorted_arcgis_object_ids",
        "source_object_id_field": str(object_id_field),
        "source_ordering": f"{object_id_field} ASC",
        "property_id_field": id_field,
        "property_id_selection_rule": (
            "Retain the first nonmissing canonical property ID in "
            "ascending source object-ID order; skip later duplicate IDs."
            if canonical_id_field
            else "Select the first configured complete unique ID field."
        ),
        "source_matching_object_id_count": len(ordered_object_ids),
        "source_object_ids_requested_count": requested_object_id_count,
        "candidate_rows_examined_count": candidate_rows_examined,
        "selected_object_id_count": len(selected_object_ids),
        "selected_first_object_id": selected_object_ids[0],
        "selected_last_object_id": selected_object_ids[-1],
        "last_requested_object_id": last_requested_object_id,
        "excluded_missing_property_id_count": (
            excluded_missing_property_id_count
        ),
        "excluded_duplicate_property_id_count": (
            excluded_duplicate_property_id_count
        ),
        "service_max_record_count": service_limit,
        "object_id_batch_size": batch_size,
        "object_id_request_method": "GET",
        "feature_request_method": "POST",
        "feature_request_count": feature_request_count,
        "request_timeout_seconds": timeout_seconds,
        "request_max_attempts": request_max_attempts,
        "request_retry_backoff_seconds": (
            request_retry_backoff_seconds
        ),
        "source_current_version": layer_metadata.get("currentVersion"),
        "source_last_edit_epoch_ms": (
            (layer_metadata.get("editingInfo") or {}).get(
                "lastEditDate"
            )
        ),
    }

    return properties, fetch_metadata


def fetch_property_points(
    config: dict[str, Any],
    timeout_seconds: int = 120,
) -> gpd.GeoDataFrame:
    properties, _ = fetch_property_points_with_metadata(
        config,
        timeout_seconds=timeout_seconds,
    )
    return properties

def write_property_cache(
    properties: gpd.GeoDataFrame,
    config: dict[str, Any],
) -> Path:
    output_path = repository_path(
        config["property_points"]["output_path"]
    )

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

    return output_path


def load_property_points(
    config: dict[str, Any],
    refresh: bool = False,
) -> gpd.GeoDataFrame:
    if not refresh:
        return load_cached_property_points(config)

    properties = fetch_property_points(config)
    write_property_cache(properties, config)

    return properties


def load_fema_polygons(
    config: dict[str, Any],
) -> gpd.GeoDataFrame:
    fema_config = config.get("fema_flood_polygons")

    if not isinstance(fema_config, dict):
        raise ValueError(
            "Configuration is missing fema_flood_polygons."
        )

    input_value = fema_config.get("manual_input_path")

    if not input_value:
        raise ValueError(
            "fema_flood_polygons.manual_input_path is missing."
        )

    input_path = repository_path(input_value)

    if not input_path.exists():
        raise FileNotFoundError(
            f"FEMA polygon file does not exist: {input_path}"
        )

    fema = gpd.read_file(input_path)

    if fema.empty:
        raise ValueError("FEMA polygon dataset is empty.")

    if fema.crs is None:
        raise ValueError("FEMA polygon dataset has no CRS.")

    id_field = select_unique_identifier(
        fema,
        fema_config["id_field_candidates"],
        "FEMA feature identifier",
    )

    fema = add_canonical_fema_fields(
        fema,
        fema_config,
    )

    fema["source_geometry_id"] = (
        fema[id_field]
        .astype("string")
        .str.strip()
    )

    fema["fema_feature_index"] = fema.index.astype(int)

    null_or_empty = (
        fema.geometry.isna()
        | fema.geometry.is_empty
    )

    if null_or_empty.any():
        print(
            "Excluded "
            f"{int(null_or_empty.sum())} FEMA rows with null or empty "
            "geometry."
        )
        fema = fema.loc[~null_or_empty].copy()

    fema = fema.set_index(
        "fema_feature_index",
        drop=False,
    )

    print(f"FEMA identifier field: {id_field}")
    print(f"FEMA usable features: {len(fema)}")
    print(
        "FEMA invalid geometries retained for current baseline: "
        f"{int((~fema.geometry.is_valid).sum())}"
    )

    return fema