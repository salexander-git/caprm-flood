from __future__ import annotations
from pathlib import Path

import pandas as pd
import pytest

from caprm.validate import (
    compare_fema_files,
    compare_fema_membership,
    normalize_bool_series,
)


def make_python_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["P1", "P2"],
            "fema_zone": ["AE", pd.NA],
            "is_sfha": [True, False],
            "matched_fema_polygon": [True, False],
            "fema_feature_index": [10, pd.NA],
        }
    )


def make_cpp_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["P1", "P2"],
            "cpp_matched_fema_polygon": ["true", "false"],
            "cpp_sfha_result": ["true", "false"],
            "cpp_fema_zone": ["AE", pd.NA],
            "cpp_fema_feature_index": [10, -1],
        }
    )


def test_boolean_normalization() -> None:
    values = pd.Series(
        [True, False, "T", "f", "yes", "0", 1, 0]
    )

    result = normalize_bool_series(
        values,
        "test_boolean",
    )

    assert result.tolist() == [
        True,
        False,
        True,
        False,
        True,
        False,
        True,
        False,
    ]

def test_cpp_scope_ignores_unqueried_python_rows(
    tmp_path: Path,
) -> None:
    python_dataframe = make_python_dataframe()
    cpp_dataframe = make_cpp_dataframe().iloc[[0]].copy()

    python_path = tmp_path / "python.csv"
    cpp_path = tmp_path / "cpp.csv"
    detail_path = tmp_path / "detail.csv"
    summary_path = tmp_path / "summary.json"

    python_dataframe.to_csv(python_path, index=False)
    cpp_dataframe.to_csv(cpp_path, index=False)

    _, summary = compare_fema_files(
        python_baseline_path=python_path,
        cpp_output_path=cpp_path,
        detail_output_path=detail_path,
        summary_output_path=summary_path,
        comparison_scope="cpp",
    )

    assert summary["comparison_scope"] == "cpp"
    assert summary["total_python_source_rows"] == 2
    assert summary["total_python_rows"] == 1
    assert summary["total_cpp_rows"] == 1
    assert summary["missing_python_rows"] == 0
    assert summary["missing_cpp_rows"] == 0
    assert summary["all_fields_agreement_rate"] == 1.0
    
def test_invalid_boolean_value_is_rejected() -> None:
    values = pd.Series(["true", "possibly"])

    with pytest.raises(
        ValueError,
        match="invalid value",
    ):
        normalize_bool_series(
            values,
            "test_boolean",
        )


def test_duplicate_property_ids_are_rejected() -> None:
    python_dataframe = make_python_dataframe()
    python_dataframe.loc[1, "property_id"] = "P1"

    with pytest.raises(
        ValueError,
        match="duplicate property_id",
    ):
        compare_fema_membership(
            python_dataframe,
            make_cpp_dataframe(),
        )


def test_matching_outputs_agree() -> None:
    detail, summary = compare_fema_membership(
        make_python_dataframe(),
        make_cpp_dataframe(),
    )

    assert summary["total_python_rows"] == 2
    assert summary["total_cpp_rows"] == 2
    assert summary["total_joined_rows"] == 2
    assert summary["missing_python_rows"] == 0
    assert summary["missing_cpp_rows"] == 0
    assert summary["all_fields_agree"] == 2
    assert summary["all_fields_agreement_rate"] == 1.0
    assert detail["all_fields_agree"].all()


def test_missing_cpp_row_is_detected() -> None:
    cpp_dataframe = make_cpp_dataframe().iloc[[0]].copy()

    _, summary = compare_fema_membership(
        make_python_dataframe(),
        cpp_dataframe,
    )

    assert summary["total_python_rows"] == 2
    assert summary["total_cpp_rows"] == 1
    assert summary["missing_cpp_rows"] == 1
    assert summary["missing_python_rows"] == 0
    assert summary["coverage_rate"] == 0.5


def test_missing_python_row_is_detected() -> None:
    cpp_dataframe = make_cpp_dataframe()

    extra_row = pd.DataFrame(
        {
            "property_id": ["P3"],
            "cpp_matched_fema_polygon": [False],
            "cpp_sfha_result": [False],
            "cpp_fema_zone": [pd.NA],
            "cpp_fema_feature_index": [-1],
        }
    )

    cpp_dataframe = pd.concat(
        [cpp_dataframe, extra_row],
        ignore_index=True,
    )

    _, summary = compare_fema_membership(
        make_python_dataframe(),
        cpp_dataframe,
    )

    assert summary["missing_python_rows"] == 1
    assert summary["missing_cpp_rows"] == 0


def test_feature_disagreement_is_detected() -> None:
    cpp_dataframe = make_cpp_dataframe()
    cpp_dataframe.loc[0, "cpp_fema_feature_index"] = 999

    detail, summary = compare_fema_membership(
        make_python_dataframe(),
        cpp_dataframe,
    )

    assert summary["feature_index_agreements"] == 1
    assert summary["all_fields_agree"] == 1

    disagreement = detail.loc[
        detail["property_id"].eq("P1")
    ].iloc[0]

    assert not bool(disagreement["feature_index_agrees"])
    assert not bool(disagreement["all_fields_agree"])