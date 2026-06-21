from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = (
    REPOSITORY_ROOT / "configs" / "monroe_fema_spike.yaml"
)

DEFAULT_BASELINE_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "baseline"
    / "python_fema_membership.csv"
)

DEFAULT_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "validation"
    / "property_cache_manifest.json"
)


def repository_path(value: str | Path) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return REPOSITORY_ROOT / path


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as input_file:
        config = yaml.safe_load(input_file)

    if not isinstance(config, dict):
        raise ValueError(
            f"Expected a YAML mapping at the root of {path}."
        )

    return config


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def validate_baseline(dataframe: pd.DataFrame) -> pd.DataFrame:
    required_columns = {
        "property_id",
        "latitude",
        "longitude",
    }

    missing_columns = sorted(
        required_columns - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Baseline is missing required columns: {missing_columns}"
        )

    prepared = dataframe[
        [
            "property_id",
            "latitude",
            "longitude",
        ]
    ].copy()

    prepared["property_id"] = (
        prepared["property_id"]
        .astype("string")
        .str.strip()
    )

    missing_ids = (
        prepared["property_id"].isna()
        | prepared["property_id"].eq("")
    )

    if missing_ids.any():
        rows = prepared.index[missing_ids].tolist()[:10]
        raise ValueError(
            f"Baseline contains missing property IDs at rows: {rows}"
        )

    duplicates = prepared.loc[
        prepared["property_id"].duplicated(keep=False),
        "property_id",
    ]

    if not duplicates.empty:
        raise ValueError(
            "Baseline contains duplicate property IDs: "
            f"{duplicates.unique()[:10].tolist()}"
        )

    prepared["latitude"] = pd.to_numeric(
        prepared["latitude"],
        errors="raise",
    )

    prepared["longitude"] = pd.to_numeric(
        prepared["longitude"],
        errors="raise",
    )

    missing_coordinates = prepared[
        ["latitude", "longitude"]
    ].isna().any(axis=1)

    if missing_coordinates.any():
        rows = prepared.index[
            missing_coordinates
        ].tolist()[:10]

        raise ValueError(
            f"Baseline contains missing coordinates at rows: {rows}"
        )

    invalid_latitude = ~prepared["latitude"].between(
        -90.0,
        90.0,
    )

    invalid_longitude = ~prepared["longitude"].between(
        -180.0,
        180.0,
    )

    if invalid_latitude.any() or invalid_longitude.any():
        raise ValueError(
            "Baseline contains coordinates outside valid longitude/"
            "latitude ranges."
        )

    prepared.insert(
        0,
        "sample_order",
        range(len(prepared)),
    )

    prepared["cache_origin"] = (
        "validated_milestone_1_baseline"
    )

    return prepared


def build_property_cache(
    baseline: pd.DataFrame,
) -> gpd.GeoDataFrame:
    properties = gpd.GeoDataFrame(
        baseline.copy(),
        geometry=gpd.points_from_xy(
            baseline["longitude"],
            baseline["latitude"],
        ),
        crs="EPSG:4326",
    )

    if properties.geometry.isna().any():
        raise RuntimeError(
            "Property cache contains null geometries."
        )

    if properties.geometry.is_empty.any():
        raise RuntimeError(
            "Property cache contains empty geometries."
        )

    if (~properties.geometry.is_valid).any():
        raise RuntimeError(
            "Property cache contains invalid point geometries."
        )

    return properties


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the validated Milestone 1 property sample as "
            "a deterministic GeoJSON cache."
        )
    )

    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
    )

    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE_PATH),
    )

    parser.add_argument(
        "--manifest-output",
        default=str(DEFAULT_MANIFEST_PATH),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing property cache.",
    )

    args = parser.parse_args()

    config_path = repository_path(args.config)
    baseline_path = repository_path(args.baseline)
    manifest_path = repository_path(
        args.manifest_output
    )

    config = load_yaml(config_path)

    property_config = config.get("property_points")

    if not isinstance(property_config, dict):
        raise ValueError(
            "Configuration is missing property_points."
        )

    configured_output = property_config.get("output_path")

    if not configured_output:
        raise ValueError(
            "property_points.output_path is missing from the "
            "configuration."
        )

    output_path = repository_path(configured_output)

    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Property cache already exists: {output_path}\n"
            "Rerun with --overwrite only when replacement is intended."
        )

    baseline_dataframe = pd.read_csv(
        baseline_path,
        dtype={"property_id": "string"},
    )

    prepared = validate_baseline(
        baseline_dataframe
    )

    properties = build_property_cache(prepared)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        f"{output_path.stem}.tmp{output_path.suffix}"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    properties.to_file(
        temporary_path,
        driver="GeoJSON",
    )

    temporary_path.replace(output_path)

    manifest = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "cache_origin": (
            "validated_milestone_1_baseline"
        ),
        "baseline_input": display_path(
            baseline_path
        ),
        "baseline_sha256": calculate_sha256(
            baseline_path
        ),
        "property_cache": display_path(
            output_path
        ),
        "property_cache_sha256": calculate_sha256(
            output_path
        ),
        "row_count": int(len(properties)),
        "unique_property_ids": int(
            properties["property_id"].nunique()
        ),
        "crs": str(properties.crs),
        "first_sample_order": int(
            properties["sample_order"].min()
        ),
        "last_sample_order": int(
            properties["sample_order"].max()
        ),
    }

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()