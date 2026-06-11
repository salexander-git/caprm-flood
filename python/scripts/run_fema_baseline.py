from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def first_existing_field(gdf: gpd.GeoDataFrame, candidates: list[str], label: str) -> str | None:
    for field in candidates:
        if field in gdf.columns:
            return field
    print(f"Warning: no {label} field found from candidates: {candidates}")
    return None


def fetch_nys_parcel_centroids(config: dict[str, Any]) -> gpd.GeoDataFrame:
    pp = config["property_points"]
    params = {
        "where": f"{pp['county_field']} = '{pp['county_value']}'",
        "outFields": "*",
        "f": "geojson",
        "returnGeometry": "true",
        "resultRecordCount": pp.get("sample_limit", 1000),
    }

    print(f"Fetching property points from {pp['source_name']}...")
    response = requests.get(pp["source_url"], params=params, timeout=120)
    response.raise_for_status()

    payload = response.json()
    if "features" not in payload:
        raise RuntimeError(f"Unexpected parcel service response: {json.dumps(payload)[:500]}")

    gdf = gpd.GeoDataFrame.from_features(payload["features"], crs="EPSG:4326")

    # ArcGIS GeoJSON responses are usually lon/lat EPSG:4326 even if service storage CRS differs.
    if gdf.empty:
        raise RuntimeError("No property points returned. Check county filter and service query.")

    id_field = first_existing_field(gdf, pp["id_field_candidates"], "property id")
    if id_field is None:
        gdf["property_id"] = [f"P{i:06d}" for i in range(len(gdf))]
    else:
        gdf["property_id"] = gdf[id_field].astype(str)

    return gdf


def load_fema_polygons(config: dict[str, Any]) -> gpd.GeoDataFrame:
    fp = config["fema_flood_polygons"]
    path = Path(fp["manual_input_path"])

    if not path.exists():
        raise FileNotFoundError(
            f"FEMA polygon file not found: {path}\n"
            "Download/extract FEMA NFHL data for Monroe County or New York, then update "
            "configs/monroe_fema_spike.yaml -> fema_flood_polygons.manual_input_path."
        )

    print(f"Loading FEMA polygons from {path}...")
    gdf = gpd.read_file(path)

    if gdf.empty:
        raise RuntimeError("FEMA polygon layer is empty.")

    if gdf.crs is None:
        raise RuntimeError("FEMA polygon layer has no CRS. Define CRS before continuing.")

    return gdf


def normalize_inputs(
    properties: gpd.GeoDataFrame,
    fema: gpd.GeoDataFrame,
    project_crs: str,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    print(f"Property CRS before transform: {properties.crs}")
    print(f"FEMA CRS before transform: {fema.crs}")
    print(f"Project CRS: {project_crs}")

    properties_projected = properties.to_crs(project_crs)
    fema_projected = fema.to_crs(project_crs)

    properties_projected["longitude"] = properties.geometry.x
    properties_projected["latitude"] = properties.geometry.y
    properties_projected["projected_x"] = properties_projected.geometry.x
    properties_projected["projected_y"] = properties_projected.geometry.y

    return properties_projected, fema_projected


def run_point_in_polygon(
    properties: gpd.GeoDataFrame,
    fema: gpd.GeoDataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    fp = config["fema_flood_polygons"]

    zone_field = first_existing_field(fema, fp["zone_field_candidates"], "FEMA zone")
    sfha_field = first_existing_field(fema, fp["sfha_field_candidates"], "SFHA flag")
    geom_id_field = first_existing_field(fema, fp["id_field_candidates"], "FEMA geometry id")

    keep_fields = ["geometry"]
    for field in [zone_field, sfha_field, geom_id_field]:
        if field is not None and field not in keep_fields:
            keep_fields.append(field)

    fema_join = fema[keep_fields].copy()

    print("Running GeoPandas point-in-polygon spatial join...")
    joined = gpd.sjoin(
        properties,
        fema_join,
        how="left",
        predicate="within",
    )

    out = pd.DataFrame()
    out["property_id"] = joined["property_id"]
    out["latitude"] = joined["latitude"]
    out["longitude"] = joined["longitude"]
    out["projected_x"] = joined["projected_x"]
    out["projected_y"] = joined["projected_y"]

    out["fema_zone"] = joined[zone_field] if zone_field else None
    out["sfha_flag"] = joined[sfha_field] if sfha_field else None
    out["source_geometry_id"] = joined[geom_id_field] if geom_id_field else joined.get("index_right")
    out["python_result"] = joined["index_right"].notna()

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CAPRM-Flood FEMA Python baseline.")
    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
        help="Path to YAML config.",
    )
    args = parser.parse_args()

    config = load_yaml(Path(args.config))
    project_crs = config["project"]["project_crs"]

    properties = fetch_nys_parcel_centroids(config)
    fema = load_fema_polygons(config)
    properties_projected, fema_projected = normalize_inputs(properties, fema, project_crs)

    output = run_point_in_polygon(properties_projected, fema_projected, config)

    output_path = Path(config["outputs"]["python_baseline_csv"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)

    print(f"Wrote {len(output)} rows to {output_path}")


if __name__ == "__main__":
    main()