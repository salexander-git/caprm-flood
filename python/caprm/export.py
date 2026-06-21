from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon, box


RING_COLUMNS = [
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

PROPERTY_COLUMNS = [
    "property_id",
    "projected_x",
    "projected_y",
    "longitude",
    "latitude",
]


def require_columns(
    dataframe: pd.DataFrame,
    required_columns: set[str],
    table_name: str,
) -> None:
    missing = sorted(required_columns - set(dataframe.columns))

    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {missing}"
        )


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def display_path(
    path: Path,
    repository_root: Path,
) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(
            repository_root.resolve()
        ).as_posix()
    except ValueError:
        return str(resolved)


def export_projected_properties(
    properties: gpd.GeoDataFrame,
    output_path: Path,
) -> dict[str, Any]:
    require_columns(
        properties,
        set(PROPERTY_COLUMNS),
        "Projected properties",
    )

    output = properties[PROPERTY_COLUMNS].copy()

    output["property_id"] = (
        output["property_id"]
        .astype("string")
        .str.strip()
    )

    missing_ids = (
        output["property_id"].isna()
        | output["property_id"].eq("")
    )

    if missing_ids.any():
        raise ValueError(
            "Projected properties contain missing property IDs."
        )

    if output["property_id"].duplicated().any():
        raise ValueError(
            "Projected properties contain duplicate property IDs."
        )

    for column in [
        "projected_x",
        "projected_y",
        "longitude",
        "latitude",
    ]:
        output[column] = pd.to_numeric(
            output[column],
            errors="raise",
        )

        if output[column].isna().any():
            raise ValueError(
                f"Projected properties contain missing {column} values."
            )

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
        "property_output_size_bytes": output_path.stat().st_size,
        "property_output_sha256": calculate_sha256(output_path),
    }


def read_baseline_feature_indices(
    baseline_path: Path,
) -> list[int]:
    try:
        baseline = pd.read_csv(
            baseline_path,
            usecols=["fema_feature_index"],
        )
    except ValueError as exc:
        raise ValueError(
            f"{baseline_path} does not contain fema_feature_index."
        ) from exc

    numeric = pd.to_numeric(
        baseline["fema_feature_index"],
        errors="raise",
    )

    nonmissing = numeric.dropna()

    if nonmissing.empty:
        raise ValueError(
            "Baseline does not reference any FEMA features."
        )

    if ((nonmissing % 1) != 0).any():
        raise ValueError(
            "Baseline contains noninteger FEMA feature indices."
        )

    return sorted(
        nonmissing.astype("int64").unique().tolist()
    )


def select_fema_features(
    properties: gpd.GeoDataFrame,
    fema: gpd.GeoDataFrame,
    scope: str,
    baseline_path: Path | None = None,
    bbox_buffer_meters: float = 1000.0,
    allow_full_export: bool = False,
) -> gpd.GeoDataFrame:
    if scope not in {"baseline", "bbox", "full"}:
        raise ValueError(
            "scope must be baseline, bbox, or full."
        )

    require_columns(
        fema,
        {
            "fema_feature_index",
            "fema_zone",
            "sfha_flag",
            "source_geometry_id",
            "geometry",
        },
        "Projected FEMA data",
    )

    if not fema.index.is_unique:
        raise ValueError(
            "Projected FEMA data has duplicate feature indices."
        )

    if scope == "full":
        if not allow_full_export:
            raise PermissionError(
                "Full FEMA export is disabled by default because it can "
                "produce files larger than 1 GB. Rerun with "
                "--allow-full-export to confirm the operation."
            )

        selected = fema.copy()

    elif scope == "baseline":
        if baseline_path is None:
            raise ValueError(
                "baseline_path is required for baseline scope."
            )

        feature_indices = read_baseline_feature_indices(
            baseline_path
        )

        missing_indices = sorted(
            set(feature_indices) - set(fema.index)
        )

        if missing_indices:
            raise ValueError(
                "Baseline references FEMA features absent from the "
                f"loaded dataset: {missing_indices[:10]}"
            )

        selected = fema.loc[feature_indices].copy()

    else:
        if bbox_buffer_meters < 0:
            raise ValueError(
                "bbox_buffer_meters cannot be negative."
            )

        min_x, min_y, max_x, max_y = (
            properties.total_bounds
        )

        selection_box = box(
            min_x - bbox_buffer_meters,
            min_y - bbox_buffer_meters,
            max_x + bbox_buffer_meters,
            max_y + bbox_buffer_meters,
        )

        selected = fema.loc[
            fema.geometry.intersects(selection_box)
        ].copy()

    if selected.empty:
        raise ValueError(
            f"FEMA feature selection for scope {scope!r} is empty."
        )

    selected = selected.sort_index(kind="stable")

    missing_source_ids = (
        selected["source_geometry_id"].isna()
        | selected["source_geometry_id"]
        .astype("string")
        .str.strip()
        .eq("")
    )

    if missing_source_ids.any():
        indices = selected.index[
            missing_source_ids
        ].tolist()[:10]

        raise ValueError(
            "Selected FEMA features lack stable source IDs: "
            f"{indices}"
        )

    return selected


