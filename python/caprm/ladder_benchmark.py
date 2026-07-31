"""Five-rung nearest-water benchmark ladder (Milestone 4, chunk B6).

This module measures. It changes nothing about the implementations it runs.

Why this is not an extension of ``caprm.water_benchmark``
--------------------------------------------------------
``water_benchmark.summarize_benchmark_runs`` asserts that the algorithm set is
exactly ``{brute_force, feature_bvh}`` and ``run_cpp_algorithm`` builds a fixed
four-positional command with no option support. Both are Milestone 2
infrastructure whose recorded artifacts
(``outputs/benchmark/water_cpp_benchmark_countywide_runs.csv``) are cited in
Current Status section 19b. Widening them in place would change the schema of a
validated artifact. This module is separate and imports the Milestone 2 prefix
maps rather than restating them, so a change to a stdout label is a single edit.

The ladder (Nucleus 14b)
------------------------
    1  brute_force    no index
    2  feature_bvh    2D, 8,572 features
    3  segment_bvh    2D, ~1.19M split-segment boxes
    4  hilbert_binary 1D, ~1.19M keys, lower_bound seed   (the control)
    5  hilbert_rmi    1D, ~1.19M keys, learned seed

Comparisons are ADJACENT: 3 vs 2, 4 vs 3, 5 vs 4. A global 5 vs 3 confounds the
dimensionality reduction with the learning and is not reported.

Benchmark eligibility (Current Status, B3b/B5/B5c)
-------------------------------------------------
``--verify-counts``, ``--uncapped-half`` and ``--seed-error-stats`` all add
counted work inside the timed region, so a run carrying any of them is not
benchmark-eligible. ``--query-stats`` is free and IS eligible; rungs 4 and 5
require it, because the resolve-descent counters are the quantity the 5-vs-4
claim rests on. The rule is enforced by an assertion over the constructed
command rather than by convention.

Timing convention
-----------------
The primary figure is the binary's self-reported computation seconds, which is
what the B2 cap sweep reported and is therefore comparable with everything
recorded through B5c. Wall-clock process seconds are recorded beside it as a
secondary figure. Every binary prints a progress line every 100 properties from
inside its timed region, so stdout is captured to a pipe for every run and never
left on a console; the destination is part of the protocol, not an accident.

Never infer a speedup from counts (Nucleus 18.22, B2): a segment check is not a
mode-invariant unit of cost. Wall clock sits beside counts in every table this
module emits.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import itertools
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from caprm.water_benchmark import FLOAT_PREFIXES as MILESTONE2_FLOAT_PREFIXES
from caprm.water_benchmark import (
    INTEGER_PREFIXES as MILESTONE2_INTEGER_PREFIXES,
)


# ---------------------------------------------------------------------------
# stdout metric vocabulary
# ---------------------------------------------------------------------------

INTEGER_PREFIXES: dict[str, str] = {
    **MILESTONE2_INTEGER_PREFIXES,
    "Index entries": "index_entries",
    "Index bytes": "index_bytes",
    "Key array bytes": "key_array_bytes",
    "RMI model bytes": "rmi_model_bytes",
    "RMI second-stage models": "rmi_leaf_count",
    "RMI probe records asserted": "rmi_probe_records_asserted",
    "Split segments (BVH leaves)": "split_segment_count",
    "Split segments (index entries)": "split_segment_count",
    "Original segments (split input)": "original_segment_count",
    "Added segments": "added_segment_count",
    "Hilbert order (bits/axis)": "hilbert_order_bits_per_axis",
    "Total segment box tests": "total_segment_box_tests",
}

FLOAT_PREFIXES: dict[str, str] = {
    **MILESTONE2_FLOAT_PREFIXES,
    # Four binaries, four labels, one quantity.
    "Segment-BVH computation seconds": "computation_seconds",
    "Hilbert computation seconds": "computation_seconds",
    # The hilbert binary labels phase-2 verification explicitly. It is the same
    # counter as the segment BVH's, under the same original-mode verification,
    # which is what makes the 4-vs-3 comparison direct (Current Status B3b).
    "Average phase-2 segment checks per property":
        "average_segment_checks_per_property",
    "Average seed probes per property": "average_seed_probes_per_property",
    "Average RESOLVE descent entries per property":
        "resolve_entries_per_property",
    "Average RESOLVE descent nodes per property":
        "resolve_nodes_per_property",
    "Average entries scanned per property (N_decomp)":
        "n_decomp_per_property",
    "Average entries satisfying the predicate (N_true_r)":
        "n_true_r_per_property",
    "Average midpoints in disk(r+L/2) per property (N_disk_infl)":
        "n_disk_infl_per_property",
    "Geometric L/2 inflation, capped (N_disk_infl / N_true_r)":
        "geometric_inflation_capped",
    "Box-vs-disk indexing inflation (N_decomp / N_disk_infl)":
        "box_versus_disk_inflation",
    "Mean d_seed / d_best": "mean_d_seed_over_d_best",
    "Average segment box tests per property":
        "average_segment_box_tests_per_property",
    "Max entry extent (m)": "max_entry_extent_m",
    "Max split segment length L (m)": "max_split_segment_length_m",
    "Inflation half L/2 (m)": "inflation_half_m",
}

STRING_PREFIXES: dict[str, str] = {
    "Verification mode": "verification_mode",
    "Region mode": "region_mode",
    "Seed mode": "seed_mode",
}

# Some lines carry a trailing parenthetical annotation:
#     Mean d_seed / d_best: 1.252111 (max 25.058606, over 10000 properties ...)
#     Seed mode: binary (window 64 entries either side)
# The value is what precedes it. Splitting is deliberate rather than a
# permissive float scan: anything after the value that is NOT a parenthesised
# annotation is still a parse error, because a silently truncated number is
# worse than a crash.
ANNOTATED_VALUE = re.compile(r"^(?P<value>[^(]*?)\s*\((?P<annotation>.*)\)\s*$")

SEED_WINDOW_ANNOTATION = re.compile(r"window\s+(?P<entries>\d+)\s+entries")


def split_annotation(raw_value: str) -> tuple[str, str | None]:
    """Return ``(value, annotation)`` for a possibly annotated stdout value."""
    match = ANNOTATED_VALUE.match(raw_value)
    if match is None:
        return raw_value, None
    return match.group("value"), match.group("annotation")


# ---------------------------------------------------------------------------
# eligibility
# ---------------------------------------------------------------------------

FORBIDDEN_BENCHMARK_FLAGS: tuple[str, ...] = (
    "--verify-counts",
    "--uncapped-half",
    "--seed-error-stats",
)


class BenchmarkIneligibleError(RuntimeError):
    """Raised when a command would time work a benchmark must not include."""


def assert_benchmark_eligible(command: Sequence[str]) -> None:
    """Refuse to time a command carrying a counting-only diagnostic flag.

    Current Status B3b/B5/B5c: these three flags add work inside the timed
    region. ``--query-stats`` is deliberately absent from the list; its counters
    are free and rungs 4 and 5 need them on the runs they time.
    """
    for token in command:
        bare = str(token).split("=", maxsplit=1)[0]
        if bare in FORBIDDEN_BENCHMARK_FLAGS:
            raise BenchmarkIneligibleError(
                f"Not benchmark-eligible: {bare} adds counted work inside the "
                f"timed region. Command: {list(command)}"
            )


# ---------------------------------------------------------------------------
# peak memory
# ---------------------------------------------------------------------------

class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def peak_memory(
    process: subprocess.Popen,
) -> tuple[int | None, int | None, str]:
    """Peak memory of a finished child, read from the parent.

    Returns ``(peak_working_set, peak_pagefile, method)``.

    Both are true OS-maintained peaks rather than polls, and the handle
    ``subprocess`` holds stays valid after the child exits. The two differ and
    the difference matters: the working set is RESIDENT pages and is subject to
    trimming, while the pagefile figure is peak PRIVATE COMMIT and is not. B6a
    measured rung 4's peak working set at 166 MB above its baseline while its
    persistent structure is 9.5 MB; separating demanded from resident memory is
    what makes that gap attributable instead of arguable.

    Off Windows this returns ``None`` with a stated reason. An unmeasured number
    is recorded as unmeasured, never estimated.
    """
    if sys.platform != "win32":
        return None, None, f"unavailable:{sys.platform}"

    handle = getattr(process, "_handle", None)
    if handle is None:
        return None, None, "unavailable:no_process_handle"

    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(_ProcessMemoryCounters)

    for library_name, symbol in (
        ("psapi", "GetProcessMemoryInfo"),
        ("kernel32", "K32GetProcessMemoryInfo"),
    ):
        try:
            library = ctypes.WinDLL(library_name)  # type: ignore[attr-defined]
            function = getattr(library, symbol)
        except (OSError, AttributeError):
            continue
        if function(
            ctypes.c_void_p(int(handle)),
            ctypes.byref(counters),
            counters.cb,
        ):
            return (
                int(counters.PeakWorkingSetSize),
                int(counters.PeakPagefileUsage),
                f"{library_name}:{symbol}",
            )

    return None, None, "unavailable:getprocessmemoryinfo_failed"


# ---------------------------------------------------------------------------
# rung specifications
# ---------------------------------------------------------------------------

VERIFICATION_MODES: tuple[str, ...] = ("original", "split")
DEFAULT_VERIFICATION_MODE = "original"


@dataclass(frozen=True)
class RungSpec:
    """One rung of the ladder: which binary, which arguments, what it must emit."""

    number: int
    name: str
    executable_key: str
    trailing_positionals: tuple[str, ...] = ()
    required_metrics: frozenset[str] = frozenset()
    wants_query_stats: bool = False
    seed_mode: str | None = None
    wants_manifest: bool = False
    # Index into ``trailing_positionals`` holding the verification mode, or None
    # for a rung that has no such argument. Rungs 1 and 2 verify over original
    # geometry by construction -- brute force scans original segments and the
    # feature BVH rescans each candidate feature's original geometry -- so there
    # is no fork to select and no cell to run under `split`.
    verification_mode_position: int | None = None


COMMON_REQUIRED = frozenset(
    {
        "property_count",
        "water_feature_count",
        "vertex_count",
        "computation_seconds",
    }
)

# Positional interface, unchanged from the binaries' own usage strings:
#   segment_bvh: <crs> <cap_m> <verification_mode>
#   hilbert:     <crs> <cap_m> <verification_mode> <region_mode> <order> <manifest>
DISTANCE_CRS = "EPSG:26918"
SEGMENT_LENGTH_CAP_M = "25"
VERIFICATION_MODE = "original"
REGION_MODE = "disk"
HILBERT_ORDER = "32"

LADDER: tuple[RungSpec, ...] = (
    RungSpec(
        number=1,
        name="brute_force",
        executable_key="brute_force",
        required_metrics=COMMON_REQUIRED
        | {"total_segment_checks", "average_segment_checks_per_property"},
    ),
    RungSpec(
        number=2,
        name="feature_bvh",
        executable_key="feature_bvh",
        required_metrics=COMMON_REQUIRED
        | {
            "total_segment_checks",
            "average_segment_checks_per_property",
            "bvh_node_count",
            "index_construction_seconds",
            "average_node_visits_per_property",
            "average_candidate_features_per_property",
        },
    ),
    RungSpec(
        number=3,
        name="segment_bvh",
        executable_key="segment_bvh",
        trailing_positionals=(
            DISTANCE_CRS,
            SEGMENT_LENGTH_CAP_M,
            VERIFICATION_MODE,
        ),
        required_metrics=COMMON_REQUIRED
        | {
            "average_segment_checks_per_property",
            "average_candidate_features_per_property",
            "index_entries",
            "index_bytes",
            "index_construction_seconds",
            "verification_mode",
        },
        verification_mode_position=2,
    ),
    RungSpec(
        number=4,
        name="hilbert_binary",
        executable_key="hilbert",
        trailing_positionals=(
            DISTANCE_CRS,
            SEGMENT_LENGTH_CAP_M,
            VERIFICATION_MODE,
            REGION_MODE,
            HILBERT_ORDER,
        ),
        required_metrics=COMMON_REQUIRED
        | {
            "average_segment_checks_per_property",
            "average_seed_probes_per_property",
            "resolve_entries_per_property",
            "resolve_nodes_per_property",
            "n_true_r_per_property",
            "n_disk_infl_per_property",
            "geometric_inflation_capped",
            "index_entries",
            "key_array_bytes",
            "seed_mode",
            "region_mode",
        },
        wants_query_stats=True,
        wants_manifest=True,
        seed_mode="binary",
        verification_mode_position=2,
    ),
    RungSpec(
        number=5,
        name="hilbert_rmi",
        executable_key="hilbert",
        trailing_positionals=(
            DISTANCE_CRS,
            SEGMENT_LENGTH_CAP_M,
            VERIFICATION_MODE,
            REGION_MODE,
            HILBERT_ORDER,
        ),
        required_metrics=COMMON_REQUIRED
        | {
            "average_segment_checks_per_property",
            "average_seed_probes_per_property",
            "resolve_entries_per_property",
            "resolve_nodes_per_property",
            "n_true_r_per_property",
            "n_disk_infl_per_property",
            "geometric_inflation_capped",
            "index_entries",
            "key_array_bytes",
            "rmi_model_bytes",
            "rmi_probe_records_asserted",
            "seed_mode",
            "region_mode",
        },
        wants_query_stats=True,
        wants_manifest=True,
        seed_mode="rmi",
        verification_mode_position=2,
    ),
)

LADDER_BY_NAME: dict[str, RungSpec] = {rung.name: rung for rung in LADDER}


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def parse_ladder_output(standard_output: str, rung: RungSpec) -> dict[str, Any]:
    """Parse a rung's stdout into metrics, failing loudly on a missing required one."""
    metrics: dict[str, Any] = {"algorithm": rung.name, "rung": rung.number}

    for raw_line in standard_output.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        prefix, raw_value = line.split(":", maxsplit=1)
        prefix = prefix.strip()
        raw_value = raw_value.strip()

        value, annotation = split_annotation(raw_value)

        if prefix in INTEGER_PREFIXES:
            metrics[INTEGER_PREFIXES[prefix]] = int(value)
        elif prefix in FLOAT_PREFIXES:
            metrics[FLOAT_PREFIXES[prefix]] = float(value)
        elif prefix in STRING_PREFIXES:
            metrics[STRING_PREFIXES[prefix]] = value
            # "Seed mode: binary (window 64 entries either side)" is a second,
            # independent report of the window the binary was BUILT with. B6b
            # produces one binary per window; running the wrong one is the
            # chunk's main hazard, so the value is captured and cross-checked
            # against the --query-stats JSON rather than discarded.
            if prefix == "Seed mode" and annotation:
                window = SEED_WINDOW_ANNOTATION.search(annotation)
                if window:
                    metrics["seed_window_entries_stdout"] = int(
                        window.group("entries")
                    )

    missing = sorted(rung.required_metrics - set(metrics))
    if missing:
        raise ValueError(
            f"{rung.name}: stdout is missing required metrics {missing}.\n\n"
            f"Captured output:\n{standard_output}"
        )
    return metrics


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# command construction
# ---------------------------------------------------------------------------

