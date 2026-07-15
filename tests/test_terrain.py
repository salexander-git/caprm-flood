from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from caprm.terrain import (
    _as_float_array,
    _slope_degrees_from_3x3,
    build_terrain_evidence,
    prepare_terrain_inputs,
    summarize_terrain_evidence,
)


def test_as_float_array_replaces_nodata_with_nan() -> None:
    values = np.array([[1, -9999], [3, 4]], dtype="int32")

    result = _as_float_array(values, nodata=-9999)

    assert result.dtype == "float64"
    assert result[0, 0] == 1.0
    assert np.isnan(result[0, 1])


def test_prepare_terrain_inputs_requires_expected_crs() -> None:
    evidence = pd.DataFrame(
        {
            "property_id": ["A"],
            "water_projected_x": [100.0],
            "water_projected_y": [200.0],
            "distance_crs": ["EPSG:3857"],
        }
    )

    with pytest.raises(ValueError, match="Evidence CRS"):
        prepare_terrain_inputs(evidence, expected_crs="EPSG:26918")


def test_prepare_terrain_inputs_rejects_duplicate_property_ids() -> None:
    evidence = pd.DataFrame(
        {
            "property_id": ["A", "A"],
            "water_projected_x": [100.0, 101.0],
            "water_projected_y": [200.0, 201.0],
            "distance_crs": ["EPSG:26918", "EPSG:26918"],
        }
    )

    with pytest.raises(ValueError, match="duplicate property IDs"):
        prepare_terrain_inputs(evidence, expected_crs="EPSG:26918")


def test_slope_degrees_from_3x3_plane() -> None:
    values = np.array(
        [
            [0.0, 1.0, 2.0],
            [0.0, 1.0, 2.0],
            [0.0, 1.0, 2.0],
        ]
    )

    slope = _slope_degrees_from_3x3(
        values,
        pixel_width_m=1.0,
        pixel_height_m=1.0,
    )

    assert math.isclose(slope, 45.0, rel_tol=1e-12)


def test_build_terrain_evidence_from_projected_raster(tmp_path) -> None:
    raster_path = tmp_path / "dem.tif"

    data = np.arange(49, dtype="float32").reshape((7, 7))

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=7,
        width=7,
        count=1,
        dtype="float32",
        crs="EPSG:26918",
        transform=from_origin(0.0, 70.0, 10.0, 10.0),
        nodata=-9999.0,
    ) as raster:
        raster.write(data, 1)

    evidence = pd.DataFrame(
        {
            "sample_order": [0],
            "property_id": ["A"],
            "water_projected_x": [35.0],
            "water_projected_y": [35.0],
            "distance_crs": ["EPSG:26918"],
        }
    )

    terrain = build_terrain_evidence(
        evidence=evidence,
        raster_path=raster_path,
        terrain_crs="EPSG:26918",
        sample_radius_meters=15.0,
    )

    assert len(terrain) == 1
    assert terrain.loc[0, "property_id"] == "A"
    assert terrain.loc[0, "terrain_crs"] == "EPSG:26918"
    assert terrain.loc[0, "terrain_sample_radius_m"] == 15.0
    assert np.isfinite(terrain.loc[0, "terrain_elevation_m"])
    assert np.isfinite(terrain.loc[0, "terrain_relative_elevation_m"])
    assert np.isfinite(terrain.loc[0, "terrain_slope_degrees"])


def test_summarize_terrain_evidence() -> None:
    terrain = pd.DataFrame(
        {
            "property_id": ["A", "B"],
            "terrain_elevation_m": [100.0, 110.0],
            "terrain_local_mean_elevation_m": [101.0, 105.0],
            "terrain_relative_elevation_m": [-1.0, 5.0],
            "terrain_slope_degrees": [2.0, 4.0],
            "terrain_sample_radius_m": [90.0, 90.0],
            "terrain_crs": ["EPSG:26918", "EPSG:26918"],
        }
    )

    summary = summarize_terrain_evidence(terrain)

    assert summary["property_count"] == 2
    assert summary["unique_property_ids"] == 2
    assert summary["minimum_elevation_m"] == 100.0
    assert summary["maximum_elevation_m"] == 110.0
    assert summary["missing_slope_count"] == 0
    assert summary["terrain_crs_values"] == ["EPSG:26918"]