from __future__ import annotations 

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd 
import rasterio
from rasterio.windows import Window



INPUT_COLUMNS = {
    "property_id",
    "water_projected_x",
    "water_projected_y",
    "distance_crs",
}

OUTPUT_COLUMNS = [
    "property_id",
    "terrain_elevation_m",
    "terrain_local_mean_elevation_m",
    "terrain_relative_elevation_m",
    "terrain_slope_degrees",
    "terrain_sample_radius_m",
    "terrain_crs",
]

"""
We hash files to create a **reproducibility fingerprint**. It lets us prove that a result
was generated from a specific DEM/evidence file, and lets us detect if the input file changed later.
This is relevant here because public geospatial data is subject to updates, and we want proof similar to our
FEMA/hydrography workflow.
"""

"""
SHA-256 is a standard hash algorithm that produces a 256-bit hash value; with 
2^256 possible hash values, the probability of collisions is functionally zero. 
"""


def calculate_sha256(path: Path) -> str:
    """Calculate the SHA256 hash of a file.
    Args:
        path (Path): The path to the file.
    Returns:
        str: The SHA256 hash of the file.
    """
    digest = hashlib.sha256() #

    """
    we use path.open("rb") as f, i.e., binary mode, for SHA-256 hashing.
    This is because checksums must be computed from the file's exact raw bytes,
    with no text decoding, newline conversion, or character encoding interpretations.
    This facilitates the same hash across different platforms.
    """  
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""): #iterates over size 1024*1024 bytes, i.e., 1MiB
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
    
def prepare_terrain_inputs(
    evidence: pd.DataFrame,
    expected_crs: str,
) -> pd.DataFrame:
    require_columns(evidence, INPUT_COLUMNS, "Integrated property evidence")
    prepared = evidence.copy()

    prepared["property_id"] = (
        prepared["property_id"].astype("string").str.strip()
    )

    if (
        prepared["property_id"].isna().any()
        or prepared["property_id"].eq("").any()
    ):
        raise ValueError(
            "Integrated evidence contains missing property IDs."
        )

    if prepared["property_id"].duplicated().any():
        raise ValueError(
            "Integrated evidence contains duplicate property IDs."
        )

    for column in ["water_projected_x", "water_projected_y"]:
        prepared[column] = pd.to_numeric(
            prepared[column], errors="raise",
        ).astype("float64")

        if (~np.isfinite(prepared[column])).any():
            raise ValueError(f"Integrated evidence contains nonfinite {column}.")
        
        observed_crs = set(
            prepared["distance_crs"].astype("string").str.strip().dropna()
        )

        if observed_crs != {expected_crs}:
            raise ValueError(
                "Evidence CRS doesn't match the terrain raster CRS."
                f"Observed: {sorted(observed_crs)}; expected: {expected_crs}"
            )
        
        if "sample_order" in prepared.columns:
            prepared["sample_order"] = pd.to_numeric(
                prepared["sample_order"], errors="raise",
            ).astype("int64")

            prepared = prepared.sort_values(
                "sample_order",
                kind="stable",
            )

        return prepared.reset_index(drop=True)
    
    
    
def _as_float_array(
    values: np.ndarray,
    nodata: float | int | None,
) -> np.ndarray:
    array = values.astype("float64")

    if nodata is not None:
        array = np.where(array == float(nodata), np.nan, array)

    return array



def _window_for_point(
    row: int,
    col: int,
    radius_pixels_x: int,
    radius_pixels_y: int,
    width: int,
    height: int,
) -> Window:
    col_start = max(0, col - radius_pixels_x)
    row_start = max(0, row - radius_pixels_y)

    col_stop = min(width, col + radius_pixels_x + 1)
    row_stop = min(height, row + radius_pixels_y + 1)

    return Window(
        col_off=col_start,
        row_off=row_start,
        width=col_stop - col_start,
        height=row_stop - row_start
    )


def _slope_degrees_from_3x3(
        values: np.ndarray,
        pixel_width_m: float,
        pixel_height_m: float,
) -> float:
    if values.shape != (3, 3):
        return float("nan")
    
    if np.isnan(values).any():
        return float("nan")
    
    z1, z2, z3 = values[0, 0], values[0, 1], values[0, 2]
    z4, _, z6 = values[1, 0], values[1, 1], values[1, 2]
    z7, z8, z9 = values[2, 0], values[2, 1], values[2, 2]

    dzdx = ((z3 + 2 * z6 + z9) - (z1 + 2 * z4 + z7)) / (8 * pixel_width_m) 
    dzdy = ((z7 + 2 * z8 + z9) - (z1 + 2 * z2 + z3)) / (8 * pixel_height_m)

    slope_radians = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2))

    return float(np.degrees(slope_radians))


