"""C4 item 2. What the exact pipeline costs — staging and the declared boundary.

This module holds two things that must exist BEFORE any stage is timed.

**The boundary.** A wall clock without a declared boundary is not a
measurement, and a boundary written after the numbers are in is not a
declaration. :data:`TIMING_BOUNDARY` therefore lives in source, is committed
before the first timing run, and is copied verbatim into every artifact the
harness writes. Four choices, each with the reason it was made: warm or cold,
what counts as inside, marginal or total, and which stages are counted.

**The nesting gate.** The FEMA and nearest-water stages select their workload by
config YAML. Nothing downstream of the evidence merge does:
``build_terrain_evidence.py`` and ``build_exposure_index.py`` are shaped around
the countywide evidence product and have no workload flag. Re-running
``build_property_evidence.py`` to manufacture one would pull its
``{brute_force, feature_bvh}`` assertion into the timing path and put two more
evidence products beside frozen ones, so the harness subsets the countywide
evidence instead.

That substitution is only sound if the smaller workloads really are subsets.
``ingest.build_nested_property_sample`` builds each sample as the regression set
plus a ``head()`` of one deterministic ordering, so 10,000 within 100,000 holds
by construction. **Countywide is materialised by a different script and carries
no such guarantee**, which is why :func:`nesting_report` checks that link first
and raises rather than warning. Subsetting is by ``property_id`` and never by
``sample_order``, which is per-workload and renumbered from zero in every build.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from caprm.c4_benchmark import TimingResult, timed_repeats

TOOL_VERSION = "caprm.pipeline_cost/c4.0"

#: Every timed cell must carry a spread. One repeat is a diagnostic, not a
#: measurement (18.32), and a TimingResult built from a single sample reports a
#: relative spread of 0.0, which reads as perfect precision and is the opposite
#: of what it means. The harness refuses rather than relying on a reader to
#: notice n_repeat.
MINIMUM_REPEATS = 2

KEY_COLUMN = "property_id"

#: Everything the harness writes goes here. Not outputs/evidence, not
#: outputs/index, not outputs/validation/*_manifest.json. A benchmark that
#: silently regenerates the products it was measuring has destroyed the thing
#: it measured, and the defence is a path that cannot collide by construction.
SCRATCH_DIRECTORY = "outputs/scratch/c4"


TIMING_BOUNDARY: dict[str, Any] = {
    "declared_in_source_before_any_run": True,
    "warm_or_cold": {
        "choice": "warm",
        "detail": (
            "Caches are staged and every stage gets one discarded warm-up "
            "invocation at each workload size before the timed repeats."
        ),
        "not_claimed": (
            "Cold start is a different number. C4 does not measure it and does "
            "not claim it."
        ),
    },
    "what_is_inside": {
        "choice": "two columns, reported separately",
        "setup_s": (
            "config load, cached property GeoJSON read, NFHL shapefile read, CRS "
            "normalization, the hydrography GeoPackage sha256 and its read, and "
            "the evidence/terrain CSV reads"
        ),
        "compute_s": "the per-property kernel call only, timed with perf_counter",
        "correction_2026_07_30": (
            "An earlier draft placed the DEM open in setup_s. It is not there "
            "and cannot be: caprm.terrain.build_terrain_evidence takes a raster "
            "PATH and opens it internally, so for the terrain stage the raster "
            "open, its window reads and its close all fall inside compute_s. "
            "Corrected BEFORE any timing run. This is one reason the terrain "
            "stage is expected to carry a large fixed term a, and the fit must "
            "not be read as though a were pure per-row overhead."
        ),
        "why": (
            "A reader wants the marginal cost and the total, and they differ by "
            "a large factor. run_water_baseline.py digests a 21.2 MB GeoPackage "
            "on every invocation; that is a fixed I/O cost of the shipped CLI "
            "and not a cost of the algorithm."
        ),
    },
    "marginal_or_total": {
        "choice": "both, via a + b*N fitted over three workload sizes",
        "a": "fixed cost in seconds, independent of property count",
        "b": "marginal cost in seconds per additional property",
        "why": (
            "Total seconds over properties is not the marginal cost of one more "
            "property when setup is fixed."
        ),
        "caveat": (
            "Three points is the MINIMUM for a linearity claim, not a "
            "comfortable number of them. The residual is reported with the fit; "
            "a fit reported without its residual is an assertion that the model "
            "is linear."
        ),
    },
    "stages_timed": [
        {
            "stage": "fema_point_in_polygon",
            "entry_point": "caprm.baseline.run_fema_point_in_polygon",
            "workload_selection": "config YAML",
        },
        {
            "stage": "nearest_water_python",
            "entry_point": "caprm.water_distance.nearest_water_reference",
            "workload_selection": "config YAML",
        },
        {
            "stage": "terrain_sampling",
            "entry_point": "caprm.terrain.build_terrain_evidence",
            "workload_selection": "scratch subset of the countywide evidence CSV",
        },
        {
            "stage": "scoring",
            "entry_point": "caprm.scoring.build_exposure_index",
            "workload_selection": "scratch subsets of the evidence and terrain CSVs",
        },
    ],
    "stages_cited_not_measured": [
        {
            "stage": "nearest_water_cpp",
            "source": "outputs/validation/b6_analysis.json, docs/benchmark_results.md",
            "operating_point": "25 m entry-extent cap, original verification, disk predicate",
            "why": (
                "B6 already measured it at the shipped operating point. "
                "Re-running it here would add a second measurement of the same "
                "thing under a different harness. B1's cap=100 figures belong to "
                "a different operating point and are not quoted."
            ),
        }
    ],
    "stages_skipped": [
        {"stage": "property_cache_refresh", "why": "network; --refresh-properties is never passed"},
        {
            "stage": "evidence_merge",
            "script": "build_property_evidence.py",
            "why": (
                "It asserts the water benchmark summary's algorithm set and has "
                "no workload flag. Subsetting replaces it, so it is outside the "
                "boundary and named here rather than silently omitted."
            ),
        },
        {"stage": "cpp_input_export", "why": "export is not part of the per-property computation"},
        {"stage": "figure_generation", "why": "presentation, not pipeline"},
        {"stage": "cpp_compilation", "why": "build cost, measured nowhere in this project"},
    ],
    "two_clocks": {
        "in_process_s": "perf_counter around the library call, inside one interpreter",
        "process_wall_clock_s": (
            "the shipped CLI run as a subprocess, including interpreter startup "
            "and the geopandas import"
        ),
        "why_both": (
            "Interpreter startup plus the geopandas import is a real fixed cost "
            "of the shipped CLI and a meaningless fixed cost of the algorithm. "
            "Both belong in the table, labelled."
        ),
    },
}


class PipelineCostError(RuntimeError):
    """Raised when a staging precondition fails. Never downgraded to a warning."""


# ---------------------------------------------------------------------------
# workloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Workload:
    """One workload size, and where both sides of the pipeline read it from."""

    name: str
    config: str
    property_points: str
    expected_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "config": self.config,
            "property_points": self.property_points,
            "expected_rows": self.expected_rows,
        }


WORKLOADS: tuple[Workload, ...] = (
    Workload(
        name="10000",
        config="configs/monroe_fema_spike_10000.yaml",
        property_points="data/processed/monroe_property_points_sample_10000.geojson",
        expected_rows=10_000,
    ),
    Workload(
        name="100000",
        config="configs/monroe_fema_spike_100000.yaml",
        property_points="data/processed/monroe_property_points_sample_100000.geojson",
        expected_rows=100_000,
    ),
    Workload(
        name="countywide",
        config="configs/monroe_fema_spike_countywide.yaml",
        property_points="data/processed/monroe_property_points_countywide.geojson",
        expected_rows=267_362,
    ),
)


def sha256_file(path: str | Path, chunk_bytes: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# the nesting gate
# ---------------------------------------------------------------------------


def property_ids(frame: pd.DataFrame, source: str) -> pd.Index:
    """The ``property_id`` column as an index, refusing duplicates.

    A duplicated key would let a subset appear nested while carrying a
    different number of rows than its id set, which is the failure this
    function exists upstream of.
    """
    if KEY_COLUMN not in frame.columns:
        raise PipelineCostError(
            f"{source} has no {KEY_COLUMN!r} column; available: {sorted(frame.columns)[:12]}"
        )
    ids = pd.Index(frame[KEY_COLUMN].astype("string"))
    if ids.has_duplicates:
        duplicated = int(ids.duplicated().sum())
        raise PipelineCostError(f"{source} has {duplicated} duplicated {KEY_COLUMN} values")
    return ids


def assert_nested(
    subset: pd.Index, superset: pd.Index, subset_name: str, superset_name: str
) -> dict[str, Any]:
    """``subset`` must be contained in ``superset``. Raises, never warns."""
    missing = subset.difference(superset)
    record = {
        "subset": subset_name,
        "superset": superset_name,
        "n_subset": int(len(subset)),
        "n_superset": int(len(superset)),
        "n_missing_from_superset": int(len(missing)),
        "nested": bool(len(missing) == 0),
        "examples_missing": [str(value) for value in missing[:5]],
    }
    if not record["nested"]:
        raise PipelineCostError(
            f"{subset_name} is not contained in {superset_name}: "
            f"{record['n_missing_from_superset']} of {record['n_subset']} ids are absent. "
            "Subsetting the countywide evidence would silently measure a different "
            "property set than the config-selected workloads do."
        )
    return record


def nesting_report(id_sets: dict[str, pd.Index]) -> dict[str, Any]:
    """Check the link that can fail first, then the one guaranteed by construction.

    100,000 within countywide is checked first and deliberately: countywide is
    materialised by a different script than the nested samples and shares none
    of their ordering guarantee. 10,000 within 100,000 follows from two
    ``head()`` calls on one deterministic ordering and is checked anyway,
    because a guarantee that is never exercised is a guarantee nobody has
    tested.
    """
    missing = [name for name in ("10000", "100000", "countywide") if name not in id_sets]
    if missing:
        raise PipelineCostError(f"nesting check needs id sets for {missing}")
    return {
        "checked_first_because_it_can_fail": assert_nested(
            id_sets["100000"], id_sets["countywide"], "100000", "countywide"
        ),
        "guaranteed_by_construction_checked_anyway": assert_nested(
            id_sets["10000"], id_sets["100000"], "10000", "100000"
        ),
        "subset_key": KEY_COLUMN,
        "never_subset_by": (
            "sample_order, which is per-workload and renumbered from zero in "
            "every build"
        ),
    }


# ---------------------------------------------------------------------------
# scratch subsets
# ---------------------------------------------------------------------------


def subset_by_ids(frame: pd.DataFrame, ids: Sequence[str] | pd.Index, source: str) -> pd.DataFrame:
    """Rows whose ``property_id`` is in ``ids``, with column order preserved.

    Row order follows the source frame rather than ``ids`` so the subset is a
    contiguous restriction of the countywide product, not a reordering of it.
    """
    wanted = pd.Index(pd.Series(list(ids), dtype="string"))
    if wanted.has_duplicates:
        raise PipelineCostError("id set contains duplicates")
    available = property_ids(frame, source)
    absent = wanted.difference(available)
    if len(absent):
        raise PipelineCostError(
            f"{len(absent)} of {len(wanted)} requested ids are absent from {source}"
        )
    selected = frame.loc[available.isin(wanted)].copy()
    if len(selected) != len(wanted):
        raise PipelineCostError(
            f"subset of {source} has {len(selected)} rows for {len(wanted)} ids"
        )
    return selected


def write_subsets(
    frame: pd.DataFrame,
    id_sets: dict[str, pd.Index],
    output_directory: str | Path,
    stem: str,
    source: str,
) -> dict[str, dict[str, Any]]:
    """Write one scratch CSV per workload, and record what was written."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, dict[str, Any]] = {}
    for name, ids in id_sets.items():
        subset = subset_by_ids(frame, ids, source)
        path = directory / f"{stem}_{name}.csv"
        subset.to_csv(path, index=False)
        written[name] = {
            "path": str(path),
            "rows": int(len(subset)),
            "columns": int(subset.shape[1]),
            "sha256": sha256_file(path),
        }
    return written


