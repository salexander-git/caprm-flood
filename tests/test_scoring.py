from __future__ import annotations

import math

import pandas as pd
import pytest

from caprm.scoring import (
    DEFAULT_WEIGHTS,
    build_exposure_index,
    fema_component_score,
    percentile_score,
    summarize_exposure_index,
    validate_weights,
)


def evidence_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["A", "B", "C"],
            "matched_fema_polygon": [True, True, True],
            "fema_zone": ["X", "AE", "VE"],
            "is_sfha": [False, True, True],
            "nearest_water_distance_m": [1000.0, 100.0, 0.0],
            "distance_crs": ["EPSG:26918", "EPSG:26918", "EPSG:26918"],
        }
    )


def terrain_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["A", "B", "C"],
            "terrain_elevation_m": [150.0, 100.0, 75.0],
            "terrain_relative_elevation_m": [5.0, 0.0, -2.0],
            "terrain_slope_degrees": [1.0, 2.0, 3.0],
            "terrain_crs": ["EPSG:26918", "EPSG:26918", "EPSG:26918"],
        }
    )


def test_validate_weights_accepts_default_weights() -> None:
    assert validate_weights(DEFAULT_WEIGHTS) == DEFAULT_WEIGHTS


def test_validate_weights_rejects_bad_sum() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_weights(
            {
                "fema": 0.4,
                "water": 0.4,
                "terrain": 0.4,
            }
        )


def test_percentile_score_reverses_low_values_when_requested() -> None:
    values = pd.Series([100.0, 50.0, 0.0])

    scores = percentile_score(
        values,
        higher_value_is_higher_exposure=False,
    )

    assert scores.tolist() == pytest.approx(
        [
            33.3333333333,
            66.6666666667,
            100.0,
        ]
    )


def test_fema_component_score_orders_zones() -> None:
    scores = fema_component_score(evidence_frame())

    assert scores.tolist() == [10.0, 95.0, 100.0]


def test_build_exposure_index_outputs_expected_schema() -> None:
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    assert len(index) == 3
    assert index["property_id"].tolist() == ["A", "B", "C"]
    assert index["scoring_policy_version"].nunique() == 1

    for column in [
        "fema_component_0_100",
        "water_component_0_100",
        "terrain_component_0_100",
        "exposure_index_0_100",
        "exposure_percentile",
    ]:
        assert index[column].between(0.0, 100.0).all()


def test_build_exposure_index_rejects_crs_mismatch() -> None:
    evidence = evidence_frame()
    evidence.loc[0, "distance_crs"] = "EPSG:3857"

    with pytest.raises(ValueError, match="Evidence distance CRS mismatch"):
        build_exposure_index(
            evidence=evidence,
            terrain=terrain_frame(),
        )


def test_build_exposure_index_rejects_lost_rows() -> None:
    terrain = terrain_frame().iloc[:2].copy()

    with pytest.raises(ValueError, match="lost property rows"):
        build_exposure_index(
            evidence=evidence_frame(),
            terrain=terrain,
        )


def test_summarize_exposure_index() -> None:
    index = build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )

    summary = summarize_exposure_index(index)

    assert summary["property_count"] == 3
    assert summary["unique_property_ids"] == 3
    assert summary["scoring_policy_version"] == "preliminary_exposure_index_v1"
    assert math.isclose(
        summary["mean_exposure_index"],
        float(index["exposure_index_0_100"].mean()),
    )