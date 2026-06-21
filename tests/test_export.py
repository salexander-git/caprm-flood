from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from caprm.export import (
    export_fema_rings,
    select_fema_features,
)


def make_properties() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "property_id": ["P1"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:3857",
    )


def make_fema() -> gpd.GeoDataFrame:
    polygon_with_hole = Polygon(
        shell=[
            (0, 0),
            (4, 0),
            (4, 4),
            (0, 4),
            (0, 0),
        ],
        holes=[
            [
                (1, 1),
                (2, 1),
                (2, 2),
                (1, 2),
                (1, 1),
            ]
        ],
    )

    second_polygon = Polygon(
        [
            (10, 10),
            (11, 10),
            (11, 11),
            (10, 11),
            (10, 10),
        ]
    )

    fema = gpd.GeoDataFrame(
        {
            "fema_feature_index": [10, 20],
            "fema_zone": ["AE", "X"],
            "sfha_flag": ["T", "F"],
            "source_geometry_id": [
                "FEATURE_10",
                "FEATURE_20",
            ],
        },
        geometry=[
            polygon_with_hole,
            second_polygon,
        ],
        crs="EPSG:3857",
    )

    fema.index = [10, 20]
    return fema


def test_baseline_scope_selects_referenced_features(
    tmp_path: Path,
) -> None:
    baseline_path = tmp_path / "baseline.csv"

    pd.DataFrame(
        {
            "fema_feature_index": [10, 10],
        }
    ).to_csv(
        baseline_path,
        index=False,
    )

    selected = select_fema_features(
        properties=make_properties(),
        fema=make_fema(),
        scope="baseline",
        baseline_path=baseline_path,
    )

    assert selected.index.tolist() == [10]


def test_full_scope_requires_explicit_confirmation() -> None:
    with pytest.raises(
        PermissionError,
        match="Full FEMA export is disabled",
    ):
        select_fema_features(
            properties=make_properties(),
            fema=make_fema(),
            scope="full",
        )


def test_ring_export_streams_exterior_and_hole(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "rings.csv"

    statistics = export_fema_rings(
        make_fema().loc[[10]],
        output_path,
    )

    exported = pd.read_csv(output_path)

    assert exported.columns.tolist() == [
        "fema_feature_index",
        "part_index",
        "ring_index",
        "vertex_index",
        "x",
        "y",
        "fema_zone",
        "sfha_flag",
        "source_geometry_id",
    ]

    assert statistics["fema_feature_count"] == 1
    assert statistics["polygon_part_count"] == 1
    assert statistics["ring_count"] == 2
    assert statistics["ring_vertex_count"] == 10

    assert exported["ring_index"].tolist() == [
        0,
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        1,
        1,
    ]

    assert exported["source_geometry_id"].unique().tolist() == [
        "FEATURE_10"
    ]