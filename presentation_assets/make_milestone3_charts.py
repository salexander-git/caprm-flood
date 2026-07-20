"""
Generate the Milestone 3 presentation charts from the frozen artifacts.

Reads only generated outputs. Writes PNG at 300 dpi for slides and SVG for
any later editing, matching the Milestone 2 chart workflow.

    python presentation_assets/make_milestone3_charts.py

Requires matplotlib, which is presentation tooling rather than a pipeline
dependency:

    .\\.venv\\Scripts\\python.exe -m pip install matplotlib
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter


# Palette lifted from the Milestone 2 deck so the charts sit inside the
# theme rather than next to it.
SAGE = "#A8BF9A"
CREAM = "#FAF7F0"
FOREST = "#2D4A32"
FOREST_DARK = "#1F3A28"
RUST = "#C1704F"
STONE = "#8A9A8F"
GRID = "#DCDCDC"
INK = "#1A1A1A"

COMPONENT_LABELS = {
    "fema": "FEMA\nflood zone",
    "water": "Distance to\nwater",
    "terrain_absolute": "Elevation",
    "terrain_relative": "Relative\nelevation",
}

FAMILY_STYLE = {
    "baseline": (FOREST_DARK, "Baseline", 90),
    "structured": (FOREST, "Structured reweighting", 55),
    "perturbation": (STONE, "Seeded perturbation", 35),
    "reference_corner": (RUST, "Reference corner (calibration)", 70),
}


def style_axes(axes: plt.Axes) -> None:
    axes.set_facecolor("white")
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    axes.spines["left"].set_color(GRID)
    axes.spines["bottom"].set_color(GRID)
    axes.tick_params(colors=INK, labelsize=11)


def save(figure: plt.Figure, output_directory: Path, name: str) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)

    for extension in ("png", "svg"):
        path = output_directory / f"{name}.{extension}"
        figure.savefig(
            path,
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
            transparent=False,
        )
        print(f"  wrote {path}")

    plt.close(figure)


def chart_weight_vs_influence(
    manifest: dict,
    output_directory: Path,
) -> None:
    """
    Slide 8. Declared weight against measured variance share.

    The point is the gap: FEMA holds the largest weight and the smallest
    share of the variance, because 98.1 percent of properties sit at one
    value and a constant cannot move a ranking.
    """
    influence = manifest["summary"]["component_influence"]["components"]
    names = list(influence)

    weights = [influence[name]["weight"] for name in names]
    shares = [influence[name]["variance_share"] for name in names]

    positions = np.arange(len(names))
    width = 0.38

    figure, axes = plt.subplots(figsize=(9.5, 5.0))
    style_axes(axes)

    weight_bars = axes.bar(
        positions - width / 2,
        weights,
        width,
        label="Declared weight",
        color=STONE,
        edgecolor="none",
    )
    share_bars = axes.bar(
        positions + width / 2,
        shares,
        width,
        label="Measured variance share",
        color=FOREST_DARK,
        edgecolor="none",
    )

    for bars in (weight_bars, share_bars):
        for bar in bars:
            axes.annotate(
                f"{bar.get_height():.2f}",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                textcoords="offset points",
                xytext=(0, 4),
                ha="center",
                fontsize=11,
                fontweight="bold",
                color=INK,
            )

    axes.set_xticks(positions)
    axes.set_xticklabels([COMPONENT_LABELS[name] for name in names], fontsize=12)
    axes.set_ylabel("Share of the index", fontsize=12, color=INK)
    axes.set_ylim(0, 0.78)
    axes.yaxis.grid(True, color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    axes.legend(frameon=False, fontsize=11, loc="upper right")

    save(figure, output_directory, "slide08_weight_vs_influence")


def chart_scenario_stability(
    summary: pd.DataFrame,
    output_directory: Path,
) -> None:
    """
    Slide 9. Every scenario's rank correlation with the baseline.

    The reference corners are the reason the plausible cluster can be read
    at all: they establish what a genuinely different weighting does to
    this metric.
    """
    order = ["reference_corner", "perturbation", "structured", "baseline"]
    present = [family for family in order if family in set(summary["family"])]

    figure, axes = plt.subplots(figsize=(10.5, 4.6))
    style_axes(axes)

    for threshold, label in ((0.95, "stable ≥ 0.95"), (0.85, "moderate ≥ 0.85")):
        axes.axvline(threshold, color=GRID, linewidth=1.4, linestyle="--", zorder=1)
        axes.annotate(
            label,
            (threshold, len(present) - 0.35),
            fontsize=9,
            color="#6E6E6E",
            ha="center",
        )

    generator = np.random.default_rng(7)

    for row, family in enumerate(present):
        subset = summary[summary["family"].eq(family)]
        color, label, size = FAMILY_STYLE[family]

        jitter = generator.uniform(-0.13, 0.13, len(subset))

        axes.scatter(
            subset["spearman_with_baseline"],
            np.full(len(subset), row) + jitter,
            s=size,
            color=color,
            alpha=0.85,
            edgecolors="white",
            linewidths=0.6,
            zorder=3,
            label=label,
        )

    for scenario, note, offset in (
        ("equal", "equal weighting\nworst plausible", (-6, 30)),
        ("water_only", "water alone —\ncloser than equal", (10, 30)),
    ):
        match = summary[summary["scenario"].eq(scenario)]

        if match.empty:
            continue

        value = float(match["spearman_with_baseline"].iloc[0])
        row = present.index(match["family"].iloc[0])

        axes.annotate(
            note,
            (value, row),
            textcoords="offset points",
            xytext=offset,
            fontsize=10,
            color=INK,
            ha="center",
            arrowprops={"arrowstyle": "-", "color": "#6E6E6E", "linewidth": 1},
        )

    axes.set_yticks(range(len(present)))
    axes.set_yticklabels(
        [FAMILY_STYLE[family][1].split(" (")[0] for family in present],
        fontsize=11,
    )
    axes.set_ylim(-0.6, len(present) - 0.15)
    axes.set_xlim(0.0, 1.04)
    axes.set_xlabel(
        "Rank correlation with the baseline ranking (Spearman)",
        fontsize=12,
        color=INK,
    )
    axes.xaxis.grid(True, color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)

    save(figure, output_directory, "slide09_scenario_stability")


def chart_stability_by_rank(
    shifts: pd.DataFrame,
    output_directory: Path,
    bin_count: int = 50,
) -> None:
    """
    Slide 10. How far a property moves, as a function of where it ranks.

    Both ends are pinned. The middle is where weight choice decides the
    ordering.
    """
    frame = shifts[["baseline_percentile", "percentile_range"]].copy()

    edges = np.linspace(0.0, 100.0, bin_count + 1)
    frame["bin"] = pd.cut(frame["baseline_percentile"], edges, include_lowest=True)

    grouped = frame.groupby("bin", observed=True)["percentile_range"]

    centers = np.array([interval.mid for interval in grouped.median().index])
    median = grouped.median().to_numpy()
    upper = grouped.quantile(0.90).to_numpy()
    lower = grouped.quantile(0.10).to_numpy()

    figure, axes = plt.subplots(figsize=(10.5, 5.0))
    style_axes(axes)

    axes.fill_between(
        centers,
        lower,
        upper,
        color=SAGE,
        alpha=0.55,
        linewidth=0,
        label="10th–90th percentile of properties in each band",
        zorder=2,
    )
    axes.plot(
        centers,
        median,
        color=FOREST_DARK,
        linewidth=2.6,
        label="Median property",
        zorder=3,
    )

    peak = int(np.argmax(median))

    axes.annotate(
        f"peak instability\n≈ {centers[peak]:.0f}th percentile",
        (centers[peak], median[peak]),
        textcoords="offset points",
        xytext=(0, 26),
        ha="center",
        fontsize=10,
        color=INK,
        arrowprops={"arrowstyle": "-", "color": "#6E6E6E", "linewidth": 1},
    )

    for position, label in ((4, "bottom of the\nranking holds"), (96, "top of the\nranking holds")):
        axes.annotate(
            label,
            (position, 2.0),
            textcoords="offset points",
            xytext=(0, 22),
            ha="center",
            fontsize=10,
            color=RUST,
        )

    axes.set_xlabel("Where the property ranks at the baseline weights (percentile)", fontsize=12, color=INK)
    axes.set_ylabel("Percentile points moved\nacross 36 weightings", fontsize=12, color=INK)
    axes.set_xlim(0, 100)
    axes.set_ylim(0, max(upper) * 1.15)
    axes.yaxis.grid(True, color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    axes.legend(frameon=False, fontsize=11, loc="upper left")

    save(figure, output_directory, "slide10_stability_by_rank")


def chart_index_distribution(
    index: pd.DataFrame,
    output_directory: Path,
) -> None:
    """
    Slide 7. The countywide index distribution.

    The spike near 16 is zone X: 98.1 percent of the county shares one FEMA
    score, so the shape of the whole distribution is set by the other three
    components.
    """
    values = index["exposure_index_0_100"]

    figure, axes = plt.subplots(figsize=(6.5, 8.0))
    style_axes(axes)

    axes.hist(values, bins=120, color=FOREST, edgecolor="none", alpha=0.9)

    statistics = [
        (float(values.median()), f"median {values.median():.1f}", RUST),
        (float(values.mean()), f"mean {values.mean():.1f}", INK),
    ]
    statistics.sort(key=lambda item: item[0])

    for position, (value, label, color) in enumerate(statistics):
        axes.axvline(value, color=color, linewidth=1.8, linestyle="--", zorder=3)

        # Put the lower-value label to the left of its line and the
        # higher-value label to the right so nearby statistics do not overlap.
        is_lower_value = position == 0
        axes.annotate(
            label,
            (value, axes.get_ylim()[1] * 0.92),
            textcoords="offset points",
            xytext=(-6, 0) if is_lower_value else (6, 0),
            ha="right" if is_lower_value else "left",
            va="center",
            fontsize=11,
            color=color,
            fontweight="bold",
        )

    axes.set_xlabel("Exposure index (0–100)", fontsize=12, color=INK)
    axes.set_ylabel("Properties", fontsize=12, color=INK)
    axes.set_xlim(0, 100)
    axes.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    axes.yaxis.grid(True, color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)

    save(figure, output_directory, "slide07_index_distribution")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Milestone 3 presentation charts."
    )
    parser.add_argument(
        "--index-manifest",
        default="outputs/validation/property_exposure_index_countywide_manifest.json",
    )
    parser.add_argument(
        "--index",
        default="outputs/index/property_exposure_index_countywide.csv",
    )
    parser.add_argument(
        "--sensitivity-summary",
        default="outputs/analysis/scoring_sensitivity_summary.csv",
    )
    parser.add_argument(
        "--property-shifts",
        default="outputs/analysis/scoring_sensitivity_property_shifts.csv",
    )
    parser.add_argument(
        "--output-directory",
        default="presentation_assets/charts",
    )

    args = parser.parse_args()

    output_directory = Path(args.output_directory)

    print("Slide 8: declared weight vs measured influence")
    chart_weight_vs_influence(
        json.loads(Path(args.index_manifest).read_text(encoding="utf-8")),
        output_directory,
    )

    print("Slide 9: scenario stability")
    chart_scenario_stability(
        pd.read_csv(args.sensitivity_summary),
        output_directory,
    )

    print("Slide 10: stability by rank")
    chart_stability_by_rank(
        pd.read_csv(args.property_shifts, dtype={"property_id": "string"}),
        output_directory,
    )

    print("Slide 7: index distribution")
    chart_index_distribution(
        pd.read_csv(args.index, dtype={"property_id": "string"}),
        output_directory,
    )

    print("\nDone.")


if __name__ == "__main__":
    main()