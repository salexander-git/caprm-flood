from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


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


def fetch_property_points(
    config: dict[str, Any],
    timeout_seconds: int = 120,
) -> gpd.GeoDataFrame:
    property_config = config["property_points"]

    query_url = property_config["source_url"]
    layer_url = query_url.removesuffix("/query")

    metadata_response = requests.get(
        layer_url,
        params={"f": "json"},
        timeout=timeout_seconds,
    )
    metadata_response.raise_for_status()

    metadata = metadata_response.json()

    object_id_field = metadata.get("objectIdField")

    if not object_id_field:
        raise RuntimeError(
            "ArcGIS service metadata did not provide objectIdField."
        )

    sample_limit = int(
        property_config.get("sample_limit", 1000)
    )

    service_limit = int(
        metadata.get("maxRecordCount", 1000)
    )

    county_value = str(
        property_config["county_value"]
    ).replace("'", "''")

    where_clause = (
        f"{property_config['county_field']} = "
        f"'{county_value}'"
    )

    features: list[dict[str, Any]] = []
    result_offset = 0

    while len(features) < sample_limit:
        remaining = sample_limit - len(features)
        page_size = min(service_limit, remaining)

        response = requests.get(
            query_url,
            params={
                "where": where_clause,
                "outFields": "*",
                "f": "geojson",
                "returnGeometry": "true",
                "outSR": 4326,
                "orderByFields": f"{object_id_field} ASC",
                "resultOffset": result_offset,
                "resultRecordCount": page_size,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()

        page_features = payload.get("features")

        if not isinstance(page_features, list):
            raise RuntimeError(
                "Unexpected ArcGIS response: "
                f"{json.dumps(payload)[:500]}"
            )

        if not page_features:
            break

        features.extend(page_features)
        result_offset += len(page_features)

        if len(page_features) < page_size:
            break

    if len(features) != sample_limit:
        raise RuntimeError(
            f"Requested {sample_limit} properties but received "
            f"{len(features)}."
        )

    properties = gpd.GeoDataFrame.from_features(
        features,
        crs="EPSG:4326",
    )

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
    properties["cache_origin"] = "arcgis_refresh"

    return validate_property_points(
        properties,
        expected_limit=sample_limit,
    )


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

    fema = fema.copy()

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