def verification_positionals(
    rung: RungSpec, verification_mode: str | None
) -> tuple[str, ...]:
    """Return the rung's trailing positionals with the verification mode set.

    B6's kickoff document names the Option A / Option B cross-product as the
    primary deliverable: the ROW difference is index quality and the COLUMN
    difference is the cost of exactness. Substituting one slot is all it takes,
    because B2 implemented both modes behind a single flag on one code path
    rather than forking the implementation.

    The current value of the slot is asserted to be a known mode, so a change to
    the positional order fails here instead of silently rewriting the segment
    length cap or the region predicate.
    """
    positionals = list(rung.trailing_positionals)
    if verification_mode is None:
        return tuple(positionals)
    if rung.verification_mode_position is None:
        if verification_mode != DEFAULT_VERIFICATION_MODE:
            raise ValueError(
                f"{rung.name} has no verification-mode argument; it verifies "
                f"over original geometry by construction. Requested "
                f"{verification_mode!r}."
            )
        return tuple(positionals)
    if verification_mode not in VERIFICATION_MODES:
        raise ValueError(
            f"Unknown verification mode {verification_mode!r}; "
            f"expected one of {VERIFICATION_MODES}."
        )
    position = rung.verification_mode_position
    current = positionals[position]
    if current not in VERIFICATION_MODES:
        raise ValueError(
            f"{rung.name}: positional {position} holds {current!r}, which is "
            f"not a verification mode. The positional order has changed and "
            f"substituting here would corrupt the command."
        )
    positionals[position] = verification_mode
    return tuple(positionals)


