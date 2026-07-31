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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

TOOL_VERSION = "caprm.pipeline_cost/c4.0"

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
            "normalization, the hydrography GeoPackage sha256 and its read, DEM "
            "open, and the evidence/terrain CSV reads"
        ),
        "compute_s": "the per-property kernel call only, timed with perf_counter",
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