from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import (
    LineString,
    Point,
    Polygon,
)

from caprm.study_area import (
    build_buffered_study_area,
    filter_features_to_study_area,
    study_area_envelope,
    validate_properties_within_county,
)


CRS = "EPSG:26918"


def make_county() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "county_geoid": ["36055"],
            "county_name": ["Test County"],
            "source_object_id": [1],
        },
        geometry=[
            Polygon(
                [
                    (0, 0),
                    (10, 0),
                    (10, 10),
                    (0, 10),
                    (0, 0),
                ]
            )
        ],
        crs=CRS,
    )


def test_county_buffer_expands_metric_envelope() -> None:
    buffered = build_buffered_study_area(
        make_county(),
        distance_crs=CRS,
        buffer_meters=2.0,
    )

    assert study_area_envelope(buffered) == (
        -2.0,
        -2.0,
        12.0,
        12.0,
    )


def test_properties_are_covered_by_county() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": [
                "inside",
                "boundary",
            ]
        },
        geometry=[
            Point(5, 5),
            Point(0, 5),
        ],
        crs=CRS,
    )

    statistics = (
        validate_properties_within_county(
            properties,
            make_county(),
        )
    )

    assert statistics[
        "properties_covered_by_county"
    ] == 2

    assert statistics[
        "properties_outside_county"
    ] == 0


def test_outside_property_is_rejected() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["outside"],
        },
        geometry=[Point(20, 20)],
        crs=CRS,
    )

    with pytest.raises(
        ValueError,
        match="outside the official county boundary",
    ):
        validate_properties_within_county(
            properties,
            make_county(),
        )


def test_hydrography_is_filtered_to_buffered_area() -> None:
    study_area = build_buffered_study_area(
        make_county(),
        distance_crs=CRS,
        buffer_meters=2.0,
    )

    features = gpd.GeoDataFrame(
        {
            "water_feature_id": [
                "inside",
                "crossing",
                "outside",
            ]
        },
        geometry=[
            LineString(
                [(2, 2), (3, 3)]
            ),
            LineString(
                [(11, 5), (13, 5)]
            ),
            LineString(
                [(20, 20), (21, 21)]
            ),
        ],
        crs=CRS,
    )

    retained, statistics = (
        filter_features_to_study_area(
            features,
            study_area,
        )
    )

    assert retained[
        "water_feature_id"
    ].tolist() == [
        "inside",
        "crossing",
    ]

    assert statistics[
        "feature_count_before_study_filter"
    ] == 3

    assert statistics[
        "retained_feature_count"
    ] == 2

    assert statistics[
        "excluded_outside_study_area_count"
    ] == 1