def boundary_manifest(
    nesting: dict[str, Any],
    subsets: dict[str, Any],
    inputs: dict[str, Any],
    generated_utc: str,
) -> dict[str, Any]:
    """The artifact that must be committed before a single stage is timed."""
    return {
        "task": "C4_item2_pipeline_cost_boundary",
        "schema_version": "c4_pipeline_boundary_v1",
        "tool_version": TOOL_VERSION,
        "generated_utc": generated_utc,
        "timing_boundary": TIMING_BOUNDARY,
        "workloads": [workload.to_dict() for workload in WORKLOADS],
        "nesting": nesting,
        "scratch_subsets": subsets,
        "inputs": inputs,
        "scratch_directory": SCRATCH_DIRECTORY,
        "frozen_paths_not_written": [
            "outputs/evidence/property_flood_evidence_countywide.csv",
            "outputs/evidence/property_terrain_evidence_countywide.csv",
            "outputs/index/property_exposure_index_countywide.csv",
            "outputs/validation/property_terrain_evidence_countywide_manifest.json",
            "outputs/validation/property_exposure_index_countywide_manifest.json",
            "outputs/validation/water_cpp_benchmark_summary.json",
            "outputs/validation/water_bruteforce_agreement.csv",
        ],
    }


# ---------------------------------------------------------------------------
# the harness
# ---------------------------------------------------------------------------