def build_terrain_evidence(
    evidence: pd.DataFrame,
    raster_path: Path,
    terrain_crs: str,
    sample_radius_meters: float,
) -> pd.DataFrame:
    if sample_radius_meters <= 0:
        raise ValueError("sample_radius_meters must be greater than zero.")
    
    prepared = prepare_terrain_inputs(evidence, terrain_crs)

    if not raster_path.exists():
        raise FileNotFoundError(f"Terrain raster file not found: {raster_path}")
    
    records: list[dict[str, Any]] = []

    with rasterio.open(raster_path) as raster:
        if raster.crs is None:
            raise ValueError(f"Terrain raster has no CRS: {raster_path}")
        
        if raster.crs.to_string() != terrain_crs:
            raise ValueError(
                f"Terrain raster CRS doesn't match expected CRS."
                f"Observed: {raster.crs.to_string()}; expected: {terrain_crs}"
            )
        
        if not raster.crs.is_projected:
            raise ValueError(
                "Terrain raster must be projected in meters before sampling."
            )
        
        pixel_width_m = abs(float(raster.transform.a))
        pixel_height_m = abs(float(raster.transform.e))

        if pixel_width_m <= 0 or pixel_height_m <= 0:
            raise ValueError("Terrain raster has invalid pixel dimensions.")
        
        radius_pixels_x = max(1, int(np.ceil(sample_radius_meters / pixel_width_m)))
        radius_pixels_y = max(1, int(np.ceil(sample_radius_meters / pixel_height_m)))

        for row in prepared.itertuples(index=False):
            x = float(row.water_projected_x)
            y = float(row.water_projected_y)

            pixel_row, pixel_col = raster.index(x, y) # Convert world coordinates to pixel coordinatesq

            if (
                pixel_row < 0
                or pixel_col < 0
                or pixel_row >= raster.height
                or pixel_col >= raster.width
            ): 
                raise ValueError(
                    f"Property {row.property_id} falls outside the terrain raster."
                )
            
            center = raster.read(1, window=Window(pixel_col, pixel_row, 1, 1))
            center_value = _as_float_array(center, raster.nodata)[0, 0]

            if not np.isfinite(center_value):
                raise ValueError(
                    f"Terrain raster has no data at property {row.property_id}."
                )
            
            local_window = _window_for_point(
                row=pixel_row,
                col=pixel_col,
                radius_pixels_x=radius_pixels_x,
                radius_pixels_y=radius_pixels_y,
                width=raster.width,
                height=raster.height,
            )

            local_values = _as_float_array(
                raster.read(1, window=local_window), 
                raster.nodata,
            )

            if np.isfinite(local_values).sum() == 0:
                raise ValueError(
                    f"Property {row.property_id} has no valid local terrain window."
                )
            
            local_mean = float(np.nanmean(local_values))

            slope_window = _window_for_point(
                row=pixel_row,
                col=pixel_col,
                radius_pixels_x=1,
                radius_pixels_y=1,
                width=raster.width,
                height=raster.height,
            )

            slope_values = _as_float_array(
                raster.read(1, window=slope_window),
                raster.nodata,
            )

            slope_degrees = _slope_degrees_from_3x3(
                values=slope_values,
                pixel_width_m=pixel_width_m,
                pixel_height_m=pixel_height_m,
            )

            records.append({
                "property_id": row.property_id,
                "terrain_elevation_m": center_value,
                "terrain_local_mean_elevation_m": local_mean,
                "terrain_relative_elevation_m": center_value - local_mean,
                "terrain_slope_degrees": slope_degrees,
                "terrain_sample_radius_m": sample_radius_meters,
                "terrain_crs": terrain_crs,
            })
    
    output = pd.DataFrame.from_records(records, columns=OUTPUT_COLUMNS)

    if output["property_id"].duplicated().any():
        raise RuntimeError("Terrain evidence contains duplicate property IDs.")
    
    numeric_columns = [
        "terrain_elevation_m",
        "terrain_local_mean_elevation_m",
        "terrain_relative_elevation_m",
        "terrain_sample_radius_m",
    ]

    for column in numeric_columns:
        if (~np.isfinite(output[column])).any():
            raise RuntimeError(f"Terrain evidence contains nonfinite {column}.")
        
    if output["terrain_slope_degrees"].isna().all():
        raise RuntimeError("Terrain slope couldn't be computed for any property.")
    
    return output


def summarize_terrain_evidence(
        terrain: pd.DataFrame,
) -> dict[str, Any]:
    require_columns(terrain, set(OUTPUT_COLUMNS), "Terrain evidence")

    return {
        "property_count": int(len(terrain)),
        "unique_property_ids": int(terrain["property_id"].nunique()),
        "minimum_elevation_m": float(terrain["terrain_elevation_m"].min()),
        "maximum_elevation_m": float(terrain["terrain_elevation_m"].max()),
        "mean_elevation_m": float(terrain["terrain_elevation_m"].mean()),
        "median_elevation_m": float(terrain["terrain_elevation_m"].median()),
        "minimum_relative_elevation_m": float(terrain["terrain_relative_elevation_m"].min()),
        "maximum_relative_elevation_m": float(terrain["terrain_relative_elevation_m"].max()),
        "mean_relative_elevation_m": float(terrain["terrain_relative_elevation_m"].mean()),
        "median_relative_elevation_m": float(terrain["terrain_relative_elevation_m"].median()),
        "missing_slope_count": int(terrain["terrain_slope_degrees"].isna().sum()),
        "mean_slope_degrees": float(terrain["terrain_slope_degrees"].dropna().mean()),
        "median_slope_degrees": float(terrain["terrain_slope_degrees"].dropna().median()),
        "terrain_crs_values": sorted(terrain["terrain_crs"].astype("string").dropna().unique().tolist()),
    }

