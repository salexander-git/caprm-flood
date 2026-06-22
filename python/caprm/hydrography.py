from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import requests


DESIRED_SOURCE_FIELDS = {
    "OBJECTID",
    "id3dhp",
    "featuredate",
    "featuretype",
    "featuretypelabel",
    "gnisid",
    "gnisidlabel",
    "workunitid",
    "lengthkm",
    "areasqkm",
}


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def build_query_envelope(
    properties: gpd.GeoDataFrame,
    query_crs: str,
    buffer_meters: float,
) -> tuple[float, float, float, float]:
    if buffer_meters <= 0:
        raise ValueError(
            "Hydrography query buffer must be greater than zero."
        )

    if properties.empty:
        raise ValueError("Property dataset is empty.")

    if properties.crs is None:
        raise ValueError("Property dataset has no CRS.")

    projected = properties.to_crs(query_crs)

    bounds = projected.total_bounds.astype(float)

    if not np.isfinite(bounds).all():
        raise ValueError(
            "Property dataset produced nonfinite query bounds."
        )

    min_x, min_y, max_x, max_y = bounds

    return (
        min_x - buffer_meters,
        min_y - buffer_meters,
        max_x + buffer_meters,
        max_y + buffer_meters,
    )


def case_insensitive_column(
    dataframe: pd.DataFrame,
    required_name: str,
) -> str:
    mapping = {
        column.lower(): column
        for column in dataframe.columns
    }

    actual = mapping.get(required_name.lower())

    if actual is None:
        raise ValueError(
            f"Required source field is absent: {required_name}"
        )

    return actual


def feature_type_counts(
    dataframe: pd.DataFrame,
) -> dict[str, int]:
    counts = (
        dataframe["water_feature_type"]
        .value_counts(dropna=False)
    )

    return {
        "<missing>" if pd.isna(key) else str(key): int(value)
        for key, value in counts.items()
    }


def geometry_type_counts(
    dataframe: gpd.GeoDataFrame,
) -> dict[str, int]:
    counts = dataframe.geometry.geom_type.value_counts(
        dropna=False
    )

    return {
        "<missing>" if pd.isna(key) else str(key): int(value)
        for key, value in counts.items()
    }