def build_command(
    rung: RungSpec,
    executable: Path,
    properties_path: Path,
    features_path: Path,
    vertices_path: Path,
    output_path: Path,
    manifest_path: Path | None = None,
    query_stats_path: Path | None = None,
    rmi_model_path: Path | None = None,
    rmi_probes: str | None = None,
    verification_mode: str | None = None,
) -> list[str]:
    """Assemble one benchmark-eligible invocation.

    Raises if the result would not be eligible, or if a rung that needs the
    model or its probe records was not given them. The RMI probe string must be
    derived from the model manifest by ``rmi_probe_args.probe_argument`` and
    never transcribed (Nucleus 18.20).
    """
    command = [
        str(Path(executable).resolve()),
        str(Path(properties_path).resolve()),
        str(Path(features_path).resolve()),
        str(Path(vertices_path).resolve()),
        str(Path(output_path).resolve()),
        *verification_positionals(rung, verification_mode),
    ]

    if rung.wants_manifest:
        if manifest_path is None:
            raise ValueError(f"{rung.name} requires a manifest path.")
        command.append(str(Path(manifest_path).resolve()))

    if rung.seed_mode is not None:
        command += ["--seed", rung.seed_mode]

    if rung.seed_mode == "rmi":
        if rmi_model_path is None or not rmi_probes:
            raise ValueError(
                f"{rung.name} requires --rmi-model and --rmi-probes; the probe "
                f"records are how the float contract is checked rather than "
                f"inherited."
            )
        command += [
            "--rmi-model",
            str(Path(rmi_model_path).resolve()),
            "--rmi-probes",
            rmi_probes,
        ]

    if rung.wants_query_stats:
        if query_stats_path is None:
            raise ValueError(
                f"{rung.name} requires --query-stats: the resolve-descent "
                f"counters are the quantity the 5-vs-4 claim rests on."
            )
        command += ["--query-stats", str(Path(query_stats_path).resolve())]

    assert_benchmark_eligible(command)
    return command


