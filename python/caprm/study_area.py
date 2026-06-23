from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import requests
from pyproj import CRS


REQUIRED_COUNTY_COLUMNS = {
    "county_geoid",
    "county_name",
    "source_object_id",
    "geometry",
}


def require_single_geometry(
    dataframe: gpd.GeoDataFrame,
    table_name: str,
) -> None:
    if len(dataframe) != 1:
        raise ValueError(
            f"{table_name} must contain exactly one feature; "
            f"received {len(dataframe)}."
        )

    if dataframe.crs is None:
        raise ValueError(
            f"{table_name} does not have a CRS."
        )

    geometry = dataframe.geometry.iloc[0]

    if geometry is None or geometry.is_empty:
        raise ValueError(
            f"{table_name} contains a null or empty geometry."
        )

    if not geometry.is_valid:
        raise ValueError(
            f"{table_name} contains an invalid geometry."
        )

    if geometry.geom_type not in {
        "Polygon",
        "MultiPolygon",
    }:
        raise ValueError(
            f"{table_name} must contain polygon geometry; "
            f"received {geometry.geom_type}."
        )


def case_insensitive_column(
    dataframe: gpd.GeoDataFrame,
    required_name: str,
) -> str:
    mapping = {
        column.lower(): column
        for column in dataframe.columns
    }

    actual = mapping.get(required_name.lower())

    if actual is None:
        raise ValueError(
            f"Required county field is absent: {required_name}"
        )

    return actual


