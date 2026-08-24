"""C4 item 2b. What the exact pipeline costs, per stage and per workload size.

    # cheap workloads first, so a crash on countywide costs nothing already earned
    python python/scripts/benchmark_c4_pipeline.py --workloads 10000 100000
    python python/scripts/benchmark_c4_pipeline.py --workloads countywide

Appends one JSON record per (stage, workload) cell to
``outputs/benchmark/c4_pipeline_runs.jsonl``. Every output written by every
stage is redirected under ``outputs/scratch/c4/`` and asserted to be there
before the stage runs; no frozen product, manifest or fixture is touched.

The boundary this harness measures against is declared in
``caprm.pipeline_cost.TIMING_BOUNDARY``, committed before the first run, and
copied into the analysis artifact verbatim.

Stages, in pipeline order:
    fema_point_in_polygon   caprm.baseline.run_fema_point_in_polygon
    nearest_water_python    caprm.water_distance.nearest_water_reference
    terrain_sampling        caprm.terrain.build_terrain_evidence
    scoring                 caprm.scoring.build_exposure_index

The C++ nearest-water figure is CITED from B6 at the 25 m cap, original
verification, disk predicate operating point. It is not re-measured here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

from caprm import pipeline_cost as pc  # noqa: E402

STAGES = ("fema_point_in_polygon", "nearest_water_python", "terrain_sampling", "scoring")

#: Fewer repeats as the workload grows. Recorded per cell so a reader never has
#: to infer it, and never below MINIMUM_REPEATS so every cell has a spread.
DEFAULT_COMPUTE_REPEATS = {"10000": 5, "100000": 3, "countywide": 3}
DEFAULT_SETUP_REPEATS = {"10000": 3, "100000": 2, "countywide": 2}
DEFAULT_PROCESS_REPEATS = {"10000": 3, "100000": 2, "countywide": 2}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure the exact pipeline's cost.")
    parser.add_argument("--workloads", nargs="+", default=[w.name for w in pc.WORKLOADS])
    parser.add_argument("--stages", nargs="+", default=list(STAGES))
    parser.add_argument("--scratch", default=pc.SCRATCH_DIRECTORY)
    parser.add_argument("--runs", default="outputs/benchmark/c4_pipeline_runs.jsonl")
    parser.add_argument("--terrain-raster", default="data/raw/terrain/monroe_dem_utm18.tif")
    parser.add_argument("--sample-radius-meters", type=float, default=90.0)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument(
        "--skip-process-clock",
        action="store_true",
        help="Measure only the in-process clock. Halves the runtime; loses the shipped-CLI figure.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the plan and exit.")
    return parser


def stage_callables(stage: str, workload: pc.Workload, args, scratch: Path):
    """Return ``(setup, compute)`` for one stage at one workload.

    Heavy imports are local so that importing ``caprm.pipeline_cost`` in the
    test suite does not require rasterio, geopandas or a DEM on disk.
    """
    config_path = REPOSITORY_ROOT / workload.config

    if stage == "fema_point_in_polygon":
        from caprm.baseline import run_fema_point_in_polygon
        from caprm.crs import normalize_inputs
        from caprm.ingest import load_fema_polygons, load_property_points, load_yaml

        def setup():
            config = load_yaml(config_path)
            properties = load_property_points(config, refresh=False)
            fema = load_fema_polygons(config)
            projected, fema_projected = normalize_inputs(
                properties, fema, config["project"]["project_crs"]
            )
            return config, projected, fema_projected

        def compute(inputs):
            config, projected, fema_projected = inputs
            return run_fema_point_in_polygon(
                projected, fema_projected, config, predicate="within"
            )

        return setup, compute

    if stage == "nearest_water_python":
        from caprm.hydrography import calculate_sha256
        from caprm.ingest import load_property_points, load_yaml, repository_path
        from caprm.water_distance import (
            load_hydrography_cache,
            nearest_water_reference,
            prepare_distance_properties,
        )

        def setup():
            config = load_yaml(config_path)
            hydrography_config = config["hydrography"]
            distance_crs = config["project"]["distance_crs"]
            cache_path = repository_path(hydrography_config["cache_path"])
            calculate_sha256(cache_path)  # the shipped CLI does this every run
            properties = load_property_points(config, refresh=False)
            projected = prepare_distance_properties(properties, distance_crs)
            hydrography = load_hydrography_cache(cache_path, distance_crs)
            return projected, hydrography, float(hydrography_config["query_buffer_meters"]), distance_crs

        def compute(inputs):
            projected, hydrography, buffer_m, distance_crs = inputs
            return nearest_water_reference(
                properties=projected,
                hydrography=hydrography,
                query_buffer_meters=buffer_m,
                distance_crs=distance_crs,
                tie_tolerance_meters=1e-6,
            )

        return setup, compute

    if stage == "terrain_sampling":
        import pandas as pd

        from caprm.terrain import build_terrain_evidence

        evidence_csv = scratch / f"evidence_{workload.name}.csv"
        raster_path = REPOSITORY_ROOT / args.terrain_raster

        def setup():
            return pd.read_csv(evidence_csv, dtype={"property_id": "string"})

        def compute(evidence):
            return build_terrain_evidence(
                evidence=evidence,
                raster_path=raster_path,
                terrain_crs="EPSG:26918",
                sample_radius_meters=args.sample_radius_meters,
            )

        return setup, compute

    if stage == "scoring":
        import pandas as pd

        from caprm.scoring import DEFAULT_WEIGHTS, build_exposure_index

        evidence_csv = scratch / f"evidence_{workload.name}.csv"
        terrain_csv = scratch / f"terrain_{workload.name}.csv"

        def setup():
            return (
                pd.read_csv(evidence_csv, dtype={"property_id": "string"}),
                pd.read_csv(terrain_csv, dtype={"property_id": "string"}),
            )

        def compute(inputs):
            evidence, terrain = inputs
            return build_exposure_index(
                evidence=evidence,
                terrain=terrain,
                expected_distance_crs="EPSG:26918",
                expected_terrain_crs="EPSG:26918",
                weights=DEFAULT_WEIGHTS,
            )

        return setup, compute

    raise SystemExit(f"unknown stage {stage!r}")


def stage_command(stage: str, workload: pc.Workload, args, scratch: Path) -> list[str]:
    """The shipped CLI invocation, with EVERY output flag redirected to scratch."""
    cli = scratch / "cli"
    name = workload.name

    def out(filename: str) -> str:
        path = pc.assert_under_scratch(cli / filename, scratch)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    scripts = REPOSITORY_ROOT / "python" / "scripts"
    if stage == "fema_point_in_polygon":
        return [
            sys.executable, str(scripts / "run_fema_baseline.py"),
            "--config", workload.config,
            "--output", out(f"fema_{name}.csv"),
        ]
    if stage == "nearest_water_python":
        return [
            sys.executable, str(scripts / "run_water_baseline.py"),
            "--config", workload.config,
            "--output", out(f"water_{name}.csv"),
            "--summary-output", out(f"water_{name}_summary.json"),
        ]
    if stage == "terrain_sampling":
        return [
            sys.executable, str(scripts / "build_terrain_evidence.py"),
            "--evidence", str(scratch / f"evidence_{name}.csv"),
            "--terrain-raster", args.terrain_raster,
            "--sample-radius-meters", str(args.sample_radius_meters),
            "--output", out(f"terrain_out_{name}.csv"),
            "--manifest-output", out(f"terrain_manifest_{name}.json"),
        ]
    if stage == "scoring":
        return [
            sys.executable, str(scripts / "build_exposure_index.py"),
            "--evidence", str(scratch / f"evidence_{name}.csv"),
            "--terrain", str(scratch / f"terrain_{name}.csv"),
            "--output", out(f"index_{name}.csv"),
            "--manifest-output", out(f"index_manifest_{name}.json"),
        ]
    raise SystemExit(f"unknown stage {stage!r}")


def main() -> int:
    args = build_parser().parse_args()
    scratch = REPOSITORY_ROOT / args.scratch
    workloads = [w for w in pc.WORKLOADS if w.name in args.workloads]
    if not workloads:
        raise SystemExit(f"no workloads matched {args.workloads}")

    plan = [(stage, w) for w in workloads for stage in args.stages]
    print(f"{len(plan)} cells: {[s for s in args.stages]} x {[w.name for w in workloads]}")
    for stage, workload in plan:
        print(f"  {stage:22} {workload.name:11} {' '.join(stage_command(stage, workload, args, scratch)[1:])}")
    if args.dry_run:
        return 0

    runs_path = REPOSITORY_ROOT / args.runs
    for stage, workload in plan:
        name = workload.name
        print(f"\n[{stage} @ {name}]")
        setup, compute = stage_callables(stage, workload, args, scratch)

        in_process = pc.time_stage_in_process(
            setup,
            compute,
            n_setup_repeats=DEFAULT_SETUP_REPEATS[name],
            n_compute_repeats=DEFAULT_COMPUTE_REPEATS[name],
            n_warmup=args.warmups,
        )
        print(
            f"  setup   {in_process['setup_s']['median_s']:>9.3f} s  "
            f"spread {in_process['setup_s']['relative_spread']:.3f}"
        )
        print(
            f"  compute {in_process['compute_s']['median_s']:>9.3f} s  "
            f"spread {in_process['compute_s']['relative_spread']:.3f}  "
            f"rows {in_process['result_rows']}"
        )

        record = {
            "schema_version": "c4_pipeline_cell_v1",
            "tool_version": pc.TOOL_VERSION,
            "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "stage": stage,
            "workload": name,
            "n_properties": workload.expected_rows,
            "config": workload.config,
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            **in_process,
        }

        if not args.skip_process_clock:
            command = stage_command(stage, workload, args, scratch)
            process = pc.time_process_wall_clock(
                command,
                cwd=REPOSITORY_ROOT,
                n_repeats=DEFAULT_PROCESS_REPEATS[name],
                n_warmup=args.warmups,
            )
            record["process"] = process
            wall = process["process_wall_clock_s"]
            print(
                f"  process {wall['median_s']:>9.3f} s  spread {wall['relative_spread']:.3f}  "
                f"(startup + geopandas import included)"
            )

        pc.append_run_record(runs_path, record)

    print(f"\nappended {len(plan)} cells to {runs_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())