def assert_under_scratch(path: str | Path, scratch_root: str | Path) -> Path:
    """Refuse any output path that is not inside the scratch directory.

    The single failure this project cannot undo by re-running is a benchmark
    that regenerates the artifact it was measuring. ``git status`` catches it
    afterwards; this catches it before. It is a cheap check against an
    expensive mistake, and it has already happened once in this repository —
    ``compare_python_cpp_water.py --detail-output`` defaults to the 1,000-
    property regression fixture and overwrote it at the 100,000 workload.
    """
    resolved = Path(path).resolve()
    root = Path(scratch_root).resolve()
    if not resolved.is_relative_to(root):
        raise PipelineCostError(
            f"refusing to write outside the scratch directory:\n  path {resolved}\n  root {root}"
        )
    return resolved


def time_stage_in_process(
    setup: Callable[[], Any],
    compute: Callable[[Any], Any],
    n_setup_repeats: int = 2,
    n_compute_repeats: int = 3,
    n_warmup: int = 1,
) -> dict[str, Any]:
    """Time setup and per-property computation separately, in one interpreter.

    ``setup`` is re-run for each of its repeats rather than hoisted: reading the
    NFHL shapefile is part of what setup costs, and timing it once while reusing
    the parsed result would measure the second read's page cache rather than the
    stage. Its repeat count is separate and lower because it is the expensive
    half to repeat and the cheap half to characterise.
    """
    for name, count in (("setup", n_setup_repeats), ("compute", n_compute_repeats)):
        if count < MINIMUM_REPEATS:
            raise PipelineCostError(
                f"{name} needs at least {MINIMUM_REPEATS} repeats; one repeat has no spread"
            )

    setup_timing, inputs = timed_repeats(setup, n_warmup=n_warmup, n_repeat=n_setup_repeats)
    compute_timing, result = timed_repeats(
        lambda: compute(inputs), n_warmup=n_warmup, n_repeat=n_compute_repeats
    )

    rows = None
    if hasattr(result, "__len__"):
        try:
            rows = int(len(result))
        except TypeError:  # pragma: no cover - defensive
            rows = None

    return {
        "setup_s": setup_timing.to_dict(),
        "compute_s": compute_timing.to_dict(),
        "setup_plus_compute_median_s": setup_timing.median + compute_timing.median,
        "compute_fraction_of_setup_plus_compute": (
            compute_timing.median / (setup_timing.median + compute_timing.median)
            if (setup_timing.median + compute_timing.median) > 0
            else float("nan")
        ),
        "result_rows": rows,
    }


