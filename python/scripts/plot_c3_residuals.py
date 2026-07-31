"""The C3 figure. Reads the artifacts; computes no statistic of its own.

    python python/scripts/plot_c3_residuals.py

Every number drawn here comes out of a CSV or JSON that
``analyze_c3_residuals.py`` wrote and that a test covers. A plotting script that
recomputes its own numbers is a second implementation of the analysis with no
test behind it, and the two will disagree eventually.

Three panels, because the finding has three parts and the middle one is the
part a reader would otherwise supply from assumption:

    A  mean |residual| against distance to the nearest different-FEMA property,
       majority class only, both partitions, with the cluster-bootstrap
       interval. The blocked curve is a U. The random curve is not. The far arm
       therefore belongs to the partition, not to the boundary.

    B  the label's bin mean against the PREDICTION's bin mean, same bins. The
       label sweeps; the prediction is nearly flat. This is why panel A looks
       the way it does, and without it panel A reads as a boundary artifact.

    C  share of rows against share of squared error, majority against minority.
       The mechanism: a 1.9 percent population carrying a fifth to a third of
       the error, under-predicted on 100 percent of its rows.

Writes outputs/figures/c3_residual_structure.{png,svg} at the sizing measured
from presentation_assets/charts/slide07.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.chart_style import (  # noqa: E402
    DASHES,
    FIGSIZE_PORTRAIT,
    INK,
    LINEWIDTH_DASHED,
    NEUTRAL,
    PRIMARY,
    PRIMARY_ALPHA,
    SAVE_KWARGS,
    SIZE_ANNOTATION,
    rc_params,
)

BLOCKED = "blocked_kfold"
RANDOM = "random_control"
STEM = "c3_residual_structure"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="C3 poster figure")
    p.add_argument("--validation-dir", default="outputs/validation")
    p.add_argument("--out-dir", default="outputs/figures")
    return p.parse_args(argv)


def bin_centres(frame: pd.DataFrame) -> np.ndarray:
    """Geometric centres, with the open top bin placed at 1.4x its lower edge.

    The x axis is logarithmic because the bins are geometric; an open bin has no
    centre, and putting it at its lower edge would draw the far-field point on
    top of the boundary between the last two bins. 1.4x is a plotting choice and
    is stated as one — no statistic depends on it.
    """
    lower = frame["lower_m"].to_numpy(dtype=float)
    upper = frame["upper_m"].to_numpy(dtype=float)
    lower_positive = np.where(lower <= 0.0, 1.0, lower)
    centres = np.sqrt(lower_positive * np.where(np.isfinite(upper), upper, lower_positive))
    return np.where(np.isfinite(upper), centres, lower_positive * 1.4)


def load(validation_dir: Path):
    manifest = json.loads((validation_dir / "c3_error_analysis.json").read_text(encoding="utf-8"))
    tables = {}
    for partition in (BLOCKED, RANDOM):
        tables[partition] = {
            "binned_majority": pd.read_csv(validation_dir / f"c3_binned_majority_{partition}.csv"),
            "bootstrap": pd.read_csv(validation_dir / f"c3_bootstrap_{partition}.csv"),
            "classes": pd.read_csv(validation_dir / f"c3_class_decomposition_{partition}.csv"),
        }
    return manifest, tables


def panel_a(ax, tables) -> None:
    for partition, colour, label in (
        (BLOCKED, PRIMARY, "blocked K-fold"),
        (RANDOM, NEUTRAL, "random control"),
    ):
        binned = tables[partition]["binned_majority"]
        boot = tables[partition]["bootstrap"]
        x = bin_centres(binned)
        y = binned["mean_abs"].to_numpy(dtype=float)
        # the bootstrap table is written in bin order by the CLI, so it aligns
        # row for row; assert rather than trust, because a silent misalignment
        # would draw a plausible band around the wrong points
        if len(boot) != len(binned):
            raise SystemExit(f"{partition}: bootstrap has {len(boot)} rows, binned has {len(binned)}")
        ax.fill_between(
            x, boot["ci_low"].to_numpy(dtype=float), boot["ci_high"].to_numpy(dtype=float),
            color=colour, alpha=0.22, linewidth=0,
        )
        ax.plot(x, y, color=colour, linewidth=2.0, marker="o", markersize=4.5,
                label=label, alpha=PRIMARY_ALPHA)

    blocked = tables[BLOCKED]["binned_majority"]
    x = bin_centres(blocked)
    for i in (0, len(blocked) - 1):
        ax.annotate(
            f"n={int(blocked.loc[i, 'n']):,}",
            (x[i], float(blocked.loc[i, "mean_abs"])),
            textcoords="offset points", xytext=(0, 11), ha="center",
            fontsize=SIZE_ANNOTATION - 2, color=INK,
        )
    ax.set_xscale("log")
    ax.set_ylabel("mean |residual| (index points)")
    ax.set_title("A   a U under blocking, flat under the control", loc="left")
    ax.legend(loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02))


def panel_b(ax, tables) -> None:
    # encoding: COLOUR carries the partition, matching panel A; LINE STYLE
    # carries actual against predicted. Two channels for two variables, so the
    # reader does not have to hold a four-entry legend.
    for partition, colour in ((BLOCKED, PRIMARY), (RANDOM, NEUTRAL)):
        binned = tables[partition]["binned_majority"]
        x = bin_centres(binned)
        ax.plot(x, binned["mean_label"], color=colour, linewidth=2.0,
                marker="o", markersize=4.5, alpha=PRIMARY_ALPHA)
        ax.plot(x, binned["mean_predicted"], color=colour, linewidth=LINEWIDTH_DASHED,
                linestyle="--", dashes=DASHES, marker="s", markersize=4.0,
                alpha=PRIMARY_ALPHA)

    blocked = tables[BLOCKED]["binned_majority"]
    span_label = float(blocked["mean_label"].max() - blocked["mean_label"].min())
    span_pred = float(blocked["mean_predicted"].max() - blocked["mean_predicted"].min())
    ax.annotate(
        f"truth sweeps {span_label:.1f} points\nprediction sweeps {span_pred:.1f}",
        xy=(0.02, 0.06), xycoords="axes fraction", fontsize=SIZE_ANNOTATION,
        fontweight="bold", color=INK, va="bottom",
    )
    ax.set_xscale("log")
    ax.set_xlabel("distance to nearest different-FEMA property (m, log)")
    ax.set_ylabel("bin mean (index points)")
    ax.set_title("B   the prediction is flat; the truth is not", loc="left")
    ax.plot([], [], color=INK, marker="o", linewidth=2.0, label="actual")
    ax.plot([], [], color=INK, marker="s", linestyle="--", dashes=DASHES,
            linewidth=LINEWIDTH_DASHED, label="predicted")
    ax.legend(loc="lower left", ncol=2, bbox_to_anchor=(0.0, 0.16))


def panel_c(ax, manifest, tables) -> None:
    labels, rows, sse = [], [], []
    for partition, name in ((BLOCKED, "blocked"), (RANDOM, "random")):
        classes = tables[partition]["classes"]
        minority = classes[classes["class_value"] != manifest["base_rates"]["majority_class"]]
        labels.append(name)
        rows.append(float(minority["row_share"].sum()) * 100.0)
        sse.append(float(minority["sse_share"].sum()) * 100.0)

    y = np.arange(len(labels))
    height = 0.34
    ax.barh(y + height / 2, rows, height, color=NEUTRAL, alpha=PRIMARY_ALPHA,
            label="share of rows")
    ax.barh(y - height / 2, sse, height, color=PRIMARY, alpha=PRIMARY_ALPHA,
            label="share of squared error")
    for i in range(len(labels)):
        ax.text(rows[i] + 0.7, y[i] + height / 2, f"{rows[i]:.1f}%", va="center",
                fontsize=SIZE_ANNOTATION - 1, color=INK)
        ax.text(sse[i] + 0.7, y[i] - height / 2, f"{sse[i]:.1f}%", va="center",
                fontsize=SIZE_ANNOTATION - 1, fontweight="bold", color=INK)
    ax.set_yticks(y, labels)
    ax.set_xlabel("percent")
    ax.set_xlim(0, 40)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.set_title(
        "C   1.9% of rows, all of them under-predicted", loc="left"
    )
    ax.legend(loc="lower right", ncol=1)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validation_dir, out_dir = Path(args.validation_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest, tables = load(validation_dir)

    if "mean_predicted" not in tables[BLOCKED]["binned_majority"].columns:
        raise SystemExit(
            "c3_binned_majority_*.csv has no mean_predicted column; re-run "
            "analyze_c3_residuals.py after the error_analysis.py patch"
        )

    with plt.rc_context(rc_params()):
        fig, axes = plt.subplots(
            3, 1, figsize=FIGSIZE_PORTRAIT, height_ratios=[1.15, 1.05, 0.62]
        )
        panel_a(axes[0], tables)
        panel_b(axes[1], tables)
        panel_c(axes[2], manifest, tables)
        fig.align_ylabels(axes)
        fig.tight_layout(h_pad=1.6)
        for suffix in ("png", "svg"):
            fig.savefig(out_dir / f"{STEM}.{suffix}", **SAVE_KWARGS)
        plt.close(fig)

    print(f"wrote {out_dir / (STEM + '.png')} and .svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())