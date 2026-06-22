from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from caprm.water_distance import (
    nearest_water_reference,
    prepare_distance_properties,
)


DISTANCE_CRS = "EPSG:26918"


def make_feature(
    feature_id: str,
    feature_class: str,
    feature_type: str,
    geometry: object,
    object_id: int,
) -> dict[str, object]:
    return {
        "water_feature_id": feature_id,
        "water_feature_class": feature_class,
        "water_feature_type": feature_type,
        "source_feature_id": feature_id.split(
            ":",
            maxsplit=1,
        )[1],
        "source_object_id": object_id,
        "source_name": pd.NA,
        "geometry": geometry,
    }


def test_point_inside_waterbody_has_zero_distance() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1"],
        },
        geometry=[Point(5, 5)],
        crs=DISTANCE_CRS,
    )

    hydrography = gpd.GeoDataFrame(
        [
            make_feature(
                "waterbody:A",
                "waterbody",
                "Lake",
                Polygon(
                    [
                        (0, 0),
                        (10, 0),
                        (10, 10),
                        (0, 10),
                        (0, 0),
                    ]
                ),
                1,
            )
        ],
        geometry="geometry",
        crs=DISTANCE_CRS,
    )

    output = nearest_water_reference(
        properties,
        hydrography,
        query_buffer_meters=100.0,
        distance_crs=DISTANCE_CRS,
    )

    assert (
        output.loc[
            0,
            "nearest_water_distance_m",
        ]
        == 0.0
    )

    assert (
        output.loc[
            0,
            "nearest_water_feature_id",
        ]
        == "waterbody:A"
    )


def test_equal_distance_tie_uses_canonical_id() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1"],
        },
        geometry=[Point(0, 0)],
        crs=DISTANCE_CRS,
    )

    hydrography = gpd.GeoDataFrame(
        [
            make_feature(
                "flowline:B",
                "flowline",
                "Channel Line",
                LineString(
                    [
                        (-1, -10),
                        (-1, 10),
                    ]
                ),
                2,
            ),
            make_feature(
                "flowline:A",
                "flowline",
                "Channel Line",
                LineString(
                    [
                        (1, -10),
                        (1, 10),
                    ]
                ),
                1,
            ),
        ],
        geometry="geometry",
        crs=DISTANCE_CRS,
    )

    output = nearest_water_reference(
        properties,
        hydrography,
        query_buffer_meters=100.0,
        distance_crs=DISTANCE_CRS,
    )

    assert (
        output.loc[
            0,
            "nearest_water_distance_m",
        ]
        == pytest.approx(1.0)
    )

    assert (
        output.loc[
            0,
            "nearest_water_feature_id",
        ]
        == "flowline:A"
    )

    assert (
        output.loc[
            0,
            "nearest_water_tie_count",
        ]
        == 2
    )


def test_completeness_guard_rejects_buffer_boundary() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1"],
        },
        geometry=[Point(0, 0)],
        crs=DISTANCE_CRS,
    )

    hydrography = gpd.GeoDataFrame(
        [
            make_feature(
                "flowline:A",
                "flowline",
                "Channel Line",
                LineString(
                    [
                        (10, -1),
                        (10, 1),
                    ]
                ),
                1,
            )
        ],
        geometry="geometry",
        crs=DISTANCE_CRS,
    )

    with pytest.raises(
        RuntimeError,
        match="cannot prove nearest-feature completeness",
    ):
        nearest_water_reference(
            properties,
            hydrography,
            query_buffer_meters=10.0,
            distance_crs=DISTANCE_CRS,
        )


def test_properties_are_sorted_by_sample_order() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P2", "P1"],
            "sample_order": [1, 0],
        },
        geometry=[
            Point(1, 1),
            Point(0, 0),
        ],
        crs=DISTANCE_CRS,
    )

    result = prepare_distance_properties(
        properties,
        DISTANCE_CRS,
    )

    assert result["property_id"].tolist() == [
        "P1",
        "P2",
    ]