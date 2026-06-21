from __future__ import annotations

from typing import Any

import geopandas as gpd
import pandas as pd

from caprm.validate import (
    normalize_bool_series,
    prepare_python_results,
)


OUTPUT_COLUMNS = [
    "property_id",
    "latitude",
    "longitude",
    "projected_x",
    "projected_y",
    "fema_zone",
    "sfha_flag",
    "is_sfha",
    "source_geometry_id",
    "fema_feature_index",
    "matched_fema_polygon",
    "python_sfha_result",
]


def select_existing_field(
    dataframe: pd.DataFrame,
    candidates: list[str],
    label: str,
) -> str:
    for candidate in candidates:
        if candidate in dataframe.columns:
            return candidate

    raise ValueError(
        f"No {label} field was found from candidates: "
        f"{candidates}"
    )


def determine_join_index_column(
    joined: gpd.GeoDataFrame,
    right_index_name: str | None,
) -> str:
    candidates = [
        right_index_name,
        "index_right",
    ]

    for candidate in candidates:
        if candidate and candidate in joined.columns:
            return candidate

    raise RuntimeError(
        "Could not determine the FEMA feature-index column "
        "produced by the spatial join."
    )


def validate_baseline_output(
    output: pd.DataFrame,
    expected_property_ids: set[str],
) -> None:
    missing_columns = sorted(
        set(OUTPUT_COLUMNS) - set(output.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Baseline output is missing columns: {missing_columns}"
        )

    prepare_python_results(output)

    actual_property_ids = set(
        output["property_id"]
        .astype("string")
        .str.strip()
    )

    if actual_property_ids != expected_property_ids:
        missing = sorted(
            expected_property_ids - actual_property_ids
        )[:10]

        unexpected = sorted(
            actual_property_ids - expected_property_ids
        )[:10]

        raise ValueError(
            "Baseline property IDs differ from the input. "
            f"Missing: {missing}; unexpected: {unexpected}"
        )

    matched = normalize_bool_series(
        output["matched_fema_polygon"],
        "matched_fema_polygon",
    )

    matched_without_source_id = (
        matched
        & output["source_geometry_id"].isna()
    )

    if matched_without_source_id.any():
        property_ids = output.loc[
            matched_without_source_id,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "Matched properties lack stable FEMA source IDs: "
            f"{property_ids}"
        )

    python_sfha = normalize_bool_series(
        output["python_sfha_result"],
        "python_sfha_result",
    )

    is_sfha = normalize_bool_series(
        output["is_sfha"],
        "is_sfha",
    )

    disagreement = python_sfha.ne(is_sfha)

    if disagreement.any():
        property_ids = output.loc[
            disagreement,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "python_sfha_result disagrees with is_sfha: "
            f"{property_ids}"
        )


def run_fema_point_in_polygon(
    properties: gpd.GeoDataFrame,
    fema: gpd.GeoDataFrame,
    config: dict[str, Any],
    predicate: str = "within",
) -> pd.DataFrame:
    if properties.crs != fema.crs:
        raise ValueError(
            "Property and FEMA datasets must use the same CRS."
        )

    required_property_columns = {
        "property_id",
        "latitude",
        "longitude",
        "projected_x",
        "projected_y",
        "geometry",
    }

    missing_property_columns = sorted(
        required_property_columns
        - set(properties.columns)
    )

    if missing_property_columns:
        raise ValueError(
            "Projected properties are missing columns: "
            f"{missing_property_columns}"
        )

    required_fema_columns = {
        "source_geometry_id",
        "fema_feature_index",
        "geometry",
    }

    missing_fema_columns = sorted(
        required_fema_columns - set(fema.columns)
    )

    if missing_fema_columns:
        raise ValueError(
            "FEMA data is missing columns: "
            f"{missing_fema_columns}"
        )

    fema_config = config["fema_flood_polygons"]

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

    right_columns = [
        zone_field,
        sfha_field,
        "source_geometry_id",
        "geometry",
    ]

    fema_join = fema[right_columns].copy()

    joined = gpd.sjoin(
        properties,
        fema_join,
        how="left",
        predicate=predicate,
    )

    join_index_column = determine_join_index_column(
        joined,
        fema_join.index.name,
    )

    duplicate_matches = joined.loc[
        joined["property_id"].duplicated(keep=False),
        "property_id",
    ]

    if not duplicate_matches.empty:
        raise RuntimeError(
            "One or more properties matched multiple FEMA polygons. "
            "An explicit overlap-resolution policy is required. "
            f"Properties: {duplicate_matches.unique()[:10].tolist()}"
        )

    matched = joined[
        join_index_column
    ].notna()

    normalized_sfha = normalize_bool_series(
        joined[sfha_field],
        sfha_field,
        allow_missing=True,
    )

    matched_missing_sfha = (
        matched & normalized_sfha.isna()
    )

    if matched_missing_sfha.any():
        property_ids = joined.loc[
            matched_missing_sfha,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "Matched FEMA features lack an SFHA flag: "
            f"{property_ids}"
        )

    matched_missing_zone = (
        matched & joined[zone_field].isna()
    )

    if matched_missing_zone.any():
        property_ids = joined.loc[
            matched_missing_zone,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "Matched FEMA features lack a flood zone: "
            f"{property_ids}"
        )

    output = pd.DataFrame(
        {
            "property_id": joined["property_id"],
            "latitude": joined["latitude"],
            "longitude": joined["longitude"],
            "projected_x": joined["projected_x"],
            "projected_y": joined["projected_y"],
            "fema_zone": joined[zone_field],
            "sfha_flag": joined[sfha_field],
            "is_sfha": normalized_sfha.fillna(False),
            "source_geometry_id": joined[
                "source_geometry_id"
            ],
            "fema_feature_index": pd.to_numeric(
                joined[join_index_column],
                errors="raise",
            ).astype("Int64"),
            "matched_fema_polygon": matched,
        }
    )

    output["python_sfha_result"] = output[
        "is_sfha"
    ]

    if "sample_order" in joined.columns:
        output["__sample_order"] = joined[
            "sample_order"
        ].to_numpy()

        output = (
            output
            .sort_values(
                "__sample_order",
                kind="stable",
            )
            .drop(columns=["__sample_order"])
        )

    output = output[
        OUTPUT_COLUMNS
    ].reset_index(drop=True)

    expected_property_ids = set(
        properties["property_id"]
        .astype("string")
        .str.strip()
    )

    validate_baseline_output(
        output,
        expected_property_ids,
    )

    return output