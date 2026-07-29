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
    adjacent_comparisons,
    cell_statistics,
    check_invariants,
    cost_model,
    cross_invocation_agreement,
    load_runs,
    memory_table,
    per_property_curve,
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

    add("\n## Three adjacent comparisons\n")
    add("Never 5 v 3: that confounds the dimensionality reduction with the "
        "learning.\n")
    add("| workload | comparison | meaning | wall clock | segment checks | n | resolvable |")
    add("|---|---|---|---:|---:|---|---|")
    for row in analysis["adjacent_comparisons"]:
        ratio = row["segment_check_ratio"]
        checks = "--"
        if ratio:
            checks = (
                f"{ratio:.3f}x fewer" if ratio >= 1
                else f"{1 / ratio:.3f}x more"
            )
        add(
            f"| {row['workload']} | {row['comparison']} | {row['meaning']} | "
            f"{row['wall_clock_factor']:.3f}x "
            f"{row['direction_moving_up_the_ladder']} | {checks} | "
            f"{row['n'][0]}/{row['n'][1]} | "
            f"{'yes' if row['resolvable_against_full_range'] else 'NO'} |"
        )

    add("\n## Cost model: counted entries predict wall clock\n")
    model = analysis["cost_model"]
    add(f"Constant: **{model['constant_nanoseconds_per_resolve_entry']} ns per "
        f"resolve-descent entry**, measured independently. "
        f"{model['constant_provenance']}\n")
    add(f"Least-squares slope through the origin over "
        f"{model['point_count']} matched pairs: "
        f"**{model['fitted_slope_nanoseconds_per_entry_all']:.2f} ns/entry**.\n")
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

    add("\n## Memory\n")
    add("Three instruments, and they disagree in direction. None may be quoted "
        "alone (Nucleus 18.24).\n")
    add("| cell | structure bytes | peak RSS | peak commit | RSS above rung 1 | commit above rung 1 |")
    add("|---|---:|---:|---:|---:|---:|")
    for row in analysis["memory"]:
        if row["seed_window"] not in (None, 64):
            continue
        def cell(name: str) -> str:
            value = _finite(row[name])
            return f"{value:,.0f}" if value else "--"

        add(
            f"| {row['cell_key']} | {cell('persistent_structure_bytes')} | "
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
    parser.add_argument(
        "--analysis-output", default="outputs/validation/b6_analysis.json"
    )
    parser.add_argument(
        "--table-output", default="outputs/validation/b6_benchmark_tables.md"
    )
    arguments = parser.parse_args()

    ladder_path = repository_path(arguments.ladder_runs)
    sweep_path = repository_path(arguments.sweep_runs)

    ladder = cell_statistics(load_runs(ladder_path))
    sweep = cell_statistics(load_runs(sweep_path))
    combined = __import__("pandas").concat([ladder, sweep], ignore_index=True)

    analysis = {
        "chunk": "B6d",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "ladder_runs": {
                "path": arguments.ladder_runs,
                "sha256": sha256_file(ladder_path),
            },
            "sweep_runs": {
                "path": arguments.sweep_runs,
                "sha256": sha256_file(sweep_path),
            },
        },
        "invariants": check_invariants(combined),
        "adjacent_comparisons": [
            comparison.as_dict() for comparison in adjacent_comparisons(ladder)
        ],
        "cost_model": cost_model(combined),
        "per_property_curve": per_property_curve(ladder),
        "window_curve": window_curve(sweep) + window_curve(ladder),
        "memory": memory_table(combined),
        "cross_invocation_agreement": cross_invocation_agreement(
            ladder, sweep, "ladder", "sweep"
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
    slope = analysis["cost_model"]["fitted_slope_nanoseconds_per_entry_all"]
    print(f"Cost model slope: {slope:.2f} ns/entry "
          f"(B5c isolated constant: "
          f"{analysis['cost_model']['constant_nanoseconds_per_resolve_entry']})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())