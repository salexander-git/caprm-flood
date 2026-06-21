from __future__ import annotations

import geopandas as gpd
from pyproj import CRS


GEOGRAPHIC_CRS = "EPSG:4326"


def normalize_inputs(
    properties: gpd.GeoDataFrame,
    fema: gpd.GeoDataFrame,
    project_crs: str,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    if properties.crs is None:
        raise ValueError("Property dataset has no CRS.")

    if fema.crs is None:
        raise ValueError("FEMA dataset has no CRS.")

    target_crs = CRS.from_user_input(project_crs)

    if not target_crs.is_projected:
        raise ValueError(
            f"Project CRS must be projected: {project_crs}"
        )

    geographic_properties = properties.to_crs(
        GEOGRAPHIC_CRS
    )

    projected_properties = properties.to_crs(
        target_crs
    ).copy()

    projected_fema = fema.to_crs(
        target_crs
    ).copy()

    projected_properties["longitude"] = (
        geographic_properties.geometry.x.to_numpy()
    )
    projected_properties["latitude"] = (
        geographic_properties.geometry.y.to_numpy()
    )
    projected_properties["projected_x"] = (
        projected_properties.geometry.x
    )
    projected_properties["projected_y"] = (
        projected_properties.geometry.y
    )

    if projected_properties.geometry.isna().any():
        raise ValueError(
            "Projected properties contain null geometries."
        )

    if projected_fema.geometry.isna().any():
        raise ValueError(
            "Projected FEMA data contains null geometries."
        )

    return (
        projected_properties,
        projected_fema,
    )