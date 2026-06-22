from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from caprm.water_validate import compare_water_files


def write_python_reference(
    path: Path,
    distance: float = 5.0,
) -> None:
    pd.DataFrame(
        {
            "property_id": ["P1"],
            "nearest_water_distance_m": [
                distance
            ],
            "nearest_water_feature_id": [
                "flowline:A"
            ],
            "nearest_water_feature_class": [
                "flowline"
            ],
            "nearest_water_feature_type": [
                "Channel Line"
            ],
            "nearest_water_source_id": ["A"],
            "nearest_water_source_object_id": [
                10
            ],
            "nearest_water_name": [
                "Test Creek"
            ],
            "nearest_water_tie_count": [1],
            "distance_crs": ["EPSG:26918"],
        }
    ).to_csv(path, index=False)


def write_cpp_output(
    path: Path,
    distance: float = 5.0,
) -> None:
    pd.DataFrame(
        {
            "property_id": ["P1"],
            "cpp_nearest_water_distance_m": [
                distance
            ],
            "cpp_nearest_water_feature_id": [
                "flowline:A"
            ],
            "cpp_nearest_water_feature_class": [
                "flowline"
            ],
            "cpp_nearest_water_feature_type": [
                "Channel Line"
            ],
            "cpp_nearest_water_source_id": ["A"],
            "cpp_nearest_water_source_object_id": [
                10
            ],
            "cpp_nearest_water_name": [
                "Test Creek"
            ],
            "cpp_nearest_water_tie_count": [1],
            "cpp_segment_checks": [100],
            "distance_crs": ["EPSG:26918"],
            "algorithm": ["brute_force"],
        }
    ).to_csv(path, index=False)


def test_exact_water_agreement(
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "python.csv"
    cpp_path = tmp_path / "cpp.csv"

    write_python_reference(python_path)
    write_cpp_output(cpp_path)

    detail, summary = compare_water_files(
        python_path,
        cpp_path,
    )

    assert summary["total_joined_rows"] == 1
    assert summary["all_fields_agree"] == 1
    assert summary[
        "maximum_absolute_error_m"
    ] == 0.0

    assert bool(
        detail.loc[
            0,
            "all_fields_agree",
        ]
    )


def test_distance_tolerance_is_applied(
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "python.csv"
    cpp_path = tmp_path / "cpp.csv"

    write_python_reference(
        python_path,
        distance=5.0,
    )

    write_cpp_output(
        cpp_path,
        distance=5.0000005,
    )

    _, summary = compare_water_files(
        python_path,
        cpp_path,
        distance_tolerance_meters=1e-6,
    )

    assert summary["distance_agreements"] == 1
    assert summary["all_fields_agree"] == 1


def test_distance_outside_tolerance_fails(
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "python.csv"
    cpp_path = tmp_path / "cpp.csv"

    write_python_reference(
        python_path,
        distance=5.0,
    )

    write_cpp_output(
        cpp_path,
        distance=5.01,
    )

    _, summary = compare_water_files(
        python_path,
        cpp_path,
        distance_tolerance_meters=1e-6,
    )

    assert summary["distance_agreements"] == 0
    assert summary["all_fields_agree"] == 0


def test_duplicate_cpp_property_ids_are_rejected(
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "python.csv"
    cpp_path = tmp_path / "cpp.csv"

    write_python_reference(python_path)
    write_cpp_output(cpp_path)

    cpp = pd.read_csv(cpp_path)
    cpp = pd.concat(
        [cpp, cpp],
        ignore_index=True,
    )
    cpp.to_csv(cpp_path, index=False)

    with pytest.raises(
        ValueError,
        match="duplicate property IDs",
    ):
        compare_water_files(
            python_path,
            cpp_path,
        )