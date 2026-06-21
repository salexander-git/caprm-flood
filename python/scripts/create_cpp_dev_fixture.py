from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.validate import normalize_bool_series


def repository_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a small deterministic FEMA C++ development fixture."
    )
    parser.add_argument(
        "--baseline-input",
        default="outputs/baseline/python_fema_membership.csv",
    )
    parser.add_argument(
        "--properties-input",
        default="outputs/cpp_input/properties_projected.csv",
    )
    parser.add_argument(
        "--rings-input",
        default="outputs/cpp_input/fema_polygon_rings_joined_sample.csv",
    )
    parser.add_argument(
        "--properties-output",
        default="outputs/cpp_input/properties_projected_dev.csv",
    )
    parser.add_argument(
        "--rings-output",
        default="outputs/cpp_input/fema_polygon_rings_dev.csv",
    )
    parser.add_argument(
        "--max-properties",
        type=int,
        default=25,
    )

    args = parser.parse_args()

    if args.max_properties < 2:
        raise ValueError("--max-properties must be at least 2.")

    baseline_path = repository_path(args.baseline_input)
    properties_path = repository_path(args.properties_input)
    rings_path = repository_path(args.rings_input)
    properties_output = repository_path(args.properties_output)
    rings_output = repository_path(args.rings_output)

    baseline = pd.read_csv(
        baseline_path,
        dtype={"property_id": "string"},
    )
    properties = pd.read_csv(
        properties_path,
        dtype={"property_id": "string"},
    )

    require_columns(
        baseline,
        {
            "property_id",
            "is_sfha",
            "matched_fema_polygon",
            "fema_feature_index",
        },
        "Python baseline",
    )

    require_columns(
        properties,
        {
            "property_id",
            "projected_x",
            "projected_y",
        },
        "Projected properties",
    )

    baseline["property_id"] = baseline["property_id"].str.strip()
    properties["property_id"] = properties["property_id"].str.strip()

    if baseline["property_id"].isna().any():
        raise ValueError("Python baseline contains missing property IDs.")

    if properties["property_id"].isna().any():
        raise ValueError("Projected properties contain missing property IDs.")

    if baseline["property_id"].duplicated().any():
        duplicates = baseline.loc[
            baseline["property_id"].duplicated(keep=False),
            "property_id",
        ].unique()

        raise ValueError(
            "Python baseline contains duplicate property IDs: "
            f"{duplicates[:10].tolist()}"
        )

    if properties["property_id"].duplicated().any():
        duplicates = properties.loc[
            properties["property_id"].duplicated(keep=False),
            "property_id",
        ].unique()

        raise ValueError(
            "Projected properties contain duplicate property IDs: "
            f"{duplicates[:10].tolist()}"
        )

    baseline["is_sfha_normalized"] = normalize_bool_series(
        baseline["is_sfha"],
        "is_sfha",
    )

    baseline["matched_fema_polygon_normalized"] = normalize_bool_series(
        baseline["matched_fema_polygon"],
        "matched_fema_polygon",
    )

    eligible = baseline[
        baseline["matched_fema_polygon_normalized"]
        & baseline["fema_feature_index"].notna()
    ].copy()

    sfha_target = args.max_properties // 2
    non_sfha_target = args.max_properties - sfha_target

    sfha_rows = eligible[
        eligible["is_sfha_normalized"]
    ].head(sfha_target)

    non_sfha_rows = eligible[
        ~eligible["is_sfha_normalized"]
    ].head(non_sfha_target)

    dev_baseline = pd.concat(
        [sfha_rows, non_sfha_rows],
        ignore_index=True,
    )

    if len(dev_baseline) != args.max_properties:
        raise RuntimeError(
            f"Requested {args.max_properties} properties but only selected "
            f"{len(dev_baseline)} with the required SFHA balance."
        )

    dev_property_ids = dev_baseline["property_id"].tolist()
    dev_feature_indices = sorted(
        dev_baseline["fema_feature_index"]
        .astype(int)
        .unique()
        .tolist()
    )

    dev_properties = properties[
        properties["property_id"].isin(dev_property_ids)
    ].copy()

    missing_property_ids = sorted(
        set(dev_property_ids)
        - set(dev_properties["property_id"])
    )

    if missing_property_ids:
        raise RuntimeError(
            "Selected baseline properties are missing from the projected "
            f"property fixture: {missing_property_ids[:10]}"
        )

    property_order = {
        property_id: index
        for index, property_id in enumerate(dev_property_ids)
    }

    dev_properties["__order"] = (
        dev_properties["property_id"].map(property_order)
    )

    dev_properties = (
        dev_properties
        .sort_values("__order", kind="stable")
        .drop(columns=["__order"])
    )

    properties_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    dev_properties.to_csv(properties_output, index=False)

    ring_chunks: list[pd.DataFrame] = []

    for chunk in pd.read_csv(
        rings_path,
        chunksize=250_000,
    ):
        require_columns(
            chunk,
            {
                "fema_feature_index",
                "part_index",
                "ring_index",
                "vertex_index",
                "x",
                "y",
            },
            "FEMA ring fixture",
        )

        keep = (
            chunk["fema_feature_index"]
            .astype(int)
            .isin(dev_feature_indices)
        )

        if keep.any():
            ring_chunks.append(chunk.loc[keep].copy())

    if not ring_chunks:
        raise RuntimeError(
            "No FEMA ring rows matched the selected feature indices."
        )

    dev_rings = pd.concat(
        ring_chunks,
        ignore_index=True,
    )

    exported_feature_indices = set(
        dev_rings["fema_feature_index"]
        .astype(int)
        .unique()
    )

    missing_feature_indices = sorted(
        set(dev_feature_indices) - exported_feature_indices
    )

    if missing_feature_indices:
        raise RuntimeError(
            "The ring input did not contain every selected FEMA feature: "
            f"{missing_feature_indices}"
        )

    dev_rings = dev_rings.sort_values(
        [
            "fema_feature_index",
            "part_index",
            "ring_index",
            "vertex_index",
        ],
        kind="stable",
    )

    rings_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    dev_rings.to_csv(rings_output, index=False)

    print(f"Selected properties: {len(dev_properties)}")
    print(
        "SFHA properties: "
        f"{int(dev_baseline['is_sfha_normalized'].sum())}"
    )
    print(
        "Non-SFHA properties: "
        f"{int((~dev_baseline['is_sfha_normalized']).sum())}"
    )
    print(f"Selected FEMA features: {len(dev_feature_indices)}")
    print(f"FEMA feature indices: {dev_feature_indices}")
    print(f"Ring vertices: {len(dev_rings)}")
    print(f"Wrote {properties_output}")
    print(f"Wrote {rings_output}")


if __name__ == "__main__":
    main()