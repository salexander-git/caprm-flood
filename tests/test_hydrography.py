from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from caprm.hydrography import (
    build_query_envelope,
    canonicalize_hydrography,
)


def test_query_envelope_adds_requested_buffer() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1", "P2"],
        },
        geometry=[
            Point(0, 0),
            Point(10, 20),
        ],
        crs="EPSG:3857",
    )

    envelope = build_query_envelope(
        properties,
        query_crs="EPSG:3857",
        buffer_meters=1000.0,
    )

    assert envelope == (
        -1000.0,
        -1000.0,
        1010.0,
        1020.0,
    )


def make_flowlines() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "OBJECTID": [1, 2],
            "id3dhp": ["A000001", "A000002"],
            "featuretype": [1, 2],
            "featuretypelabel": [
                "Channel Line",
                "Canal",
            ],
            "gnisid": [100, 200],
            "gnisidlabel": [
                "Test Creek",
                "Test Canal",
            ],
            "featuredate": [
                "2025-01-01",
                "2025-01-02",
            ],
            "workunitid": ["W1", "W2"],
            "lengthkm": [1.5, 2.5],
        },
        geometry=[
            LineString([(0, 0), (1, 1)]),
            LineString([(2, 2), (3, 3)]),
        ],
        crs="EPSG:4326",
    )


def test_flowlines_receive_canonical_ids() -> None:
    result, statistics = (
        canonicalize_hydrography(
            dataframe=make_flowlines(),
            feature_class="flowline",
            included_feature_types=[1, 2, 3],
        )
    )

    assert result[
        "water_feature_id"
    ].tolist() == [
        "flowline:A000001",
        "flowline:A000002",
    ]

    assert result[
        "water_feature_type"
    ].tolist() == [
        "Channel Line",
        "Canal",
    ]

    assert statistics["feature_count"] == 2
    assert statistics[
        "invalid_geometry_count"
    ] == 0


def test_duplicate_source_ids_are_rejected() -> None:
    dataframe = make_flowlines()
    dataframe.loc[1, "id3dhp"] = "A000001"

    with pytest.raises(
        ValueError,
        match="duplicate canonical IDs",
    ):
        canonicalize_hydrography(
            dataframe=dataframe,
            feature_class="flowline",
            included_feature_types=[1, 2, 3],
        )


def test_unrequested_feature_type_is_rejected() -> None:
    dataframe = make_flowlines()
    dataframe.loc[1, "featuretype"] = 5

    with pytest.raises(
        ValueError,
        match="unrequested feature types",
    ):
        canonicalize_hydrography(
            dataframe=dataframe,
            feature_class="flowline",
            included_feature_types=[1, 2, 3],
        )