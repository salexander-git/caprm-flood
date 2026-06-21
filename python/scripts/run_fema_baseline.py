from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.baseline import run_fema_point_in_polygon
from caprm.crs import normalize_inputs
from caprm.ingest import (
    load_fema_polygons,
    load_property_points,
    load_yaml,
    repository_path,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the cache-first CAPRM-Flood FEMA Python baseline."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional output override. The configured baseline path "
            "is used by default."
        ),
    )

    parser.add_argument(
        "--refresh-properties",
        action="store_true",
        help=(
            "Explicitly query ArcGIS and replace the property cache. "
            "Without this flag, no remote property request is made."
        ),
    )

    args = parser.parse_args()

    config = load_yaml(args.config)

    properties = load_property_points(
        config,
        refresh=args.refresh_properties,
    )

    fema = load_fema_polygons(config)

    properties_projected, fema_projected = normalize_inputs(
        properties,
        fema,
        config["project"]["project_crs"],
    )

    output = run_fema_point_in_polygon(
        properties_projected,
        fema_projected,
        config,
        predicate="within",
    )

    configured_output = config["outputs"][
        "python_baseline_csv"
    ]

    output_path = repository_path(
        args.output or configured_output
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.to_csv(
        output_path,
        index=False,
    )

    print(f"Wrote {len(output)} rows to {output_path}")
    print(
        "Matched FEMA polygons: "
        f"{int(output['matched_fema_polygon'].sum())}"
    )
    print(
        "SFHA properties: "
        f"{int(output['is_sfha'].sum())}"
    )
    print(
        "Stable FEMA source IDs: "
        f"{output['source_geometry_id'].nunique(dropna=True)}"
    )


if __name__ == "__main__":
    main()