def query_county_boundary(
    session: requests.Session,
    service_url: str,
    layer_id: int,
    county_geoid: str,
    output_crs_wkid: int,
    timeout_seconds: int = 120,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    layer_url = (
        f"{service_url.rstrip('/')}/{layer_id}"
    )

    metadata_response = session.get(
        layer_url,
        params={"f": "json"},
        timeout=timeout_seconds,
    )
    metadata_response.raise_for_status()

    metadata = metadata_response.json()

    if "error" in metadata:
        raise RuntimeError(
            "County-layer metadata error: "
            f"{json.dumps(metadata['error'])}"
        )

    response = session.get(
        f"{layer_url}/query",
        params={
            "f": "geojson",
            "where": f"GEOID = '{county_geoid}'",
            "outFields": (
                "OBJECTID,GEOID,STATE,COUNTY,"
                "NAME,BASENAME,AREALAND,AREAWATER"
            ),
            "returnGeometry": "true",
            "returnZ": "false",
            "returnM": "false",
            "outSR": output_crs_wkid,
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    payload = response.json()

    if "error" in payload:
        raise RuntimeError(
            "County-boundary query error: "
            f"{json.dumps(payload['error'])}"
        )

    features = payload.get("features")

    if not isinstance(features, list):
        raise RuntimeError(
            "County query did not return a GeoJSON "
            "feature collection."
        )

    if len(features) != 1:
        raise RuntimeError(
            "County query must return exactly one feature "
            f"for GEOID {county_geoid}; received "
            f"{len(features)}."
        )

    raw = gpd.GeoDataFrame.from_features(
        features,
        crs=f"EPSG:{output_crs_wkid}",
    )

    geoid_column = case_insensitive_column(
        raw,
        "GEOID",
    )

    name_column = case_insensitive_column(
        raw,
        "NAME",
    )

    object_id_column = case_insensitive_column(
        raw,
        "OBJECTID",
    )

    state_column = case_insensitive_column(
        raw,
        "STATE",
    )

    county_column = case_insensitive_column(
        raw,
        "COUNTY",
    )

    area_land_column = case_insensitive_column(
        raw,
        "AREALAND",
    )

    area_water_column = case_insensitive_column(
        raw,
        "AREAWATER",
    )

    county = gpd.GeoDataFrame(
        {
            "county_geoid": (
                raw[geoid_column]
                .astype("string")
                .str.strip()
            ),
            "county_name": (
                raw[name_column]
                .astype("string")
                .str.strip()
            ),
            "state_fips": (
                raw[state_column]
                .astype("string")
                .str.strip()
            ),
            "county_fips": (
                raw[county_column]
                .astype("string")
                .str.strip()
            ),
            "source_object_id": raw[
                object_id_column
            ],
            "source_area_land_sq_m": raw[
                area_land_column
            ],
            "source_area_water_sq_m": raw[
                area_water_column
            ],
        },
        geometry=raw.geometry.copy(),
        crs=raw.crs,
    )

    require_single_geometry(
        county,
        "Queried county boundary",
    )

    observed_geoid = str(
        county.loc[0, "county_geoid"]
    )

    if observed_geoid != county_geoid:
        raise RuntimeError(
            "County query returned the wrong GEOID: "
            f"{observed_geoid}"
        )

    statistics = {
        "service_url": service_url,
        "layer_id": layer_id,
        "layer_name": metadata.get("name"),
        "layer_description": metadata.get(
            "description"
        ),
        "geometry_type": metadata.get(
            "geometryType"
        ),
        "county_geoid": county_geoid,
        "returned_feature_count": 1,
    }

    return county, statistics


def write_study_area_cache(
    county: gpd.GeoDataFrame,
    output_path: Path,
) -> None:
    require_single_geometry(
        county,
        "County boundary",
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        f"{output_path.stem}.tmp"
        f"{output_path.suffix}"
    )

    temporary_path.unlink(
        missing_ok=True
    )

    county.to_file(
        temporary_path,
        driver="GeoJSON",
    )

    temporary_path.replace(output_path)


def load_study_area_cache(
    input_path: Path,
    expected_geoid: str,
) -> gpd.GeoDataFrame:
    if not input_path.exists():
        raise FileNotFoundError(
            f"County boundary cache does not exist: "
            f"{input_path}"
        )

    county = gpd.read_file(input_path)

    missing = sorted(
        REQUIRED_COUNTY_COLUMNS
        - set(county.columns)
    )

    if missing:
        raise ValueError(
            "County boundary cache is missing columns: "
            f"{missing}"
        )

    require_single_geometry(
        county,
        "County boundary cache",
    )

    county["county_geoid"] = (
        county["county_geoid"]
        .astype("string")
        .str.strip()
    )

    observed_geoid = str(
        county.loc[0, "county_geoid"]
    )

    if observed_geoid != expected_geoid:
        raise ValueError(
            "County boundary cache has the wrong GEOID: "
            f"{observed_geoid}"
        )

    return county


def build_buffered_study_area(
    county: gpd.GeoDataFrame,
    distance_crs: str,
    buffer_meters: float,
) -> gpd.GeoDataFrame:
    require_single_geometry(
        county,
        "County boundary",
    )

    if buffer_meters <= 0:
        raise ValueError(
            "Study-area buffer must be greater than zero."
        )

    target_crs = CRS.from_user_input(
        distance_crs
    )

    if not target_crs.is_projected:
        raise ValueError(
            f"Study-area CRS must be projected: "
            f"{distance_crs}"
        )

    projected = county.to_crs(target_crs)

    county_geometry = (
        projected.geometry.union_all()
    )

    buffered_geometry = county_geometry.buffer(
        buffer_meters
    )

    if (
        buffered_geometry.is_empty
        or not buffered_geometry.is_valid
    ):
        raise ValueError(
            "County buffering produced an invalid study area."
        )

    return gpd.GeoDataFrame(
        {
            "county_geoid": [
                str(
                    county.loc[
                        county.index[0],
                        "county_geoid",
                    ]
                )
            ],
            "buffer_meters": [
                float(buffer_meters)
            ],
        },
        geometry=[buffered_geometry],
        crs=target_crs,
    )


def study_area_envelope(
    study_area: gpd.GeoDataFrame,
) -> tuple[float, float, float, float]:
    require_single_geometry(
        study_area,
        "Buffered study area",
    )

    bounds = study_area.total_bounds.astype(
        float
    )

    if not np.isfinite(bounds).all():
        raise ValueError(
            "Buffered study area produced nonfinite bounds."
        )

    return tuple(
        float(value)
        for value in bounds
    )


def validate_properties_within_county(
    properties: gpd.GeoDataFrame,
    county: gpd.GeoDataFrame,
) -> dict[str, Any]:
    require_single_geometry(
        county,
        "County boundary",
    )

    if properties.empty:
        raise ValueError(
            "Property dataset is empty."
        )

    if properties.crs is None:
        raise ValueError(
            "Property dataset does not have a CRS."
        )

    if properties.geometry.isna().any():
        raise ValueError(
            "Property dataset contains null geometries."
        )

    if properties.geometry.is_empty.any():
        raise ValueError(
            "Property dataset contains empty geometries."
        )

    if properties.geometry.geom_type.ne(
        "Point"
    ).any():
        raise ValueError(
            "Property dataset contains non-Point geometry."
        )

    projected = properties.to_crs(
        county.crs
    )

    county_geometry = (
        county.geometry.union_all()
    )

    covered = projected.geometry.apply(
        county_geometry.covers
    )

    outside_count = int(
        (~covered).sum()
    )

    if outside_count:
        id_column = (
            "property_id"
            if "property_id" in projected.columns
            else None
        )

        if id_column:
            examples = (
                projected.loc[
                    ~covered,
                    id_column,
                ]
                .astype("string")
                .head(10)
                .tolist()
            )
        else:
            examples = (
                projected.index[
                    ~covered
                ][:10].tolist()
            )

        raise ValueError(
            f"{outside_count} property points fall outside "
            f"the official county boundary. Examples: "
            f"{examples}"
        )

    return {
        "property_count": int(
            len(properties)
        ),
        "properties_covered_by_county": int(
            covered.sum()
        ),
        "properties_outside_county": (
            outside_count
        ),
    }


def filter_features_to_study_area(
    features: gpd.GeoDataFrame,
    study_area: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    require_single_geometry(
        study_area,
        "Buffered study area",
    )

    if features.crs is None:
        raise ValueError(
            "Hydrography features do not have a CRS."
        )

    if features.empty:
        raise ValueError(
            "Hydrography feature dataset is empty."
        )

    projected = features.to_crs(
        study_area.crs
    )

    study_geometry = (
        study_area.geometry.union_all()
    )

    retained_mask = (
        projected.geometry.intersects(
            study_geometry
        )
    )

    retained = (
        features.loc[retained_mask]
        .copy()
        .reset_index(drop=True)
    )

    if retained.empty:
        raise ValueError(
            "Study-area filtering removed every "
            "hydrography feature."
        )

    statistics = {
        "feature_count_before_study_filter": (
            int(len(features))
        ),
        "retained_feature_count": int(
            len(retained)
        ),
        "excluded_outside_study_area_count": (
            int((~retained_mask).sum())
        ),
    }

    return retained, statistics


def study_area_statistics(
    county: gpd.GeoDataFrame,
    buffered_study_area: gpd.GeoDataFrame,
) -> dict[str, float]:
    require_single_geometry(
        county,
        "County boundary",
    )

    require_single_geometry(
        buffered_study_area,
        "Buffered study area",
    )

    county_projected = county.to_crs(
        buffered_study_area.crs
    )

    county_area_sq_km = float(
        county_projected.geometry.area.sum()
        / 1_000_000.0
    )

    buffered_area_sq_km = float(
        buffered_study_area.geometry.area.sum()
        / 1_000_000.0
    )

    return {
        "county_area_sq_km": (
            county_area_sq_km
        ),
        "buffered_study_area_sq_km": (
            buffered_area_sq_km
        ),
    }