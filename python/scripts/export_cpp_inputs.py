from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
import yaml
from shapely.geometry import Polygon, MultiPolygon, box

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def export_projected_fema_polygon_rings(
    fema: gpd.GeoDataFrame,
    config: dict[str, Any],
    project_crs: str,
    output_path: Path,
) -> None:
    fp = config["fema_flood_polygons"]

    zone_field = first_existing_field(fema, fp["zone_field_candidates"], "FEMA zone")
    sfha_field = first_existing_field(fema, fp["sfha_field_candidates"], "SFHA flag")
    geom_id_field = first_existing_field(fema, fp["id_field_candidates"], "FEMA geometry id")

    projected = fema.to_crs(project_crs)

    rows = []

    for polygon_index, row in projected.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "Polygon":
            polygons = [geom]
        elif geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        else:
            print(f"Skipping unsupported geometry type: {geom.geom_type}")
            continue

        fema_zone = row[zone_field] if zone_field else None
        sfha_flag = row[sfha_field] if sfha_field else None
        source_geometry_id = row[geom_id_field] if geom_id_field else polygon_index

        for part_index, polygon in enumerate(polygons):
            rings = [polygon.exterior] + list(polygon.interiors)

            for ring_index, ring in enumerate(rings):
                for vertex_index, (x, y) in enumerate(ring.coords):
                    rows.append(
                        {
                            "polygon_index": polygon_index,
                            "part_index": part_index,
                            "ring_index": ring_index,
                            "vertex_index": vertex_index,
                            "x": x,
                            "y": y,
                            "fema_zone": fema_zone,
                            "sfha_flag": sfha_flag,
                            "source_geometry_id": source_geometry_id,
                        }
                    )

    out = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    print(f"Wrote projected FEMA polygon rings to {output_path}")
    print(f"Wrote {len(out)} ring vertices")

def export_sampled_fema_polygon_rings(
    properties: gpd.GeoDataFrame,
    fema: gpd.GeoDataFrame,
    config: dict[str, Any],
    project_crs: str,
    output_path: Path,
    buffer_meters: float = 1000.0,
) -> None:
    fp = config["fema_flood_polygons"]

    zone_field = first_existing_field(fema, fp["zone_field_candidates"], "FEMA zone")
    sfha_field = first_existing_field(fema, fp["sfha_field_candidates"], "SFHA flag")
    geom_id_field = first_existing_field(fema, fp["id_field_candidates"], "FEMA geometry id")

    properties_projected = properties.to_crs(project_crs)
    fema_projected = fema.to_crs(project_crs)

    minx, miny, maxx, maxy = properties_projected.total_bounds
    buffered_bbox = box(
        minx - buffer_meters,
        miny - buffer_meters,
        maxx + buffer_meters,
        maxy + buffer_meters,
    )

    fema_subset = fema_projected[fema_projected.intersects(buffered_bbox)].copy()

    print(
        f"Selected {len(fema_subset)} FEMA polygons intersecting "
        f"sample property bounding box + {buffer_meters}m buffer"
    )

    rows = []

    for polygon_index, row in fema_subset.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "Polygon":
            polygons = [geom]
        elif geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        else:
            print(f"Skipping unsupported geometry type: {geom.geom_type}")
            continue

        fema_zone = row[zone_field] if zone_field else None
        sfha_flag = row[sfha_field] if sfha_field else None
        source_geometry_id = row[geom_id_field] if geom_id_field else polygon_index

        for part_index, polygon in enumerate(polygons):
            rings = [polygon.exterior] + list(polygon.interiors)

            for ring_index, ring in enumerate(rings):
                for vertex_index, (x, y) in enumerate(ring.coords):
                    rows.append(
                        {
                            "polygon_index": polygon_index,
                            "part_index": part_index,
                            "ring_index": ring_index,
                            "vertex_index": vertex_index,
                            "x": x,
                            "y": y,
                            "fema_zone": fema_zone,
                            "sfha_flag": sfha_flag,
                            "source_geometry_id": source_geometry_id,
                        }
                    )

    out = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    print(f"Wrote sampled projected FEMA polygon rings to {output_path}")
    print(f"Wrote {len(out)} sampled ring vertices")