def query_arcgis_layer(
    session: requests.Session,
    service_url: str,
    layer_id: int,
    included_feature_types: list[int],
    envelope: tuple[float, float, float, float],
    query_crs_wkid: int,
    output_crs_wkid: int,
    timeout_seconds: int = 120,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    layer_url = f"{service_url.rstrip('/')}/{layer_id}"

    metadata_response = session.get(
        layer_url,
        params={"f": "json"},
        timeout=timeout_seconds,
    )
    metadata_response.raise_for_status()

    metadata = metadata_response.json()

    if "error" in metadata:
        raise RuntimeError(
            "ArcGIS layer metadata error: "
            f"{json.dumps(metadata['error'])}"
        )

    object_id_field = metadata.get("objectIdField")

    if not object_id_field:
        for field in metadata.get("fields", []):
            if field.get("type") == "esriFieldTypeOID":
                object_id_field = field.get("name")
                break

    if not object_id_field:
        raise RuntimeError(
            f"Layer {layer_id} does not expose an object-ID field."
        )

    available_fields = {
        field["name"]
        for field in metadata.get("fields", [])
    }

    desired_lower = {
        field.lower()
        for field in DESIRED_SOURCE_FIELDS
    }

    out_fields = sorted(
        field
        for field in available_fields
        if (
            field.lower() in desired_lower
            or field == object_id_field
        )
    )

    required_fields = {
        "id3dhp",
        "featuretype",
        "featuretypelabel",
    }

    available_lower = {
        field.lower()
        for field in out_fields
    }

    missing_required = sorted(
        required_fields - available_lower
    )

    if missing_required:
        raise RuntimeError(
            f"Layer {layer_id} lacks required fields: "
            f"{missing_required}"
        )

    max_record_count = int(
        metadata.get("maxRecordCount", 2500)
    )

    page_size = min(max_record_count, 2500)

    where_clause = (
        "featuretype IN ("
        + ",".join(
            str(value)
            for value in included_feature_types
        )
        + ")"
    )

    min_x, min_y, max_x, max_y = envelope

    features: list[dict[str, Any]] = []
    offset = 0

    while True:
        response = session.get(
            f"{layer_url}/query",
            params={
                "f": "geojson",
                "where": where_clause,
                "geometry": (
                    f"{min_x},{min_y},{max_x},{max_y}"
                ),
                "geometryType": "esriGeometryEnvelope",
                "inSR": query_crs_wkid,
                "spatialRel": "esriSpatialRelIntersects",
                "outSR": output_crs_wkid,
                "outFields": ",".join(out_fields),
                "returnGeometry": "true",
                "returnZ": "false",
                "returnM": "false",
                "orderByFields": (
                    f"{object_id_field} ASC"
                ),
                "resultOffset": offset,
                "resultRecordCount": page_size,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()

        if "error" in payload:
            raise RuntimeError(
                "ArcGIS query error: "
                f"{json.dumps(payload['error'])}"
            )

        page_features = payload.get("features")

        if not isinstance(page_features, list):
            raise RuntimeError(
                "ArcGIS query did not return a GeoJSON "
                "feature collection."
            )

        if not page_features:
            break

        features.extend(page_features)
        offset += len(page_features)

        if len(page_features) < page_size:
            break

    if not features:
        raise RuntimeError(
            f"Layer {layer_id} returned no selected features."
        )

    dataframe = gpd.GeoDataFrame.from_features(
        features,
        crs=f"EPSG:{output_crs_wkid}",
    )

    return dataframe, {
        "layer_id": layer_id,
        "layer_name": metadata.get("name"),
        "geometry_type": metadata.get("geometryType"),
        "object_id_field": object_id_field,
        "max_record_count": max_record_count,
        "where_clause": where_clause,
        "returned_feature_count": len(dataframe),
    }


def canonicalize_hydrography(
    dataframe: gpd.GeoDataFrame,
    feature_class: str,
    included_feature_types: list[int],
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    if feature_class not in {
        "flowline",
        "waterbody",
    }:
        raise ValueError(
            f"Unsupported hydrography class: {feature_class}"
        )

    source_id_column = case_insensitive_column(
        dataframe,
        "id3dhp",
    )

    object_id_column = case_insensitive_column(
        dataframe,
        "OBJECTID",
    )

    type_column = case_insensitive_column(
        dataframe,
        "featuretype",
    )

    type_label_column = case_insensitive_column(
        dataframe,
        "featuretypelabel",
    )

    prepared = dataframe.copy()

    source_ids = (
        prepared[source_id_column]
        .astype("string")
        .str.strip()
    )

    missing_ids = source_ids.isna() | source_ids.eq("")

    if missing_ids.any():
        raise ValueError(
            f"{feature_class} contains missing id3dhp values."
        )

    type_codes = pd.to_numeric(
        prepared[type_column],
        errors="raise",
    ).astype("Int64")

    unexpected_types = sorted(
        set(type_codes.dropna().astype(int))
        - set(included_feature_types)
    )

    if unexpected_types:
        raise ValueError(
            f"{feature_class} contains unrequested feature types: "
            f"{unexpected_types}"
        )

    prepared["source_feature_id"] = source_ids
    prepared["water_feature_class"] = feature_class
    prepared["water_feature_id"] = (
        feature_class
        + ":"
        + source_ids
    )

    prepared["source_object_id"] = pd.to_numeric(
        prepared[object_id_column],
        errors="raise",
    ).astype("Int64")

    prepared["water_feature_type_code"] = type_codes

    prepared["water_feature_type"] = (
        prepared[type_label_column]
        .astype("string")
        .str.strip()
    )

    optional_string_fields = {
        "source_name": "gnisidlabel",
        "source_gnis_id": "gnisid",
        "source_feature_date": "featuredate",
        "source_workunit_id": "workunitid",
    }

    lower_mapping = {
        column.lower(): column
        for column in prepared.columns
    }

    for canonical_name, source_name in (
        optional_string_fields.items()
    ):
        actual = lower_mapping.get(source_name.lower())

        if actual is None:
            prepared[canonical_name] = pd.Series(
                pd.NA,
                index=prepared.index,
                dtype="string",
            )
        else:
            prepared[canonical_name] = (
                prepared[actual]
                .astype("string")
                .str.strip()
                .mask(
                    lambda values: values.eq("")
                )
            )

    length_column = lower_mapping.get("lengthkm")
    area_column = lower_mapping.get("areasqkm")

    prepared["source_length_km"] = (
        pd.to_numeric(
            prepared[length_column],
            errors="coerce",
        ).astype("Float64")
        if length_column
        else pd.Series(
            pd.NA,
            index=prepared.index,
            dtype="Float64",
        )
    )

    prepared["source_area_sq_km"] = (
        pd.to_numeric(
            prepared[area_column],
            errors="coerce",
        ).astype("Float64")
        if area_column
        else pd.Series(
            pd.NA,
            index=prepared.index,
            dtype="Float64",
        )
    )

    null_geometry = prepared.geometry.isna()
    empty_geometry = prepared.geometry.is_empty

    excluded_geometry_count = int(
        (null_geometry | empty_geometry).sum()
    )

    prepared = prepared.loc[
        ~(null_geometry | empty_geometry)
    ].copy()

    allowed_geometry_types = (
        {"LineString", "MultiLineString"}
        if feature_class == "flowline"
        else {"Polygon", "MultiPolygon"}
    )

    observed_types = set(
        prepared.geometry.geom_type.dropna()
    )

    unsupported_types = sorted(
        observed_types - allowed_geometry_types
    )

    if unsupported_types:
        raise ValueError(
            f"{feature_class} contains unsupported geometries: "
            f"{unsupported_types}"
        )

    duplicates = prepared.loc[
        prepared["water_feature_id"].duplicated(
            keep=False
        ),
        "water_feature_id",
    ]

    if not duplicates.empty:
        raise ValueError(
            f"{feature_class} contains duplicate canonical IDs: "
            f"{duplicates.unique()[:10].tolist()}"
        )

    output_columns = [
        "water_feature_id",
        "water_feature_class",
        "water_feature_type_code",
        "water_feature_type",
        "source_feature_id",
        "source_object_id",
        "source_gnis_id",
        "source_name",
        "source_feature_date",
        "source_workunit_id",
        "source_length_km",
        "source_area_sq_km",
        "geometry",
    ]

    prepared = prepared[
        output_columns
    ].sort_values(
        "source_object_id",
        kind="stable",
    ).reset_index(drop=True)

    statistics = {
        "feature_count": int(len(prepared)),
        "excluded_null_or_empty_geometry_count": (
            excluded_geometry_count
        ),
        "invalid_geometry_count": int(
            (~prepared.geometry.is_valid).sum()
        ),
        "geometry_types": geometry_type_counts(
            prepared
        ),
        "feature_type_counts": feature_type_counts(
            prepared
        ),
    }

    return prepared, statistics


def write_hydrography_cache(
    flowlines: gpd.GeoDataFrame,
    waterbodies: gpd.GeoDataFrame,
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

    flowlines.to_file(
        temporary_path,
        layer="flowlines",
        driver="GPKG",
    )

    waterbodies.to_file(
        temporary_path,
        layer="waterbodies",
        driver="GPKG",
        mode="a",
    )

    temporary_path.replace(output_path)