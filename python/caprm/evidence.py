from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS


TRUE_VALUES = {
    "true",
    "t",
    "1",
    "yes",
    "y",
}

FALSE_VALUES = {
    "false",
    "f",
    "0",
    "no",
    "n",
}


FEMA_REQUIRED_COLUMNS = {
    "property_id",
    "latitude",
    "longitude",
    "projected_x",
    "projected_y",
    "fema_zone",
    "sfha_flag",
    "is_sfha",
    "fema_feature_index",
    "matched_fema_polygon",
}


WATER_REQUIRED_COLUMNS = {
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
}


OUTPUT_COLUMNS = [
    "sample_order",
    "property_id",
    "latitude",
    "longitude",
    "fema_projected_x",
    "fema_projected_y",
    "fema_project_crs",
    "water_projected_x",
    "water_projected_y",
    "distance_crs",
    "matched_fema_polygon",
    "fema_zone",
    "sfha_flag",
    "is_sfha",
    "fema_source_feature_id",
    "fema_feature_index",
    "nearest_water_distance_m",
    "nearest_water_feature_id",
    "nearest_water_feature_class",
    "nearest_water_feature_type",
    "nearest_water_source_id",
    "nearest_water_source_object_id",
    "nearest_water_name",
    "nearest_water_tie_count",
]


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


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


def normalize_string(
    series: pd.Series,
) -> pd.Series:
    normalized = (
        series.astype("string")
        .str.strip()
    )

    return normalized.mask(normalized.eq(""))


def strict_boolean_series(
    series: pd.Series,
    column_name: str,
) -> pd.Series:
    parsed: list[bool] = []

    for row_number, value in enumerate(
        series.tolist(),
        start=2,
    ):
        if pd.isna(value):
            raise ValueError(
                f"{column_name} contains a missing Boolean "
                f"value at CSV row {row_number}."
            )

        if isinstance(value, (bool, np.bool_)):
            parsed.append(bool(value))
            continue

        if isinstance(value, (int, np.integer)):
            if int(value) == 1:
                parsed.append(True)
                continue

            if int(value) == 0:
                parsed.append(False)
                continue

        text = str(value).strip().lower()

        if text in TRUE_VALUES:
            parsed.append(True)
            continue

        if text in FALSE_VALUES:
            parsed.append(False)
            continue

        raise ValueError(
            f"{column_name} contains an invalid Boolean "
            f"value at CSV row {row_number}: {value!r}"
        )

    return pd.Series(
        parsed,
        index=series.index,
        dtype="bool",
    )


def validate_property_ids(
    dataframe: pd.DataFrame,
    table_name: str,
) -> None:
    if "property_id" not in dataframe.columns:
        raise ValueError(
            f"{table_name} has no property_id column."
        )

    dataframe["property_id"] = normalize_string(
        dataframe["property_id"]
    )

    if dataframe["property_id"].isna().any():
        raise ValueError(
            f"{table_name} contains missing property IDs."
        )

    duplicates = dataframe.loc[
        dataframe["property_id"].duplicated(
            keep=False
        ),
        "property_id",
    ]

    if not duplicates.empty:
        raise ValueError(
            f"{table_name} contains duplicate property IDs: "
            f"{duplicates.unique()[:10].tolist()}"
        )


def require_identical_property_sets(
    named_dataframes: dict[str, pd.DataFrame],
) -> None:
    property_sets = {
        name: set(
            dataframe["property_id"].astype("string")
        )
        for name, dataframe in named_dataframes.items()
    }

    reference_name = next(iter(property_sets))
    reference_set = property_sets[reference_name]

    for name, property_set in property_sets.items():
        if property_set == reference_set:
            continue

        missing = sorted(reference_set - property_set)
        unexpected = sorted(property_set - reference_set)

        raise ValueError(
            f"{name} property IDs do not match "
            f"{reference_name}. "
            f"Missing examples: {missing[:10]}; "
            f"unexpected examples: {unexpected[:10]}"
        )


def resolve_fema_source_id_column(
    dataframe: pd.DataFrame,
) -> str:
    candidates = [
        "source_geometry_id",
        "fema_source_feature_id",
        "source_feature_id",
    ]

    for candidate in candidates:
        if candidate in dataframe.columns:
            return candidate

    raise ValueError(
        "FEMA baseline does not contain a recognized "
        "source-feature identifier column. Expected one of: "
        f"{candidates}"
    )


