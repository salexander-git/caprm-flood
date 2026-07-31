"""C4 item 1, analysed. Which measured differences are real, and which are not.

Every comparison in this module carries a resolution verdict, and the rule is
B6's: **a comparison whose gap sits inside its cells' observed range is NOT
RESOLVED and is not printed as though it carried a claim.** Two medians differ
in every sample ever taken; only some of those differences survive their own
spread. C4's inference sweep produced relative spreads up to 18.6 percent, which
is wide enough that several of the differences a reader would naturally take
from the sweep table do not survive it.

The rule is implemented once, in :func:`compare_samples`, as a statement about
the conservative speedup interval. If ``[min_a/max_b, max_a/min_b]`` contains
1.0, the two configurations were not distinguished by this measurement. That is
algebraically identical to asking whether the observed ranges overlap, and
having one implementation rather than two removes the chance of them drifting
apart.

What this module deliberately does NOT do is compute a confidence interval or a
p-value. Five to eleven repeats of a wall clock on a machine with an operating
system on it is not a sample from a distribution anyone has characterised, and
attaching an inferential statistic to it would claim more than the measurement
supports. Observed range is what was observed.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

TOOL_VERSION = "caprm.c4_analysis/c4.0"

#: The batch size ``TrainedModel.predict`` uses when the caller does not choose
#: one. Comparisons default to this because it is the shipped condition, not
#: because it was the fastest cell.
SHIPPED_DEFAULT_BATCH_LABEL = "65536"


class C4AnalysisError(RuntimeError):
    """Raised when a run artifact is missing something a comparison needs."""


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Comparison:
    """``a`` against ``b``, where a speedup above 1.0 means ``b`` was faster."""

    label_a: str
    label_b: str
    median_a_s: float
    median_b_s: float
    min_a_s: float
    max_a_s: float
    min_b_s: float
    max_b_s: float
    n_repeat_a: int
    n_repeat_b: int

    @property
    def speedup_median(self) -> float:
        return self.median_a_s / self.median_b_s if self.median_b_s else math.inf

    @property
    def speedup_low(self) -> float:
        """The least favourable speedup consistent with what was observed."""
        return self.min_a_s / self.max_b_s if self.max_b_s else math.inf

    @property
    def speedup_high(self) -> float:
        return self.max_a_s / self.min_b_s if self.min_b_s else math.inf

    @property
    def resolved(self) -> bool:
        """False when the observed ranges overlap, i.e. the interval spans 1.0."""
        return not (self.speedup_low <= 1.0 <= self.speedup_high)

    @property
    def verdict(self) -> str:
        if not self.resolved:
            return "NOT RESOLVED"
        return "b faster" if self.speedup_median > 1.0 else "a faster"

    def to_dict(self) -> dict[str, Any]:
        return {
            "label_a": self.label_a,
            "label_b": self.label_b,
            "median_a_s": self.median_a_s,
            "median_b_s": self.median_b_s,
            "observed_range_a_s": [self.min_a_s, self.max_a_s],
            "observed_range_b_s": [self.min_b_s, self.max_b_s],
            "n_repeat_a": self.n_repeat_a,
            "n_repeat_b": self.n_repeat_b,
            "speedup_median": self.speedup_median,
            "speedup_observed_interval": [self.speedup_low, self.speedup_high],
            "resolved": self.resolved,
            "verdict": self.verdict,
        }


def compare_samples(
    label_a: str, sample_a: Sequence[float], label_b: str, sample_b: Sequence[float]
) -> Comparison:
    """Compare two duration samples without assuming a distribution."""
    if not sample_a or not sample_b:
        raise C4AnalysisError("both samples must be non-empty")
    sorted_a, sorted_b = sorted(sample_a), sorted(sample_b)

    def median(values: list[float]) -> float:
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2.0

    return Comparison(
        label_a=label_a,
        label_b=label_b,
        median_a_s=median(sorted_a),
        median_b_s=median(sorted_b),
        min_a_s=sorted_a[0],
        max_a_s=sorted_a[-1],
        min_b_s=sorted_b[0],
        max_b_s=sorted_b[-1],
        n_repeat_a=len(sorted_a),
        n_repeat_b=len(sorted_b),
    )


# ---------------------------------------------------------------------------
# reading the run artifacts
# ---------------------------------------------------------------------------


def load_run(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "c4_inference_v1":
        raise C4AnalysisError(f"{path} is not a c4_inference_v1 artifact")
    return payload


def thread_count(run: dict[str, Any]) -> int:
    """The pinned BLAS thread count, refused if the run did not record one.

    A throughput figure without its thread count cannot be compared to
    anything, so an unpinned run is rejected here rather than silently
    averaged in beside a pinned one.
    """
    observed = run["environment"]["thread_environment"].get("OPENBLAS_NUM_THREADS")
    if observed is None:
        raise C4AnalysisError(
            "run did not pin OPENBLAS_NUM_THREADS; its throughput is not comparable"
        )
    return int(observed)


def batch_rows(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["batch_label"]: row for row in run["batch_sweep"]}


def _sample(timing: dict[str, Any]) -> list[float]:
    seconds = timing.get("seconds")
    if not seconds:
        raise C4AnalysisError("timing block carries no per-repeat sample")
    return [float(value) for value in seconds]


# ---------------------------------------------------------------------------
# the three tables
# ---------------------------------------------------------------------------


def batch_table(
    run: dict[str, Any], reference_label: str = SHIPPED_DEFAULT_BATCH_LABEL
) -> list[dict[str, Any]]:
    """Every batch size against the shipped default, resolution-tested."""
    rows = batch_rows(run)
    if reference_label not in rows:
        raise C4AnalysisError(f"reference batch {reference_label!r} not in this run")
    reference = rows[reference_label]
    out: list[dict[str, Any]] = []
    for label, row in rows.items():
        comparison = compare_samples(
            f"batch {label}",
            _sample(row["timing"]),
            f"batch {reference_label}",
            _sample(reference["timing"]),
        )
        out.append(
            {
                "batch_label": label,
                "is_reference": label == reference_label,
                "batch_size": row["batch_size"],
                "n_batches": row["n_batches"],
                "properties_per_second_median": row["properties_per_second_median"],
                "microseconds_per_property_median": row["microseconds_per_property_median"],
                "relative_spread": row["timing"]["relative_spread"],
                "vs_reference": comparison.to_dict(),
            }
        )
    return out


def thread_table(runs: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Per batch size, does the higher thread count actually buy anything?"""
    if len(runs) != 2:
        raise C4AnalysisError("thread comparison needs exactly two pinned runs")
    low, high = sorted(runs)
    low_rows, high_rows = batch_rows(runs[low]), batch_rows(runs[high])
    shared = [label for label in high_rows if label in low_rows]
    out: list[dict[str, Any]] = []
    for label in shared:
        comparison = compare_samples(
            f"{low} thread",
            _sample(low_rows[label]["timing"]),
            f"{high} threads",
            _sample(high_rows[label]["timing"]),
        )
        out.append(
            {
                "batch_label": label,
                "threads_low": low,
                "threads_high": high,
                "microseconds_per_property_low": low_rows[label][
                    "microseconds_per_property_median"
                ],
                "microseconds_per_property_high": high_rows[label][
                    "microseconds_per_property_median"
                ],
                "threading_speedup": comparison.to_dict(),
            }
        )
    return out


