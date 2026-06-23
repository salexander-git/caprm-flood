from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = REPOSITORY_ROOT / "python"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from caprm.ingest import (  # noqa: E402
    build_nested_property_sample,
    fetch_property_points_with_metadata,
    load_yaml,
    prepare_property_cache,
    repository_path,
)


DEFAULT_CONFIG_PATH = (
    REPOSITORY_ROOT / "configs" / "monroe_fema_spike.yaml"
)
DEFAULT_REGRESSION_CACHE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "monroe_property_points_sample.geojson"
)
DEFAULT_RECORD_COUNT = 10_000


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def default_output_path(record_count: int) -> Path:
    return (
        REPOSITORY_ROOT
        / "data"
        / "processed"
        / f"monroe_property_points_sample_{record_count}.geojson"
    )


def default_manifest_path(record_count: int) -> Path:
    return (
        REPOSITORY_ROOT
        / "outputs"
        / "validation"
        / f"property_cache_{record_count}_manifest.json"
    )


def write_geojson_atomic(
    properties: gpd.GeoDataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

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


def write_json_atomic(
    payload: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output_path.with_name(
        f"{output_path.stem}.tmp{output_path.suffix}"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    temporary_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    temporary_path.replace(output_path)


def ensure_output_is_safe(
    output_path: Path,
    regression_cache_path: Path,
    overwrite: bool,
) -> None:
    if output_path.resolve() == regression_cache_path.resolve():
        raise ValueError(
            "The workload output must not overwrite the existing "
            "1,000-property regression cache."
        )

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Property workload already exists: {output_path}\n"
            "Rerun with --overwrite only when replacement is intended."
        )


def coordinate_overlap_summary(
    regression: gpd.GeoDataFrame,
    remote: gpd.GeoDataFrame,
    tolerance_degrees: float,
) -> dict[str, Any]:
    if tolerance_degrees < 0.0:
        raise ValueError(
            "coordinate tolerance must be nonnegative."
        )

    regression_cache = prepare_property_cache(regression)
    remote_cache = prepare_property_cache(
        remote,
        default_cache_origin="arcgis_object_id_ordered",
    )

    joined = regression_cache[
        ["property_id", "latitude", "longitude"]
    ].merge(
        remote_cache[
            ["property_id", "latitude", "longitude"]
        ],
        on="property_id",
        how="inner",
        suffixes=("_regression", "_remote"),
        validate="one_to_one",
    )

    if joined.empty:
        return {
            "regression_ids_found_in_remote_selection": 0,
            "coordinate_tolerance_degrees": tolerance_degrees,
            "coordinate_matches_within_tolerance": 0,
            "coordinate_mismatches": 0,
            "max_absolute_latitude_difference_degrees": None,
            "max_absolute_longitude_difference_degrees": None,
        }

    latitude_difference = (
        joined["latitude_regression"]
        - joined["latitude_remote"]
    ).abs()
    longitude_difference = (
        joined["longitude_regression"]
        - joined["longitude_remote"]
    ).abs()

    within_tolerance = (
        latitude_difference <= tolerance_degrees
    ) & (
        longitude_difference <= tolerance_degrees
    )

    return {
        "regression_ids_found_in_remote_selection": int(len(joined)),
        "coordinate_tolerance_degrees": tolerance_degrees,
        "coordinate_matches_within_tolerance": int(
            within_tolerance.sum()
        ),
        "coordinate_mismatches": int(
            (~within_tolerance).sum()
        ),
        "max_absolute_latitude_difference_degrees": float(
            latitude_difference.max()
        ),
        "max_absolute_longitude_difference_degrees": float(
            longitude_difference.max()
        ),
    }


def validate_workload_contract(
    workload: gpd.GeoDataFrame,
    regression: gpd.GeoDataFrame,
    target_count: int,
) -> dict[str, Any]:
    prepared_workload = prepare_property_cache(workload)
    prepared_regression = prepare_property_cache(regression)

    if len(prepared_workload) != target_count:
        raise RuntimeError(
            f"Expected {target_count} workload rows, but found "
            f"{len(prepared_workload)}."
        )

    unique_property_ids = int(
        prepared_workload["property_id"].nunique()
    )

    if unique_property_ids != target_count:
        raise RuntimeError(
            f"Expected {target_count} unique property IDs, but found "
            f"{unique_property_ids}."
        )

    expected_order = list(range(target_count))
    actual_order = (
        prepared_workload["sample_order"]
        .astype(int)
        .tolist()
    )

    if actual_order != expected_order:
        raise RuntimeError(
            "Workload sample_order is not consecutive from 0 through "
            f"{target_count - 1}."
        )

    regression_count = len(prepared_regression)
    workload_prefix = prepared_workload.iloc[
        :regression_count
    ].reset_index(drop=True)

    regression_ids = (
        prepared_regression["property_id"]
        .astype(str)
        .tolist()
    )
    prefix_ids = (
        workload_prefix["property_id"]
        .astype(str)
        .tolist()
    )

    regression_prefix_preserved = prefix_ids == regression_ids

    if not regression_prefix_preserved:
        raise RuntimeError(
            "The workload does not preserve the regression fixture as "
            "its ordered prefix."
        )

    prefix_latitude_equal = (
        workload_prefix.geometry.y.to_numpy()
        == prepared_regression.geometry.y.to_numpy()
    ).all()
    prefix_longitude_equal = (
        workload_prefix.geometry.x.to_numpy()
        == prepared_regression.geometry.x.to_numpy()
    ).all()
    regression_coordinates_preserved = bool(
        prefix_latitude_equal and prefix_longitude_equal
    )

    if not regression_coordinates_preserved:
        raise RuntimeError(
            "The workload changed coordinates in the regression prefix."
        )

    regression_id_set = set(regression_ids)
    workload_id_set = set(
        prepared_workload["property_id"].astype(str)
    )
    regression_ids_present = len(
        regression_id_set & workload_id_set
    )
    regression_is_subset = (
        regression_ids_present == regression_count
    )

    if not regression_is_subset:
        raise RuntimeError(
            "The workload does not contain every regression property ID."
        )

    return {
        "row_count": int(len(prepared_workload)),
        "unique_property_ids": unique_property_ids,
        "cache_crs": str(prepared_workload.crs),
        "geometry_type_counts": {
            str(key): int(value)
            for key, value in prepared_workload.geometry.geom_type
            .value_counts()
            .items()
        },
        "first_sample_order": int(
            prepared_workload["sample_order"].min()
        ),
        "last_sample_order": int(
            prepared_workload["sample_order"].max()
        ),
        "regression_property_count": int(regression_count),
        "regression_unique_property_ids": int(
            prepared_regression["property_id"].nunique()
        ),
        "regression_ids_present_in_target": int(
            regression_ids_present
        ),
        "regression_is_subset": regression_is_subset,
        "regression_prefix_preserved": (
            regression_prefix_preserved
        ),
        "regression_coordinates_preserved": (
            regression_coordinates_preserved
        ),
        "extension_property_count": int(
            len(prepared_workload) - regression_count
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a deterministic CAPRM-Flood property workload that "
            "preserves the validated 1,000-property regression fixture "
            "and appends unique ArcGIS properties selected by ascending "
            "source object ID."
        )
    )

    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the CAPRM-Flood YAML configuration.",
    )

    parser.add_argument(
        "--regression-cache",
        default=str(DEFAULT_REGRESSION_CACHE_PATH),
        help="Path to the immutable 1,000-property regression cache.",
    )

    parser.add_argument(
        "--record-count",
        type=int,
        default=DEFAULT_RECORD_COUNT,
        help="Total number of properties in the new workload.",
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output GeoJSON path. Defaults to a record-count-specific "
            "path under data/processed/."
        ),
    )

    parser.add_argument(
        "--manifest-output",
        default=None,
        help=(
            "Output manifest path. Defaults to a record-count-specific "
            "path under outputs/validation/."
        ),
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="HTTP timeout for each ArcGIS request.",
    )

    parser.add_argument(
        "--coordinate-tolerance-degrees",
        type=float,
        default=1e-9,
        help=(
            "Tolerance used only when comparing coordinates for IDs "
            "that appear in both the regression cache and current "
            "remote selection."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing workload and manifest.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.record_count <= 0:
        raise ValueError("--record-count must be positive.")

    config_path = repository_path(args.config)
    regression_cache_path = repository_path(
        args.regression_cache
    )
    output_path = repository_path(
        args.output or default_output_path(args.record_count)
    )
    manifest_path = repository_path(
        args.manifest_output
        or default_manifest_path(args.record_count)
    )

    ensure_output_is_safe(
        output_path=output_path,
        regression_cache_path=regression_cache_path,
        overwrite=args.overwrite,
    )

    if manifest_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Property workload manifest already exists: {manifest_path}\n"
            "Rerun with --overwrite only when replacement is intended."
        )

    if not regression_cache_path.exists():
        raise FileNotFoundError(
            "Regression cache does not exist: "
            f"{regression_cache_path}"
        )

    config = load_yaml(config_path)
    property_config = config.get("property_points")

    if not isinstance(property_config, dict):
        raise ValueError(
            "Configuration is missing property_points."
        )

    canonical_id_field = property_config.get(
        "canonical_id_field"
    )

    if not canonical_id_field:
        raise ValueError(
            "property_points.canonical_id_field must be configured "
            "before creating a larger property workload."
        )

    regression = gpd.read_file(regression_cache_path)
    regression = prepare_property_cache(regression)

    if args.record_count < len(regression):
        raise ValueError(
            f"--record-count {args.record_count} is smaller than the "
            f"regression fixture count {len(regression)}."
        )

    remote, fetch_metadata = fetch_property_points_with_metadata(
        config,
        timeout_seconds=args.timeout_seconds,
        sample_limit_override=args.record_count,
    )
    remote_cache = prepare_property_cache(
        remote,
        default_cache_origin="arcgis_object_id_ordered",
    )

    overlap_summary = coordinate_overlap_summary(
        regression=regression,
        remote=remote_cache,
        tolerance_degrees=args.coordinate_tolerance_degrees,
    )

    workload = build_nested_property_sample(
        regression_properties=regression,
        remote_properties=remote_cache,
        target_count=args.record_count,
    )

    contract = validate_workload_contract(
        workload=workload,
        regression=regression,
        target_count=args.record_count,
    )

    write_geojson_atomic(workload, output_path)

    regression_ids = set(
        regression["property_id"].astype(str)
    )
    remote_ids = set(
        remote_cache["property_id"].astype(str)
    )

    manifest = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "cache_origin": (
            "nested_regression_plus_arcgis_object_id_extension"
        ),
        "stable_ordering_rule": (
            "Preserve the validated regression fixture in its existing "
            "sample_order, then append the first required unique ArcGIS "
            "records selected by ascending source object ID after "
            "excluding regression property IDs."
        ),
        "config": display_path(config_path),
        "config_sha256": calculate_sha256(config_path),
        "target_property_count": int(args.record_count),
        "canonical_property_id_field": str(
            canonical_id_field
        ),
        "property_cache": display_path(output_path),
        "property_cache_sha256": calculate_sha256(output_path),
        "property_cache_size_bytes": int(
            output_path.stat().st_size
        ),
        **contract,
        "regression_cache": display_path(
            regression_cache_path
        ),
        "regression_cache_sha256": calculate_sha256(
            regression_cache_path
        ),
        "remote_candidate_count": int(len(remote_cache)),
        "remote_overlap_with_regression_count": int(
            len(remote_ids & regression_ids)
        ),
        "source": fetch_metadata,
        "regression_remote_coordinate_comparison": (
            overlap_summary
        ),
    }

    write_json_atomic(manifest, manifest_path)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