def prepare_property_coordinates(
    properties: gpd.GeoDataFrame,
    distance_crs: str,
) -> pd.DataFrame:
    require_columns(
        properties,
        {
            "property_id",
            "geometry",
        },
        "Property cache",
    )

    if properties.crs is None:
        raise ValueError(
            "Property cache does not have a CRS."
        )

    if properties.empty:
        raise ValueError(
            "Property cache is empty."
        )

    prepared = properties.copy()

    validate_property_ids(
        prepared,
        "Property cache",
    )

    if prepared.geometry.isna().any():
        raise ValueError(
            "Property cache contains null geometries."
        )

    if prepared.geometry.is_empty.any():
        raise ValueError(
            "Property cache contains empty geometries."
        )

    if prepared.geometry.geom_type.ne("Point").any():
        raise ValueError(
            "Property cache contains non-Point geometries."
        )

    target_crs = CRS.from_user_input(
        distance_crs
    )

    if not target_crs.is_projected:
        raise ValueError(
            f"Distance CRS must be projected: {distance_crs}"
        )

    geographic = prepared.to_crs("EPSG:4326")
    projected = prepared.to_crs(target_crs)

    if "sample_order" in prepared.columns:
        sample_order = pd.to_numeric(
            prepared["sample_order"],
            errors="raise",
        ).astype("int64")
    else:
        sample_order = pd.Series(
            range(len(prepared)),
            index=prepared.index,
            dtype="int64",
        )

    coordinates = pd.DataFrame(
        {
            "sample_order": sample_order,
            "property_id": prepared["property_id"],
            "cache_latitude": geographic.geometry.y,
            "cache_longitude": geographic.geometry.x,
            "water_projected_x": projected.geometry.x,
            "water_projected_y": projected.geometry.y,
        }
    )

    coordinates = coordinates.sort_values(
        "sample_order",
        kind="stable",
    ).reset_index(drop=True)

    expected_order = list(range(len(coordinates)))

    if (
        coordinates["sample_order"].tolist()
        != expected_order
    ):
        raise ValueError(
            "Property cache sample_order must be contiguous "
            "and begin at zero."
        )

    return coordinates


