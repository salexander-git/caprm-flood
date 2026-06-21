from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from caprm.baseline import run_fema_point_in_polygon
from caprm.crs import normalize_inputs


CONFIG = {
    "fema_flood_polygons": {
        "zone_field_candidates": ["FLD_ZONE"],
        "sfha_field_candidates": ["SFHA_TF"],
    }
}


def make_properties() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "property_id": ["P1", "P2", "P3"],
            "sample_order": [0, 1, 2],
        },
        geometry=[
            Point(0.5, 0.5),
            Point(2.5, 0.5),
            Point(0.0, 0.5),
        ],
        crs="EPSG:4326",
    )


def make_fema() -> gpd.GeoDataFrame:
    fema = gpd.GeoDataFrame(
        {
            "FLD_ZONE": ["AE", "X"],
            "SFHA_TF": ["T", "F"],
            "source_geometry_id": [
                "FEATURE_AE",
                "FEATURE_X",
            ],
            "fema_feature_index": [10, 20],
        },
        geometry=[
            Polygon(
                [
                    (0, 0),
                    (1, 0),
                    (1, 1),
                    (0, 1),
                    (0, 0),
                ]
            ),
            Polygon(
                [
                    (2, 0),
                    (3, 0),
                    (3, 1),
                    (2, 1),
                    (2, 0),
                ]
            ),
        ],
        crs="EPSG:4326",
    )

    fema.index = [10, 20]
    return fema


def test_point_in_polygon_preserves_within_semantics() -> None:
    properties, fema = normalize_inputs(
        make_properties(),
        make_fema(),
        "EPSG:3857",
    )

    output = run_fema_point_in_polygon(
        properties,
        fema,
        CONFIG,
    )

    assert output["property_id"].tolist() == [
        "P1",
        "P2",
        "P3",
    ]

    assert output[
        "matched_fema_polygon"
    ].tolist() == [True, True, False]

    assert output["is_sfha"].tolist() == [
        True,
        False,
        False,
    ]

    assert output["fema_zone"].tolist()[:2] == [
        "AE",
        "X",
    ]

    assert output[
        "source_geometry_id"
    ].tolist()[:2] == [
        "FEATURE_AE",
        "FEATURE_X",
    ]

    assert output["fema_feature_index"].iloc[0] == 10
    assert output["fema_feature_index"].iloc[1] == 20
    assert pd.isna(output["fema_feature_index"].iloc[2])


def test_multiple_polygon_matches_are_rejected() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1"],
            "sample_order": [0],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )

    overlapping = make_fema().iloc[[0]].copy()
    duplicate = overlapping.copy()
    duplicate["source_geometry_id"] = "FEATURE_DUPLICATE"
    duplicate["fema_feature_index"] = 11
    duplicate.index = [11]

    fema = gpd.GeoDataFrame(
        pd.concat(
            [overlapping, duplicate]
        ),
        geometry="geometry",
        crs="EPSG:4326",
    )

    properties_projected, fema_projected = (
        normalize_inputs(
            properties,
            fema,
            "EPSG:3857",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="multiple FEMA polygons",
    ):
        run_fema_point_in_polygon(
            properties_projected,
            fema_projected,
            CONFIG,
        )