from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.crs import normalize_inputs
from caprm.export import (
    display_path,
    export_fema_rings,
    export_projected_properties,
    select_fema_features,
    write_export_manifest,
)
from caprm.ingest import (
    load_fema_polygons,
    load_property_points,
    load_yaml,
    repository_path,
)


DEFAULT_RING_OUTPUTS = {
    "baseline": (
        "outputs/cpp_input/"
        "fema_polygon_rings_joined_sample.csv"
    ),
    "bbox": (
        "outputs/cpp_input/"
        "fema_polygon_rings_sample.csv"
    ),
    "full": (
        "outputs/cpp_input/"
        "fema_polygon_rings.csv"
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export deterministic CAPRM-Flood C++ property and FEMA "
            "ring inputs. Ring rows are streamed directly to disk."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/monroe_fema_spike.yaml",
    )

    parser.add_argument(
        "--scope",
        choices=["baseline", "bbox", "full"],
        default="baseline",
        help=(
            "baseline exports only FEMA features referenced by the "
            "Python baseline; bbox exports features near the property "
            "sample; full exports every FEMA feature."
        ),
    )

    parser.add_argument(
        "--baseline-input",
        default="outputs/baseline/python_fema_membership.csv",
    )

    parser.add_argument(
        "--properties-output",
        default="outputs/cpp_input/properties_projected.csv",
    )

    parser.add_argument(
        "--rings-output",
        default=None,
        help=(
            "Optional ring CSV override. A scope-specific path is used "
            "when omitted."
        ),
    )

    parser.add_argument(
        "--manifest-output",
        default=(
            "outputs/validation/"
            "cpp_input_export_manifest.json"
        ),
    )

    parser.add_argument(
        "--bbox-buffer-meters",
        type=float,
        default=1000.0,
    )

    parser.add_argument(
        "--allow-full-export",
        action="store_true",
        help=(
            "Explicit confirmation required for full-county export."
        ),
    )

    args = parser.parse_args()

    config_path = repository_path(args.config)
    baseline_path = repository_path(
        args.baseline_input
    )
    properties_output = repository_path(
        args.properties_output
    )

    rings_output = repository_path(
        args.rings_output
        or DEFAULT_RING_OUTPUTS[args.scope]
    )

    manifest_output = repository_path(
        args.manifest_output
    )

    config = load_yaml(config_path)

    properties = load_property_points(
        config,
        refresh=False,
    )

    fema = load_fema_polygons(config)

    properties_projected, fema_projected = normalize_inputs(
        properties,
        fema,
        config["project"]["project_crs"],
    )

    selected_fema = select_fema_features(
        properties=properties_projected,
        fema=fema_projected,
        scope=args.scope,
        baseline_path=(
            baseline_path
            if args.scope == "baseline"
            else None
        ),
        bbox_buffer_meters=args.bbox_buffer_meters,
        allow_full_export=args.allow_full_export,
    )

    property_statistics = export_projected_properties(
        properties_projected,
        properties_output,
    )

    ring_statistics = export_fema_rings(
        selected_fema,
        rings_output,
    )

    manifest = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "scope": args.scope,
        "project_crs": config["project"]["project_crs"],
        "config": display_path(
            config_path,
            REPOSITORY_ROOT,
        ),
        "property_cache": display_path(
            repository_path(
                config["property_points"]["output_path"]
            ),
            REPOSITORY_ROOT,
        ),
        "baseline_input": (
            display_path(
                baseline_path,
                REPOSITORY_ROOT,
            )
            if args.scope == "baseline"
            else None
        ),
        "properties_output": display_path(
            properties_output,
            REPOSITORY_ROOT,
        ),
        "rings_output": display_path(
            rings_output,
            REPOSITORY_ROOT,
        ),
        "bbox_buffer_meters": (
            args.bbox_buffer_meters
            if args.scope == "bbox"
            else None
        ),
        **property_statistics,
        **ring_statistics,
    }

    write_export_manifest(
        manifest,
        manifest_output,
    )

    print(json.dumps(manifest, indent=2))
    print(
        f"Wrote manifest to "
        f"{display_path(manifest_output, REPOSITORY_ROOT)}"
    )


if __name__ == "__main__":
    main()