def csv_value(value: object) -> str:
    if pd.isna(value):
        return ""

    return str(value)


def polygon_parts(
    geometry: Polygon | MultiPolygon,
) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]

    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)

    raise TypeError(
        f"Unsupported FEMA geometry type: {geometry.geom_type}"
    )


def export_fema_rings(
    fema: gpd.GeoDataFrame,
    output_path: Path,
) -> dict[str, Any]:
    require_columns(
        fema,
        {
            "fema_feature_index",
            "fema_zone",
            "sfha_flag",
            "source_geometry_id",
            "geometry",
        },
        "Selected FEMA data",
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    feature_count = 0
    part_count = 0
    ring_count = 0
    vertex_count = 0
    invalid_geometry_count = 0

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.writer(output_file)
        writer.writerow(RING_COLUMNS)

        for feature_index, row in fema.iterrows():
            geometry = row.geometry

            if geometry is None or geometry.is_empty:
                raise ValueError(
                    f"FEMA feature {feature_index} has no geometry."
                )

            if not geometry.is_valid:
                invalid_geometry_count += 1

            parts = polygon_parts(geometry)

            feature_count += 1
            part_count += len(parts)

            for part_index, polygon in enumerate(parts):
                rings = [
                    polygon.exterior,
                    *polygon.interiors,
                ]

                for ring_index, ring in enumerate(rings):
                    coordinates = list(ring.coords)

                    if len(coordinates) < 4:
                        raise ValueError(
                            "FEMA ring has fewer than four coordinates: "
                            f"feature={feature_index}, "
                            f"part={part_index}, ring={ring_index}"
                        )

                    if coordinates[0] != coordinates[-1]:
                        raise ValueError(
                            "FEMA ring is not closed: "
                            f"feature={feature_index}, "
                            f"part={part_index}, ring={ring_index}"
                        )

                    ring_count += 1

                    for vertex_index, coordinate in enumerate(
                        coordinates
                    ):
                        x = float(coordinate[0])
                        y = float(coordinate[1])

                        writer.writerow(
                            [
                                int(row["fema_feature_index"]),
                                part_index,
                                ring_index,
                                vertex_index,
                                format(x, ".17g"),
                                format(y, ".17g"),
                                csv_value(row["fema_zone"]),
                                csv_value(row["sfha_flag"]),
                                csv_value(
                                    row["source_geometry_id"]
                                ),
                            ]
                        )

                        vertex_count += 1

    return {
        "fema_feature_count": feature_count,
        "polygon_part_count": part_count,
        "ring_count": ring_count,
        "ring_vertex_count": vertex_count,
        "invalid_geometry_count": invalid_geometry_count,
        "rings_output_size_bytes": output_path.stat().st_size,
        "rings_output_sha256": calculate_sha256(output_path),
    }


def write_export_manifest(
    manifest: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )