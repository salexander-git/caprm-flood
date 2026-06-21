from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from caprm.ingest import (
    select_unique_identifier,
    validate_property_points,
)


def test_unique_identifier_skips_nonunique_candidate() -> None:
    dataframe = pd.DataFrame(
        {
            "DFIRM_ID": ["36055C", "36055C"],
            "FLD_AR_ID": ["36055C_1", "36055C_2"],
        }
    )

    result = select_unique_identifier(
        dataframe,
        ["DFIRM_ID", "FLD_AR_ID"],
        "FEMA feature identifier",
    )

    assert result == "FLD_AR_ID"


def test_unique_identifier_rejects_all_invalid_candidates() -> None:
    dataframe = pd.DataFrame(
        {
            "A": ["same", "same"],
            "B": ["one", pd.NA],
        }
    )

    with pytest.raises(
        ValueError,
        match="No complete unique",
    ):
        select_unique_identifier(
            dataframe,
            ["A", "B"],
            "identifier",
        )


def test_property_points_are_sorted_by_sample_order() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P2", "P1"],
            "sample_order": [1, 0],
        },
        geometry=[
            Point(-77.6, 43.2),
            Point(-77.7, 43.1),
        ],
        crs="EPSG:4326",
    )

    result = validate_property_points(
        properties,
        expected_limit=2,
    )

    assert result["property_id"].tolist() == ["P1", "P2"]


def test_duplicate_property_ids_are_rejected() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1", "P1"],
        },
        geometry=[
            Point(-77.6, 43.2),
            Point(-77.7, 43.1),
        ],
        crs="EPSG:4326",
    )

    with pytest.raises(
        ValueError,
        match="duplicate IDs",
    ):
        validate_property_points(properties)