def time_process_wall_clock(
    command: Sequence[str],
    cwd: str | Path,
    n_repeats: int = 2,
    n_warmup: int = 1,
) -> dict[str, Any]:
    """Time the shipped CLI as a subprocess, failures included rather than hidden.

    This clock contains interpreter startup and the geopandas import, which are
    a real fixed cost of the shipped CLI and a meaningless fixed cost of the
    algorithm. Both belong in the table, labelled, which is why it is measured
    beside the in-process figure rather than instead of it.
    """
    if n_repeats < MINIMUM_REPEATS:
        raise PipelineCostError(f"process timing needs at least {MINIMUM_REPEATS} repeats")

    def run() -> int:
        completed = subprocess.run(
            list(command), cwd=str(cwd), capture_output=True, text=True
        )
        if completed.returncode != 0:
            raise PipelineCostError(
                "stage command failed:\n  "
                + " ".join(command)
                + f"\n  exit {completed.returncode}\n  {completed.stderr[-2000:]}"
            )
        return completed.returncode

    timing, _ = timed_repeats(run, n_warmup=n_warmup, n_repeat=n_repeats)
    return {"command": list(command), "process_wall_clock_s": timing.to_dict()}


def fit_linear(n_values: Sequence[float], seconds: Sequence[float]) -> dict[str, Any]:
    """Least-squares ``a + b*N``, reported with the residual that qualifies it.

    A fit reported without its residual is an assertion that the model is
    linear. Three points fit two parameters with one degree of freedom left,
    which is the minimum for the claim and is stated as the minimum rather than
    presented as a fit.

    No R^2. With three points it is trivially near 1.0 for almost any monotone
    data and would read as corroboration it cannot supply. The per-point
    residual as a fraction of the observed value is the honest summary, because
    it is the quantity a reader would use to decide whether ``b`` means
    anything.
    """
    n_array = np.asarray(n_values, dtype=np.float64)
    y_array = np.asarray(seconds, dtype=np.float64)
    if n_array.shape != y_array.shape:
        raise PipelineCostError("N and seconds must be the same length")
    if n_array.size < 3:
        raise PipelineCostError("a + b*N needs at least three workload sizes")

    design = np.column_stack([np.ones_like(n_array), n_array])
    solution, *_ = np.linalg.lstsq(design, y_array, rcond=None)
    intercept, slope = float(solution[0]), float(solution[1])
    predicted = design @ solution
    residuals = y_array - predicted
    relative = np.divide(
        np.abs(residuals), y_array, out=np.full_like(residuals, np.nan), where=y_array != 0
    )

    return {
        "a_fixed_s": intercept,
        "b_marginal_s_per_property": slope,
        "b_marginal_us_per_property": slope * 1e6,
        "n_points": int(n_array.size),
        "n_values": [float(value) for value in n_array],
        "observed_s": [float(value) for value in y_array],
        "predicted_s": [float(value) for value in predicted],
        "residual_s": [float(value) for value in residuals],
        "residual_fraction_of_observed": [float(value) for value in relative],
        "max_abs_residual_fraction": float(np.nanmax(relative)),
        "three_points_is_the_minimum": bool(n_array.size == 3),
        "caveat": (
            "Three points fit two parameters. The residual qualifies the "
            "linearity claim; it does not confirm it."
        ),
    }


