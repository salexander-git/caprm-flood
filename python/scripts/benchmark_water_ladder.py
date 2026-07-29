"""Run the nearest-water benchmark ladder (Milestone 4, chunk B6).

Measurement only. No implementation is modified by this script.

A CELL is one (rung, workload, seed window) configuration. B6a ran one workload
at one window, so a cell was a rung; B6c runs a matrix and the two are separate.

Protocol, declared before measuring (Nucleus 18.12):

  repetitions   3 + 1 warm-up for rung 1, 7 + 1 for rungs 2-5. The counts differ
                because the required precision differs: rung 1 resolves a ~20x
                effect and rungs 4/5 resolve a ~6% effect against ~4% run-to-run
                noise. ``n`` is recorded beside every figure.
  ordering      blocked by repetition, cyclically rotated by block index so that
                position within a block is not confounded with the cell.
                Rotation preserves relative adjacency, so rungs 4 and 5 stay
                neighbours and the within-invocation ratio argument holds.
  stdout        captured to a pipe on every run. Every binary prints a progress
                line per 100 properties from inside its timed region.
  eligibility   --verify-counts, --uncapped-half and --seed-error-stats are
                refused. --query-stats is required on rungs 4 and 5.
  dispersion    min / median / max and relative spread always; a standard
                deviation only at n >= 5.
  sessions      every row carries a session id, and a cell whose repetitions
                span sessions is refused. B6a measured an 11 percent shift in
                rung 1 between two sittings of an identical configuration, so a
                median over sessions is a median over machine states.
  durability    every completed run is appended to a JSON-lines sidecar and
                fsynced before the next run starts. --resume reads it back.

Examples (PowerShell, from the repository root)::

    # B6c invocation A -- the ladder across three workloads at one window
    ... --label ladder --workload 10000 100000 countywide --seed-window 64

    # B6c invocation B -- the window sweep at countywide
    ... --label sweep --workload countywide --rungs hilbert_binary hilbert_rmi `
        --seed-window 8 16 32 64 128 256 512 1024 2048 `
        --hilbert-executable-template `
            "cpp/spatial_core/build/water_distance_hilbert_w{window}.exe"
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "python" / "scripts"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))
# rmi_probe_args lives beside this script rather than in the package. Importing
# it is deliberate: the --rmi-probes record format must have exactly one
# definition, and reimplementing it here is the transcription Nucleus 18.20
# forbids.
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import pandas as pd  # noqa: E402

from caprm.ingest import repository_path  # noqa: E402
from caprm.ladder_benchmark import (  # noqa: E402
    LADDER,
    LADDER_BY_NAME,
    RunRecorder,
    RungSpec,
    assert_expected_digest,
    blocked_schedule,
    build_command,
    machine_record,
    parse_expected_digests,
    run_once,
    sha256_file,
    summarize_cell,
)
from rmi_probe_args import probe_argument  # noqa: E402

WORKLOADS = ("10000", "100000", "countywide")

DEFAULT_EXECUTABLES = {
    "brute_force": "cpp/spatial_core/build/water_distance_bruteforce.exe",
    "feature_bvh": "cpp/spatial_core/build/water_distance_indexed.exe",
    "segment_bvh": "cpp/spatial_core/build/water_distance_segment_bvh.exe",
    "hilbert": "cpp/spatial_core/build/water_distance_hilbert.exe",
}

PYTHON_REFERENCES = {
    "sample": "outputs/baseline/python_nearest_water.csv",
    "10000": "outputs/baseline/python_nearest_water_10000.csv",
    "100000": "outputs/baseline/python_nearest_water_100000.csv",
    "countywide": "outputs/baseline/python_nearest_water_countywide.csv",
}


@dataclass(frozen=True)
class Cell:
    """One (rung, workload, seed window) configuration."""

    key: str
    rung: RungSpec
    workload: str
    seed_window: int | None
    executable: str
    repetitions: int

    @property
    def stem(self) -> str:
        return self.key.replace("@", "_")


def build_cells(
    rung_names, workloads, windows, executables, template, repetitions,
    brute_force_repetitions,
) -> list[Cell]:
    """Expand the matrix.

    Rungs 1-3 have no seed window, so they get ONE cell per workload however
    many windows are swept. Scheduling them once per window would multiply the
    most expensive rung in the ladder by nine for no measurement.
    """
    cells: list[Cell] = []
    for workload in workloads:
        for name in rung_names:
            rung = LADDER_BY_NAME[name]
            count = (
                brute_force_repetitions
                if name == "brute_force"
                else repetitions
            )
            if rung.seed_mode is None:
                cells.append(
                    Cell(
                        key=f"{name}@{workload}",
                        rung=rung,
                        workload=workload,
                        seed_window=None,
                        executable=executables[rung.executable_key],
                        repetitions=count,
                    )
                )
                continue
            for window in windows:
                executable = (
                    template.format(window=window)
                    if template
                    else executables[rung.executable_key]
                )
                cells.append(
                    Cell(
                        key=f"{name}@{workload}@w{window}",
                        rung=rung,
                        workload=workload,
                        seed_window=window,
                        executable=executable,
                        repetitions=count,
                    )
                )
    return cells


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", nargs="+", choices=WORKLOADS, required=True)
    parser.add_argument(
        "--rungs",
        nargs="+",
        default=[rung.name for rung in LADDER],
        choices=[rung.name for rung in LADDER],
    )
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--repetitions-brute-force", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument(
        "--seed-window",
        nargs="+",
        type=int,
        default=[64],
        help="Window(s) the hilbert binaries were BUILT with; asserted per run.",
    )
    parser.add_argument("--hilbert-executable", default=None)
    parser.add_argument(
        "--hilbert-executable-template",
        default=None,
        help="e.g. 'cpp/.../water_distance_hilbert_w{window}.exe'. Required "
             "when more than one window is swept.",
    )
    parser.add_argument("--label", default=None)
    parser.add_argument("--rmi-model", default="models/water_hilbert_rmi.bin")
    parser.add_argument(
        "--rmi-manifest",
        default="outputs/validation/water_hilbert_rmi_manifest.json",
    )
    parser.add_argument("--power-source", required=True)
    parser.add_argument("--power-plan", required=True)
    parser.add_argument("--cpu-model", default=None)
    parser.add_argument("--physical-cores", type=int, default=None)
    parser.add_argument("--machine-notes", default="")
    parser.add_argument("--runs-output", default=None)
    parser.add_argument("--summary-output", default=None)
    parser.add_argument("--work-directory", default="outputs/benchmark/ladder_work")
    parser.add_argument(
        "--expect-digest", nargs="*", default=(), metavar="RUNG[@WORKLOAD]=SHA256"
    )
    parser.add_argument("--no-rotate", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip runs already in the JSON-lines sidecar. Cells whose "
             "repetitions end up spanning sessions are refused at summary time.",
    )
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    workloads = list(dict.fromkeys(arguments.workload))
    windows = list(dict.fromkeys(arguments.seed_window))
    template = arguments.hilbert_executable_template

    if len(windows) > 1 and not template:
        parser.error(
            "--seed-window with more than one value requires "
            "--hilbert-executable-template."
        )

    executables = dict(DEFAULT_EXECUTABLES)
    if arguments.hilbert_executable:
        executables["hilbert"] = arguments.hilbert_executable

    label = arguments.label or (
        f"{workloads[0]}_w{windows[0]}"
        if len(workloads) == 1 and len(windows) == 1
        else "matrix"
    )

    work_directory = repository_path(arguments.work_directory)
    work_directory.mkdir(parents=True, exist_ok=True)
    runs_output = repository_path(
        arguments.runs_output or f"outputs/benchmark/water_ladder_runs_{label}.csv"
    )
    summary_output = repository_path(
        arguments.summary_output
        or f"outputs/validation/water_ladder_summary_{label}.json"
    )

    rmi_manifest_path = repository_path(arguments.rmi_manifest)
    rmi_model_path = repository_path(arguments.rmi_model)
    rmi_probes = (
        probe_argument(rmi_manifest_path)
        if "hilbert_rmi" in arguments.rungs
        else None
    )

    cells = build_cells(
        arguments.rungs, workloads, windows, executables, template,
        arguments.repetitions, arguments.repetitions_brute_force,
    )
    by_key = {cell.key: cell for cell in cells}

    inputs = {
        workload: {
            kind: repository_path(
                f"outputs/cpp_input/water_{kind}_{workload}.csv"
            )
            for kind in ("properties_projected", "features", "vertices")
        }
        for workload in workloads
    }

    commands: dict[str, list[str]] = {}
    paths: dict[str, dict[str, Path]] = {}
    for cell in cells:
        paths[cell.key] = {
            "output": work_directory / f"{cell.stem}.csv",
            "manifest": work_directory / f"{cell.stem}_manifest.json",
            "query_stats": work_directory / f"{cell.stem}_query_stats.json",
        }
        commands[cell.key] = build_command(
            rung=cell.rung,
            executable=repository_path(cell.executable),
            properties_path=inputs[cell.workload]["properties_projected"],
            features_path=inputs[cell.workload]["features"],
            vertices_path=inputs[cell.workload]["vertices"],
            output_path=paths[cell.key]["output"],
            manifest_path=(
                paths[cell.key]["manifest"] if cell.rung.wants_manifest else None
            ),
            query_stats_path=(
                paths[cell.key]["query_stats"]
                if cell.rung.wants_query_stats
                else None
            ),
            rmi_model_path=rmi_model_path if cell.rung.seed_mode == "rmi" else None,
            rmi_probes=rmi_probes if cell.rung.seed_mode == "rmi" else None,
        )

    expected_digests = parse_expected_digests(arguments.expect_digest)
    schedule = blocked_schedule(
        [cell.key for cell in cells],
        {cell.key: cell.repetitions for cell in cells},
        arguments.warmups,
        rotate=not arguments.no_rotate,
    )

    if arguments.dry_run:
        for cell in cells:
            print(f"\n[{cell.key}]  n={cell.repetitions}")
            print("  " + " ".join(commands[cell.key]))
        print(f"\n{len(cells)} cells, {len(schedule)} runs scheduled")
        return 0

    session_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc).isoformat()
    recorder = RunRecorder(runs_output.with_suffix(".jsonl"))
    already: set[tuple[str, int]] = set()
    if arguments.resume:
        recovered = recorder.load_existing()
        already = recorder.completed()
        print(f"Resuming: {len(recovered)} runs recovered, session {session_id}")

    for execution_order, entry in enumerate(schedule, start=1):
        if (entry.cell_key, entry.repetition) in already:
            continue
        cell = by_key[entry.cell_key]
        print(
            f"[{execution_order}/{len(schedule)}] {entry.cell_key} "
            f"{'warmup' if entry.is_warmup else f'rep {entry.repetition}'}",
            flush=True,
        )
        metrics = run_once(
            rung=cell.rung,
            command=commands[entry.cell_key],
            output_path=paths[entry.cell_key]["output"],
            query_stats_path=(
                paths[entry.cell_key]["query_stats"]
                if cell.rung.wants_query_stats
                else None
            ),
        )
        metrics.update(
            {
                "cell_key": entry.cell_key,
                "session_id": session_id,
                "workload": cell.workload,
                "seed_window_build": cell.seed_window,
                "executable": cell.executable,
                "repetition": entry.repetition,
                "is_warmup": entry.is_warmup,
                "block": entry.block,
                "position_in_block": entry.position,
                "execution_order": execution_order,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        reported = metrics.get(
            "seed_window_entries", metrics.get("seed_window_entries_stdout")
        )
        if (
            cell.seed_window is not None
            and reported is not None
            and int(reported) != cell.seed_window
        ):
            raise RuntimeError(
                f"{entry.cell_key} self-reports seed_window_entries={reported} "
                f"but the cell claims {cell.seed_window}. The binary is not the "
                f"build this run claims."
            )
        assert_expected_digest(
            cell.rung.name,
            metrics["output_sha256"],
            expected_digests,
            cell.workload,
        )
        recorder.append(metrics)

    runs_frame = pd.DataFrame(recorder.records)
    runs_output.parent.mkdir(parents=True, exist_ok=True)
    runs_frame.to_csv(runs_output, index=False)

    timed_by_cell: dict[str, list[dict]] = {cell.key: [] for cell in cells}
    for record in recorder.records:
        if not record.get("is_warmup") and record.get("cell_key") in timed_by_cell:
            timed_by_cell[record["cell_key"]].append(record)

    summary = {
        "chunk": "B6",
        "report": "ladder_matrix",
        "label": label,
        "session_id": session_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at,
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "workloads": workloads,
        "seed_windows": windows,
        "verification_mode": "original",
        "region_mode": "disk",
        "max_segment_length_cap_m": 25.0,
        "protocol": {
            "expected_output_digests": expected_digests,
            "repetitions": {cell.key: cell.repetitions for cell in cells},
            "warmups": arguments.warmups,
            "ordering": (
                "blocked by repetition; "
                + ("fixed order within a block"
                   if arguments.no_rotate
                   else "cyclically rotated by block index")
            ),
            "resumed": bool(arguments.resume),
            "stdout": "captured to a pipe on every run",
            "timing_source": "binary self-reported computation seconds",
            "forbidden_flags": [
                "--verify-counts", "--uncapped-half", "--seed-error-stats",
            ],
        },
        "machine": machine_record(
            arguments.power_source, arguments.power_plan, arguments.machine_notes,
            cpu_model=arguments.cpu_model, physical_cores=arguments.physical_cores,
        ),
        "inputs": {
            workload: {
                kind: {
                    "path": str(path.relative_to(REPOSITORY_ROOT)),
                    "sha256": sha256_file(path),
                }
                for kind, path in kinds.items()
            }
            for workload, kinds in inputs.items()
        },
        "python_references": {
            name: {"path": path, "sha256": sha256_file(repository_path(path))}
            for name, path in PYTHON_REFERENCES.items()
            if repository_path(path).exists()
        },
        "executables": {
            path: sha256_file(repository_path(path))
            for path in sorted(
                {cell.executable for cell in cells}
                | set(DEFAULT_EXECUTABLES.values())
            )
            if repository_path(path).exists()
        },
        "cells": {
            cell.key: {
                **summarize_cell(timed_by_cell[cell.key]),
                "workload": cell.workload,
                "seed_window": cell.seed_window,
                "executable": cell.executable,
                "command": commands[cell.key],
                "output_path": str(
                    paths[cell.key]["output"].relative_to(REPOSITORY_ROOT)
                ),
            }
            for cell in cells
            if timed_by_cell[cell.key]
        },
    }

    if "hilbert_rmi" in arguments.rungs:
        summary["rmi_model"] = {
            "path": arguments.rmi_model,
            "sha256": sha256_file(rmi_model_path),
            "manifest": arguments.rmi_manifest,
            "manifest_sha256": sha256_file(rmi_manifest_path),
        }

    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nRuns:    {runs_output}")
    print(f"Sidecar: {recorder.path}")
    print(f"Summary: {summary_output}")
    for key in sorted(summary["cells"]):
        seconds = summary["cells"][key]["computation_seconds"]
        print(
            f"  {key:<38} n={seconds['n']} "
            f"median={seconds['median']:.4f} s "
            f"spread={seconds['relative_spread'] * 100:.2f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())