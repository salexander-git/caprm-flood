from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.ingest import repository_path
from caprm.terrain import calculate_sha256


RESAMPLING_METHODS = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
}


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)
    

def raster_summary(path: Path) -> dict[str, Any]:
    with rasterio.open(path) as raster:
        return {
            "path": display_path(path),
            "sha256": calculate_sha256(path),
            "crs": raster.crs.to_string() if raster.crs else None,
            "width": int(raster.width),
            "height": int(raster.height),
            "band_count": int(raster.count),
            "dtype": raster.dtypes[0] if raster.dtypes else None,
            "nodata": raster.nodata,
            "bounds": {
                "left": float(raster.bounds.left),
                "bottom": float(raster.bounds.bottom),
                "right": float(raster.bounds.right),
                "top": float(raster.bounds.top),
            },
            "transform": tuple(float(value) for value in raster.transform),
        }
    

def prepare_terrain_raster(
        source_path: Path,
        output_path: Path,
        target_crs_text: str,
        resampling_name: str,
) -> dict[str, Any]:
    if not source_path.exists():
        raise FileNotFoundError(f"Source DEM does not exist: {source_path}")
    
    if resampling_name not in RESAMPLING_METHODS:
        raise ValueError(
            f"Unsupported resampling method: {resampling_name}"
        )
    
    target_crs = CRS.from_string(target_crs_text)

    if not target_crs.is_projected:
        raise ValueError(
            f"Target terrain CRS must be projected: {target_crs_text}"
        )
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(source_path) as source:
        if source.crs is None:
            raise ValueError("Source DEM has no CRS.")
        
        if source.count < 1:
            raise ValueError("Source DEM contains no raster bands.")
        
        transform, width, height = calculate_default_transform(
            source.crs, 
            target_crs,
            source.width,
            source.height,
            *source.bounds
        )

        profile = source.profile.copy()
        profile.update(
            {
                "driver": "GTiff",
                "crs": target_crs,
                "transform": transform,
                "width": width,
                "height": height,
                "compress": "lzw",
                "tiled": True,
                "bigtiff": "if_safer",
            }
        )

        temporary_path = output_path.with_name(
            f"{output_path.stem}.tmp{output_path.suffix}"
        )

        temporary_path.unlink(missing_ok=True)

        with rasterio.open(temporary_path, "w", **profile) as destination:
            for band_index in range(1, source.count + 1):
                reproject(
                    rasterio.band(source, band_index),
                    rasterio.band(destination, band_index),
                    src_transform=source.transform,
                    src_crs=source.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=RESAMPLING_METHODS[resampling_name],
                    src_nodata=source.nodata,
                    dst_nodata=source.nodata,
                )

        temporary_path.replace(output_path)

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "terrain_raster_prepare_v1",
        "source": raster_summary(source_path),
        "output": raster_summary(output_path),
        "target_crs": target_crs_text,
        "resampling": resampling_name,
        "purpose": (
            "Reproject source DEM into the project distance CRS so terrain "
            "sampling, local-radius calculations, and slope calculations use "
            "meter-based coordinates."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reproject a source DEM into the CAPRM-Flood terrain CRS."
        )
    )

    parser.add_argument(
        "--source",
        default = "data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif",
    )

    parser.add_argument(
        "--output",
        default="data/raw/terrain/monroe_dem_utm18.tif",
    )

    parser.add_argument(
        "--target-crs",
        default="EPSG:26918"
    )

    parser.add_argument(
        "--resampling",
        choices=sorted(RESAMPLING_METHODS),
        default="bilinear",
    )

    parser.add_argument(
        "--manifest-output",
        default="outputs/validation/terrain_raster_prepare_manifest.json",
    )

    args = parser.parse_args()

    source_path = repository_path(args.source)
    output_path = repository_path(args.output)
    manifest_path = repository_path(args.manifest_output)

    manifest = prepare_terrain_raster(
        source_path=source_path,
        output_path=output_path,
        target_crs_text=args.target_crs,
        resampling_name=args.resampling,
    )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()