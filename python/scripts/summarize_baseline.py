from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.validate import normalize_bool_series


def repository_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def value_counts(series: pd.Series) -> dict[str, int]:
    counts = series.value_counts(dropna=False)

    return {
        "<missing>" if pd.isna(key) else str(key): int(value)
        for key, value in counts.items()
    }


def boolean_summary(series: pd.Series) -> dict[str, int]:
    return {
        "true": int(series.eq(True).sum()),
        "false": int(series.eq(False).sum()),
        "unknown": int(series.isna().sum()),
    }


def build_summary(
    dataframe: pd.DataFrame,
    input_path: Path,
) -> dict[str, Any]:
    required_columns = {
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
    }

    missing_columns = sorted(
        required_columns - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Baseline is missing required columns: {missing_columns}"
        )

    dataframe = dataframe.copy()
    dataframe["property_id"] = (
        dataframe["property_id"]
        .astype("string")
        .str.strip()
    )

    matched = normalize_bool_series(
        dataframe["matched_fema_polygon"],
        "matched_fema_polygon",
        allow_missing=True,
    )

    is_sfha = normalize_bool_series(
        dataframe["is_sfha"],
        "is_sfha",
        allow_missing=True,
    )

    python_sfha = normalize_bool_series(
        dataframe["python_sfha_result"],
        "python_sfha_result",
        allow_missing=True,
    )

    duplicate_property_rows = int(
        dataframe["property_id"]
        .duplicated(keep=False)
        .sum()
    )

    duplicate_property_ids = int(
        dataframe.loc[
            dataframe["property_id"].duplicated(keep=False),
            "property_id",
        ].nunique()
    )

    missing_coordinates = (
        dataframe[
            [
                "latitude",
                "longitude",
                "projected_x",
                "projected_y",
            ]
        ]
        .isna()
        .any(axis=1)
    )

    matched_without_zone = (
        matched.fillna(False)
        & dataframe["fema_zone"].isna()
    )

    matched_without_feature = (
        matched.fillna(False)
        & dataframe["fema_feature_index"].isna()
    )

    sfha_without_match = (
        is_sfha.fillna(False)
        & ~matched.fillna(False)
    )

    sfha_result_disagreement = (
        is_sfha.notna()
        & python_sfha.notna()
        & is_sfha.ne(python_sfha)
    )

    return {
        "input_file": input_path.resolve()
        .relative_to(REPOSITORY_ROOT)
        .as_posix(),
        "total_rows": int(len(dataframe)),
        "unique_property_ids": int(
            dataframe["property_id"].nunique(dropna=True)
        ),
        "missing_property_ids": int(
            dataframe["property_id"].isna().sum()
            + dataframe["property_id"].eq("").sum()
        ),
        "duplicate_property_rows": duplicate_property_rows,
        "duplicate_property_ids": duplicate_property_ids,
        "rows_with_missing_coordinates": int(
            missing_coordinates.sum()
        ),
        "matched_fema_polygon": boolean_summary(matched),
        "is_sfha": boolean_summary(is_sfha),
        "python_sfha_result": boolean_summary(python_sfha),
        "matched_without_fema_zone": int(
            matched_without_zone.sum()
        ),
        "matched_without_feature_index": int(
            matched_without_feature.sum()
        ),
        "sfha_true_without_polygon_match": int(
            sfha_without_match.sum()
        ),
        "is_sfha_python_result_disagreements": int(
            sfha_result_disagreement.sum()
        ),
        "sfha_flag_counts": value_counts(
            dataframe["sfha_flag"]
        ),
        "fema_zone_counts": value_counts(
            dataframe["fema_zone"]
        ),
        "fema_feature_count": int(
            dataframe["fema_feature_index"].nunique(
                dropna=True
            )
        ),
        "source_geometry_count": int(
            dataframe["source_geometry_id"].nunique(
                dropna=True
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize and structurally inspect the FEMA baseline."
    )
    parser.add_argument(
        "--input",
        default="outputs/baseline/python_fema_membership.csv",
    )
    parser.add_argument(
        "--output",
        default="outputs/validation/python_baseline_summary.json",
    )

    args = parser.parse_args()

    input_path = repository_path(args.input)
    output_path = repository_path(args.output)

    dataframe = pd.read_csv(
        input_path,
        dtype={"property_id": "string"},
    )

    summary = build_summary(
        dataframe,
        input_path,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()