# ---------------------------------------------------------------------------
# scheduling
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScheduledRun:
    cell_key: str
    repetition: int
    is_warmup: bool
    block: int
    position: int


def blocked_schedule(
    cell_keys: Sequence[str],
    repetitions: Mapping[str, int],
    warmups: int = 1,
    rotate: bool = True,
) -> list[ScheduledRun]:
    """Order runs by repetition block, not by cell.

    A CELL is one (rung, workload, seed window) configuration. B6a ran one
    workload at one window so a cell was a rung; B6c runs a matrix, so the two
    are separated. Everything below is stated in cells.

    Running every repetition of one cell before every repetition of another
    would confound configuration with wall-clock time: thermal drift or a
    background task lands entirely on one cell. Blocking cannot remove drift; it
    spreads it over the things being compared.

    Repetition counts may differ per cell -- rung 1 costs ~19 minutes per
    countywide run against ~20 seconds for rung 4 -- so a cell stops appearing
    once its count is exhausted. ``n`` is recorded per cell.

    ``rotate`` cyclically shifts the within-block order by the block index. With
    a fixed order, position within the block is confounded with the cell: the
    cell that always runs first is always measured on the coldest machine, and
    B6a measured rung 1's three countywide repetitions rising monotonically
    within a sitting, so that effect is real here. Rotation is deterministic,
    reproducible from the block index alone, and PRESERVES RELATIVE ADJACENCY --
    rungs 4 and 5 stay neighbours under a cyclic shift except at the one wrap
    point per cycle -- so the within-invocation ratio argument survives it.
    """
    schedule: list[ScheduledRun] = []

    for warmup_index in range(warmups):
        for position, key in enumerate(cell_keys):
            schedule.append(
                ScheduledRun(key, -(warmup_index + 1), True, 0, position)
            )

    highest = max(repetitions[key] for key in cell_keys)
    for block in range(1, highest + 1):
        participating = [
            key for key in cell_keys if block <= repetitions[key]
        ]
        if rotate and participating:
            shift = (block - 1) % len(participating)
            participating = (
                participating[shift:] + participating[:shift]
            )
        for position, key in enumerate(participating):
            schedule.append(
                ScheduledRun(key, block, False, block, position)
            )

    return schedule


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------

