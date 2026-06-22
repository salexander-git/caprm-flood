from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, Polygon

from caprm.water_export import (
    export_water_feature_metadata,
    export_water_properties,
    export_water_vertices,
    prepare_water_features,
    validate_reference_alignment,
)


CRS = "EPSG:26918"


def make_hydrography() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "water_feature_id": [
                "waterbody:B",
                "flowline:A",
            ],
            "water_feature_class": [
                "waterbody",
                "flowline",
            ],
            "water_feature_type": [
                "Lake",
                "Channel Line",
            ],
            "source_feature_id": ["B", "A"],
            "source_object_id": [2, 1],
            "source_gnis_id": [pd.NA, pd.NA],
            "source_name": ["Test Lake", "Test Creek"],
        },
        geometry=[
            Polygon(
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
            ),
            LineString(
                [
                    (10, 0),
                    (10, 5),
                ]
            ),
        ],
        crs=CRS,
    )


def test_feature_indices_are_deterministic() -> None:
    result = prepare_water_features(
        make_hydrography()
    )

    assert result["water_feature_id"].tolist() == [
        "flowline:A",
        "waterbody:B",
    ]

    assert result[
        "water_feature_index"
    ].tolist() == [0, 1]

    assert result["geometry_kind"].tolist() == [
        "line",
        "polygon",
    ]


def test_cpp_export_preserves_geometry_structure(
    tmp_path: Path,
) -> None:
    features = prepare_water_features(
        make_hydrography()
    )

    metadata_path = tmp_path / "features.csv"
    vertices_path = tmp_path / "vertices.csv"

    metadata_statistics = (
        export_water_feature_metadata(
            features,
            metadata_path,
        )
    )

    vertex_statistics = export_water_vertices(
        features,
        vertices_path,
    )

    metadata = pd.read_csv(metadata_path)
    vertices = pd.read_csv(vertices_path)

    assert metadata_statistics[
        "water_feature_count"
    ] == 2

    assert vertex_statistics["segment_count"] == 9
    assert vertex_statistics["vertex_count"] == 12

    polygon_vertices = vertices[
        vertices["water_feature_index"].eq(1)
    ]

    assert sorted(
        polygon_vertices["ring_index"].unique()
    ) == [0, 1]


def test_reference_alignment_and_property_export(
    tmp_path: Path,
) -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P2", "P1"],
            "sample_order": [1, 0],
        },
        geometry=[
            Point(5, 5),
            Point(0, 0),
        ],
        crs=CRS,
    )

    features = prepare_water_features(
        make_hydrography()
    )

    reference = pd.DataFrame(
        {
            "property_id": ["P1", "P2"],
            "nearest_water_feature_id": [
                "flowline:A",
                "waterbody:B",
            ],
        }
    )

    validate_reference_alignment(
        properties,
        features,
        reference,
    )

    output_path = tmp_path / "properties.csv"

    statistics = export_water_properties(
        properties,
        output_path,
    )

    exported = pd.read_csv(output_path)

    assert statistics["property_count"] == 2
    assert exported["property_id"].tolist() == [
        "P1",
        "P2",
    ]