def prepare_fema_evidence(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    require_columns(
        dataframe,
        FEMA_REQUIRED_COLUMNS,
        "FEMA baseline",
    )

    prepared = dataframe.copy()

    validate_property_ids(
        prepared,
        "FEMA baseline",
    )

    source_id_column = (
        resolve_fema_source_id_column(prepared)
    )

    prepared["latitude"] = pd.to_numeric(
        prepared["latitude"],
        errors="raise",
    ).astype("float64")

    prepared["longitude"] = pd.to_numeric(
        prepared["longitude"],
        errors="raise",
    ).astype("float64")

    prepared["projected_x"] = pd.to_numeric(
        prepared["projected_x"],
        errors="raise",
    ).astype("float64")

    prepared["projected_y"] = pd.to_numeric(
        prepared["projected_y"],
        errors="raise",
    ).astype("float64")

    coordinate_columns = [
        "latitude",
        "longitude",
        "projected_x",
        "projected_y",
    ]

    for column in coordinate_columns:
        if (~np.isfinite(prepared[column])).any():
            raise ValueError(
                f"FEMA baseline contains nonfinite {column}."
            )

    prepared["matched_fema_polygon"] = (
        strict_boolean_series(
            prepared["matched_fema_polygon"],
            "matched_fema_polygon",
        )
    )

    prepared["is_sfha"] = strict_boolean_series(
        prepared["is_sfha"],
        "is_sfha",
    )

    if "python_sfha_result" in prepared.columns:
        python_result = strict_boolean_series(
            prepared["python_sfha_result"],
            "python_sfha_result",
        )

        if not python_result.equals(
            prepared["is_sfha"]
        ):
            raise ValueError(
                "FEMA baseline is_sfha and "
                "python_sfha_result disagree."
            )

    prepared["fema_zone"] = normalize_string(
        prepared["fema_zone"]
    )

    prepared["sfha_flag"] = normalize_string(
        prepared["sfha_flag"]
    )

    prepared["fema_source_feature_id"] = (
        normalize_string(
            prepared[source_id_column]
        )
    )

    prepared["fema_feature_index"] = (
        pd.to_numeric(
            prepared["fema_feature_index"],
            errors="coerce",
        ).astype("Int64")
    )

    matched = prepared["matched_fema_polygon"]

    if prepared.loc[
        matched,
        "fema_zone",
    ].isna().any():
        raise ValueError(
            "Matched FEMA rows contain missing flood zones."
        )

    if prepared.loc[
        matched,
        "fema_source_feature_id",
    ].isna().any():
        raise ValueError(
            "Matched FEMA rows contain missing source IDs."
        )

    if prepared.loc[
        matched,
        "fema_feature_index",
    ].isna().any():
        raise ValueError(
            "Matched FEMA rows contain missing feature indices."
        )

    return prepared[
        [
            "property_id",
            "latitude",
            "longitude",
            "projected_x",
            "projected_y",
            "matched_fema_polygon",
            "fema_zone",
            "sfha_flag",
            "is_sfha",
            "fema_source_feature_id",
            "fema_feature_index",
        ]
    ].rename(
        columns={
            "projected_x": "fema_projected_x",
            "projected_y": "fema_projected_y",
        }
    )


def prepare_water_evidence(
    dataframe: pd.DataFrame,
    expected_distance_crs: str,
    query_buffer_meters: float,
) -> pd.DataFrame:
    require_columns(
        dataframe,
        WATER_REQUIRED_COLUMNS,
        "Nearest-water baseline",
    )

    prepared = dataframe.copy()

    validate_property_ids(
        prepared,
        "Nearest-water baseline",
    )

    prepared["nearest_water_distance_m"] = (
        pd.to_numeric(
            prepared[
                "nearest_water_distance_m"
            ],
            errors="raise",
        ).astype("float64")
    )

    distances = prepared[
        "nearest_water_distance_m"
    ]

    if (~np.isfinite(distances)).any():
        raise ValueError(
            "Nearest-water baseline contains "
            "nonfinite distances."
        )

    if distances.lt(0).any():
        raise ValueError(
            "Nearest-water baseline contains "
            "negative distances."
        )

    if distances.ge(query_buffer_meters).any():
        raise ValueError(
            "Nearest-water baseline contains a distance "
            "that does not satisfy the hydrography-cache "
            "completeness condition."
        )

    string_columns = [
        "nearest_water_feature_id",
        "nearest_water_feature_class",
        "nearest_water_feature_type",
        "nearest_water_source_id",
        "nearest_water_name",
        "distance_crs",
    ]

    for column in string_columns:
        prepared[column] = normalize_string(
            prepared[column]
        )

    required_nonmissing = [
        "nearest_water_feature_id",
        "nearest_water_feature_class",
        "nearest_water_feature_type",
        "nearest_water_source_id",
        "distance_crs",
    ]

    for column in required_nonmissing:
        if prepared[column].isna().any():
            raise ValueError(
                f"Nearest-water baseline contains "
                f"missing {column} values."
            )

    observed_crs = set(
        prepared["distance_crs"].dropna()
    )

    if observed_crs != {expected_distance_crs}:
        raise ValueError(
            "Nearest-water baseline CRS does not match "
            f"the configured distance CRS. Observed: "
            f"{sorted(observed_crs)}"
        )

    prepared[
        "nearest_water_source_object_id"
    ] = pd.to_numeric(
        prepared[
            "nearest_water_source_object_id"
        ],
        errors="raise",
    ).astype("Int64")

    prepared["nearest_water_tie_count"] = (
        pd.to_numeric(
            prepared[
                "nearest_water_tie_count"
            ],
            errors="raise",
        ).astype("Int64")
    )

    if prepared[
        "nearest_water_tie_count"
    ].lt(1).any():
        raise ValueError(
            "Nearest-water tie counts must be at least one."
        )

    return prepared[
        [
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
    ]


def build_property_evidence(
    property_coordinates: pd.DataFrame,
    fema_baseline: pd.DataFrame,
    water_baseline: pd.DataFrame,
    fema_project_crs: str,
    distance_crs: str,
    query_buffer_meters: float,
    coordinate_tolerance_degrees: float = 1e-7,
) -> pd.DataFrame:
    if coordinate_tolerance_degrees < 0:
        raise ValueError(
            "coordinate_tolerance_degrees cannot be negative."
        )

    coordinates = property_coordinates.copy()

    require_columns(
        coordinates,
        {
            "sample_order",
            "property_id",
            "cache_latitude",
            "cache_longitude",
            "water_projected_x",
            "water_projected_y",
        },
        "Property coordinates",
    )

    validate_property_ids(
        coordinates,
        "Property coordinates",
    )

    fema = prepare_fema_evidence(
        fema_baseline
    )

    water = prepare_water_evidence(
        water_baseline,
        expected_distance_crs=distance_crs,
        query_buffer_meters=query_buffer_meters,
    )

    require_identical_property_sets(
        {
            "Property coordinates": coordinates,
            "FEMA baseline": fema,
            "Nearest-water baseline": water,
        }
    )

    integrated = coordinates.merge(
        fema,
        on="property_id",
        how="inner",
        validate="one_to_one",
    )

    integrated = integrated.merge(
        water,
        on="property_id",
        how="inner",
        validate="one_to_one",
    )

    latitude_error = (
        integrated["cache_latitude"]
        - integrated["latitude"]
    ).abs()

    longitude_error = (
        integrated["cache_longitude"]
        - integrated["longitude"]
    ).abs()

    if latitude_error.gt(
        coordinate_tolerance_degrees
    ).any():
        raise ValueError(
            "Property-cache latitude differs from "
            "the FEMA baseline beyond tolerance."
        )

    if longitude_error.gt(
        coordinate_tolerance_degrees
    ).any():
        raise ValueError(
            "Property-cache longitude differs from "
            "the FEMA baseline beyond tolerance."
        )

    integrated["latitude"] = (
        integrated["cache_latitude"]
    )

    integrated["longitude"] = (
        integrated["cache_longitude"]
    )

    integrated["fema_project_crs"] = (
        fema_project_crs
    )

    integrated = integrated.sort_values(
        "sample_order",
        kind="stable",
    ).reset_index(drop=True)

    integrated = integrated.drop(
        columns=[
            "cache_latitude",
            "cache_longitude",
        ]
    )

    if integrated["property_id"].duplicated().any():
        raise RuntimeError(
            "Integrated evidence contains duplicate "
            "property IDs."
        )

    if len(integrated) != len(coordinates):
        raise RuntimeError(
            "Integrated evidence lost property rows."
        )

    return integrated[OUTPUT_COLUMNS]


def count_values(
    series: pd.Series,
) -> dict[str, int]:
    counts = series.value_counts(
        dropna=False
    )

    return {
        "<missing>" if pd.isna(key) else str(key):
            int(value)
        for key, value in counts.items()
    }


def summarize_property_evidence(
    evidence: pd.DataFrame,
) -> dict[str, Any]:
    distances = evidence[
        "nearest_water_distance_m"
    ]

    return {
        "property_count": int(len(evidence)),
        "unique_property_ids": int(
            evidence["property_id"].nunique()
        ),
        "matched_fema_polygon_count": int(
            evidence[
                "matched_fema_polygon"
            ].sum()
        ),
        "sfha_property_count": int(
            evidence["is_sfha"].sum()
        ),
        "non_sfha_property_count": int(
            (~evidence["is_sfha"]).sum()
        ),
        "fema_zone_counts": count_values(
            evidence["fema_zone"]
        ),
        "unique_fema_source_feature_count": int(
            evidence[
                "fema_source_feature_id"
            ].nunique(dropna=True)
        ),
        "minimum_water_distance_m": float(
            distances.min()
        ),
        "maximum_water_distance_m": float(
            distances.max()
        ),
        "mean_water_distance_m": float(
            distances.mean()
        ),
        "median_water_distance_m": float(
            distances.median()
        ),
        "zero_water_distance_property_count": int(
            distances.eq(0.0).sum()
        ),
        "unique_nearest_water_feature_count": int(
            evidence[
                "nearest_water_feature_id"
            ].nunique()
        ),
        "nearest_water_class_counts": count_values(
            evidence[
                "nearest_water_feature_class"
            ]
        ),
        "nearest_water_type_counts": count_values(
            evidence[
                "nearest_water_feature_type"
            ]
        ),
    }


def require_full_agreement_summary(
    summary_path: Path,
    validation_name: str,
) -> dict[str, Any]:
    if not summary_path.exists():
        raise FileNotFoundError(
            f"{validation_name} summary does not exist: "
            f"{summary_path}"
        )

    summary = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    required = {
        "total_union_rows",
        "total_joined_rows",
        "missing_python_rows",
        "missing_cpp_rows",
        "all_fields_agree",
    }

    missing = sorted(
        required - set(summary)
    )

    if missing:
        raise ValueError(
            f"{validation_name} summary is missing "
            f"fields: {missing}"
        )

    total_union_rows = int(
        summary["total_union_rows"]
    )

    if total_union_rows <= 0:
        raise ValueError(
            f"{validation_name} validated no rows."
        )

    if int(summary["missing_python_rows"]) != 0:
        raise ValueError(
            f"{validation_name} has missing Python rows."
        )

    if int(summary["missing_cpp_rows"]) != 0:
        raise ValueError(
            f"{validation_name} has missing C++ rows."
        )

    if (
        int(summary["total_joined_rows"])
        != total_union_rows
    ):
        raise ValueError(
            f"{validation_name} does not have full row coverage."
        )

    if (
        int(summary["all_fields_agree"])
        != total_union_rows
    ):
        raise ValueError(
            f"{validation_name} does not have full "
            "field agreement."
        )

    return summary