def run_once(
    rung: RungSpec,
    command: Sequence[str],
    output_path: Path,
    query_stats_path: Path | None = None,
) -> dict[str, Any]:
    """Run one invocation, capture stdout to a pipe, and record what it cost."""
    assert_benchmark_eligible(command)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    started = time.perf_counter()
    with subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        standard_output, standard_error = process.communicate()
        total_process_seconds = time.perf_counter() - started
        return_code = process.returncode
        peak_bytes, peak_commit, peak_method = peak_memory(process)

    if return_code != 0:
        raise RuntimeError(
            f"{rung.name} exited {return_code}.\n\n"
            f"stdout:\n{standard_output}\n\nstderr:\n{standard_error}"
        )
    if not output_path.exists():
        raise RuntimeError(f"{rung.name} produced no output at {output_path}.")

    metrics = parse_ladder_output(standard_output, rung)
    metrics.update(
        {
            "total_process_seconds": total_process_seconds,
            "peak_working_set_bytes": peak_bytes,
            "peak_commit_bytes": peak_commit,
            "peak_memory_method": peak_method,
            "output_sha256": sha256_file(output_path),
            "output_size_bytes": output_path.stat().st_size,
        }
    )

    if query_stats_path is not None:
        metrics.update(_merge_query_stats(Path(query_stats_path), metrics))

    return metrics


