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

RUNG_ORDER = (
    "brute_force",
    "feature_bvh",
    "segment_bvh",
    "hilbert_binary",
    "hilbert_rmi",
)

ADJACENT_PAIRS = (
    ("feature_bvh", "brute_force", "2 v 1", "no index -> feature BVH"),
    ("segment_bvh", "feature_bvh", "3 v 2", "granularity: feature -> segment"),
    ("hilbert_binary", "segment_bvh", "4 v 3", "dimensionality: 2D -> 1D"),
    ("hilbert_rmi", "hilbert_binary", "5 v 4", "machine learning: search -> model"),
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


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_runs(path: Path) -> pd.DataFrame:
    """Load a runs CSV and drop warm-ups, which are never analysed."""
    frame = pd.read_csv(path)
    if "is_warmup" in frame.columns:
        warmup = frame["is_warmup"].astype(str).str.lower().isin({"true", "1"})
        frame = frame.loc[~warmup].copy()
    return frame


def cell_statistics(runs: pd.DataFrame) -> pd.DataFrame:
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
        for column in (
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
            "peak_working_set_bytes",
            "peak_commit_bytes",
        ):
            record[column] = _constant_or_none(group, column, key)
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
    for (workload, window), group in hilbert.groupby(
        ["workload", "seed_window"], dropna=False
    ):
        if len(group) < 2:
            continue
        for counter in SEED_INVARIANT_COUNTERS:
            values = set(group[counter].dropna())
            checks.append(
                {
                    "check": f"seed-invariant: {counter}",
                    "cell": f"{workload}@w{window}",
                    "expected": "identical across seeders",
                    "measured": sorted(values),
                    "passed": len(values) <= 1,
                }
            )

    for (workload, algorithm), group in statistics[
        statistics["rung"].isin({4, 5})
    ].groupby(["workload", "algorithm"]):
        if len(group) < 2:
            continue
        digests = set(group["output_sha256"])
        checks.append(
            {
                "check": "seed window is byte-neutral",
                "cell": f"{algorithm}@{workload}",
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
                    "cell": f"{algorithm}@{workload}",
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
    faster_cell: str
    slower_cell: str
    time_ratio: float
    counter_ratio: float | None
    gap_seconds: float
    range_seconds: float
    z: float
    resolvable_conservative: bool
    n_faster: int
    n_slower: int

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
            "numerator_cell": self.slower_cell,
            "denominator_cell": self.faster_cell,
            "direction_moving_up_the_ladder": self.direction,
            "wall_clock_factor": self.factor,
            "wall_clock_ratio": self.time_ratio,
            "segment_check_ratio": self.counter_ratio,
            "gap_seconds": self.gap_seconds,
            "larger_cell_range_seconds": self.range_seconds,
            "z_of_median_difference": self.z,
            "resolvable_against_full_range": self.resolvable_conservative,
            "n": [self.n_slower, self.n_faster],
        }


def adjacent_comparisons(
    statistics: pd.DataFrame, seed_window: int | None = 64
) -> list[Comparison]:
    """The three adjacent comparisons, plus 2 v 1 as context.

    Never 5 v 3: that confounds the dimensionality reduction with the learning,
    which is the whole reason the ladder has five rungs rather than three.
    """
    comparisons: list[Comparison] = []
    for workload, group in statistics.groupby("workload"):
        by_algorithm = {}
        for _, row in group.iterrows():
            if row["rung"] in (4, 5) and seed_window is not None:
                if row["seed_window"] != seed_window:
                    continue
            by_algorithm[row["algorithm"]] = row
        for upper, lower, label, meaning in ADJACENT_PAIRS:
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
                    faster_cell=a["cell_key"],
                    slower_cell=b["cell_key"],
                    time_ratio=b["median_seconds"] / a["median_seconds"],
                    counter_ratio=counter_ratio,
                    gap_seconds=gap,
                    range_seconds=largest_range,
                    z=gap / standard_error if standard_error > 0 else float("inf"),
                    resolvable_conservative=gap > largest_range,
                    n_faster=int(a["n"]),
                    n_slower=int(b["n"]),
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
    keyed = statistics.set_index("cell_key")
    for (workload, window), group in statistics[
        statistics["rung"].isin({4, 5})
    ].groupby(["workload", "seed_window"], dropna=False):
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
    return {
        "constant_nanoseconds_per_resolve_entry": nanoseconds_per_entry,
        "constant_provenance": B5C_PROVENANCE,
        "points": points,
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
    return sorted(rows, key=lambda r: (r["workload"], r["cell_key"]))


def window_curve(statistics: pd.DataFrame) -> list[dict[str, Any]]:
    """The learned rung against its control, per window, at one workload."""
    rows: list[dict[str, Any]] = []
    for (workload, window), group in statistics[
        statistics["rung"].isin({4, 5})
    ].groupby(["workload", "seed_window"], dropna=False):
        by_algorithm = {row["algorithm"]: row for _, row in group.iterrows()}
        if len(by_algorithm) < 2:
            continue
        binary, learned = by_algorithm["hilbert_binary"], by_algorithm["hilbert_rmi"]
        rows.append(
            {
                "workload": workload,
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
    return sorted(rows, key=lambda r: (r["workload"], r["seed_window"] or 0))


def cross_invocation_agreement(
    left: pd.DataFrame, right: pd.DataFrame, left_name: str, right_name: str
) -> list[dict[str, Any]]:
    """Cells measured in both invocations, and how far apart they landed.

    No comparison in the report crosses invocations. This quantifies what such a
    comparison would be worth if one did.
    """
    shared = set(left["cell_key"]) & set(right["cell_key"])
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