from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from caprm.evidence import (
    build_property_evidence,
    require_full_agreement_summary,
    summarize_property_evidence,
)


def make_coordinates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sample_order": [0, 1],
            "property_id": ["P1", "P2"],
            "cache_latitude": [43.1, 43.2],
            "cache_longitude": [-77.6, -77.7],
            "water_projected_x": [
                288000.0,
                289000.0,
            ],
            "water_projected_y": [
                4775000.0,
                4776000.0,
            ],
        }
    )


def make_fema() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["P1", "P2"],
            "latitude": [43.1, 43.2],
            "longitude": [-77.6, -77.7],
            "projected_x": [
                -8630000.0,
                -8640000.0,
            ],
            "projected_y": [
                5320000.0,
                5330000.0,
            ],
            "fema_zone": ["AE", "X"],
            "sfha_flag": ["T", "F"],
            "is_sfha": [True, False],
            "source_geometry_id": ["F1", "F2"],
            "fema_feature_index": [10, 20],
            "matched_fema_polygon": [
                True,
                True,
            ],
            "python_sfha_result": [
                True,
                False,
            ],
        }
    )


def make_water() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["P1", "P2"],
            "nearest_water_distance_m": [
                20.0,
                40.0,
            ],
            "nearest_water_feature_id": [
                "flowline:A",
                "waterbody:B",
            ],
            "nearest_water_feature_class": [
                "flowline",
                "waterbody",
            ],
            "nearest_water_feature_type": [
                "Channel Line",
                "Lake",
            ],
            "nearest_water_source_id": [
                "A",
                "B",
            ],
            "nearest_water_source_object_id": [
                100,
                200,
            ],
            "nearest_water_name": [
                "Test Creek",
                "Test Lake",
            ],
            "nearest_water_tie_count": [1, 1],
            "distance_crs": [
                "EPSG:26918",
                "EPSG:26918",
            ],
        }
    )


def test_integrated_evidence_preserves_both_sources() -> None:
    result = build_property_evidence(
        property_coordinates=make_coordinates(),
        fema_baseline=make_fema(),
        water_baseline=make_water(),
        fema_project_crs="EPSG:3857",
        distance_crs="EPSG:26918",
        query_buffer_meters=20000.0,
    )

    assert result["property_id"].tolist() == [
        "P1",
        "P2",
    ]

    assert result["fema_zone"].tolist() == [
        "AE",
        "X",
    ]

    assert result[
        "nearest_water_feature_id"
    ].tolist() == [
        "flowline:A",
        "waterbody:B",
    ]

    assert result[
        "fema_project_crs"
    ].unique().tolist() == [
        "EPSG:3857"
    ]

    assert result[
        "distance_crs"
    ].unique().tolist() == [
        "EPSG:26918"
    ]


def test_property_set_mismatch_is_rejected() -> None:
    water = make_water()
    water.loc[1, "property_id"] = "P3"

    with pytest.raises(
        ValueError,
        match="property IDs do not match",
    ):
        build_property_evidence(
            property_coordinates=make_coordinates(),
            fema_baseline=make_fema(),
            water_baseline=water,
            fema_project_crs="EPSG:3857",
            distance_crs="EPSG:26918",
            query_buffer_meters=20000.0,
        )


def test_coordinate_mismatch_is_rejected() -> None:
    fema = make_fema()
    fema.loc[0, "latitude"] = 44.0

    with pytest.raises(
        ValueError,
        match="latitude differs",
    ):
        build_property_evidence(
            property_coordinates=make_coordinates(),
            fema_baseline=fema,
            water_baseline=make_water(),
            fema_project_crs="EPSG:3857",
            distance_crs="EPSG:26918",
            query_buffer_meters=20000.0,
        )


def test_evidence_summary_reports_counts() -> None:
    evidence = build_property_evidence(
        property_coordinates=make_coordinates(),
        fema_baseline=make_fema(),
        water_baseline=make_water(),
        fema_project_crs="EPSG:3857",
        distance_crs="EPSG:26918",
        query_buffer_meters=20000.0,
    )

    summary = summarize_property_evidence(
        evidence
    )

    assert summary["property_count"] == 2
    assert summary["sfha_property_count"] == 1

    assert (
        summary[
            "unique_nearest_water_feature_count"
        ]
        == 2
    )


def test_validation_summary_requires_full_agreement(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "summary.json"

    summary_path.write_text(
        json.dumps(
            {
                "total_union_rows": 2,
                "total_joined_rows": 2,
                "missing_python_rows": 0,
                "missing_cpp_rows": 0,
                "all_fields_agree": 1,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="full field agreement",
    ):
        require_full_agreement_summary(
            summary_path,
            "Test validation",
        )