def _merge_query_stats(
    query_stats_path: Path, metrics: Mapping[str, Any]
) -> dict[str, Any]:
    """Fold the ``--query-stats`` JSON in, and cross-check it against stdout.

    ``query_seconds`` in the JSON and the computation seconds on stdout are the
    same clock written twice. Disagreement means the two reports were not
    produced by the same run, which is worth failing on rather than averaging.
    """
    report = json.loads(query_stats_path.read_text(encoding="utf-8"))

    if not report.get("benchmark_eligible", False):
        raise BenchmarkIneligibleError(
            f"{query_stats_path} reports benchmark_eligible=false."
        )

    query_seconds = float(report["query_seconds"])
    computation_seconds = float(metrics["computation_seconds"])
    if abs(query_seconds - computation_seconds) > 1e-6:
        raise RuntimeError(
            f"{query_stats_path}: query_seconds {query_seconds} disagrees with "
            f"stdout computation seconds {computation_seconds}."
        )

    reported_window = int(report["seed_window_entries"])
    stdout_window = metrics.get("seed_window_entries_stdout")
    if stdout_window is not None and int(stdout_window) != reported_window:
        raise RuntimeError(
            f"{query_stats_path}: seed_window_entries {reported_window} "
            f"disagrees with the {stdout_window} the same run printed. The "
            f"stats file and the stdout did not come from one binary."
        )

    resolve = report["resolve_descent"]
    tight = report["tight_descent"]
    quality = report["seed_quality"]

    return {
        "seed_window_entries": reported_window,
        "qs_resolve_entries_per_property": float(resolve["entries_per_property"]),
        "qs_resolve_nodes_per_property": float(resolve["nodes_per_property"]),
        "tight_entries_per_property": float(tight["entries_per_property"]),
        "tight_nodes_per_property": float(tight["nodes_per_property"]),
        "fraction_window_missed": float(quality["fraction_window_missed"]),
        "mean_d_seed_over_d_best": float(quality["mean_d_seed_over_d_best"]),
        "max_d_seed_over_d_best": float(quality["max_d_seed_over_d_best"]),
        "qs_phase2_segment_checks_per_property": float(
            report["phase2_segment_checks_per_property"]
        ),
    }


# ---------------------------------------------------------------------------
# summarising
# ---------------------------------------------------------------------------

