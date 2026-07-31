"""Derive and record PHASE B's reported quantities (Milestone 4, chunk B6d).

Reads the B6c measurement artifacts and writes every derived number to
``outputs/validation/b6_analysis.json`` plus a report-ready markdown table.
Nothing in the benchmark tables is computed anywhere else.

Usage (PowerShell, from the repository root)::

    .\\.venv\\Scripts\\python.exe python\\scripts\\analyze_b6_results.py
"""

from __future__ import annotations

import argparse
import json
import sys
import math
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

from caprm.ingest import repository_path  # noqa: E402
from caprm.ladder_analysis import (  # noqa: E402
    UNCAPPED_MAX_SEGMENT_LENGTH_M,
    access_pattern_fit,
    adjacent_comparisons,
    cell_statistics,
    check_invariants,
    cost_model,
    cross_invocation_agreement,
    inflation_axis,
    load_runs,
    memory_table,
    per_property_curve,
    verification_decomposition,
    window_curve,
)
from caprm.ladder_benchmark import sha256_file  # noqa: E402


def _finite(value) -> float | None:
    """None for absent OR NaN. A counter a rung does not emit is not a zero."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def markdown_tables(analysis: dict) -> str:
    lines: list[str] = []
    add = lines.append

    add("# PHASE B benchmark results\n")
    add(f"Generated {analysis['created_at_utc']} by "
        "`python/scripts/analyze_b6_results.py` from the artifacts listed in "
        "`outputs/validation/b6_analysis.json`. Do not hand-edit.\n")

    add("\n## Three adjacent comparisons, per workload and per verification mode\n")
    add("Never 5 v 3: that confounds the dimensionality reduction with the "
        "learning. Rung 1 is in no adjacent comparison; it carries a 31.71 "
        "percent spread at n=3 and is listed separately below as context.\n")
    add("Segment-check counts are comparable WITHIN a verification mode and not "
        "across modes (Nucleus, B2), so the count column is never used to infer "
        "the clock column. **Option A dilutes 4 v 3**: rungs 3 and 4 share the "
        "verification term, so the Option A ratio divides two numbers that mostly "
        "consist of the same work. Option B is the correct column for it "
        "(Nucleus 18.27).\n")
    add("| workload | mode | comparison | meaning | wall clock | us/property | "
        "segment checks | n | resolvable |")
    add("|---|---|---|---|---:|---:|---:|---|---|")
    for row in analysis["adjacent_comparisons"]:
        ratio = row["segment_check_ratio"]
        checks = "--"
        if ratio:
            checks = (
                f"{ratio:.3f}x fewer" if ratio >= 1
                else f"{1 / ratio:.3f}x more"
            )
        note = ""
        if row["comparison"] == "4 v 3" and row["verification_mode"] == "original":
            note = " (diluted)"
        # The absolute gap per property is the invariant; the percentage is the
        # artifact of whatever the denominator happens to be (Nucleus 18.27).
        gap = row.get("gap_microseconds_per_property")
        add(
            f"| {row['workload']} | {row['verification_mode']}{note} | "
            f"{row['comparison']} | {row['meaning']} | "
            f"{row['wall_clock_factor']:.3f}x "
            f"{row['direction_moving_up_the_ladder']} | "
            + (f"{gap:.3f} | " if gap is not None else "-- | ")
            + f"{checks} | "
            f"{row['n'][0]}/{row['n'][1]} | "
            f"{'yes' if row['resolvable_against_full_range'] else '**NOT RESOLVED**'} |"
        )

    add("\n### Context, not an adjacent comparison\n")
    add("| workload | mode | comparison | wall clock | segment checks | n | resolvable |")
    add("|---|---|---|---:|---:|---|---|")
    for row in analysis["context_comparisons"]:
        ratio = row["segment_check_ratio"]
        checks = f"{ratio:.3f}x fewer" if ratio else "--"
        add(
            f"| {row['workload']} | {row['verification_mode']} | "
            f"{row['comparison']} | {row['wall_clock_factor']:.3f}x "
            f"{row['direction_moving_up_the_ladder']} | {checks} | "
            f"{row['n'][0]}/{row['n'][1]} | "
            f"{'yes' if row['resolvable_against_full_range'] else '**NOT RESOLVED**'} |"
        )

    add("\n## Search and verification, as separate columns\n")
    decomposition = analysis["verification_decomposition"]
    add(f"Per-check cost is calibrated from rung 3 only, assuming its search is "
        f"{decomposition['rung3_search_fraction_assumed'] * 100:.1f} percent of "
        f"its query time. {decomposition['rung3_search_fraction_provenance']}\n")
    for row in decomposition["per_check_nanoseconds"]:
        ratio = row.get("original_over_split_ratio")
        suffix = f", ratio {ratio:.4f}x" if ratio else ""
        add(f"- {row['workload']} `{row['verification_mode']}`: "
            f"**{row['nanoseconds_per_check']:.4f} ns/check** from "
            f"`{row['calibrated_from']}`{suffix}")
    add("")
    add("| cell | mode | total us/p | search us/p | verification us/p | search share | physical |")
    add("|---|---|---:|---:|---:|---:|---|")
    for row in decomposition["cells"]:
        add(
            f"| {row['cell_key']} | {row['verification_mode']} | "
            f"{row['total_microseconds_per_property']:.3f} | "
            f"{row['search_microseconds_per_property']:.3f} | "
            f"{row['verification_microseconds_per_property']:.3f} | "
            f"{row['search_share_of_query'] * 100:.2f}% | "
            f"{'yes' if row['search_is_physical'] else '**NEGATIVE**'} |"
        )
    add("")
    add("Out-of-sample check. Rungs 4 and 5 never entered the calibration, and "
        "search cost must be mode-invariant because the traversal does not know "
        "which geometry the kernel will rescan:\n")
    for row in decomposition["search_mode_invariance"]:
        add(f"- {row['workload']} {row['algorithm']}: modes disagree by "
            f"**{row['relative_disagreement'] * 100:.3f} percent**")
    for row in decomposition["exactly_determined_diagnostic"]:
        add("")
        add(f"Recorded failure. Solving for both per-check costs with no assumed "
            f"search fraction is exactly determined at two rungs times two modes, "
            f"and it is unusable: the two check-count ratios are "
            f"{row['check_count_ratio_rung3']:.4f} and "
            f"{row['check_count_ratio_rung4']:.4f}, so the system is nearly "
            f"singular and it implies a rung-3 search cost of "
            f"**{row['implied_rung3_search_microseconds_per_property']:.3f} "
            f"us/property**. This is why the calibration is anchored instead.")

    add("\n## Cost model: counted entries predict wall clock\n")
    model = analysis["cost_model"]
    add(f"Constant: **{model['constant_nanoseconds_per_resolve_entry']} ns per "
        f"resolve-descent entry**, measured independently. "
        f"{model['constant_provenance']}\n")
    add("The population is part of the number. A slope over the window sweep "
        "and a slope over the sweep plus other workloads are different "
        "quantities:\n")
    for name, population in model["populations"].items():
        slope = population["slope_nanoseconds_per_entry"]
        caveat = ""
        if name == "resolvable_only" and not population.get("is_a_fit"):
            caveat = "  **not a fit at this count; do not quote as one**"
        add(f"- `{name}` (n={population['point_count']}): "
            + (f"**{slope:.2f} ns/entry**" if slope else "--")
            + f" -- {population['description']}{caveat}")
    add("")
    add("| workload | W | delta entries | predicted us | measured us | m/p | resolvable |")
    add("|---|---:|---:|---:|---:|---:|---|")
    for point in model["points"]:
        ratio = point["measured_over_predicted"]
        add(
            f"| {point['workload']} | {point['seed_window']:g} | "
            f"{point['delta_resolve_entries']:.3f} | "
            f"{point['predicted_microseconds_per_property']:.3f} | "
            f"{point['measured_microseconds_per_property']:.3f} | "
            f"{ratio:.3f} | "
            f"{'yes' if point['resolvable_against_full_range'] else 'NO'} |"
        )

    add("\n## Query-count curve\n")
    add("Varies QUERY COUNT at a fixed 1,189,589-entry index. NOT the "
        "index-size axis the learned-index literature argues over.\n")
    add("| rung | workload | us/property | checks/property | candidates | checks per candidate |")
    add("|---|---|---:|---:|---:|---:|")
    for row in analysis["per_property_curve"]:
        if row["seed_window"] not in (None, 64):
            continue
        per_candidate = _finite(row["segment_checks_per_candidate_feature"])
        candidates = _finite(row["candidate_features_per_property"])
        add(
            f"| {row['algorithm']} | {row['workload']} | "
            f"{row['microseconds_per_property']:.3f} | "
            f"{row['segment_checks_per_property']:.2f} | "
            + (f"{candidates:.3f} | " if candidates else "-- | ")
            + (f"{per_candidate:,.0f} |" if per_candidate else "-- |")
        )

    add("\n## Seed-window curve\n")
    add("| workload | W | binary s | rmi s | rmi/binary | binary missed | rmi missed | exchange rate | uncounted 2W |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in analysis["window_curve"]:
        rate = row["exchange_rate_entries_per_probe"]
        add(
            f"| {row['workload']} | {row['seed_window']:g} | "
            f"{row['binary_median_seconds']:.4f} | "
            f"{row['rmi_median_seconds']:.4f} | "
            f"{row['rmi_over_binary']:.5f} | "
            f"{row['binary_fraction_window_missed']:.4f} | "
            f"{row['rmi_fraction_window_missed']:.4f} | "
            f"{rate:.2f}:1 | {row['uncounted_window_scan_entries']:g} |"
        )

    add("\n## Inflation, as a first-class axis\n")
    add("Ordering extended objects by a representative point requires searching "
        "`disk(r + L/2)` to stay exact. That inflation is the price of treating "
        "extended objects as points and is the reason the learned-index "
        "literature has stayed on point data.\n")
    add("The capped inflation and the phase-2 check count move in OPPOSITE "
        "directions across workloads, so no inflation figure is meaningful "
        "without its workload. The `2W` seed-window scan appears in NO emitted "
        "counter and is reported beside the counted work, never summed with it.\n")
    add("| cell | mode | W | entries in range | midpoints admitted | inflation | "
        "phase-2 checks | admitted/checks | uncounted 2W | 2W/counted |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in analysis["inflation_axis"]:
        window = row["seed_window"]
        add(
            f"| {row['cell_key']} | {row['verification_mode']} | "
            + (f"{window:g} | " if window else "-- | ")
            + f"{row['entries_satisfying_range_predicate']:.4f} | "
            f"{row['midpoints_admitted']:.4f} | "
            f"{row['geometric_inflation_capped']:.4f}x | "
            f"{row['phase2_segment_checks_per_property']:,.2f} | "
            f"{row['admitted_over_phase2_checks']:.2e} | "
            + (f"{row['uncounted_window_scan_entries']:g} | " if window else "-- | ")
            + (f"{row['uncounted_over_counted_entries']:.4f} |" if window else "-- |")
        )
    add("")
    add(f"Uncapped, one Lake Ontario boundary chord of "
        f"{analysis['uncapped_max_segment_length_m']:,.4f} m would set `L` for "
        f"the entire index. Capping is what makes the inflation a modest "
        f"constant rather than a barrier.\n")

    fit = analysis["access_pattern_fit"]
    add("### The two access patterns\n")
    add("**EXPLORATORY, not a validated prediction.** An uncounted window-scan "
        "entry and a counted resolve-descent entry are not the same unit of "
        "cost, which is why the two are never summed. The intercept is free and "
        "absorbs verification.\n")
    add("| workload | mode | invocation | n | W | window-scan ns | resolve ns | premium | R^2 |")
    add("|---|---|---|---:|---:|---:|---:|---:|---:|")
    for row in fit["fits"]:
        add(
            f"| {row['workload']} | {row['verification_mode']} | "
            f"{row['invocation'] or '--'} | "
            f"{row['point_count']} | {row['distinct_windows']} | "
            f"{row['window_scan_nanoseconds_per_entry']:.4f} | "
            f"{row['resolve_descent_nanoseconds_per_entry']:.4f} | "
            f"{row['locality_premium']:.3f}x | {row['r_squared']:.5f} |"
        )

    add("\n## Memory\n")
    add("Three instruments, and they disagree in direction. None may be quoted "
        "alone (Nucleus 18.24).\n")
    add("| cell | invocation | structure bytes | peak RSS | peak commit | "
        "RSS above rung 1 | commit above rung 1 |")
    add("|---|---|---:|---:|---:|---:|---:|")
    for row in analysis["memory"]:
        window = row["seed_window"]
        if window is not None and not (
            isinstance(window, float) and math.isnan(window)
        ) and int(window) != 64:
            continue
        def cell(name: str) -> str:
            value = _finite(row[name])
            return f"{value:,.0f}" if value else "--"

        add(
            f"| {row['cell_key']} | {row['invocation'] or '--'} | "
            f"{cell('persistent_structure_bytes')} | "
            f"{cell('peak_working_set_bytes')} | {cell('peak_commit_bytes')} | "
            f"{cell('peak_working_set_above_baseline')} | "
            f"{cell('peak_commit_above_baseline')} |"
        )

    failed = [c for c in analysis["invariants"] if not c["passed"]]
    add(f"\n## Invariants\n")
    add(f"{len(analysis['invariants']) - len(failed)} of "
        f"{len(analysis['invariants'])} re-derived checks passed.\n")
    for check in failed:
        add(f"- **FAILED** {check['check']} at {check['cell']}: {check['measured']}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ladder-runs", default="outputs/benchmark/water_ladder_runs_ladder.csv"
    )
    parser.add_argument(
        "--sweep-runs", default="outputs/benchmark/water_ladder_runs_sweep.csv"
    )
    # The cross-product invocations. Each is optional so the script still runs
    # against the B6c artifacts alone, which is what makes the regression in
    # tests/test_ladder_analysis.py meaningful.
    parser.add_argument(
        "--cross-product-runs",
        default="outputs/benchmark/water_ladder_runs_b6c2.csv",
    )
    parser.add_argument(
        "--sweep-split-runs",
        default="outputs/benchmark/water_ladder_runs_sweepB.csv",
    )
    parser.add_argument(
        "--mode-grid-runs",
        default="outputs/benchmark/water_ladder_runs_gridAB.csv",
    )
    parser.add_argument(
        "--analysis-output", default="outputs/validation/b6_analysis.json"
    )
    parser.add_argument(
        "--table-output", default="outputs/validation/b6_benchmark_tables.md"
    )
    arguments = parser.parse_args()

    import pandas as pd

    requested = {
        "ladder_runs": arguments.ladder_runs,
        "sweep_runs": arguments.sweep_runs,
        "cross_product_runs": arguments.cross_product_runs,
        "sweep_split_runs": arguments.sweep_split_runs,
        "mode_grid_runs": arguments.mode_grid_runs,
    }
    sources: dict[str, dict[str, str]] = {}
    frames: dict[str, Any] = {}
    for name, relative in requested.items():
        path = repository_path(relative)
        if not path.exists():
            # Absent rather than silently empty. A table built from four of five
            # invocations must say which one it is missing.
            sources[name] = {"path": relative, "sha256": None, "present": False}
            continue
        frames[name] = cell_statistics(load_runs(path), invocation=name)
        sources[name] = {
            "path": relative,
            "sha256": sha256_file(path),
            "present": True,
            "cell_count": int(len(frames[name])),
        }

    if "ladder_runs" not in frames:
        raise SystemExit(f"required source missing: {arguments.ladder_runs}")
    ladder = frames["ladder_runs"]
    sweep = frames.get("sweep_runs")
    combined = pd.concat(list(frames.values()), ignore_index=True)
    # The ladder alone carries all five rungs at all three workloads under Option
    # A; the cross-product invocations add the split column. Comparisons are
    # drawn from the union, and each row names the mode and workload it belongs
    # to, so nothing crosses a boundary silently.
    comparison_frame = pd.concat(
        [
            frame for name, frame in frames.items()
            if name in {"ladder_runs", "cross_product_runs", "mode_grid_runs"}
        ],
        ignore_index=True,
    )

    analysis = {
        "chunk": "B6d",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "invariants": check_invariants(combined),
        "adjacent_comparisons": [
            comparison.as_dict()
            for comparison in adjacent_comparisons(comparison_frame)
        ],
        "context_comparisons": [
            comparison.as_dict()
            for comparison in adjacent_comparisons(
                comparison_frame, include_context=True
            )
            if comparison.is_context
        ],
        "cost_model": cost_model(combined),
        "per_property_curve": per_property_curve(comparison_frame),
        "window_curve": (
            (window_curve(sweep) if sweep is not None else [])
            + window_curve(ladder)
            + sum(
                (
                    window_curve(frames[name])
                    for name in ("sweep_split_runs", "mode_grid_runs")
                    if name in frames
                ),
                [],
            )
        ),
        "verification_decomposition": verification_decomposition(comparison_frame),
        "inflation_axis": inflation_axis(comparison_frame),
        "uncapped_max_segment_length_m": UNCAPPED_MAX_SEGMENT_LENGTH_M,
        "access_pattern_fit": access_pattern_fit(combined),
        "memory": memory_table(combined),
        "cross_invocation_agreement": (
            cross_invocation_agreement(ladder, sweep, "ladder", "sweep")
            if sweep is not None else []
        ),
    }

    analysis_output = repository_path(arguments.analysis_output)
    analysis_output.parent.mkdir(parents=True, exist_ok=True)
    analysis_output.write_text(json.dumps(analysis, indent=2, default=str),
                               encoding="utf-8")
    table_output = repository_path(arguments.table_output)
    table_output.write_text(markdown_tables(analysis), encoding="utf-8")

    failed = [c for c in analysis["invariants"] if not c["passed"]]
    print(f"Analysis: {analysis_output}")
    print(f"Tables:   {table_output}")
    print(f"Invariants: {len(analysis['invariants']) - len(failed)} passed, "
          f"{len(failed)} failed")
    for check in failed:
        print(f"  FAILED {check['check']} at {check['cell']}")
    missing = [n for n, s in analysis["sources"].items() if not s.get("present")]
    if missing:
        print(f"Sources ABSENT (tables are incomplete): {', '.join(missing)}")
    for name, population in analysis["cost_model"]["populations"].items():
        slope = population["slope_nanoseconds_per_entry"]
        print(f"Cost model slope [{name}] n={population['point_count']}: "
              + (f"{slope:.2f} ns/entry" if slope else "--"))
    print(f"  B5c isolated constant: "
          f"{analysis['cost_model']['constant_nanoseconds_per_resolve_entry']}")
    unphysical = [
        c for c in analysis["verification_decomposition"]["cells"]
        if not c["search_is_physical"]
    ]
    if unphysical:
        print(f"WARNING: {len(unphysical)} cell(s) imply a negative search cost "
              f"and must not be published as a decomposition")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())