from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely.strtree import STRtree


REQUIRED_WATER_COLUMNS = {
    "water_feature_id",
    "water_feature_class",
    "water_feature_type",
    "source_feature_id",
    "source_object_id",
    "source_name",
    "geometry",
}

OUTPUT_COLUMNS = [
    "property_id",
    "nearest_water_distance_m",
    "nearest_water_feature_id",
    "nearest_water_feature_class",
    "nearest_water_feature_type",
    "nearest_water_source_id",
    "nearest_water_source_object_id",
    "nearest_water_name",
    "nearest_water_tie_count",
    "distance_crs",
]


def require_columns(
    dataframe: pd.DataFrame,
    required_columns: set[str],
    table_name: str,
) -> None:
    missing = sorted(
        required_columns - set(dataframe.columns)
    )

    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {missing}"
        )


def load_hydrography_cache(
    cache_path: Path,
    distance_crs: str,
) -> gpd.GeoDataFrame:
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Hydrography cache does not exist: {cache_path}"
        )

    flowlines = gpd.read_file(
        cache_path,
        layer="flowlines",
    )

    waterbodies = gpd.read_file(
        cache_path,
        layer="waterbodies",
    )

    if flowlines.crs is None:
        raise ValueError(
            "Cached flowlines do not have a CRS."
        )

    if waterbodies.crs is None:
        raise ValueError(
            "Cached waterbodies do not have a CRS."
        )

    if flowlines.crs != waterbodies.crs:
        raise ValueError(
            "Cached hydrography layers use different CRSs."
        )

    hydrography = gpd.GeoDataFrame(
        pd.concat(
            [flowlines, waterbodies],
            ignore_index=True,
        ),
        geometry="geometry",
        crs=flowlines.crs,
    )

    require_columns(
        hydrography,
        REQUIRED_WATER_COLUMNS,
        "Hydrography cache",
    )

    missing_ids = (
        hydrography["water_feature_id"].isna()
        | hydrography["water_feature_id"]
        .astype("string")
        .str.strip()
        .eq("")
    )

    if missing_ids.any():
        raise ValueError(
            "Hydrography cache contains missing canonical IDs."
        )

    duplicates = hydrography.loc[
        hydrography["water_feature_id"].duplicated(
            keep=False
        ),
        "water_feature_id",
    ]

    if not duplicates.empty:
        raise ValueError(
            "Hydrography cache contains duplicate canonical IDs: "
            f"{duplicates.unique()[:10].tolist()}"
        )

    null_or_empty = (
        hydrography.geometry.isna()
        | hydrography.geometry.is_empty
    )

    if null_or_empty.any():
        raise ValueError(
            "Hydrography cache contains null or empty geometries."
        )

    invalid = ~hydrography.geometry.is_valid

    if invalid.any():
        feature_ids = hydrography.loc[
            invalid,
            "water_feature_id",
        ].tolist()[:10]

        raise ValueError(
            "Hydrography cache contains invalid geometries: "
            f"{feature_ids}"
        )

    target_crs = CRS.from_user_input(
        distance_crs
    )

    if not target_crs.is_projected:
        raise ValueError(
            f"Distance CRS must be projected: {distance_crs}"
        )

    hydrography = hydrography.to_crs(
        target_crs
    )

    hydrography = (
        hydrography
        .sort_values(
            "water_feature_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    return hydrography


def prepare_distance_properties(
    properties: gpd.GeoDataFrame,
    distance_crs: str,
) -> gpd.GeoDataFrame:
    require_columns(
        properties,
        {
            "property_id",
            "geometry",
        },
        "Property dataset",
    )

    if properties.crs is None:
        raise ValueError(
            "Property dataset does not have a CRS."
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
        raise ValueError(
            "Property dataset contains missing property IDs."
        )

    if prepared["property_id"].duplicated().any():
        raise ValueError(
            "Property dataset contains duplicate property IDs."
        )

    if prepared.geometry.isna().any():
        raise ValueError(
            "Property dataset contains null geometries."
        )

    if prepared.geometry.is_empty.any():
        raise ValueError(
            "Property dataset contains empty geometries."
        )

    if (~prepared.geometry.is_valid).any():
        raise ValueError(
            "Property dataset contains invalid geometries."
        )

    nonpoints = ~prepared.geometry.geom_type.eq(
        "Point"
    )

    if nonpoints.any():
        raise ValueError(
            "Property dataset contains non-Point geometries."
        )

    prepared = prepared.to_crs(distance_crs)

    if "sample_order" in prepared.columns:
        prepared = prepared.sort_values(
            "sample_order",
            kind="stable",
        )

    return prepared.reset_index(drop=True)


def nearest_water_reference(
    properties: gpd.GeoDataFrame,
    hydrography: gpd.GeoDataFrame,
    query_buffer_meters: float,
    distance_crs: str,
    tie_tolerance_meters: float = 1e-6,
) -> pd.DataFrame:
    if query_buffer_meters <= 0:
        raise ValueError(
            "query_buffer_meters must be greater than zero."
        )

    if tie_tolerance_meters < 0:
        raise ValueError(
            "tie_tolerance_meters cannot be negative."
        )

    require_columns(
        hydrography,
        REQUIRED_WATER_COLUMNS,
        "Hydrography dataset",
    )

    if properties.crs != hydrography.crs:
        raise ValueError(
            "Properties and hydrography must use the same CRS."
        )

    if properties.empty:
        raise ValueError(
            "Property dataset is empty."
        )

    if hydrography.empty:
        raise ValueError(
            "Hydrography dataset is empty."
        )

    geometry_values = hydrography.geometry.array
    spatial_index = STRtree(geometry_values)

    records: list[dict[str, Any]] = []

    for property_row in properties.itertuples(
        index=False
    ):
        point = property_row.geometry

        indices, distances = (
            spatial_index.query_nearest(
                point,
                all_matches=True,
                return_distance=True,
            )
        )

        candidate_indices = np.atleast_1d(
            indices
        ).astype(int)

        candidate_distances = np.atleast_1d(
            distances
        ).astype(float)

        if len(candidate_indices) == 0:
            raise RuntimeError(
                f"No nearest water feature was found for "
                f"property {property_row.property_id}."
            )

        minimum_distance = float(
            candidate_distances.min()
        )

        tie_mask = (
            candidate_distances
            <= minimum_distance
            + tie_tolerance_meters
        )

        tied_indices = candidate_indices[
            tie_mask
        ]

        tied_features = hydrography.iloc[
            tied_indices
        ].copy()

        tied_features = tied_features.sort_values(
            "water_feature_id",
            kind="stable",
        )

        selected = tied_features.iloc[0]

        selected_index = int(
            tied_features.index[0]
        )

        selected_distance = float(
            point.distance(
                hydrography.geometry.iloc[
                    selected_index
                ]
            )
        )

        records.append(
            {
                "property_id": (
                    property_row.property_id
                ),
                "nearest_water_distance_m": (
                    selected_distance
                ),
                "nearest_water_feature_id": (
                    selected["water_feature_id"]
                ),
                "nearest_water_feature_class": (
                    selected["water_feature_class"]
                ),
                "nearest_water_feature_type": (
                    selected["water_feature_type"]
                ),
                "nearest_water_source_id": (
                    selected["source_feature_id"]
                ),
                "nearest_water_source_object_id": (
                    selected["source_object_id"]
                ),
                "nearest_water_name": (
                    selected["source_name"]
                ),
                "nearest_water_tie_count": int(
                    len(tied_features)
                ),
                "distance_crs": distance_crs,
            }
        )

    output = pd.DataFrame.from_records(
        records,
        columns=OUTPUT_COLUMNS,
    )

    if output[
        "nearest_water_distance_m"
    ].isna().any():
        raise RuntimeError(
            "Nearest-water output contains missing distances."
        )

    if (
        output["nearest_water_distance_m"] < 0
    ).any():
        raise RuntimeError(
            "Nearest-water output contains negative distances."
        )

    incomplete = (
        output["nearest_water_distance_m"]
        >= query_buffer_meters
    )

    if incomplete.any():
        examples = output.loc[
            incomplete,
            [
                "property_id",
                "nearest_water_distance_m",
            ],
        ].head(10)

        raise RuntimeError(
            "The hydrography query buffer cannot prove nearest-feature "
            "completeness for every property. Distances must be strictly "
            f"less than {query_buffer_meters} meters.\n"
            f"{examples.to_string(index=False)}"
        )

    if output["property_id"].duplicated().any():
        raise RuntimeError(
            "Nearest-water output contains duplicate property IDs."
        )

    return output


def summarize_nearest_water(
    output: pd.DataFrame,
) -> dict[str, Any]:
    distances = output[
        "nearest_water_distance_m"
    ]

    class_counts = (
        output["nearest_water_feature_class"]
        .value_counts(dropna=False)
    )

    type_counts = (
        output["nearest_water_feature_type"]
        .value_counts(dropna=False)
    )

    return {
        "property_count": int(len(output)),
        "unique_property_ids": int(
            output["property_id"].nunique()
        ),
        "minimum_distance_m": float(
            distances.min()
        ),
        "maximum_distance_m": float(
            distances.max()
        ),
        "mean_distance_m": float(
            distances.mean()
        ),
        "median_distance_m": float(
            distances.median()
        ),
        "zero_distance_property_count": int(
            distances.eq(0.0).sum()
        ),
        "multiple_nearest_tie_count": int(
            output["nearest_water_tie_count"]
            .gt(1)
            .sum()
        ),
        "unique_nearest_feature_count": int(
            output["nearest_water_feature_id"]
            .nunique()
        ),
        "nearest_feature_class_counts": {
            str(key): int(value)
            for key, value in class_counts.items()
        },
        "nearest_feature_type_counts": {
            str(key): int(value)
            for key, value in type_counts.items()
        },
    }