class RunRecorder:
    """Append every completed run to a JSON-lines sidecar, immediately.

    B6c is a multi-hour invocation. Buffering results in memory and writing one
    CSV at the end means an interruption at run 200 of 250 discards 200 runs and
    the machine state that produced them, which cannot be recovered by rerunning
    -- B6a measured an 11 percent shift in rung 1 between two sittings, so a
    partial rerun is not the same experiment.

    JSON lines rather than CSV because the schema is ragged: rung 1 emits no
    descent counters and only rungs 4 and 5 emit seed quality, so the CSV header
    is not knowable until every rung has run once. The CSV is written at the end
    from the accumulated records; the sidecar is the crash-safe copy and the
    input to ``--resume``.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []

    def load_existing(self) -> list[dict[str, Any]]:
        """Read a previous invocation's records, for --resume."""
        if not self.path.exists():
            return []
        recovered: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    recovered.append(json.loads(line))
                except json.JSONDecodeError as error:
                    # A truncated final line is the expected shape of a crash.
                    raise ValueError(
                        f"{self.path}:{line_number} is not valid JSON. If this "
                        f"is the last line, the previous invocation died "
                        f"mid-write; delete that line and resume."
                    ) from error
        self.records = list(recovered)
        return recovered

    def append(self, record: Mapping[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(record), default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.records.append(dict(record))

    def completed(self) -> set[tuple[str, int]]:
        """``(cell_key, repetition)`` pairs already recorded."""
        return {
            (record["cell_key"], int(record["repetition"]))
            for record in self.records
            if "cell_key" in record and "repetition" in record
        }


DETERMINISTIC_COUNTERS: tuple[str, ...] = (
    "average_segment_checks_per_property",
    "average_seed_probes_per_property",
    "resolve_entries_per_property",
    "tight_entries_per_property",
    "n_true_r_per_property",
    "n_disk_infl_per_property",
    "n_decomp_per_property",
    "resolve_nodes_per_property",
    "geometric_inflation_capped",
    "mean_d_seed_over_d_best",
)


def dispersion(values: Sequence[float]) -> dict[str, Any]:
    """Summarise repeated timings without over-claiming at small n.

    At n = 3 a standard deviation is a number that looks like a measurement and
    is not one, so it is omitted rather than reported. Relative spread is
    ``(max - min) / median``, directly comparable with the 3.85 percent B5c
    measured between two runs of the same configuration.
    """
    ordered = sorted(float(value) for value in values)
    count = len(ordered)
    if count == 0:
        raise ValueError("dispersion() requires at least one value.")

    median = statistics.median(ordered)
    summary: dict[str, Any] = {
        "n": count,
        "minimum": ordered[0],
        "median": median,
        "maximum": ordered[-1],
        "relative_spread": (ordered[-1] - ordered[0]) / median if median else None,
    }
    summary["standard_deviation"] = (
        statistics.stdev(ordered) if count >= 5 else None
    )
    summary["standard_deviation_withheld_reason"] = (
        None if count >= 5 else f"n={count} does not support a dispersion statistic"
    )
    return summary


def summarize_cell(
    runs: Sequence[Mapping[str, Any]],
    allow_multiple_sessions: bool = False,
) -> dict[str, Any]:
    """Summarise the timed runs of one (rung, workload, window, seed) cell.

    Also asserts the two determinism properties every prior chunk asserted:
    identical output bytes across repetitions, and identical values for the
    counters that are deterministic by construction. A counter that drifts
    between repetitions of the same configuration is a defect, not noise.
    """
    timed = [run for run in runs if not run.get("is_warmup", False)]
    if not timed:
        raise ValueError("summarize_cell() received no timed runs.")

    sessions = {
        run.get("session_id") for run in timed if run.get("session_id")
    }
    if len(sessions) > 1 and not allow_multiple_sessions:
        raise RuntimeError(
            f"This cell's repetitions span {len(sessions)} invocations: "
            f"{sorted(sessions)}. B6a measured an 11 percent shift in rung 1 "
            f"between two sittings of an identical configuration, so a median "
            f"over sessions is a median over machine states. Rerun the cell, "
            f"or pass allow_multiple_sessions and record the caveat."
        )

    digests = {run["output_sha256"] for run in timed}
    if len(digests) != 1:
        raise RuntimeError(
            f"Repetitions of one configuration produced different output bytes: "
            f"{sorted(digests)}"
        )

    counter_values: dict[str, Any] = {}
    for counter in DETERMINISTIC_COUNTERS:
        present = {run[counter] for run in timed if counter in run}
        if not present:
            continue
        if len(present) != 1:
            raise RuntimeError(
                f"Deterministic counter {counter} varied across repetitions: "
                f"{sorted(present)}"
            )
        counter_values[counter] = present.pop()

    first = timed[0]
    summary: dict[str, Any] = {
        "algorithm": first["algorithm"],
        "rung": first["rung"],
        "sessions": sorted(sessions),
        "output_sha256": digests.pop(),
        "computation_seconds": dispersion(
            [run["computation_seconds"] for run in timed]
        ),
        "total_process_seconds": dispersion(
            [run["total_process_seconds"] for run in timed]
        ),
        "deterministic_counters": counter_values,
    }

    for memory_field in ("peak_working_set_bytes", "peak_commit_bytes"):
        peaks = [
            run[memory_field]
            for run in timed
            if run.get(memory_field) is not None
        ]
        summary[memory_field] = dispersion(peaks) if peaks else None
    summary["peak_memory_method"] = first.get("peak_memory_method")

    for byte_field in ("index_bytes", "key_array_bytes", "rmi_model_bytes"):
        if byte_field in first:
            summary[byte_field] = first[byte_field]

    return summary


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def total_physical_memory_bytes() -> int | None:
    """Installed RAM, or ``None`` where it cannot be read."""
    if sys.platform != "win32":
        try:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, AttributeError, OSError):
            return None
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    try:
        kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined]
    except OSError:
        return None
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPhys)


def parse_expected_digests(specifications: Sequence[str]) -> dict[str, str]:
    """Parse ``rung=sha256`` or ``rung@workload=sha256`` pairs into a mapping.

    The workload-qualified form exists because B6c runs a matrix: the correct
    output digest differs per workload, while a window sweep at one workload
    wants a single digest applying to every window. Lookup prefers the
    qualified key.
    """
    expected: dict[str, str] = {}
    for specification in specifications:
        if "=" not in specification:
            raise ValueError(
                f"Expected 'rung=sha256' or 'rung@workload=sha256', "
                f"received {specification!r}."
            )
        name, digest = specification.split("=", maxsplit=1)
        name = name.strip()
        digest = digest.strip().lower()
        rung_part = name.split("@", maxsplit=1)[0]  # rung, rung@workload, or cell key
        if rung_part not in LADDER_BY_NAME:
            raise ValueError(f"Unknown rung in --expect-digest: {rung_part!r}.")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"Not a SHA-256 hex digest: {digest!r}.")
        expected[name] = digest
    return expected


