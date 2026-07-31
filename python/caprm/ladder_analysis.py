"""Derive PHASE B's reported quantities from the B6 benchmark artifacts.

Every number this project reports about the five-rung ladder is computed here
from ``outputs/benchmark/water_ladder_runs_*.csv``, and nowhere else. The rule
this module exists to enforce is Roadmap section 8: do not rely on private chat
history to explain how a result was produced. An analysis performed in
conversation and pasted into a document is unreproducible even when it is
correct, and it cannot follow a regenerated measurement.

What is a measurement and what is a derivation
----------------------------------------------
The runs CSV is the measurement. Everything below is a derivation from it:
adjacent comparisons, the per-property curve, the cost model, the memory
attribution. Re-running the measurement and re-running this module must produce
a consistent pair; that is the property the split buys.

Resolvability
-------------
B6c measured cell-to-cell spreads of 4.6 to 14.2 percent at countywide, against
effects as small as 6.5 percent. A ratio whose gap is inside the noise is
reported WITH that fact attached rather than quietly. Two criteria are emitted:

  conservative   gap exceeds the full range (max - min) of both cells
  z              gap divided by the combined standard error of the medians,
                 using 1.253 * sd / sqrt(n) as the median's standard error

Neither is a significance test. They are there so a number that cannot carry a
claim is never printed as though it can.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

# B5c isolated the marginal cost of one resolve-descent entry by an independent
# measurement. It is a MEASURED CONSTANT with provenance, not a fitted parameter
# of this module, and the point of the cost model below is that a constant
# measured one way predicts wall clock measured another.
B5C_NANOSECONDS_PER_RESOLVE_ENTRY = 20.40
B5C_PROVENANCE = (
    "Current Status B5c: marginal cost of one resolve-descent entry, "
    "measured in isolation before any B6 timing existed."
)

BRUTE_FORCE_SEGMENT_CHECKS_PER_PROPERTY = 1_063_159.0

# Mirrored from ``caprm.ladder_benchmark`` rather than imported, so that the
# analysis module stays free of the harness's Win32 memory structures. The
# duplication is not left to trust: ``tests/test_ladder_analysis.py`` asserts
# these two names equal the harness's. Rungs 1-2 have no verification-mode
# argument -- brute force scans original segments and the feature BVH rescans
# each candidate feature's original geometry -- so their column is EMPTY in the
# runs CSV and pandas reads it as NaN. NaN is not "original" and is not equal to
# itself, so an ungrounded groupby on this column silently drops 3 v 2 at every
# workload. See ``normalize_verification_mode``.
VERIFICATION_MODES = ("original", "split")
DEFAULT_VERIFICATION_MODE = "original"

RUNG_ORDER = (
    "brute_force",
    "feature_bvh",
    "segment_bvh",
    "hilbert_binary",
    "hilbert_rmi",
)

# THE THREE adjacent comparisons. 2 v 1 is deliberately not among them: rung 1
# carries a 31.71 percent spread at n=3, five times any other cell, so its figure
# is an order-of-magnitude statement rather than a measurement and it belongs in
# no adjacent comparison (Current Status B6c). It is available separately as
# CONTEXT_PAIRS so that the table headed "three adjacent comparisons" contains
# three rows per cross-product cell and not four.
ADJACENT_PAIRS = (
    ("segment_bvh", "feature_bvh", "3 v 2", "granularity: feature -> segment"),
    ("hilbert_binary", "segment_bvh", "4 v 3", "dimensionality: 2D -> 1D"),
    ("hilbert_rmi", "hilbert_binary", "5 v 4", "machine learning: search -> model"),
)

CONTEXT_PAIRS = (
    ("feature_bvh", "brute_force", "2 v 1", "no index -> feature BVH"),
)

# Counters that must not vary between the two seeders at one workload and
# window. Seed choice changes where the descent starts, never what is computed.
SEED_INVARIANT_COUNTERS = (
    "average_segment_checks_per_property",
    "tight_entries_per_property",
    "n_true_r_per_property",
    "n_disk_infl_per_property",
    "geometric_inflation_capped",
)


# Counters and structural sizes that MUST reproduce across repetitions of one
# configuration. B6a established that every one of these is identical to the
# last digit across repetitions and across invocations, so variation is a defect
# and is raised rather than averaged.
DETERMINISTIC_COLUMNS = (
    "average_segment_checks_per_property",
    "average_candidate_features_per_property",
    "average_node_visits_per_property",
    "average_seed_probes_per_property",
    "resolve_entries_per_property",
    "resolve_nodes_per_property",
    "tight_entries_per_property",
    "n_true_r_per_property",
    "n_disk_infl_per_property",
    "geometric_inflation_capped",
    "fraction_window_missed",
    "mean_d_seed_over_d_best",
    "max_d_seed_over_d_best",
    "index_bytes",
    "key_array_bytes",
    "rmi_model_bytes",
)

# Quantities the OPERATING SYSTEM reports, not the program. Peak working set and
# peak commit are influenced by allocator behaviour, page-fault timing and
# working-set trimming under whatever else the machine was doing, so they vary
# between repetitions of an identical configuration -- B6a measured spreads of
# 0.05 to 0.43 percent. They are summarised, never asserted constant.
MEASURED_COLUMNS = (
    "peak_working_set_bytes",
    "peak_commit_bytes",
)


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_runs(path: Path) -> pd.DataFrame:
    """Load a runs CSV, drop warm-ups, and ground the verification mode."""
    frame = pd.read_csv(path)
    if "is_warmup" in frame.columns:
        warmup = frame["is_warmup"].astype(str).str.lower().isin({"true", "1"})
        frame = frame.loc[~warmup].copy()
    return normalize_verification_mode(frame)


def normalize_verification_mode(frame: pd.DataFrame) -> pd.DataFrame:
    """Fill the absent verification mode with the mode those rungs actually use.

    Rungs 1 and 2 have no verification-mode argument, so the harness writes
    nothing and pandas reads NaN. They nonetheless DO verify, over original
    geometry, by construction. Leaving the column NaN is not a neutral choice:
    every downstream grouping that includes the mode would place rung 2 in a NaN
    group and rung 3 in an "original" group, and 3 v 2 -- the comparison this
    phase considers most durable -- would vanish without an error.

    A value outside the known set raises rather than being carried, because the
    positional interface the harness substitutes into is the only thing that
    decides what the binary actually did.
    """
    frame = frame.copy()
    if "verification_mode" not in frame.columns:
        frame["verification_mode"] = DEFAULT_VERIFICATION_MODE
        return frame
    # A column that is entirely absent reads as float64, and assigning a string
    # into it raises on pandas 3. Cast first: this is the same dtype trap as the
    # seed-window column, one column over.
    frame["verification_mode"] = frame["verification_mode"].astype(object)
    column = frame["verification_mode"]
    blank = column.isna() | (column.astype(str).str.strip() == "")
    frame.loc[blank, "verification_mode"] = DEFAULT_VERIFICATION_MODE
    frame["verification_mode"] = frame["verification_mode"].astype(str).str.strip()
    unknown = sorted(set(frame["verification_mode"]) - set(VERIFICATION_MODES))
    if unknown:
        raise ValueError(
            f"Unknown verification mode(s) {unknown}; expected one of "
            f"{VERIFICATION_MODES}. The positional interface has changed and "
            f"grouping on this column would silently mix modes."
        )
    return frame


def cell_statistics(
    runs: pd.DataFrame, invocation: str | None = None
) -> pd.DataFrame:
    """Per-cell timing statistics and the cell's deterministic counters.

    Counters are asserted constant within a cell rather than averaged. B6a
    established that they reproduce to the last digit across repetitions and
    across invocations; averaging them would hide a defect instead of raising.
    """
    records: list[dict[str, Any]] = []
    for key, group in runs.groupby("cell_key", sort=False):
        seconds = group["computation_seconds"].astype(float)
        count = len(seconds)
        standard_deviation = float(seconds.std(ddof=1)) if count >= 2 else float("nan")
        record: dict[str, Any] = {
            "cell_key": key,
            "algorithm": group["algorithm"].iloc[0],
            "rung": int(group["rung"].iloc[0]),
            "workload": group["workload"].iloc[0],
            # Read from the COLUMN, never parsed out of cell_key. The key omits
            # "@original" so that B6c's recorded keys stay comparable across the
            # cross-product, which means the key alone cannot distinguish an
            # Option A cell from a cell whose mode is unknown.
            "verification_mode": group["verification_mode"].iloc[0],
            "invocation": invocation,
            "seed_window": _single_or_none(group, "seed_window_build"),
            "n": count,
            "minimum_seconds": float(seconds.min()),
            "median_seconds": float(seconds.median()),
            "maximum_seconds": float(seconds.max()),
            "range_seconds": float(seconds.max() - seconds.min()),
            "relative_spread": float(
                (seconds.max() - seconds.min()) / seconds.median()
            ),
            "standard_deviation_seconds": standard_deviation,
            "median_standard_error_seconds": (
                1.253 * standard_deviation / math.sqrt(count)
                if count >= 2 and not math.isnan(standard_deviation)
                else float("nan")
            ),
            "property_count": int(group["property_count"].iloc[0]),
            "output_sha256": group["output_sha256"].iloc[0],
            "sessions": sorted(set(group.get("session_id", pd.Series(dtype=str)).dropna())),
        }
        for column in DETERMINISTIC_COLUMNS:
            record[column] = _constant_or_none(group, column, key)
        for column in MEASURED_COLUMNS:
            values = group[column].dropna() if column in group.columns else None
            if values is None or values.empty:
                record[column] = None
                record[f"{column}_minimum"] = None
                record[f"{column}_maximum"] = None
                continue
            record[column] = float(values.median())
            record[f"{column}_minimum"] = float(values.min())
            record[f"{column}_maximum"] = float(values.max())
        record["microseconds_per_property"] = (
            record["median_seconds"] / record["property_count"] * 1e6
        )
        records.append(record)
    frame = pd.DataFrame(records)
    # A column mixing None and 64 becomes float64, and the Nones become NaN
    # again -- the same trap as _single_or_none, one layer further out. Rungs
    # 1-3 have no seed window and must stay None so that filters written as
    # "seed_window in (None, 64)" include them.
    if "seed_window" in frame.columns:
        frame["seed_window"] = (
            frame["seed_window"]
            .astype(object)
            .where(frame["seed_window"].notna(), None)
        )
    return frame


def _single_or_none(group: pd.DataFrame, column: str) -> Any:
    """First non-null value, with NaN normalised to None.

    Rungs 1-3 have no seed window, so the column is empty for them and pandas
    reads it as NaN. NaN is not None and is not equal to itself, so leaving it
    in place silently excluded every non-Hilbert rung from any filter written
    as ``seed_window in (None, 64)``.
    """
    if column not in group.columns:
        return None
    values = group[column].dropna().unique()
    if len(values) == 0:
        return None
    value = values[0].item() if hasattr(values[0], "item") else values[0]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _constant_or_none(group: pd.DataFrame, column: str, key: str) -> float | None:
    """A counter that varies inside one cell is a defect, so raise on it."""
    if column not in group.columns:
        return None
    values = group[column].dropna().unique()
    if len(values) == 0:
        return None
    values = [v for v in values
              if not (isinstance(v, float) and math.isnan(v))]
    if len(values) == 0:
        return None
    if len(values) > 1:
        raise ValueError(
            f"{key}: {column} varied across repetitions of one configuration "
            f"({sorted(values)}). Deterministic counters must reproduce."
        )
    value = values[0]
    return float(value) if isinstance(value, (int, float)) else value


# ---------------------------------------------------------------------------
# invariants
# ---------------------------------------------------------------------------

def check_invariants(statistics: pd.DataFrame) -> list[dict[str, Any]]:
    """Re-derive the byte- and counter-level invariants from the artifacts.

    These are already gated at measurement time. Re-checking them here means the
    published analysis stands on its own inputs rather than on the assertion
    that some earlier command exited zero.
    """
    checks: list[dict[str, Any]] = []

    brute = statistics[statistics["algorithm"] == "brute_force"]
    for _, row in brute.iterrows():
        checks.append(
            {
                "check": "brute force examines every segment",
                "cell": row["cell_key"],
                "expected": BRUTE_FORCE_SEGMENT_CHECKS_PER_PROPERTY,
                "measured": row["average_segment_checks_per_property"],
                "passed": row["average_segment_checks_per_property"]
                == BRUTE_FORCE_SEGMENT_CHECKS_PER_PROPERTY,
            }
        )

    hilbert = statistics[statistics["rung"].isin({4, 5})]
    for (workload, mode, window), group in hilbert.groupby(
        ["workload", "verification_mode", "seed_window"], dropna=False
    ):
        if len(group) < 2:
            continue
        for counter in SEED_INVARIANT_COUNTERS:
            values = set(group[counter].dropna())
            checks.append(
                {
                    "check": f"seed-invariant: {counter}",
                    "cell": f"{workload}@{mode}@w{window}",
                    "expected": "identical across seeders",
                    "measured": sorted(values),
                    "passed": len(values) <= 1,
                }
            )

    # The digest is byte-neutral across SEED WINDOWS and is NOT byte-neutral
    # across verification modes: Option A and Option B legitimately produce
    # different output (max abs error 4.658e-10 m against 9.157e-10 m). Grouping
    # without the mode made this check fail on correct data, which is the third
    # appearance of one defect shape -- a dimension the code does not know is a
    # dimension. Current Status B6c-2 records the first two.
    for (workload, mode, algorithm), group in statistics[
        statistics["rung"].isin({4, 5})
    ].groupby(["workload", "verification_mode", "algorithm"]):
        if len(group) < 2:
            continue
        digests = set(group["output_sha256"])
        checks.append(
            {
                "check": "seed window is byte-neutral",
                "cell": f"{algorithm}@{workload}@{mode}",
                "expected": "one digest across all windows",
                "measured": sorted(digests),
                "passed": len(digests) == 1,
            }
        )
        for counter in ("average_segment_checks_per_property",
                        "tight_entries_per_property"):
            values = set(group[counter].dropna())
            checks.append(
                {
                    "check": f"window-invariant: {counter}",
                    "cell": f"{algorithm}@{workload}@{mode}",
                    "expected": "identical across windows",
                    "measured": sorted(values),
                    "passed": len(values) <= 1,
                }
            )

    return checks


# ---------------------------------------------------------------------------
# comparisons
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Comparison:
    label: str
    meaning: str
    workload: str
    verification_mode: str
    is_context: bool
    faster_cell: str
    slower_cell: str
    time_ratio: float
    counter_ratio: float | None
    gap_seconds: float
    range_seconds: float
    z: float
    crosses_invocation: bool
    resolvable_conservative: bool
    n_faster: int
    n_slower: int
    property_count: int

    @property
    def direction(self) -> str:
        """Whether moving UP the ladder makes it faster or slower.

        ``time_ratio`` is the lower rung's median over the upper rung's, so it
        exceeds 1 when the upper rung wins. Both 3 v 2 (a 6.9x win) and 4 v 3
        (a 1.9x loss) live in this table, so the direction is emitted as a word
        rather than left to be inferred from whether a number is under one.
        """
        return "faster" if self.time_ratio >= 1.0 else "slower"

    @property
    def factor(self) -> float:
        """The ratio stated as a magnitude, to be read with ``direction``."""
        return self.time_ratio if self.time_ratio >= 1.0 else 1.0 / self.time_ratio

    def as_dict(self) -> dict[str, Any]:
        return {
            "comparison": self.label,
            "meaning": self.meaning,
            "workload": self.workload,
            # Nucleus 18.27 binds every published comparison to name its window,
            # its verification mode and its workload. Two of the three are here;
            # the window is in the cell keys and in the cost-model points.
            "verification_mode": self.verification_mode,
            "is_context_not_adjacent": self.is_context,
            # Absolutes move about one percent between invocations while adjacent
            # ratios agree to 0.116 percentage points, so a ratio drawn from two
            # invocations is worth less than one drawn from inside a single
            # invocation. It is emitted with the fact attached rather than
            # suppressed, because rung 2 exists in only one invocation and the
            # Option B granularity comparison cannot be formed without borrowing.
            "crosses_invocation": self.crosses_invocation,
            "numerator_cell": self.slower_cell,
            "denominator_cell": self.faster_cell,
            "direction_moving_up_the_ladder": self.direction,
            "wall_clock_factor": self.factor,
            "wall_clock_ratio": self.time_ratio,
            "segment_check_ratio": self.counter_ratio,
            "gap_seconds": self.gap_seconds,
            # Nucleus 18.27: the counted quantity is the invariant and the
            # percentage is the artifact. Option B's absolute 5-v-4 gap matches
            # B5c's counted prediction at every workload while the percentage
            # roughly doubles, because verification is a large shared term that
            # compresses every percentage toward zero. So the absolute is
            # published beside the ratio, never behind it.
            "gap_microseconds_per_property": (
                self.gap_seconds / self.property_count * 1e6
                if self.property_count else None
            ),
            "larger_cell_range_seconds": self.range_seconds,
            "z_of_median_difference": self.z,
            "resolvable_against_full_range": self.resolvable_conservative,
            "n": [self.n_slower, self.n_faster],
        }


def adjacent_comparisons(
    statistics: pd.DataFrame,
    seed_window: int | None = 64,
    include_context: bool = False,
) -> list[Comparison]:
    """The three adjacent comparisons, per workload AND per verification mode.

    Never 5 v 3: that confounds the dimensionality reduction with the learning,
    which is the whole reason the ladder has five rungs rather than three.

    The verification mode is part of the grouping key, not a filter applied
    afterwards. Before it was, ``by_algorithm[row["algorithm"]]`` was assigned
    once per matching row and the LAST write won, so feeding this function a
    frame containing both modes emitted one set of comparisons drawn from
    whichever mode happened to iterate last -- silently, with no mode recorded on
    the output. Measured on the b6c2 artifact, that produced two Option B rows
    and dropped Option A entirely.

    Rungs 1 and 2 appear in both mode groups, because their single measured cell
    IS their result in both columns: they have no verification fork to take.
    """
    comparisons: list[Comparison] = []
    pairs = ADJACENT_PAIRS + (CONTEXT_PAIRS if include_context else ())
    context_labels = {label for _, _, label, _ in CONTEXT_PAIRS}
    group_columns = ["workload", "verification_mode"]
    if statistics["invocation"].notna().any():
        group_columns.append("invocation")
    for group_key, group in statistics.groupby(group_columns, dropna=False):
        workload, mode = group_key[0], group_key[1]
        invocation = group_key[2] if len(group_key) > 2 else None
        by_algorithm = {}
        for _, row in group.iterrows():
            if row["rung"] in (4, 5) and seed_window is not None:
                if row["seed_window"] != seed_window:
                    continue
            by_algorithm[row["algorithm"]] = row
        # Rungs 1-2 verify over original geometry by construction, so when the
        # split column is built they are borrowed from the original group rather
        # than being absent. Without this, 3 v 2 exists only in Option A.
        # Rungs 1-2 have no verification fork and may live in another invocation,
        # so they are borrowed. Every comparison that consumes a borrowed row is
        # marked as crossing an invocation.
        fallback = statistics[
            (statistics["workload"] == workload)
            & (statistics["verification_mode"] == DEFAULT_VERIFICATION_MODE)
            & (statistics["rung"].isin({1, 2}))
        ]
        for _, row in fallback.iterrows():
            by_algorithm.setdefault(row["algorithm"], row)
        for upper, lower, label, meaning in pairs:
            if upper not in by_algorithm or lower not in by_algorithm:
                continue
            a, b = by_algorithm[upper], by_algorithm[lower]
            gap = abs(a["median_seconds"] - b["median_seconds"])
            largest_range = max(a["range_seconds"], b["range_seconds"])
            standard_error = math.sqrt(
                _nan_to_zero(a["median_standard_error_seconds"]) ** 2
                + _nan_to_zero(b["median_standard_error_seconds"]) ** 2
            )
            counter_ratio = None
            if a["average_segment_checks_per_property"] and b[
                "average_segment_checks_per_property"
            ]:
                counter_ratio = (
                    b["average_segment_checks_per_property"]
                    / a["average_segment_checks_per_property"]
                )
            comparisons.append(
                Comparison(
                    label=label,
                    meaning=meaning,
                    workload=workload,
                    verification_mode=mode,
                    is_context=label in context_labels,
                    faster_cell=a["cell_key"],
                    slower_cell=b["cell_key"],
                    time_ratio=b["median_seconds"] / a["median_seconds"],
                    counter_ratio=counter_ratio,
                    gap_seconds=gap,
                    range_seconds=largest_range,
                    z=gap / standard_error if standard_error > 0 else float("inf"),
                    # Borrowing rung 2 into the split column does NOT itself
                    # cross an invocation; the two rows may be from the same one.
                    # Only the recorded invocations decide.
                    crosses_invocation=a["invocation"] != b["invocation"],
                    resolvable_conservative=gap > largest_range,
                    n_faster=int(a["n"]),
                    n_slower=int(b["n"]),
                    property_count=int(a["property_count"]),
                )
            )
    return comparisons


def _nan_to_zero(value: float) -> float:
    return 0.0 if value is None or math.isnan(value) else float(value)


# ---------------------------------------------------------------------------
# cost model
# ---------------------------------------------------------------------------

def cost_model(
    statistics: pd.DataFrame,
    nanoseconds_per_entry: float = B5C_NANOSECONDS_PER_RESOLVE_ENTRY,
) -> dict[str, Any]:
    """Predict the 5-v-4 wall-clock gap from counted resolve-descent entries.

    The prediction uses a constant measured independently at B5c, so agreement
    is a test of the mechanism rather than a fit. The slope reported alongside
    is the least-squares estimate through the origin over every matched pair,
    and is what the constant would have to be for the data to be explained by
    resolve-descent entries alone.
    """
    points: list[dict[str, Any]] = []
    hilbert = statistics[statistics["rung"].isin({4, 5})]
    # INVOCATION is part of the key. Without it, the ladder's and the sweep's
    # W=64 countywide cells land in one group and ``rows[algorithm]`` keeps
    # whichever iterated last, so the sweep population silently acquired a point
    # from another invocation and the slope moved 21.02 -> 21.46. No comparison in
    # this project crosses an invocation; that rule has to be enforced by the
    # grouping key rather than remembered.
    columns = ["workload", "verification_mode", "seed_window"]
    if hilbert["invocation"].notna().any():
        columns.append("invocation")
    for group_key, group in hilbert.groupby(columns, dropna=False):
        workload, mode, window = group_key[0], group_key[1], group_key[2]
        invocation = group_key[3] if len(group_key) > 3 else None
        rows = {row["algorithm"]: row for _, row in group.iterrows()}
        if "hilbert_binary" not in rows or "hilbert_rmi" not in rows:
            continue
        binary, learned = rows["hilbert_binary"], rows["hilbert_rmi"]
        delta_entries = (
            learned["resolve_entries_per_property"]
            - binary["resolve_entries_per_property"]
        )
        properties = binary["property_count"]
        measured = (
            (learned["median_seconds"] - binary["median_seconds"])
            / properties * 1e6
        )
        predicted = delta_entries * nanoseconds_per_entry / 1000.0
        largest_range = max(binary["range_seconds"], learned["range_seconds"])
        gap = abs(learned["median_seconds"] - binary["median_seconds"])
        points.append(
            {
                "workload": workload,
                "invocation": invocation,
                "verification_mode": mode,
                "seed_window": window,
                "delta_resolve_entries": delta_entries,
                "predicted_microseconds_per_property": predicted,
                "measured_microseconds_per_property": measured,
                "measured_over_predicted": (
                    measured / predicted if predicted else None
                ),
                "gap_seconds": gap,
                "larger_cell_range_seconds": largest_range,
                "resolvable_against_full_range": gap > largest_range,
            }
        )

    resolvable = [p for p in points if p["resolvable_against_full_range"]]
    # THE POPULATION IS PART OF THE NUMBER. A slope fitted over the nine-window
    # countywide sweep and a slope fitted over the sweep plus two other workloads
    # are different quantities, and PHASE B published them under one label: the
    # artifact reported 20.33 ns/entry over 11 mixed points while Current Status
    # B6c reported 21.02 "over the sweep". Each population is now named and
    # emitted separately, so a document can quote one without implying the other.
    # Keyed on (workload, MODE). Keyed on workload alone, a single Option B
    # point at the operating window joined Option A's nine-window sweep and moved
    # the slope from 21.02 to 21.42 -- a mode contamination inside the very
    # population split that exists to prevent it.
    def _key(point):
        return (
            point["workload"], point["verification_mode"], point["invocation"]
        )

    windows_per_cell = {}
    for point in points:
        windows_per_cell.setdefault(_key(point), set()).add(point["seed_window"])
    sweep_cells = {key for key, windows in windows_per_cell.items()
                   if len(windows) > 1}
    sweep_only = [p for p in points if _key(p) in sweep_cells]
    return {
        "constant_nanoseconds_per_resolve_entry": nanoseconds_per_entry,
        "constant_provenance": B5C_PROVENANCE,
        "points": points,
        "populations": {
            "all_points": {
                "description": (
                    "every matched binary/RMI pair present, mixing the window "
                    "sweep with single-window workloads"
                ),
                "point_count": len(points),
                "slope_nanoseconds_per_entry": _slope_through_origin(points),
            },
            "window_sweep_only": {
                "description": (
                    "only workloads measured at more than one seed window, "
                    "which is the population Current Status B6c reports"
                ),
                "workload_mode_invocation": sorted(
                    f"{workload}@{mode}@{invocation}"
                    for workload, mode, invocation in sweep_cells
                ),
                "point_count": len(sweep_only),
                "slope_nanoseconds_per_entry": (
                    _slope_through_origin(sweep_only) if sweep_only else None
                ),
            },
            "resolvable_only": {
                "description": (
                    "points whose gap exceeds both cells' full range. Reported "
                    "for completeness; at small counts this is not a fit and "
                    "must not be quoted as one"
                ),
                "point_count": len(resolvable),
                "slope_nanoseconds_per_entry": (
                    _slope_through_origin(resolvable) if resolvable else None
                ),
                "is_a_fit": len(resolvable) >= 5,
            },
        },
        # Retained under their original names so a regenerated artifact stays
        # readable by anything that consumed the previous schema.
        "fitted_slope_nanoseconds_per_entry_all": _slope_through_origin(points),
        "fitted_slope_nanoseconds_per_entry_resolvable_only": (
            _slope_through_origin(resolvable) if resolvable else None
        ),
        "resolvable_point_count": len(resolvable),
        "point_count": len(points),
    }


def _slope_through_origin(points: Sequence[Mapping[str, Any]]) -> float | None:
    numerator = sum(
        p["delta_resolve_entries"] * p["measured_microseconds_per_property"]
        for p in points
    )
    denominator = sum(p["delta_resolve_entries"] ** 2 for p in points)
    if not denominator:
        return None
    return numerator / denominator * 1000.0


# ---------------------------------------------------------------------------
# the other reported tables
# ---------------------------------------------------------------------------

def per_property_curve(statistics: pd.DataFrame) -> list[dict[str, Any]]:
    """Cost per property against query count, with the counter beside it.

    This axis varies QUERY COUNT at a fixed index of 1,189,589 entries. It is
    not the index-size axis the learned-index literature argues over; see
    Nucleus 14b.
    """
    rows: list[dict[str, Any]] = []
    for _, row in statistics.iterrows():
        checks = row["average_segment_checks_per_property"]
        candidates = row["average_candidate_features_per_property"]
        rows.append(
            {
                "cell_key": row["cell_key"],
                "algorithm": row["algorithm"],
                "rung": row["rung"],
                "workload": row["workload"],
                "verification_mode": row["verification_mode"],
                "seed_window": row["seed_window"],
                "property_count": row["property_count"],
                "microseconds_per_property": row["microseconds_per_property"],
                "segment_checks_per_property": checks,
                "candidate_features_per_property": candidates,
                # The feature BVH rescans every segment of a candidate feature,
                # so its cost tracks feature SIZE, not feature count. The
                # segment BVH prunes within a feature and does not.
                "segment_checks_per_candidate_feature": (
                    checks / candidates if checks and candidates else None
                ),
            }
        )
    return sorted(rows, key=lambda r: (r["rung"], r["property_count"]))


def memory_table(statistics: pd.DataFrame) -> list[dict[str, Any]]:
    """Persistent structure, peak resident and peak committed, side by side.

    Nucleus 18.24: these are different claims and disagree in direction, so none
    of them may be quoted alone. The baseline subtraction uses rung 1, which
    holds the geometry and the property array and no index at all.
    """
    rows: list[dict[str, Any]] = []
    # Rung 1 exists in one mode only, so the baseline is keyed on workload alone.
    # B6c-2 measured resident and committed peaks agreeing between modes to
    # within 0.1 percent at every rung, so one baseline serves both columns.
    baselines = {
        row["workload"]: row
        for _, row in statistics[statistics["algorithm"] == "brute_force"].iterrows()
    }
    for _, row in statistics.iterrows():
        baseline = baselines.get(row["workload"])
        structure = 0.0
        for column in ("index_bytes", "key_array_bytes", "rmi_model_bytes"):
            value = row[column]
            # NaN is truthy, so a bare `if row[column]` poisons the sum with it.
            if value is not None and not (
                isinstance(value, float) and math.isnan(value)
            ):
                structure += float(value)
        rows.append(
            {
                "cell_key": row["cell_key"],
                "workload": row["workload"],
                "verification_mode": row["verification_mode"],
                # A cell measured in two invocations produces two rows here, and
                # it must: absolutes move ~1 percent between invocations, so the
                # two 232 MB countywide Hilbert rows are two measurements rather
                # than a duplicate. Naming the invocation is what makes the pair
                # readable; silently deduplicating would discard a measurement
                # and silently keeping both without the label, as before, prints
                # one cell twice with different numbers and no explanation.
                "invocation": row["invocation"],
                "seed_window": row["seed_window"],
                "persistent_structure_bytes": structure or None,
                "peak_working_set_bytes": row["peak_working_set_bytes"],
                "peak_commit_bytes": row["peak_commit_bytes"],
                "peak_working_set_above_baseline": (
                    row["peak_working_set_bytes"] - baseline["peak_working_set_bytes"]
                    if baseline is not None and row["peak_working_set_bytes"]
                    else None
                ),
                "peak_commit_above_baseline": (
                    row["peak_commit_bytes"] - baseline["peak_commit_bytes"]
                    if baseline is not None and row["peak_commit_bytes"]
                    else None
                ),
            }
        )
    return sorted(
        rows,
        key=lambda r: (r["workload"], r["cell_key"], r["invocation"] or ""),
    )


def window_curve(statistics: pd.DataFrame) -> list[dict[str, Any]]:
    """The learned rung against its control, per window, at one workload."""
    rows: list[dict[str, Any]] = []
    for (workload, mode, window), group in statistics[
        statistics["rung"].isin({4, 5})
    ].groupby(["workload", "verification_mode", "seed_window"], dropna=False):
        by_algorithm = {row["algorithm"]: row for _, row in group.iterrows()}
        if len(by_algorithm) < 2:
            continue
        binary, learned = by_algorithm["hilbert_binary"], by_algorithm["hilbert_rmi"]
        rows.append(
            {
                "workload": workload,
                "verification_mode": mode,
                "seed_window": window,
                "binary_median_seconds": binary["median_seconds"],
                "rmi_median_seconds": learned["median_seconds"],
                "rmi_over_binary": (
                    learned["median_seconds"] / binary["median_seconds"]
                ),
                "binary_resolve_entries": binary["resolve_entries_per_property"],
                "rmi_resolve_entries": learned["resolve_entries_per_property"],
                "binary_fraction_window_missed": binary["fraction_window_missed"],
                "rmi_fraction_window_missed": learned["fraction_window_missed"],
                "binary_mean_d_seed_over_d_best": binary["mean_d_seed_over_d_best"],
                "rmi_mean_d_seed_over_d_best": learned["mean_d_seed_over_d_best"],
                "binary_max_d_seed_over_d_best": binary["max_d_seed_over_d_best"],
                "rmi_max_d_seed_over_d_best": learned["max_d_seed_over_d_best"],
                "seed_probes_saved_per_property": (
                    binary["average_seed_probes_per_property"]
                ),
                "extra_resolve_entries_per_property": (
                    learned["resolve_entries_per_property"]
                    - binary["resolve_entries_per_property"]
                ),
                "exchange_rate_entries_per_probe": (
                    (learned["resolve_entries_per_property"]
                     - binary["resolve_entries_per_property"])
                    / binary["average_seed_probes_per_property"]
                    if binary["average_seed_probes_per_property"]
                    else None
                ),
                # The window scan is 2W distance computations per query and
                # appears in NO counter. It is analytically known rather than
                # instrumented; its per-entry cost differs from a resolve-descent
                # entry's, so the two must not be summed.
                "uncounted_window_scan_entries": (
                    2 * window if window is not None else None
                ),
            }
        )
    return sorted(
        rows,
        key=lambda r: (r["workload"], r["verification_mode"], r["seed_window"] or 0),
    )


def cross_invocation_agreement(
    left: pd.DataFrame, right: pd.DataFrame, left_name: str, right_name: str
) -> list[dict[str, Any]]:
    """Cells measured in both invocations, and how far apart they landed.

    No comparison in the report crosses invocations. This quantifies what such a
    comparison would be worth if one did.
    """
    shared = set(left["cell_key"]) & set(right["cell_key"])
    if left["cell_key"].duplicated().any() or right["cell_key"].duplicated().any():
        raise ValueError(
            "cross_invocation_agreement expects one row per cell in each frame; "
            "pass the per-invocation statistics, not a concatenation of them."
        )
    left_by_key = left.set_index("cell_key")
    right_by_key = right.set_index("cell_key")
    return [
        {
            "cell_key": key,
            f"{left_name}_median_seconds": float(left_by_key.loc[key, "median_seconds"]),
            f"{right_name}_median_seconds": float(right_by_key.loc[key, "median_seconds"]),
            "relative_difference": float(
                right_by_key.loc[key, "median_seconds"]
                / left_by_key.loc[key, "median_seconds"] - 1
            ),
            "digests_match": (
                left_by_key.loc[key, "output_sha256"]
                == right_by_key.loc[key, "output_sha256"]
            ),
        }
        for key in sorted(shared)
    ]

# ---------------------------------------------------------------------------
# search versus verification
# ---------------------------------------------------------------------------

# B1 derived the segment BVH's phase-1 search at roughly 0.4 percent of query
# time by counting box and node operations; B6c-2 derived ~0.6 percent by a
# different route. The decomposition below needs one such external number, and
# the reason it cannot derive its own is recorded in
# ``verification_decomposition``.
# Rungs 3, 4 and 5 only. A "segment check" is not a unit of cost shared with
# rungs 1 and 2: brute force fuses its scan with no index at all and the feature
# BVH rescans a whole candidate feature, so applying rung 3's per-check constant
# to them is exactly what B2's rule forbids -- counts are comparable within a
# verification mode, and not across implementations that verify differently.
# Doing it anyway produced search costs of -2,261 us/property, which is how the
# error announced itself.
DECOMPOSABLE_RUNGS = (3, 4, 5)

RUNG3_SEARCH_FRACTION = 0.006
RUNG3_SEARCH_FRACTION_PROVENANCE = (
    "B1 counted ~35 box and node operations per property against 9,407.62 "
    "segment checks (~0.4 percent); B6c-2 reached ~0.6 percent independently. "
    "The larger figure is used so the verification term is not overstated."
)


def _is_operating_window(value: Any, window: int = 64) -> bool:
    """True for the operating window and for a rung that has no window.

    ``seed_window`` is None for rungs 1-3, and a column mixing None with 64
    becomes float64 with the None as NaN. ``NaN not in (None, 64)`` is True, so
    a membership test written that way silently excludes every non-Hilbert rung
    -- which is how the segment-BVH rows vanished from the decomposition's
    calibration the first time it was run. ``_single_or_none`` and
    ``cell_statistics`` already defend against this for frames this module
    builds; this defends against it for any frame a caller passes in.
    """
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return int(value) == window
    except (TypeError, ValueError):
        return False


def verification_decomposition(
    statistics: pd.DataFrame,
    rung3_search_fraction: float = RUNG3_SEARCH_FRACTION,
) -> dict[str, Any]:
    """Split each cell's query time into search and verification.

    Why this needs an external constant. Search cost is mode-invariant -- the
    traversal does not know which geometry the kernel will rescan -- so for one
    rung measured in both modes::

        t_A = search + checks_A * c_A
        t_B = search + checks_B * c_B

    Two equations, three unknowns. Adding a second rung closes the system
    exactly: four equations, four unknowns (two search costs, two per-check
    costs). That system was solved on the countywide b6c2 artifact and it is
    UNUSABLE. Both rungs' check-count ratios are ~1.45, so the two constraints
    are nearly collinear, and the solution returns a NEGATIVE search cost for
    rung 3 (-6.82 us/property) with a per-check ratio of 2.27x against the 4.21x
    B2 measured independently. The ill-conditioning is reported by
    ``exactly_determined_diagnostic`` rather than left for someone to rediscover.

    So the calibration is anchored instead: rung 3's search is a known small
    fraction of its query time, the per-check costs follow, and the validation is
    that the search cost predicted for rungs 4 and 5 -- which the calibration
    never saw -- agrees between the two modes, as mode-invariance requires.

    Assumptions, stated: verification cost is linear in the check count within a
    mode; a check's cost does not depend on which rung issued it; and search cost
    does not depend on the verification mode. The first two are what "a segment
    check is not a mode-invariant unit of cost" (Nucleus, B2) permits -- counts
    are comparable WITHIN a mode -- and the third is structural.
    """
    results: dict[str, Any] = {
        "rung3_search_fraction_assumed": rung3_search_fraction,
        "rung3_search_fraction_provenance": RUNG3_SEARCH_FRACTION_PROVENANCE,
        "per_check_nanoseconds": [],
        "cells": [],
        "search_mode_invariance": [],
        "exactly_determined_diagnostic": [],
    }

    decomposable = statistics[statistics["rung"].isin(set(DECOMPOSABLE_RUNGS))]
    # Grouped by INVOCATION as well. Absolutes move about 1 percent between
    # invocations, so calibrating on one invocation's rung 3 and applying the
    # constant to another's put rung 3's own residual below zero.
    group_columns = ["workload"]
    if decomposable["invocation"].notna().any():
        group_columns.append("invocation")
    for group_key, group in decomposable.groupby(group_columns, dropna=False):
        workload = group_key[0] if isinstance(group_key, tuple) else group_key
        invocation = (
            group_key[1] if isinstance(group_key, tuple) and len(group_key) > 1
            else None
        )
        modes = {}
        for _, row in group.iterrows():
            if row["algorithm"] != "segment_bvh":
                continue
            modes[row["verification_mode"]] = row
        if not modes:
            continue

        # Per-check cost, one per mode, calibrated from rung 3 only.
        per_check: dict[str, float] = {}
        for mode, row in modes.items():
            checks = row["average_segment_checks_per_property"]
            if not checks:
                continue
            verification_us = row["microseconds_per_property"] * (
                1.0 - rung3_search_fraction
            )
            per_check[mode] = verification_us * 1000.0 / checks
            results["per_check_nanoseconds"].append(
                {
                    "workload": workload,
                    "invocation": invocation,
                    "verification_mode": mode,
                    "calibrated_from": row["cell_key"],
                    "checks_per_property": checks,
                    "nanoseconds_per_check": per_check[mode],
                }
            )
        if len(per_check) == 2:
            results["per_check_nanoseconds"][-1]["original_over_split_ratio"] = (
                per_check["original"] / per_check["split"]
            )

        # Apply it to every cell that reports a check count.
        for _, row in group.iterrows():
            mode = row["verification_mode"]
            checks = row["average_segment_checks_per_property"]
            cost = per_check.get(mode)
            if cost is None or not checks:
                continue
            total = row["microseconds_per_property"]
            verification = checks * cost / 1000.0
            search = total - verification
            results["cells"].append(
                {
                    "cell_key": row["cell_key"],
                    "workload": workload,
                    "invocation": invocation,
                    "verification_mode": mode,
                    "rung": int(row["rung"]),
                    "seed_window": row["seed_window"],
                    "total_microseconds_per_property": total,
                    "search_microseconds_per_property": search,
                    "verification_microseconds_per_property": verification,
                    "search_share_of_query": search / total if total else None,
                    # A negative search cost means the calibration cannot be
                    # applied to this cell. It is emitted, flagged, and must not
                    # be published as a decomposition.
                    "search_is_physical": search >= 0.0,
                }
            )

        # Out-of-sample validation: rungs 4 and 5 were not used to calibrate.
        for algorithm in ("hilbert_binary", "hilbert_rmi"):
            paired = {}
            for _, row in group.iterrows():
                if row["algorithm"] != algorithm:
                    continue
                if not _is_operating_window(row["seed_window"]):
                    continue
                paired[row["verification_mode"]] = row
            if len(paired) < 2:
                continue
            estimates = {}
            for mode, row in paired.items():
                cost = per_check.get(mode)
                if cost is None:
                    continue
                estimates[mode] = (
                    row["microseconds_per_property"]
                    - row["average_segment_checks_per_property"] * cost / 1000.0
                )
            if len(estimates) < 2:
                continue
            low, high = min(estimates.values()), max(estimates.values())
            results["search_mode_invariance"].append(
                {
                    "workload": workload,
                    "invocation": invocation,
                    "algorithm": algorithm,
                    "search_microseconds_by_mode": estimates,
                    "relative_disagreement": (high - low) / high if high else None,
                    "out_of_sample": True,
                }
            )

        # The exactly-determined solve, kept as a recorded failure. It needs both
        # modes at rung 3 AND at rung 4; the helper returns None when they are
        # not all present, which is the only gate required.
        if len(modes) == 2:
            diagnostic = _exactly_determined_per_check(group, workload)
            if diagnostic is not None:
                results["exactly_determined_diagnostic"].append(diagnostic)

    return results


def _exactly_determined_per_check(
    statistics: pd.DataFrame, workload: str
) -> dict[str, Any] | None:
    """Solve for both per-check costs with no assumed search fraction.

    Retained because its FAILURE is the justification for the anchored
    calibration. Two rungs times two modes is four equations in four unknowns,
    but the design matrix is nearly singular and the solution is unphysical.
    """
    rows: dict[tuple[str, str], Any] = {}
    for _, row in statistics.iterrows():
        if row["algorithm"] not in ("segment_bvh", "hilbert_binary"):
            continue
        if not _is_operating_window(row["seed_window"]):
            continue
        rows[(row["algorithm"], row["verification_mode"])] = row
    needed = [
        ("segment_bvh", "original"), ("segment_bvh", "split"),
        ("hilbert_binary", "original"), ("hilbert_binary", "split"),
    ]
    if any(key not in rows for key in needed):
        return None

    def checks(key): return rows[key]["average_segment_checks_per_property"]
    def micro(key): return rows[key]["microseconds_per_property"]

    a11, a12 = checks(needed[0]), -checks(needed[1])
    a21, a22 = checks(needed[2]), -checks(needed[3])
    b1 = (micro(needed[0]) - micro(needed[1])) * 1000.0
    b2 = (micro(needed[2]) - micro(needed[3])) * 1000.0
    determinant = a11 * a22 - a12 * a21
    if determinant == 0:
        return None
    original = (b1 * a22 - a12 * b2) / determinant
    split = (a11 * b2 - b1 * a21) / determinant
    search3 = micro(needed[0]) - checks(needed[0]) * original / 1000.0
    return {
        "workload": workload,
        "nanoseconds_per_check_original": original,
        "nanoseconds_per_check_split": split,
        "original_over_split_ratio": split and original / split,
        "implied_rung3_search_microseconds_per_property": search3,
        "check_count_ratio_rung3": checks(needed[0]) / checks(needed[1]),
        "check_count_ratio_rung4": checks(needed[2]) / checks(needed[3]),
        "usable": search3 >= 0.0,
        "why_not_usable": (
            None if search3 >= 0.0 else
            "implied rung-3 search cost is negative; the two check-count ratios "
            "are nearly equal, so the system is ill-conditioned and this solve "
            "must not be used to publish a decomposition"
        ),
    }


# ---------------------------------------------------------------------------
# inflation
# ---------------------------------------------------------------------------

# B1a measured the longest ORIGINAL segment in the hydrography: one Lake Ontario
# boundary chord. Uncapped, that single object sets L for the whole index and
# inflates every query by L/2.
UNCAPPED_MAX_SEGMENT_LENGTH_M = 5748.2396


def inflation_axis(statistics: pd.DataFrame) -> list[dict[str, Any]]:
    """Search-radius inflation as a first-class axis, per Nucleus 18.19.

    Ordering extended objects by a representative point is lossy: a segment's
    midpoint can lie outside a query disk while its nearest point lies inside,
    so exactness requires searching ``disk(r + L/2)``. This is the price of
    treating extended objects as points and it is the reason the learned-index
    literature has stayed on point data.

    Two things reported here are easy to state wrongly.

    The capped geometric inflation RISES on the near-water subset while phase-2
    checks FALL, because properties nearer water have a smaller ``r`` and the
    fixed ``L/2`` = 12.5 m is a larger fraction of it, while a smaller ``r``
    also means fewer and smaller candidate features to rescan. Inflation and
    verification move in OPPOSITE directions across workloads, so an inflation
    figure that does not name its workload is not a figure.

    The ``2W`` seed-window scan is inflation's uncounted twin. It appears in no
    emitted counter, and its per-entry cost differs from a resolve-descent
    entry's by roughly 7.8x because one access pattern is sequential and the
    other scattered. The two are reported side by side and never summed; see
    ``access_pattern_fit``.
    """
    rows: list[dict[str, Any]] = []
    for _, row in statistics.iterrows():
        true_r = row["n_true_r_per_property"]
        admitted = row["n_disk_infl_per_property"]
        if true_r is None or admitted is None:
            continue
        if (isinstance(true_r, float) and math.isnan(true_r)) or (
            isinstance(admitted, float) and math.isnan(admitted)
        ):
            continue
        window = row["seed_window"]
        rows.append(
            {
                "cell_key": row["cell_key"],
                "workload": row["workload"],
                "verification_mode": row["verification_mode"],
                "algorithm": row["algorithm"],
                "seed_window": window,
                "entries_satisfying_range_predicate": true_r,
                "midpoints_admitted": admitted,
                "geometric_inflation_capped": row["geometric_inflation_capped"],
                "geometric_inflation_recomputed": (
                    admitted / true_r if true_r else None
                ),
                "phase2_segment_checks_per_property": (
                    row["average_segment_checks_per_property"]
                ),
                # The counted phase-1 admission against the counted phase-2
                # verification. B3b's durable reading: phase-1 admission is a
                # rounding error in the query's total work, so further index work
                # belongs in verification rather than in search.
                "admitted_over_phase2_checks": (
                    admitted / row["average_segment_checks_per_property"]
                    if row["average_segment_checks_per_property"] else None
                ),
                "uncounted_window_scan_entries": (
                    2 * window if window is not None else None
                ),
                # Uncounted 2W scan against the counted resolve descent, as a
                # ratio of ENTRIES. Not a ratio of cost: see access_pattern_fit.
                "uncounted_over_counted_entries": (
                    2 * window / row["resolve_entries_per_property"]
                    if window is not None and row["resolve_entries_per_property"]
                    else None
                ),
            }
        )
    return sorted(
        rows,
        key=lambda r: (
            r["workload"], r["verification_mode"], r["algorithm"],
            r["seed_window"] or 0,
        ),
    )


def access_pattern_fit(statistics: pd.DataFrame) -> dict[str, Any]:
    """Separate the sequential window scan from the scattered resolve descent.

    Fits ``ns/property = intercept + a*(2W) + b*(resolve entries)`` over the
    window sweep. The intercept is FREE and absorbs verification and fixed
    per-property overhead, both of which are constant across the sweep; without
    it the regressors are asked to explain a ~42 us/property verification term
    they have no access to, and the fit inverts.

    EXPLORATORY, not a validated prediction. Nucleus records structured
    residuals, and the coefficient on ``2W`` is identified only by the sweep's
    range of ``W`` rather than by any independent measurement of a sequential
    read. It is reported because the ~7.8x premium it estimates is the reason an
    uncounted entry and a counted entry must never be summed -- B2 said a segment
    check is not mode-invariant, and this says an entry is not
    access-pattern-invariant.
    """
    out: dict[str, Any] = {"is_exploratory": True, "fits": []}
    frame = statistics[statistics["rung"].isin({4, 5})]
    columns = ["workload", "verification_mode"]
    if frame["invocation"].notna().any():
        columns.append("invocation")
    for group_key, group in frame.groupby(columns, dropna=False):
        workload, mode = group_key[0], group_key[1]
        invocation = group_key[2] if len(group_key) > 2 else None
        usable = [
            row for _, row in group.iterrows()
            if row["seed_window"] is not None
            and row["resolve_entries_per_property"] is not None
            and not (
                isinstance(row["resolve_entries_per_property"], float)
                and math.isnan(row["resolve_entries_per_property"])
            )
        ]
        windows = {row["seed_window"] for row in usable}
        if len(windows) < 3:
            continue
        design = [
            [1.0, 2.0 * row["seed_window"], row["resolve_entries_per_property"]]
            for row in usable
        ]
        observed = [
            row["median_seconds"] / row["property_count"] * 1e9 for row in usable
        ]
        solution = _least_squares(design, observed)
        if solution is None:
            continue
        intercept, window_ns, resolve_ns = solution
        predicted = [
            sum(c * x for c, x in zip(solution, columns)) for columns in design
        ]
        mean = sum(observed) / len(observed)
        residual = sum((o - p) ** 2 for o, p in zip(observed, predicted))
        variance = sum((o - mean) ** 2 for o in observed)
        out["fits"].append(
            {
                "workload": workload,
                "invocation": invocation,
                "verification_mode": mode,
                "point_count": len(usable),
                "distinct_windows": len(windows),
                "intercept_nanoseconds_per_property": intercept,
                "window_scan_nanoseconds_per_entry": window_ns,
                "resolve_descent_nanoseconds_per_entry": resolve_ns,
                "locality_premium": (
                    resolve_ns / window_ns if window_ns else None
                ),
                "r_squared": 1.0 - residual / variance if variance else None,
            }
        )
    return out


def _least_squares(
    design: Sequence[Sequence[float]], observed: Sequence[float]
) -> list[float] | None:
    """Normal-equation solve with Gaussian elimination and partial pivoting.

    Written out rather than pulled from numpy because this module's only
    third-party dependency is pandas and a three-column normal-equation solve
    does not justify adding another. The matrix is 3x3 and the pivoting makes it
    well behaved at this size; a larger design would want a QR routine.
    """
    width = len(design[0])
    normal = [
        [sum(r[i] * r[j] for r in design) for j in range(width)] + [
            sum(r[i] * y for r, y in zip(design, observed))
        ]
        for i in range(width)
    ]
    for column in range(width):
        pivot = max(range(column, width), key=lambda r: abs(normal[r][column]))
        if abs(normal[pivot][column]) < 1e-12:
            return None
        normal[column], normal[pivot] = normal[pivot], normal[column]
        divisor = normal[column][column]
        normal[column] = [v / divisor for v in normal[column]]
        for other in range(width):
            if other == column:
                continue
            factor = normal[other][column]
            normal[other] = [
                v - factor * p for v, p in zip(normal[other], normal[column])
            ]
    return [normal[i][width] for i in range(width)]