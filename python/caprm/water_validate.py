from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PYTHON_REQUIRED_COLUMNS = {
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

CPP_REQUIRED_COLUMNS = {
    "property_id",
    "cpp_nearest_water_distance_m",
    "cpp_nearest_water_feature_id",
    "cpp_nearest_water_feature_class",
    "cpp_nearest_water_feature_type",
    "cpp_nearest_water_source_id",
    "cpp_nearest_water_source_object_id",
    "cpp_nearest_water_name",
    "cpp_nearest_water_tie_count",
    "cpp_segment_checks",
    "distance_crs",
    "algorithm",
}


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


def nullable_equal(
    left: pd.Series,
    right: pd.Series,
) -> pd.Series:
    return (
        left.eq(right)
        | (left.isna() & right.isna())
    ).fillna(False)


def validate_property_ids(
    dataframe: pd.DataFrame,
    table_name: str,
) -> None:
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


def display_path(
    path: Path,
    root: Path | None,
) -> str:
    resolved = path.resolve()

    if root is not None:
        try:
            return resolved.relative_to(
                root.resolve()
            ).as_posix()
        except ValueError:
            pass

    return str(resolved)


def compare_water_files(
    python_reference_path: Path,
    cpp_output_path: Path,
    distance_tolerance_meters: float = 1e-6,
    path_display_root: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if distance_tolerance_meters < 0:
        raise ValueError(
            "distance_tolerance_meters cannot be negative."
        )

    python_reference_path = Path(
        python_reference_path
    )

    cpp_output_path = Path(
        cpp_output_path
    )

    if not python_reference_path.exists():
        raise FileNotFoundError(
            "Python nearest-water reference does not exist: "
            f"{python_reference_path}"
        )

    if not cpp_output_path.exists():
        raise FileNotFoundError(
            f"C++ nearest-water output does not exist: "
            f"{cpp_output_path}"
        )

    python_dataframe = pd.read_csv(
        python_reference_path,
        dtype={
            "property_id": "string",
            "nearest_water_feature_id": "string",
            "nearest_water_source_id": "string",
        },
    )

    cpp_dataframe = pd.read_csv(
        cpp_output_path,
        dtype={
            "property_id": "string",
            "cpp_nearest_water_feature_id": "string",
            "cpp_nearest_water_source_id": "string",
        },
    )

    require_columns(
        python_dataframe,
        PYTHON_REQUIRED_COLUMNS,
        "Python nearest-water reference",
    )

    require_columns(
        cpp_dataframe,
        CPP_REQUIRED_COLUMNS,
        "C++ nearest-water output",
    )

    validate_property_ids(
        python_dataframe,
        "Python nearest-water reference",
    )

    validate_property_ids(
        cpp_dataframe,
        "C++ nearest-water output",
    )

    python_dataframe = python_dataframe.rename(
        columns={
            "nearest_water_distance_m":
                "python_distance_m",
            "nearest_water_feature_id":
                "python_feature_id",
            "nearest_water_feature_class":
                "python_feature_class",
            "nearest_water_feature_type":
                "python_feature_type",
            "nearest_water_source_id":
                "python_source_id",
            "nearest_water_source_object_id":
                "python_source_object_id",
            "nearest_water_name":
                "python_name",
            "nearest_water_tie_count":
                "python_tie_count",
            "distance_crs":
                "python_distance_crs",
        }
    )

    cpp_dataframe = cpp_dataframe.rename(
        columns={
            "cpp_nearest_water_distance_m":
                "cpp_distance_m",
            "cpp_nearest_water_feature_id":
                "cpp_feature_id",
            "cpp_nearest_water_feature_class":
                "cpp_feature_class",
            "cpp_nearest_water_feature_type":
                "cpp_feature_type",
            "cpp_nearest_water_source_id":
                "cpp_source_id",
            "cpp_nearest_water_source_object_id":
                "cpp_source_object_id",
            "cpp_nearest_water_name":
                "cpp_name",
            "cpp_nearest_water_tie_count":
                "cpp_tie_count",
            "distance_crs":
                "cpp_distance_crs",
        }
    )

    string_columns = [
        "python_feature_id",
        "python_feature_class",
        "python_feature_type",
        "python_source_id",
        "python_name",
        "python_distance_crs",
    ]

    for column in string_columns:
        python_dataframe[column] = normalize_string(
            python_dataframe[column]
        )

    cpp_string_columns = [
        "cpp_feature_id",
        "cpp_feature_class",
        "cpp_feature_type",
        "cpp_source_id",
        "cpp_name",
        "cpp_distance_crs",
        "algorithm",
    ]

    for column in cpp_string_columns:
        cpp_dataframe[column] = normalize_string(
            cpp_dataframe[column]
        )

    numeric_columns = [
        (
            python_dataframe,
            "python_distance_m",
            "float64",
        ),
        (
            cpp_dataframe,
            "cpp_distance_m",
            "float64",
        ),
        (
            python_dataframe,
            "python_source_object_id",
            "Int64",
        ),
        (
            cpp_dataframe,
            "cpp_source_object_id",
            "Int64",
        ),
        (
            python_dataframe,
            "python_tie_count",
            "Int64",
        ),
        (
            cpp_dataframe,
            "cpp_tie_count",
            "Int64",
        ),
        (
            cpp_dataframe,
            "cpp_segment_checks",
            "Int64",
        ),
    ]

    for dataframe, column, dtype in numeric_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="raise",
        ).astype(dtype)

    if (
        ~np.isfinite(
            python_dataframe["python_distance_m"]
        )
    ).any():
        raise ValueError(
            "Python reference contains nonfinite distances."
        )

    if (
        ~np.isfinite(
            cpp_dataframe["cpp_distance_m"]
        )
    ).any():
        raise ValueError(
            "C++ output contains nonfinite distances."
        )

    if (
        python_dataframe["python_distance_m"] < 0
    ).any():
        raise ValueError(
            "Python reference contains negative distances."
        )

    if (
        cpp_dataframe["cpp_distance_m"] < 0
    ).any():
        raise ValueError(
            "C++ output contains negative distances."
        )

    if (
        cpp_dataframe["cpp_segment_checks"] < 0
    ).any():
        raise ValueError(
            "C++ output contains negative segment-check counts."
        )

    algorithms = (
        cpp_dataframe["algorithm"]
        .dropna()
        .unique()
        .tolist()
    )

    if len(algorithms) != 1:
        raise ValueError(
            "C++ output must contain exactly one algorithm value."
        )

    detail = python_dataframe.merge(
        cpp_dataframe,
        on="property_id",
        how="outer",
        indicator=True,
        validate="one_to_one",
    )

    detail["missing_python_row"] = (
        detail["_merge"].eq("right_only")
    )

    detail["missing_cpp_row"] = (
        detail["_merge"].eq("left_only")
    )

    joined = detail["_merge"].eq("both")

    detail["distance_absolute_error_m"] = (
        detail["python_distance_m"]
        - detail["cpp_distance_m"]
    ).abs()

    detail["distance_within_tolerance"] = (
        joined
        & detail[
            "distance_absolute_error_m"
        ].le(distance_tolerance_meters)
    )

    comparisons = {
        "feature_id_agrees": (
            "python_feature_id",
            "cpp_feature_id",
        ),
        "feature_class_agrees": (
            "python_feature_class",
            "cpp_feature_class",
        ),
        "feature_type_agrees": (
            "python_feature_type",
            "cpp_feature_type",
        ),
        "source_id_agrees": (
            "python_source_id",
            "cpp_source_id",
        ),
        "source_object_id_agrees": (
            "python_source_object_id",
            "cpp_source_object_id",
        ),
        "name_agrees": (
            "python_name",
            "cpp_name",
        ),
        "tie_count_agrees": (
            "python_tie_count",
            "cpp_tie_count",
        ),
        "distance_crs_agrees": (
            "python_distance_crs",
            "cpp_distance_crs",
        ),
    }

    for result_column, (
        python_column,
        cpp_column,
    ) in comparisons.items():
        detail[result_column] = (
            joined
            & nullable_equal(
                detail[python_column],
                detail[cpp_column],
            )
        )

    agreement_columns = [
        "distance_within_tolerance",
        *comparisons.keys(),
    ]

    detail["all_fields_agree"] = (
        joined
        & detail[agreement_columns].all(axis=1)
    )

    joined_detail = detail.loc[joined]

    distance_errors = joined_detail[
        "distance_absolute_error_m"
    ]

    total_python_rows = int(
        len(python_dataframe)
    )

    total_cpp_rows = int(
        len(cpp_dataframe)
    )

    total_union_rows = int(len(detail))
    total_joined_rows = int(joined.sum())

    summary: dict[str, Any] = {
        "total_python_rows": total_python_rows,
        "total_cpp_rows": total_cpp_rows,
        "total_union_rows": total_union_rows,
        "total_joined_rows": total_joined_rows,
        "missing_python_rows": int(
            detail["missing_python_row"].sum()
        ),
        "missing_cpp_rows": int(
            detail["missing_cpp_row"].sum()
        ),
        "coverage_rate": (
            total_joined_rows / total_union_rows
            if total_union_rows
            else 0.0
        ),
        "distance_tolerance_meters": (
            distance_tolerance_meters
        ),
        "distance_agreements": int(
            detail[
                "distance_within_tolerance"
            ].sum()
        ),
        "feature_id_agreements": int(
            detail["feature_id_agrees"].sum()
        ),
        "feature_class_agreements": int(
            detail["feature_class_agrees"].sum()
        ),
        "feature_type_agreements": int(
            detail["feature_type_agrees"].sum()
        ),
        "source_id_agreements": int(
            detail["source_id_agrees"].sum()
        ),
        "source_object_id_agreements": int(
            detail[
                "source_object_id_agrees"
            ].sum()
        ),
        "name_agreements": int(
            detail["name_agrees"].sum()
        ),
        "tie_count_agreements": int(
            detail["tie_count_agrees"].sum()
        ),
        "distance_crs_agreements": int(
            detail["distance_crs_agrees"].sum()
        ),
        "all_fields_agree": int(
            detail["all_fields_agree"].sum()
        ),
        "maximum_absolute_error_m": (
            float(distance_errors.max())
            if not distance_errors.empty
            else None
        ),
        "mean_absolute_error_m": (
            float(distance_errors.mean())
            if not distance_errors.empty
            else None
        ),
        "median_absolute_error_m": (
            float(distance_errors.median())
            if not distance_errors.empty
            else None
        ),
        "total_cpp_segment_checks": int(
            cpp_dataframe[
                "cpp_segment_checks"
            ].sum()
        ),
        "average_cpp_segment_checks_per_property": (
            float(
                cpp_dataframe[
                    "cpp_segment_checks"
                ].mean()
            )
        ),
        "algorithm": algorithms[0],
        "python_reference": display_path(
            python_reference_path,
            path_display_root,
        ),
        "cpp_output": display_path(
            cpp_output_path,
            path_display_root,
        ),
    }

    denominator = (
        total_union_rows
        if total_union_rows
        else 1
    )

    rate_columns = {
        "distance_agreement_rate":
            "distance_agreements",
        "feature_id_agreement_rate":
            "feature_id_agreements",
        "all_fields_agreement_rate":
            "all_fields_agree",
    }

    for rate_name, count_name in rate_columns.items():
        summary[rate_name] = (
            summary[count_name] / denominator
        )

    detail = detail.drop(columns=["_merge"])

    return detail, summary