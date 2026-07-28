"""Milestone 4, chunk B2 — figure for the segment-BVH entry-extent sweep.

Reads the sweep summary written by ``python/scripts/sweep_segment_bvh_cap.py``
and draws the entries-vs-extent tradeoff curve alongside the search and
verification cost axes, so the shape of the curve can be read rather than
inferred from a table.

The unlimited-extent point (cap 0) has no finite cap value, so it is drawn at
the right-hand edge of the log axis and labelled, rather than being dropped or
silently plotted at zero.

Usage (from the repository root)::

    python python/scripts/plot_segment_bvh_cap_sweep.py

Requires matplotlib, which is pinned in requirements.txt at 3.11.0.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

try:
    import matplotlib
except ModuleNotFoundError as error:  # pragma: no cover
    raise SystemExit(
        "matplotlib is required for the B2 figure. It is pinned in "
        "requirements.txt; install it into the project virtual "
        "environment rather than globally:\n"
        "    .\\.venv\\Scripts\\python.exe -m pip install "
        "-r requirements.txt"
    ) from error

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from caprm.ingest import repository_path  # noqa: E402

MODE_STYLE = {
    "original": {
        "label": "verify over original geometry",
        "marker": "o",
        "linestyle": "-",
    },
    "split": {
        "label": "verify over split geometry",
        "marker": "s",
        "linestyle": "--",
    },
}


def finite_caps(points: list[dict[str, Any]]) -> list[float]:
    return sorted(
        {
            float(point["max_segment_length_cap_m"])
            for point in points
            if float(point["max_segment_length_cap_m"]) > 0.0
        }
    )


def plot_position(
    cap_meters: float,
    unlimited_position: float,
) -> float:
    """X position for a cap value on the log axis.

    Cap 0 means "do not split", which is an unbounded extent rather than a
    zero one. Plotting it at 0 on a log axis is impossible and plotting it as
    a small number would be a lie, so it is placed past the largest finite cap
    and labelled.
    """
    cap_meters = float(cap_meters)

    return (
        unlimited_position
        if cap_meters <= 0.0
        else cap_meters
    )


def series_for_mode(
    points: list[dict[str, Any]],
    verification_mode: str,
    unlimited_position: float,
    value: Any,
) -> tuple[list[float], list[float]]:
    selected = [
        point
        for point in points
        if point["verification_mode"] == verification_mode
    ]

    selected.sort(
        key=lambda point: plot_position(
            point["max_segment_length_cap_m"],
            unlimited_position,
        )
    )

    positions = [
        plot_position(
            point["max_segment_length_cap_m"],
            unlimited_position,
        )
        for point in selected
    ]

    values = [float(value(point)) for point in selected]

    return positions, values


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Draw the segment-BVH entry-extent sweep figure."
        )
    )

    parser.add_argument(
        "--summary",
        default=(
            "outputs/validation/"
            "water_segment_bvh_cap_sweep_summary.json"
        ),
    )

    parser.add_argument(
        "--figure-output",
        default=(
            "outputs/figures/segment_bvh_cap_sweep.png"
        ),
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=160,
    )

    args = parser.parse_args()

    summary_path = repository_path(args.summary)

    if not summary_path.exists():
        raise SystemExit(
            f"Sweep summary does not exist: {summary_path}. "
            "Run python/scripts/sweep_segment_bvh_cap.py first."
        )

    summary = json.loads(
        summary_path.read_text(encoding="utf-8")
    )

    points: list[dict[str, Any]] = summary["points"]

    if not points:
        raise SystemExit("Sweep summary contains no points.")

    caps = finite_caps(points)
    unlimited_position = (max(caps) * 3.0) if caps else 1.0

    modes = sorted(
        {point["verification_mode"] for point in points}
    )

    figure, axes = plt.subplots(
        2,
        2,
        figsize=(12.0, 8.5),
    )

    property_count = int(summary["property_count"])

    figure.suptitle(
        "CAPRM-Flood M4 B2 — segment-BVH entry-extent sweep, "
        f"{property_count:,} properties, EPSG:26918",
        fontsize=12,
    )

    # Panel 1: the tradeoff itself. Entries and extent against the cap.
    entries_axis = axes[0][0]

    positions, entries = series_for_mode(
        points,
        modes[0],
        unlimited_position,
        lambda point: point["index_entry_count"],
    )

    entries_axis.plot(
        positions,
        entries,
        marker="o",
        color="tab:blue",
        label="index entries",
    )

    entries_axis.set_xscale("log")
    entries_axis.set_yscale("log")
    entries_axis.set_xlabel("entry-extent cap (m)")
    entries_axis.set_ylabel("index entries")
    entries_axis.set_title("Entries vs entry-extent cap")

    extent_axis = entries_axis.twinx()

    _, extents = series_for_mode(
        points,
        modes[0],
        unlimited_position,
        lambda point: point["max_entry_extent_m"],
    )

    extent_axis.plot(
        positions,
        extents,
        marker="^",
        color="tab:red",
        linestyle=":",
        label="max entry extent",
    )

    extent_axis.set_yscale("log")
    extent_axis.set_ylabel(
        "max entry extent (m)", color="tab:red"
    )

    # Panel 2: search cost. This is the axis run grouping would have moved.
    search_axis = axes[0][1]

    for mode in modes:
        style = MODE_STYLE[mode]

        positions, node_visits = series_for_mode(
            points,
            mode,
            unlimited_position,
            lambda point: point["per_property"][
                "index_node_visits"
            ],
        )

        search_axis.plot(
            positions,
            node_visits,
            marker=style["marker"],
            linestyle=style["linestyle"],
            label=f"node visits, {mode}",
        )

        _, box_tests = series_for_mode(
            points,
            mode,
            unlimited_position,
            lambda point: point["per_property"][
                "segment_box_tests"
            ],
        )

        search_axis.plot(
            positions,
            box_tests,
            marker=style["marker"],
            linestyle=style["linestyle"],
            alpha=0.6,
            label=f"entry box tests, {mode}",
        )

    search_axis.set_xscale("log")
    search_axis.set_xlabel("entry-extent cap (m)")
    search_axis.set_ylabel("operations per property")
    search_axis.set_title(
        "Search cost (phase 1 traversal)"
    )
    search_axis.legend(fontsize=8)

    # Panel 3: verification cost, the part B1 identified as dominant.
    verification_axis = axes[1][0]

    for mode in modes:
        style = MODE_STYLE[mode]

        positions, checks = series_for_mode(
            points,
            mode,
            unlimited_position,
            lambda point: point["per_property"][
                "segment_checks"
            ],
        )

        verification_axis.plot(
            positions,
            checks,
            marker=style["marker"],
            linestyle=style["linestyle"],
            label=style["label"],
        )

    verification_axis.set_xscale("log")
    verification_axis.set_yscale("log")
    verification_axis.set_xlabel("entry-extent cap (m)")
    verification_axis.set_ylabel(
        "segment checks per property"
    )
    verification_axis.set_title(
        "Verification cost (phase 2)"
    )
    verification_axis.legend(fontsize=8)

    # Panel 4: wall clock. The prediction under test is that the original-mode
    # curve is nearly flat because verification dominates.
    clock_axis = axes[1][1]

    for mode in modes:
        style = MODE_STYLE[mode]

        positions, seconds = series_for_mode(
            points,
            mode,
            unlimited_position,
            lambda point: point["computation_seconds"][
                "median"
            ],
        )

        clock_axis.plot(
            positions,
            seconds,
            marker=style["marker"],
            linestyle=style["linestyle"],
            label=style["label"],
        )

    clock_axis.set_xscale("log")
    clock_axis.set_xlabel("entry-extent cap (m)")
    clock_axis.set_ylabel(
        "median query seconds "
        f"({summary['repetitions']} reps)"
    )
    clock_axis.set_title("Wall clock")
    clock_axis.legend(fontsize=8)

    for axis in (
        entries_axis,
        search_axis,
        verification_axis,
        clock_axis,
    ):
        axis.grid(True, which="both", alpha=0.25)

        if any(
            float(point["max_segment_length_cap_m"]) <= 0.0
            for point in points
        ):
            axis.axvline(
                unlimited_position,
                color="grey",
                linestyle="-.",
                alpha=0.5,
            )

            axis.annotate(
                "no split",
                xy=(unlimited_position, 1.0),
                xycoords=("data", "axes fraction"),
                xytext=(-4, -12),
                textcoords="offset points",
                rotation=90,
                fontsize=7,
                color="grey",
                ha="right",
                va="top",
            )

    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))

    figure_output_path = repository_path(args.figure_output)
    figure_output_path.parent.mkdir(
        parents=True, exist_ok=True
    )

    figure.savefig(figure_output_path, dpi=args.dpi)

    print(f"Wrote {figure_output_path}")


if __name__ == "__main__":
    main()