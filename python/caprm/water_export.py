from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPolygon,
    Polygon,
)


FEATURE_COLUMNS = [
    "water_feature_index",
    "water_feature_id",
    "water_feature_class",
    "water_feature_type",
    "source_feature_id",
    "source_object_id",
    "source_gnis_id",
    "source_name",
    "geometry_kind",
]

VERTEX_COLUMNS = [
    "water_feature_index",
    "part_index",
    "ring_index",
    "vertex_index",
    "x",
    "y",
]


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_columns(
    dataframe: pd.DataFrame,
    required: set[str],
    table_name: str,
) -> None:
    missing = sorted(required - set(dataframe.columns))

    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {missing}"
        )


def geometry_kind(geometry: object) -> str:
    if isinstance(
        geometry,
        (LineString, MultiLineString),
    ):
        return "line"

    if isinstance(
        geometry,
        (Polygon, MultiPolygon),
    ):
        return "polygon"

    geometry_type = getattr(
        geometry,
        "geom_type",
        type(geometry).__name__,
    )

    raise TypeError(
        f"Unsupported water geometry type: {geometry_type}"
    )


def prepare_water_features(
    hydrography: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    require_columns(
        hydrography,
        {
            "water_feature_id",
            "water_feature_class",
            "water_feature_type",
            "source_feature_id",
            "source_object_id",
            "source_gnis_id",
            "source_name",
            "geometry",
        },
        "Hydrography",
    )

    if hydrography.empty:
        raise ValueError("Hydrography dataset is empty.")

    prepared = hydrography.copy()

    prepared["water_feature_id"] = (
        prepared["water_feature_id"]
        .astype("string")
        .str.strip()
    )

    missing_ids = (
        prepared["water_feature_id"].isna()
        | prepared["water_feature_id"].eq("")
    )

    if missing_ids.any():
        raise ValueError(
            "Hydrography contains missing canonical feature IDs."
        )

    if prepared["water_feature_id"].duplicated().any():
        raise ValueError(
            "Hydrography contains duplicate canonical feature IDs."
        )

    if prepared.geometry.isna().any():
        raise ValueError(
            "Hydrography contains null geometries."
        )

    if prepared.geometry.is_empty.any():
        raise ValueError(
            "Hydrography contains empty geometries."
        )

    if (~prepared.geometry.is_valid).any():
        raise ValueError(
            "Hydrography contains invalid geometries."
        )

    prepared["geometry_kind"] = [
        geometry_kind(geometry)
        for geometry in prepared.geometry
    ]

    prepared = prepared.sort_values(
        "water_feature_id",
        kind="stable",
    ).reset_index(drop=True)

    prepared.insert(
        0,
        "water_feature_index",
        range(len(prepared)),
    )

    return prepared


def validate_reference_alignment(
    properties: gpd.GeoDataFrame,
    feature_table: gpd.GeoDataFrame,
    reference: pd.DataFrame,
) -> None:
    require_columns(
        reference,
        {
            "property_id",
            "nearest_water_feature_id",
        },
        "Python nearest-water reference",
    )

    property_ids = (
        properties["property_id"]
        .astype("string")
        .str.strip()
    )

    reference_property_ids = (
        reference["property_id"]
        .astype("string")
        .str.strip()
    )

    if reference_property_ids.duplicated().any():
        raise ValueError(
            "Python nearest-water reference contains duplicate "
            "property IDs."
        )

    if set(property_ids) != set(reference_property_ids):
        raise ValueError(
            "Python nearest-water reference property IDs do not "
            "match the projected property input."
        )

    feature_ids = set(
        feature_table["water_feature_id"]
        .astype("string")
    )

    reference_feature_ids = set(
        reference["nearest_water_feature_id"]
        .dropna()
        .astype("string")
    )

    missing_feature_ids = sorted(
        reference_feature_ids - feature_ids
    )

    if missing_feature_ids:
        raise ValueError(
            "Python nearest-water reference contains feature IDs "
            "absent from the exported hydrography: "
            f"{missing_feature_ids[:10]}"
        )


def export_water_properties(
    properties: gpd.GeoDataFrame,
    output_path: Path,
) -> dict[str, Any]:
    require_columns(
        properties,
        {
            "property_id",
            "geometry",
        },
        "Projected properties",
    )

    if properties.geometry.geom_type.ne("Point").any():
        raise ValueError(
            "Projected properties contain non-Point geometries."
        )

    output = pd.DataFrame(
        {
            "property_id": (
                properties["property_id"]
                .astype("string")
                .str.strip()
            ),
            "projected_x": properties.geometry.x,
            "projected_y": properties.geometry.y,
        }
    )

    if "sample_order" in properties.columns:
        output["sample_order"] = pd.to_numeric(
            properties["sample_order"],
            errors="raise",
        )

        output = output.sort_values(
            "sample_order",
            kind="stable",
        )
    else:
        output["sample_order"] = range(len(output))

    if output["property_id"].duplicated().any():
        raise ValueError(
            "Projected properties contain duplicate IDs."
        )

    output = output[
        [
            "sample_order",
            "property_id",
            "projected_x",
            "projected_y",
        ]
    ]

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.to_csv(
        output_path,
        index=False,
        float_format="%.17g",
    )

    return {
        "property_count": int(len(output)),
        "properties_size_bytes": output_path.stat().st_size,
        "properties_sha256": calculate_sha256(output_path),
    }


def export_water_feature_metadata(
    feature_table: gpd.GeoDataFrame,
    output_path: Path,
) -> dict[str, Any]:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    feature_table[FEATURE_COLUMNS].to_csv(
        output_path,
        index=False,
    )

    return {
        "water_feature_count": int(
            len(feature_table)
        ),
        "line_feature_count": int(
            feature_table["geometry_kind"]
            .eq("line")
            .sum()
        ),
        "polygon_feature_count": int(
            feature_table["geometry_kind"]
            .eq("polygon")
            .sum()
        ),
        "features_size_bytes": output_path.stat().st_size,
        "features_sha256": calculate_sha256(output_path),
    }


def line_parts(
    geometry: LineString | MultiLineString,
) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]

    return list(geometry.geoms)


