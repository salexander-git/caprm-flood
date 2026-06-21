from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG = (
    REPOSITORY_ROOT / "configs" / "monroe_fema_spike.yaml"
)

DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "outputs"
    / "validation"
    / "fema_schema_inventory.json"
)


def repository_path(value: str | Path) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return REPOSITORY_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as input_file:
        config = yaml.safe_load(input_file)

    if not isinstance(config, dict):
        raise ValueError(
            f"Expected a YAML mapping at the root of {path}."
        )

    return config


def summarize_column(series: pd.Series) -> dict[str, Any]:
    nonmissing = series.dropna()

    sample_values = [
        str(value)
        for value in nonmissing.astype(str).drop_duplicates().head(10)
    ]

    return {
        "dtype": str(series.dtype),
        "row_count": int(len(series)),
        "nonmissing_count": int(series.notna().sum()),
        "missing_count": int(series.isna().sum()),
        "unique_nonmissing_count": int(nonmissing.nunique()),
        "duplicate_nonmissing_rows": int(
            nonmissing.duplicated(keep=False).sum()
        ),
        "is_unique_when_nonmissing": bool(
            nonmissing.is_unique
        ),
        "sample_values": sample_values,
    }


def build_inventory(
    fema: gpd.GeoDataFrame,
    id_candidates: list[str],
) -> dict[str, Any]:
    geometry_types = {
        str(key): int(value)
        for key, value in (
            fema.geometry.geom_type
            .value_counts(dropna=False)
            .items()
        )
    }

    id_candidate_summary = {}

    for candidate in id_candidates:
        if candidate in fema.columns:
            id_candidate_summary[candidate] = summarize_column(
                fema[candidate]
            )
        else:
            id_candidate_summary[candidate] = {
                "present": False
            }

    all_column_summary = {
        column: {
            "dtype": str(fema[column].dtype),
            "nonmissing_count": int(fema[column].notna().sum()),
            "unique_nonmissing_count": int(
                fema[column].nunique(dropna=True)
            ),
        }
        for column in fema.columns
        if column != fema.geometry.name
    }

    viable_unique_candidates = [
        candidate
        for candidate, summary in id_candidate_summary.items()
        if summary.get("is_unique_when_nonmissing") is True
        and summary.get("missing_count") == 0
    ]

    return {
        "row_count": int(len(fema)),
        "crs": str(fema.crs),
        "geometry_column": fema.geometry.name,
        "geometry_types": geometry_types,
        "null_geometry_count": int(
            fema.geometry.isna().sum()
        ),
        "empty_geometry_count": int(
            fema.geometry.is_empty.sum()
        ),
        "invalid_geometry_count": int(
            (~fema.geometry.is_valid).sum()
        ),
        "configured_id_candidates": id_candidates,
        "id_candidate_summary": id_candidate_summary,
        "viable_unique_id_candidates": viable_unique_candidates,
        "all_columns": all_column_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect FEMA polygon schema and determine which source "
            "fields can serve as stable feature identifiers."
        )
    )

    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
    )

    args = parser.parse_args()

    config_path = repository_path(args.config)
    output_path = repository_path(args.output)

    config = load_yaml(config_path)
    fema_config = config["fema_flood_polygons"]

    fema_path = repository_path(
        fema_config["manual_input_path"]
    )

    if not fema_path.exists():
        raise FileNotFoundError(
            f"FEMA polygon file does not exist: {fema_path}"
        )

    print(f"Loading FEMA polygons from {fema_path}...")
    fema = gpd.read_file(fema_path)

    inventory = build_inventory(
        fema=fema,
        id_candidates=fema_config.get(
            "id_field_candidates",
            [],
        ),
    )

    inventory["input_file"] = (
        fema_path.resolve()
        .relative_to(REPOSITORY_ROOT)
        .as_posix()
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(inventory, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(
        {
            "row_count": inventory["row_count"],
            "crs": inventory["crs"],
            "geometry_types": inventory["geometry_types"],
            "invalid_geometry_count": (
                inventory["invalid_geometry_count"]
            ),
            "id_candidate_summary": (
                inventory["id_candidate_summary"]
            ),
            "viable_unique_id_candidates": (
                inventory["viable_unique_id_candidates"]
            ),
        },
        indent=2,
    ))

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()