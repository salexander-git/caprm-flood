from __future__ import annotations

import json
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import pandas as pd


TRUE_VALUES = {"true", "t", "1", "yes", "y"}
FALSE_VALUES = {"false", "f", "0", "no", "n"}

PYTHON_REQUIRED_COLUMNS = {
    "property_id",
    "fema_zone",
    "is_sfha",
    "matched_fema_polygon",
    "fema_feature_index",
}

CPP_REQUIRED_COLUMNS = {
    "property_id",
    "cpp_matched_fema_polygon",
    "cpp_sfha_result",
    "cpp_fema_zone",
    "cpp_fema_feature_index",
}


def require_columns(
    dataframe: pd.DataFrame,
    required_columns: set[str],
    table_name: str,
) -> None:
    missing = sorted(required_columns - set(dataframe.columns))

    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {missing}"
        )


def normalize_property_ids(
    series: pd.Series,
    table_name: str,
) -> pd.Series:
    normalized = series.astype("string").str.strip()

    missing = normalized.isna() | normalized.eq("")

    if missing.any():
        rows = normalized.index[missing].tolist()[:10]
        raise ValueError(
            f"{table_name} contains missing or empty property_id values "
            f"at rows: {rows}"
        )

    duplicates = normalized[normalized.duplicated(keep=False)]

    if not duplicates.empty:
        duplicate_values = sorted(duplicates.unique().tolist())[:10]
        raise ValueError(
            f"{table_name} contains duplicate property_id values: "
            f"{duplicate_values}"
        )

    return normalized


def normalize_bool_value(value: object) -> bool | pd._libs.missing.NAType:
    if pd.isna(value):
        return pd.NA

    if isinstance(value, bool):
        return value

    if isinstance(value, Integral):
        if value == 1:
            return True
        if value == 0:
            return False

    if isinstance(value, Real):
        if float(value) == 1.0:
            return True
        if float(value) == 0.0:
            return False

    text = str(value).strip().lower()

    if text in TRUE_VALUES:
        return True

    if text in FALSE_VALUES:
        return False

    raise ValueError(f"Unrecognized Boolean value: {value!r}")


def normalize_bool_series(
    series: pd.Series,
    field_name: str,
    allow_missing: bool = False,
) -> pd.Series:
    values: list[bool | pd._libs.missing.NAType] = []

    for row_index, value in series.items():
        try:
            values.append(normalize_bool_value(value))
        except ValueError as exc:
            raise ValueError(
                f"{field_name} contains an invalid value at row "
                f"{row_index}: {value!r}"
            ) from exc

    normalized = pd.Series(
        values,
        index=series.index,
        dtype="boolean",
    )

    if not allow_missing and normalized.isna().any():
        rows = normalized.index[normalized.isna()].tolist()[:10]
        raise ValueError(
            f"{field_name} contains missing Boolean values at rows: {rows}"
        )

    return normalized