def export_joined_sample_fema_polygon_rings(
    fema: gpd.GeoDataFrame,
    config: dict[str, Any],
    project_crs: str,
    baseline_path: Path,
    output_path: Path,
) -> None:
    fp = config["fema_flood_polygons"]

    zone_field = first_existing_field(fema, fp["zone_field_candidates"], "FEMA zone")
    sfha_field = first_existing_field(fema, fp["sfha_field_candidates"], "SFHA flag")
    geom_id_field = first_existing_field(fema, fp["id_field_candidates"], "FEMA geometry id")

    baseline = pd.read_csv(baseline_path)

    if "fema_feature_index" not in baseline.columns:
        raise RuntimeError(
            f"Baseline file {baseline_path} does not contain fema_feature_index."
        )

    feature_indices = (
        baseline["fema_feature_index"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    projected = fema.to_crs(project_crs)
    fema_subset = projected.loc[feature_indices].copy()

    print(
        f"Selected {len(fema_subset)} FEMA polygons matched by Python baseline "
        f"from {len(feature_indices)} unique fema_feature_index values"
    )

    rows = []

    for polygon_index, row in fema_subset.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "Polygon":
            polygons = [geom]
        elif geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        else:
            print(f"Skipping unsupported geometry type: {geom.geom_type}")
            continue

        fema_zone = row[zone_field] if zone_field else None
        sfha_flag = row[sfha_field] if sfha_field else None
        source_geometry_id = row[geom_id_field] if geom_id_field else polygon_index

        for part_index, polygon in enumerate(polygons):
            rings = [polygon.exterior] + list(polygon.interiors)

            for ring_index, ring in enumerate(rings):
                for vertex_index, (x, y) in enumerate(ring.coords):
                    rows.append(
                        {
                            "fema_feature_index": polygon_index,
                            "part_index": part_index,
                            "ring_index": ring_index,
                            "vertex_index": vertex_index,
                            "x": x,
                            "y": y,
                            "fema_zone": fema_zone,
                            "sfha_flag": sfha_flag,
                            "source_geometry_id": source_geometry_id,
                        }
                    )

    out = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    print(f"Wrote joined-sample FEMA polygon rings to {output_path}")
    print(f"Wrote {len(out)} joined-sample ring vertices")

def first_existing_field(
    gdf: gpd.GeoDataFrame,
    candidates: list[str],
    label: str,
) -> str | None:
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
        raise RuntimeError(
            f"Unexpected parcel service response: {json.dumps(payload)[:500]}"
        )

    gdf = gpd.GeoDataFrame.from_features(payload["features"], crs="EPSG:4326")

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


def export_projected_properties(
    properties: gpd.GeoDataFrame,
    project_crs: str,
    output_path: Path,
) -> None:
    projected = properties.to_crs(project_crs)

    out = pd.DataFrame(
        {
            "property_id": projected["property_id"],
            "projected_x": projected.geometry.x,
            "projected_y": projected.geometry.y,
            "longitude": properties.geometry.x,
            "latitude": properties.geometry.y,
        }
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    print(f"Wrote projected property points to {output_path}")


def export_projected_fema_polygons(
    fema: gpd.GeoDataFrame,
    config: dict[str, Any],
    project_crs: str,
    output_path: Path,
) -> None:
    fp = config["fema_flood_polygons"]

    zone_field = first_existing_field(fema, fp["zone_field_candidates"], "FEMA zone")
    sfha_field = first_existing_field(fema, fp["sfha_field_candidates"], "SFHA flag")
    geom_id_field = first_existing_field(fema, fp["id_field_candidates"], "FEMA geometry id")

    projected = fema.to_crs(project_crs)

    keep_fields = ["geometry"]
    for field in [zone_field, sfha_field, geom_id_field]:
        if field is not None and field not in keep_fields:
            keep_fields.append(field)

    projected = projected[keep_fields].copy()

    if zone_field and zone_field != "fema_zone":
        projected["fema_zone"] = projected[zone_field]

    if sfha_field and sfha_field != "sfha_flag":
        projected["sfha_flag"] = projected[sfha_field]

    if geom_id_field and geom_id_field != "source_geometry_id":
        projected["source_geometry_id"] = projected[geom_id_field]

    final_fields = ["fema_zone", "sfha_flag", "source_geometry_id", "geometry"]
    projected = projected[[field for field in final_fields if field in projected.columns]]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    projected.to_file(output_path, driver="GeoJSON")

    print(f"Wrote projected FEMA polygons to {output_path}")



def main() -> None:
    parser = argparse.ArgumentParser(description="Export C++ input fixtures for CAPRM-Flood.")
    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
        help="Path to YAML config.",
    )
    parser.add_argument(
        "--properties-output",
        default="outputs/cpp_input/properties_projected.csv",
        help="Output CSV path for projected property points.",
    )
    parser.add_argument(
        "--fema-output",
        default="outputs/cpp_input/fema_polygons_projected.geojson",
        help="Output GeoJSON path for projected FEMA polygons.",
    )
    parser.add_argument(
        "--fema-rings-output",
        default="outputs/cpp_input/fema_polygon_rings.csv",
        help="Output CSV path for projected FEMA polygon rings.",
    )
    
    parser.add_argument(
        "--fema-sample-rings-output",
        default="outputs/cpp_input/fema_polygon_rings_sample.csv",
        help="Output CSV path for sampled projected FEMA polygon rings.",
    )

    parser.add_argument(
        "--bbox-buffer-meters",
        type=float,
        default=1000.0,
        help="Buffer around sampled property bounding box for selecting FEMA polygons.",
    )
    
    parser.add_argument(
        "--baseline-input",
        default="outputs/baseline/python_fema_membership.csv",
        help="Python baseline CSV containing fema_feature_index values.",
    )

    parser.add_argument(
        "--fema-joined-rings-output",
        default="outputs/cpp_input/fema_polygon_rings_joined_sample.csv",
        help="Output CSV path for FEMA polygon rings matched by the Python baseline.",
    )

    args = parser.parse_args()

    config = load_yaml(Path(args.config))
    project_crs = config["project"]["project_crs"]

    properties = fetch_nys_parcel_centroids(config)
    fema = load_fema_polygons(config)

    print(f"Property CRS before transform: {properties.crs}")
    print(f"FEMA CRS before transform: {fema.crs}")
    print(f"Project CRS: {project_crs}")

    export_projected_properties(
        properties=properties,
        project_crs=project_crs,
        output_path=Path(args.properties_output),
    )

    export_projected_fema_polygons(
        fema=fema,
        config=config,
        project_crs=project_crs,
        output_path=Path(args.fema_output),
    )
    
    export_projected_fema_polygon_rings(
        fema=fema,
        config=config,
        project_crs=project_crs,
        output_path=Path(args.fema_rings_output),
    )
    
    export_sampled_fema_polygon_rings(
        properties=properties,
        fema=fema,
        config=config,
        project_crs=project_crs,
        output_path=Path(args.fema_sample_rings_output),
        buffer_meters=args.bbox_buffer_meters,
    )
    
    export_joined_sample_fema_polygon_rings(
        fema=fema,
        config=config,
        project_crs=project_crs,
        baseline_path=Path(args.baseline_input),
        output_path=Path(args.fema_joined_rings_output),
    )


if __name__ == "__main__":
    main()