def expected_digest_for(
    rung_name: str,
    workload: str,
    expected: Mapping[str, str],
    cell_key: str | None = None,
    allow_unqualified: bool = True,
) -> str | None:
    """Most specific match: full cell key, then ``rung@workload``, then ``rung``.

    The fallback is legitimate across a BYTE-NEUTRAL dimension and illegitimate
    across a byte-changing one, and the ladder has one of each:

    - The seed window is byte-neutral. B6b proved it at nine window sizes on two
      workloads: every emitted counter comes from the tight descent, which is
      seed-invariant, and the only seed-dependent columns do not vary with window
      size. So one ``hilbert_binary=<digest>`` correctly gates all nine windows.
    - The verification mode is NOT byte-neutral. B2 measured 8.82e-10 to 9.17e-10
      m under split against 4.658e-10 under original, so Option A and Option B
      outputs differ by design.

    ``allow_unqualified`` encodes that distinction. A bare ``rung`` or
    ``rung@workload`` key means "the canonical answer," which is the DEFAULT
    verification mode by definition; a non-default cell must be named explicitly
    by its full cell key or it carries no expectation. Without this, B6c-2's
    Option B cells inherited the Option A digests and failed on the first run.
    """
    if cell_key and cell_key in expected:
        return expected[cell_key]
    if not allow_unqualified:
        return None
    qualified = f"{rung_name}@{workload}"
    if qualified in expected:
        return expected[qualified]
    return expected.get(rung_name)


def assert_expected_digest(
    rung_name: str,
    measured: str,
    expected_by_rung: Mapping[str, str],
    workload: str = "",
    cell_key: str | None = None,
    allow_unqualified: bool = True,
) -> None:
    """Fail a run whose output does not reproduce a known-good digest.

    The seed window is byte-neutral: every emitted counter comes from the tight
    descent, which is seed-invariant, and the only seed-dependent columns are
    ``cpp_seed_probes`` and ``seed_mode``, neither of which varies with window
    size. So each of B6b's fourteen builds must reproduce one of exactly two
    countywide digests, and exactness is re-proved at every point of the sweep
    at no cost. A build that does not is either mis-built or non-neutral, and
    either way its timings are meaningless.
    """
    expected = expected_digest_for(
        rung_name, workload, expected_by_rung, cell_key, allow_unqualified
    )
    if expected is None:
        return
    if measured.lower() != expected.lower():
        raise RuntimeError(
            f"{cell_key or rung_name}: output sha256 {measured} does not match "
            f"the expected {expected}. Every dimension this digest is asserted "
            f"across is byte-neutral, so this is a changed answer rather than a "
            f"changed cost. If the configuration legitimately changes the bytes "
            f"-- a different verification mode does -- name the cell key "
            f"explicitly instead of the rung."
        )


def machine_record(
    power_source: str,
    power_plan: str,
    notes: str = "",
    cpu_model: str | None = None,
    physical_cores: int | None = None,
) -> dict[str, Any]:
    """Record the machine state the protocol declares, so it lands in the manifest.

    A wall-clock figure without the machine that produced it is not
    reproducible, and this project's own numbers already show why: B5c measured
    3.85 percent spread between two runs of one configuration, which is the
    order of the effects being claimed.

    ``cpu_model`` and ``physical_cores`` are operator-declared, because neither
    the marketing name nor the physical core count is available from the
    standard library. Everything else is queried. Fields that could not be read
    are recorded as null rather than guessed.
    """
    uname = platform.uname()
    return {
        "cpu_model_declared": cpu_model,
        "physical_cores_declared": physical_cores,
        "processor_identifier": os.environ.get("PROCESSOR_IDENTIFIER"),
        "processor": platform.processor(),
        "logical_processors": os.cpu_count(),
        "total_physical_memory_bytes": total_physical_memory_bytes(),
        "operating_system": uname.system,
        "operating_system_release": uname.release,
        "operating_system_version": uname.version,
        "machine": uname.machine,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "power_source": power_source,
        "power_plan": power_plan,
        "notes": notes,
    }