def append_run_record(path: str | Path, record: dict[str, Any]) -> None:
    """Append one cell to the JSONL run log, so a crash costs one cell.

    Mirrors B6's ``water_ladder_runs_*.jsonl`` convention: the run log is the
    measurement of record and the analysis reads it, so a long benchmark can be
    split across invocations and resumed without any cell being recomputed
    under different conditions than its neighbours.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=float) + "\n")


def read_run_records(path: str | Path) -> list[dict[str, Any]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def fit_stage(records: Sequence[dict[str, Any]], stage: str, clock: str) -> dict[str, Any]:
    """Fit one stage's chosen clock across every workload it was measured at."""
    cells = [record for record in records if record["stage"] == stage]
    if not cells:
        raise PipelineCostError(f"no records for stage {stage!r}")
    ordered = sorted(cells, key=lambda record: record["n_properties"])
    seconds = []
    for cell in ordered:
        block = cell.get(clock)
        if block is None:
            raise PipelineCostError(f"{stage} at N={cell['n_properties']} has no {clock!r}")
        seconds.append(block["median_s"])
    fit = fit_linear([cell["n_properties"] for cell in ordered], seconds)
    fit["stage"] = stage
    fit["clock"] = clock
    fit["workloads"] = [cell["workload"] for cell in ordered]
    return fit