def split_table(runs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Which half of inference responds to threads, and which does not.

    The Fourier encoding is one small float64 GEMM plus a cosine and a sine over
    ``(n, 64)``. Only the GEMM goes through BLAS; numpy's transcendental ufuncs
    are single-threaded whatever the BLAS thread count is. The MLP is three
    float32 GEMMs and nothing else. If threading moves one half and not the
    other, that asymmetry is the mechanism, and it is checkable here rather than
    assertable in prose.
    """
    if len(runs) != 2:
        raise C4AnalysisError("split comparison needs exactly two pinned runs")
    low, high = sorted(runs)
    out: dict[str, Any] = {"threads_low": low, "threads_high": high, "stages": {}}
    for stage in ("fourier_encoding", "mlp_forward", "full_predict"):
        comparison = compare_samples(
            f"{stage} @ {low} thread",
            _sample(runs[low]["stage_split"][stage]),
            f"{stage} @ {high} threads",
            _sample(runs[high]["stage_split"][stage]),
        )
        out["stages"][stage] = comparison.to_dict()

    for threads in (low, high):
        split = runs[threads]["stage_split"]
        out[f"ratio_at_{threads}_threads"] = {
            "fourier_us_per_property": split["fourier_microseconds_per_property"],
            "mlp_us_per_property": split["mlp_microseconds_per_property"],
            "fourier_over_mlp_ratio": split["fourier_over_mlp_ratio"],
            "parts_minus_whole_fraction_of_whole": split[
                "parts_minus_whole_fraction_of_whole"
            ],
        }
    return out


def agreement_summary(runs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Which batch sizes breached C2's recorded bound, and identically or not.

    A deviation that is identical across thread counts is a property of the
    kernel dispatched at that operand shape. A deviation that moves with the
    thread count is a reduction-order effect. They are different findings and
    the artifact should say which one this is.
    """
    per_thread: dict[str, Any] = {}
    breaching: dict[int, set[str]] = {}
    deviations: dict[str, set[float]] = {}
    for threads, run in sorted(runs.items()):
        report = run["batch_agreement"]
        failures = {
            label
            for label, entry in report["per_batch"].items()
            if not entry["within_tolerance"]
        }
        breaching[threads] = failures
        for label, entry in report["per_batch"].items():
            deviations.setdefault(label, set()).add(entry["max_abs_deviation"])
        per_thread[str(threads)] = {
            "tolerance_index_points": report["tolerance_index_points"],
            "max_abs_deviation_index_points": report["max_abs_deviation_index_points"],
            "breaching_batches": sorted(failures),
        }

    invariant = {
        label: len(values) == 1 for label, values in deviations.items()
    }
    consistent = len({frozenset(v) for v in breaching.values()}) == 1
    return {
        "per_thread_count": per_thread,
        "same_batches_breach_at_every_thread_count": consistent,
        "deviation_identical_across_thread_counts": invariant,
        "interpretation": (
            "A deviation identical across thread counts is a kernel-dispatch "
            "effect at that operand shape, not a reduction-order effect."
        ),
    }


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def _row(cells: Iterable[Any]) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def markdown_tables(analysis: dict[str, Any]) -> str:
    """The tables as they should appear in the report, verdicts included."""
    lines: list[str] = ["# C4 item 1 — surrogate inference cost", ""]

    high = analysis["threads_high"]
    lines += [
        f"## Batch sweep at {high} threads, against the shipped default batch "
        f"({SHIPPED_DEFAULT_BATCH_LABEL})",
        "",
        _row(["batch", "n batches", "prop/s", "us/prop", "spread", "interval vs default", "verdict"]),
        _row(["---"] * 7),
    ]
    for row in analysis["batch_table_high"]:
        comparison = row["vs_reference"]
        low_bound, high_bound = comparison["speedup_observed_interval"]
        # A cell compared against itself always overlaps itself. Printing that
        # as NOT RESOLVED would read as a failed comparison rather than as the
        # reference row it is.
        interval = "-" if row["is_reference"] else f"{low_bound:.3f}-{high_bound:.3f}"
        verdict = "reference" if row["is_reference"] else comparison["verdict"]
        lines.append(
            _row(
                [
                    row["batch_label"],
                    f"{row['n_batches']:,}",
                    f"{row['properties_per_second_median']:,.0f}",
                    f"{row['microseconds_per_property_median']:.3f}",
                    f"{row['relative_spread']:.3f}",
                    interval,
                    verdict,
                ]
            )
        )

    low = analysis["threads_low"]
    lines += [
        "",
        f"## Threading: {low} thread against {high} threads",
        "",
        _row(["batch", f"us/prop @{low}", f"us/prop @{high}", "speedup", "interval", "verdict"]),
        _row(["---"] * 6),
    ]
    for row in analysis["thread_table"]:
        comparison = row["threading_speedup"]
        low_bound, high_bound = comparison["speedup_observed_interval"]
        lines.append(
            _row(
                [
                    row["batch_label"],
                    f"{row['microseconds_per_property_low']:.3f}",
                    f"{row['microseconds_per_property_high']:.3f}",
                    f"{comparison['speedup_median']:.3f}x",
                    f"{low_bound:.3f}-{high_bound:.3f}",
                    comparison["verdict"],
                ]
            )
        )

    lines += [
        "",
        "## Where the time goes",
        "",
        _row(["stage", f"threading speedup", "interval", "verdict"]),
        _row(["---"] * 4),
    ]
    for stage, comparison in analysis["split_table"]["stages"].items():
        low_bound, high_bound = comparison["speedup_observed_interval"]
        lines.append(
            _row(
                [
                    stage,
                    f"{comparison['speedup_median']:.3f}x",
                    f"{low_bound:.3f}-{high_bound:.3f}",
                    comparison["verdict"],
                ]
            )
        )

    lines += [
        "",
        "The surrogate emits one scalar. It does not produce the four components,",
        "their provenance, or the source-feature identifiers the pipeline produces,",
        "and no figure above should be read without that sentence beside it.",
        "",
    ]
    return "\n".join(lines)


def analyse(runs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Every table, from exactly two pinned runs."""
    if len(runs) != 2:
        raise C4AnalysisError("analysis needs exactly two pinned thread counts")
    low, high = sorted(runs)
    return {
        "tool_version": TOOL_VERSION,
        "threads_low": low,
        "threads_high": high,
        "resolution_rule": (
            "A comparison whose observed speedup interval contains 1.0 is NOT "
            "RESOLVED. The interval is [min_a/max_b, max_a/min_b] over the "
            "per-repeat samples; no distributional assumption is made."
        ),
        "n_properties": runs[high]["inputs"]["n_properties"],
        "batch_table_high": batch_table(runs[high]),
        "batch_table_low": batch_table(runs[low]),
        "thread_table": thread_table(runs),
        "split_table": split_table(runs),
        "agreement": agreement_summary(runs),
    }