def polygon_parts(
    geometry: Polygon | MultiPolygon,
) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]

    return list(geometry.geoms)


def write_coordinates(
    writer: csv.writer,
    feature_index: int,
    part_index: int,
    ring_index: int,
    coordinates: list[tuple[float, ...]],
) -> int:
    for vertex_index, coordinate in enumerate(
        coordinates
    ):
        writer.writerow(
            [
                feature_index,
                part_index,
                ring_index,
                vertex_index,
                format(float(coordinate[0]), ".17g"),
                format(float(coordinate[1]), ".17g"),
            ]
        )

    return len(coordinates)


def export_water_vertices(
    feature_table: gpd.GeoDataFrame,
    output_path: Path,
) -> dict[str, Any]:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    line_part_count = 0
    polygon_part_count = 0
    polygon_ring_count = 0
    vertex_count = 0
    segment_count = 0

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.writer(output_file)
        writer.writerow(VERTEX_COLUMNS)

        for row in feature_table.itertuples(
            index=False
        ):
            feature_index = int(
                row.water_feature_index
            )
            geometry = row.geometry

            if row.geometry_kind == "line":
                parts = line_parts(geometry)

                for part_index, part in enumerate(
                    parts
                ):
                    coordinates = list(part.coords)

                    if len(coordinates) < 2:
                        raise ValueError(
                            "Water line contains fewer than two "
                            f"vertices: feature {feature_index}"
                        )

                    line_part_count += 1
                    vertex_count += write_coordinates(
                        writer,
                        feature_index,
                        part_index,
                        0,
                        coordinates,
                    )
                    segment_count += len(coordinates) - 1

            elif row.geometry_kind == "polygon":
                parts = polygon_parts(geometry)

                for part_index, polygon in enumerate(
                    parts
                ):
                    polygon_part_count += 1

                    rings = [
                        polygon.exterior,
                        *polygon.interiors,
                    ]

                    for ring_index, ring in enumerate(
                        rings
                    ):
                        coordinates = list(ring.coords)

                        if len(coordinates) < 4:
                            raise ValueError(
                                "Water polygon ring contains fewer "
                                "than four vertices: "
                                f"feature {feature_index}"
                            )

                        if coordinates[0] != coordinates[-1]:
                            raise ValueError(
                                "Water polygon ring is not closed: "
                                f"feature {feature_index}"
                            )

                        polygon_ring_count += 1
                        vertex_count += write_coordinates(
                            writer,
                            feature_index,
                            part_index,
                            ring_index,
                            coordinates,
                        )
                        segment_count += (
                            len(coordinates) - 1
                        )

            else:
                raise RuntimeError(
                    f"Unexpected geometry kind: "
                    f"{row.geometry_kind}"
                )

    return {
        "line_part_count": line_part_count,
        "polygon_part_count": polygon_part_count,
        "polygon_ring_count": polygon_ring_count,
        "vertex_count": vertex_count,
        "segment_count": segment_count,
        "vertices_size_bytes": output_path.stat().st_size,
        "vertices_sha256": calculate_sha256(output_path),
    }