def normalize_text_series(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip()
    return normalized.mask(normalized.eq(""), pd.NA)


def normalize_feature_ids(
    series: pd.Series,
    field_name: str,
    negative_one_is_missing: bool = False,
) -> pd.Series:
    try:
        numeric = pd.to_numeric(series, errors="raise")
    except Exception as exc:
        raise ValueError(
            f"{field_name} contains a nonnumeric feature identifier."
        ) from exc

    numeric = pd.Series(numeric, index=series.index, dtype="Float64")

    if negative_one_is_missing:
        numeric = numeric.mask(numeric.eq(-1), pd.NA)

    nonmissing = numeric.dropna()

    if ((nonmissing % 1) != 0).any():
        raise ValueError(
            f"{field_name} contains a noninteger feature identifier."
        )

    return numeric.astype("Int64")


def nullable_equal(
    left: pd.Series,
    right: pd.Series,
) -> pd.Series:
    both_missing = left.isna() & right.isna()
    equal_values = left.eq(right).fillna(False)

    return (both_missing | equal_values).astype(bool)


def prepare_python_results(dataframe: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        dataframe,
        PYTHON_REQUIRED_COLUMNS,
        "Python baseline",
    )

    prepared = dataframe.copy()

    prepared["property_id"] = normalize_property_ids(
        prepared["property_id"],
        "Python baseline",
    )

    prepared["python_matched_fema_polygon"] = normalize_bool_series(
        prepared["matched_fema_polygon"],
        "matched_fema_polygon",
    )

    prepared["python_is_sfha"] = normalize_bool_series(
        prepared["is_sfha"],
        "is_sfha",
    )

    prepared["python_fema_zone"] = normalize_text_series(
        prepared["fema_zone"]
    )

    prepared["python_fema_feature_index"] = normalize_feature_ids(
        prepared["fema_feature_index"],
        "fema_feature_index",
    )

    invalid_sfha = (
        prepared["python_is_sfha"]
        & ~prepared["python_matched_fema_polygon"]
    )

    if invalid_sfha.any():
        property_ids = prepared.loc[
            invalid_sfha,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "Python baseline contains SFHA=true for properties that did "
            f"not match a FEMA polygon: {property_ids}"
        )

    matched_missing_evidence = (
        prepared["python_matched_fema_polygon"]
        & (
            prepared["python_fema_zone"].isna()
            | prepared["python_fema_feature_index"].isna()
        )
    )

    if matched_missing_evidence.any():
        property_ids = prepared.loc[
            matched_missing_evidence,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "Python baseline contains matched properties without FEMA "
            f"zone or feature evidence: {property_ids}"
        )

    return prepared[
        [
            "property_id",
            "python_matched_fema_polygon",
            "python_is_sfha",
            "python_fema_zone",
            "python_fema_feature_index",
        ]
    ]


def prepare_cpp_results(dataframe: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        dataframe,
        CPP_REQUIRED_COLUMNS,
        "C++ output",
    )

    prepared = dataframe.copy()

    prepared["property_id"] = normalize_property_ids(
        prepared["property_id"],
        "C++ output",
    )

    prepared["cpp_matched_fema_polygon"] = normalize_bool_series(
        prepared["cpp_matched_fema_polygon"],
        "cpp_matched_fema_polygon",
    )

    prepared["cpp_is_sfha"] = normalize_bool_series(
        prepared["cpp_sfha_result"],
        "cpp_sfha_result",
    )

    prepared["cpp_fema_zone"] = normalize_text_series(
        prepared["cpp_fema_zone"]
    )

    prepared["cpp_fema_feature_index"] = normalize_feature_ids(
        prepared["cpp_fema_feature_index"],
        "cpp_fema_feature_index",
        negative_one_is_missing=True,
    )

    invalid_sfha = (
        prepared["cpp_is_sfha"]
        & ~prepared["cpp_matched_fema_polygon"]
    )

    if invalid_sfha.any():
        property_ids = prepared.loc[
            invalid_sfha,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "C++ output contains SFHA=true for properties that did not "
            f"match a FEMA polygon: {property_ids}"
        )

    matched_missing_evidence = (
        prepared["cpp_matched_fema_polygon"]
        & (
            prepared["cpp_fema_zone"].isna()
            | prepared["cpp_fema_feature_index"].isna()
        )
    )

    if matched_missing_evidence.any():
        property_ids = prepared.loc[
            matched_missing_evidence,
            "property_id",
        ].tolist()[:10]

        raise ValueError(
            "C++ output contains matched properties without FEMA zone "
            f"or feature evidence: {property_ids}"
        )

    return prepared[
        [
            "property_id",
            "cpp_matched_fema_polygon",
            "cpp_is_sfha",
            "cpp_fema_zone",
            "cpp_fema_feature_index",
        ]
    ]


def compare_fema_membership(
    python_dataframe: pd.DataFrame,
    cpp_dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    python_prepared = prepare_python_results(python_dataframe)
    cpp_prepared = prepare_cpp_results(cpp_dataframe)

    merged = python_prepared.merge(
        cpp_prepared,
        on="property_id",
        how="outer",
        indicator=True,
        validate="one_to_one",
    )

    merged["present_in_both"] = merged["_merge"].eq("both")
    merged["missing_python_result"] = merged["_merge"].eq("right_only")
    merged["missing_cpp_result"] = merged["_merge"].eq("left_only")

    merged["matched_agrees"] = (
        merged["present_in_both"]
        & nullable_equal(
            merged["python_matched_fema_polygon"],
            merged["cpp_matched_fema_polygon"],
        )
    )

    merged["sfha_agrees"] = (
        merged["present_in_both"]
        & nullable_equal(
            merged["python_is_sfha"],
            merged["cpp_is_sfha"],
        )
    )

    merged["zone_agrees"] = (
        merged["present_in_both"]
        & nullable_equal(
            merged["python_fema_zone"],
            merged["cpp_fema_zone"],
        )
    )

    merged["feature_index_agrees"] = (
        merged["present_in_both"]
        & nullable_equal(
            merged["python_fema_feature_index"],
            merged["cpp_fema_feature_index"],
        )
    )

    merged["all_fields_agree"] = (
        merged["matched_agrees"]
        & merged["sfha_agrees"]
        & merged["zone_agrees"]
        & merged["feature_index_agrees"]
    )

    joined_rows = int(merged["present_in_both"].sum())
    union_rows = int(len(merged))

    def joined_rate(column: str) -> float:
        if joined_rows == 0:
            return 0.0

        return float(merged.loc[
            merged["present_in_both"],
            column,
        ].mean())

    summary: dict[str, Any] = {
        "total_python_rows": int(len(python_prepared)),
        "total_cpp_rows": int(len(cpp_prepared)),
        "total_union_rows": union_rows,
        "total_joined_rows": joined_rows,
        "missing_python_rows": int(
            merged["missing_python_result"].sum()
        ),
        "missing_cpp_rows": int(
            merged["missing_cpp_result"].sum()
        ),
        "coverage_rate": (
            float(joined_rows / union_rows)
            if union_rows > 0
            else 0.0
        ),
        "matched_agreements": int(
            merged["matched_agrees"].sum()
        ),
        "sfha_agreements": int(
            merged["sfha_agrees"].sum()
        ),
        "zone_agreements": int(
            merged["zone_agrees"].sum()
        ),
        "feature_index_agreements": int(
            merged["feature_index_agrees"].sum()
        ),
        "all_fields_agree": int(
            merged["all_fields_agree"].sum()
        ),
        "matched_agreement_rate": joined_rate(
            "matched_agrees"
        ),
        "sfha_agreement_rate": joined_rate(
            "sfha_agrees"
        ),
        "zone_agreement_rate": joined_rate(
            "zone_agrees"
        ),
        "feature_index_agreement_rate": joined_rate(
            "feature_index_agrees"
        ),
        "all_fields_agreement_rate": joined_rate(
            "all_fields_agree"
        ),
    }

    merged = merged.sort_values(
        "property_id",
        kind="stable",
    ).reset_index(drop=True)

    return merged, summary

def compare_fema_files(
    python_baseline_path: Path,
    cpp_output_path: Path,
    detail_output_path: Path,
    summary_output_path: Path,
    comparison_scope: str = "union",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if comparison_scope not in {"union", "cpp"}:
        raise ValueError(
            "comparison_scope must be either 'union' or 'cpp'."
        )

    python_dataframe = pd.read_csv(
        python_baseline_path,
        dtype={"property_id": "string"},
    )

    cpp_dataframe = pd.read_csv(
        cpp_output_path,
        dtype={"property_id": "string"},
    )

    total_python_source_rows = len(python_dataframe)

    if comparison_scope == "cpp":
        cpp_property_ids = set(
            cpp_dataframe["property_id"].astype("string").str.strip()
        )

        python_dataframe = python_dataframe[
            python_dataframe["property_id"]
            .astype("string")
            .str.strip()
            .isin(cpp_property_ids)
        ].copy()

    detail, summary = compare_fema_membership(
        python_dataframe,
        cpp_dataframe,
    )

    summary["comparison_scope"] = comparison_scope
    summary["total_python_source_rows"] = int(
        total_python_source_rows
    )
    summary["python_baseline"] = str(python_baseline_path)
    summary["cpp_output"] = str(cpp_output_path)

    detail_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    detail.to_csv(detail_output_path, index=False)

    summary_output_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    return detail, summary