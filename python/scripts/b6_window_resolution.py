"""Window-sweep resolution check and Figure 2 generation.

Reads the two countywide seed-window sweep run tables, computes per-cell
minimum/median/maximum computation time, applies the project's interval
resolution rule to every binary-versus-RMI pair, and renders the
window-sweep figure used in the performance evaluation section.

The resolution rule, as declared in the report:

    ratio interval = [min_rmi / max_binary, max_rmi / min_binary]

taken over per-repetition samples within a cell. A comparison is RESOLVED
only if that interval excludes 1.0. No distributional assumption is made
and no standard error is computed.

Warm-up rows are excluded. Cells are keyed by
(verification_mode, seed_window_entries, algorithm) so that no two
invocations are pooled.

Usage
-----
    python scripts/b6_window_resolution.py

Outputs
-------
    outputs/validation/b6_window_resolution.json
    outputs/validation/b6_window_resolution.csv
    outputs/figures/fig_window_sweep.png
    outputs/figures/fig_window_sweep.pdf
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]

SOURCES = [
    (REPO / "outputs/benchmark/water_ladder_runs_sweep.csv", "original"),
    (REPO / "outputs/benchmark/water_ladder_runs_sweepB.csv", "split"),
]

VALIDATION_DIR = REPO / "outputs/validation"
FIGURE_DIR = REPO / "outputs/figures"

TIME_COLUMN = "computation_seconds"
ALGORITHMS = ("hilbert_binary", "hilbert_rmi")


def is_warmup(row: dict[str, str]) -> bool:
    """True when the row is a discarded warm-up invocation."""
    return str(row.get("is_warmup", "")).strip().lower() in {"true", "1"}


def load_cells() -> dict[tuple[str, int, str], list[float]]:
    """Return {(verification_mode, window, algorithm): [seconds, ...]}."""
    cells: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    for path, declared_mode in SOURCES:
        if not path.exists():
            raise FileNotFoundError(f"missing source table: {path}")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if is_warmup(row):
                    continue
                if row.get("workload") != "countywide":
                    continue
                algorithm = row.get("algorithm", "")
                if algorithm not in ALGORITHMS:
                    continue
                mode = row.get("verification_mode") or declared_mode
                window_raw = row.get("seed_window_entries", "")
                seconds_raw = row.get(TIME_COLUMN, "")
                if not window_raw or not seconds_raw:
                    continue
                window = int(float(window_raw))
                cells[(mode, window, algorithm)].append(float(seconds_raw))
    if not cells:
        raise RuntimeError(
            "no countywide non-warmup rows matched; check column names with "
            "`Import-Csv <path> | Select-Object -First 1 | Format-List`"
        )
    return cells


def summarise(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    return {
        "n": len(ordered),
        "minimum_seconds": ordered[0],
        "median_seconds": median(ordered),
        "maximum_seconds": ordered[-1],
    }


def compare(binary: list[float], rmi: list[float]) -> dict[str, object]:
    """Apply the interval resolution rule to one binary/RMI pair."""
    low = min(rmi) / max(binary)
    high = max(rmi) / min(binary)
    resolved = not (low <= 1.0 <= high)
    if resolved:
        direction = "rmi_faster" if high < 1.0 else "binary_faster"
    else:
        direction = "not_resolved"
    return {
        "median_ratio_rmi_over_binary": median(sorted(rmi)) / median(sorted(binary)),
        "interval_low": low,
        "interval_high": high,
        "interval_contains_one": not resolved,
        "verdict": "RESOLVED" if resolved else "NOT RESOLVED",
        "direction": direction,
    }


def build_report(cells) -> dict[str, object]:
    modes = sorted({mode for (mode, _, _) in cells})
    report: dict[str, object] = {
        "rule": (
            "interval = [min_rmi/max_binary, max_rmi/min_binary] over "
            "per-repetition samples; RESOLVED only if 1.0 is excluded"
        ),
        "warmups_excluded": True,
        "sources": [str(path.relative_to(REPO)) for path, _ in SOURCES],
        "cells": [],
    }
    rows: list[dict[str, object]] = []
    for mode in modes:
        windows = sorted({w for (m, w, _) in cells if m == mode})
        for window in windows:
            binary = cells.get((mode, window, "hilbert_binary"))
            rmi = cells.get((mode, window, "hilbert_rmi"))
            if not binary or not rmi:
                continue
            entry = {
                "verification_mode": mode,
                "seed_window_entries": window,
                "binary": summarise(binary),
                "rmi": summarise(rmi),
                "comparison": compare(binary, rmi),
            }
            report["cells"].append(entry)
            rows.append(
                {
                    "verification_mode": mode,
                    "seed_window_entries": window,
                    "n_binary": entry["binary"]["n"],
                    "n_rmi": entry["rmi"]["n"],
                    "binary_median_s": round(entry["binary"]["median_seconds"], 6),
                    "rmi_median_s": round(entry["rmi"]["median_seconds"], 6),
                    "median_ratio": round(
                        entry["comparison"]["median_ratio_rmi_over_binary"], 6
                    ),
                    "interval_low": round(entry["comparison"]["interval_low"], 6),
                    "interval_high": round(entry["comparison"]["interval_high"], 6),
                    "verdict": entry["comparison"]["verdict"],
                    "direction": entry["comparison"]["direction"],
                }
            )
    report["table"] = rows
    return report


def render_figure(report: dict[str, object]) -> None:
    cells = report["cells"]
    modes = sorted({c["verification_mode"] for c in cells})

    figure, axes = plt.subplots(
        2, len(modes), figsize=(3.45 * len(modes), 4.4), sharex=True
    )
    if len(modes) == 1:
        axes = axes.reshape(2, 1)

    for column, mode in enumerate(modes):
        subset = [c for c in cells if c["verification_mode"] == mode]
        subset.sort(key=lambda c: c["seed_window_entries"])
        windows = [c["seed_window_entries"] for c in subset]
        binary = [c["binary"]["median_seconds"] for c in subset]
        rmi = [c["rmi"]["median_seconds"] for c in subset]
        ratio = [c["comparison"]["median_ratio_rmi_over_binary"] for c in subset]
        low = [c["comparison"]["interval_low"] for c in subset]
        high = [c["comparison"]["interval_high"] for c in subset]
        resolved = [c["comparison"]["verdict"] == "RESOLVED" for c in subset]

        top = axes[0][column]
        top.plot(windows, binary, marker="o", markersize=3.5,
                 linewidth=1.2, label="binary seed", color="#1b3a5c")
        top.plot(windows, rmi, marker="s", markersize=3.5,
                 linewidth=1.2, label="learned seed", color="#b3541e")
        top.set_xscale("log", base=2)
        top.set_ylabel("median computation (s)")
        top.set_title(f"{mode} verification", fontsize=9)
        top.grid(True, alpha=0.25, linewidth=0.5)
        if column == 0:
            top.legend(fontsize=7.5, frameon=False)

        bottom = axes[1][column]
        bottom.axhline(1.0, color="#666666", linewidth=0.9, linestyle="--")
        bottom.fill_between(windows, low, high, color="#b3541e",
                            alpha=0.15, linewidth=0)
        bottom.plot(windows, ratio, marker="o", markersize=3.5,
                    linewidth=1.2, color="#b3541e")
        for w, r, ok in zip(windows, ratio, resolved):
            if not ok:
                bottom.plot([w], [r], marker="o", markersize=7,
                            markerfacecolor="none", markeredgecolor="#666666",
                            markeredgewidth=1.0)
        bottom.set_xscale("log", base=2)
        bottom.set_xlabel("seed window (entries)")
        bottom.set_ylabel("learned / binary")
        bottom.grid(True, alpha=0.25, linewidth=0.5)

    figure.tight_layout()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        figure.savefig(FIGURE_DIR / f"fig_window_sweep.{suffix}", dpi=300)
    plt.close(figure)


def main() -> None:
    cells = load_cells()
    report = build_report(cells)

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    (VALIDATION_DIR / "b6_window_resolution.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    rows = report["table"]
    with (VALIDATION_DIR / "b6_window_resolution.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    render_figure(report)

    header = (
        f"{'mode':<9}{'w':>6}{'n':>4}{'binary':>10}{'rmi':>10}"
        f"{'ratio':>9}{'low':>9}{'high':>9}  verdict"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['verification_mode']:<9}{row['seed_window_entries']:>6}"
            f"{row['n_binary']:>4}{row['binary_median_s']:>10.4f}"
            f"{row['rmi_median_s']:>10.4f}{row['median_ratio']:>9.4f}"
            f"{row['interval_low']:>9.4f}{row['interval_high']:>9.4f}"
            f"  {row['verdict']}"
        )
    print()
    print("wrote outputs/validation/b6_window_resolution.{json,csv}")
    print("wrote outputs/figures/fig_window_sweep.{png,pdf}")


if __name__ == "__main__":
    main()