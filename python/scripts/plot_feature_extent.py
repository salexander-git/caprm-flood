"""The poster's exemplar figure: why indexing whole features fails.

    python python/scripts/plot_feature_extent.py

Two panels, one argument.

    Left    the distribution of bounding-box diagonals across every cached water
            feature, on a log axis, with Lake Ontario, the Genesee River and the
            Erie Canal marked individually out at the tail.
    Right   the Monroe County outline with Lake Ontario's axis-aligned bounding
            box drawn over it, swallowing the frame.

The quantity plotted is the BOUNDING-BOX DIAGONAL, not the feature's length or
area, because the bounding box is precisely what a feature-level hierarchy
stores and tests against. A viewer who understands the left panel understands
why the right panel looks the way it does, and why pruning 93 percent of
features still leaves tens of thousands of exact segment checks.

WHAT THIS SCRIPT WILL NOT DO. It recomputes nothing that belongs to the
benchmark artifacts. The candidates-examined and segment-check counts, and the
ratio between selected and average feature size, are measured by the C++
harness and must be quoted from its output rather than re-derived here from
geometry — a second derivation that happened to agree would prove nothing, and
one that disagreed would be a defect discovered on a poster deadline. This
script prints the distribution statistics it DOES measure so the caption can be
written from numbers rather than from memory.

PROVENANCE THE CAPTION NEEDS. The hydrography cache was retrieved for the county
plus a 20,000 m buffer, so Lake Ontario's geometry here is clipped to the study
area. The box drawn on the right is the box of the CACHED feature, not of the
whole lake. The printed summary says so, and the caption must repeat it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from caprm import chart_style as style  # noqa: E402

DISTANCE_CRS = "EPSG:26918"

#: Landscape, unlike chart_style.FIGSIZE_PORTRAIT. A deliberate departure: this
#: figure spans two panels on a landscape poster, and the portrait canvas the
#: existing slides use would force both panels to be unreadably narrow. Every
#: other style value is inherited unchanged so it still reads as one family.
FIGSIZE_LANDSCAPE = (13.0, 5.4)

#: Matched case-insensitively against source_name. Anything not found is
#: reported rather than silently omitted; a missing label on a poster figure is
#: a caption that cannot be trusted.
NAMED_FEATURES = ("Lake Ontario", "Genesee River", "Erie Canal")

BOX_FEATURE = "Lake Ontario"


def load_features(cache_path: Path) -> gpd.GeoDataFrame:
    """Both hydrography layers, concatenated and projected to metres."""
    layers = []
    for layer in ("flowlines", "waterbodies"):
        frame = gpd.read_file(cache_path, layer=layer)
        if frame.crs is None:
            raise SystemExit(f"layer {layer!r} has no CRS")
        frame["layer"] = layer
        layers.append(frame.to_crs(DISTANCE_CRS))
    features = gpd.GeoDataFrame(
        pd.concat(layers, ignore_index=True), geometry="geometry", crs=DISTANCE_CRS
    )
    if "source_name" not in features.columns:
        raise SystemExit(
            f"no source_name column; available: {sorted(features.columns)}"
        )
    return features


def bounding_box_diagonal(features: gpd.GeoDataFrame) -> np.ndarray:
    """The diagonal of each feature's axis-aligned bounding box, in metres."""
    bounds = features.geometry.bounds
    width = (bounds["maxx"] - bounds["minx"]).to_numpy()
    height = (bounds["maxy"] - bounds["miny"]).to_numpy()
    return np.hypot(width, height)


def find_named(features: gpd.GeoDataFrame, name: str) -> pd.DataFrame:
    names = features["source_name"].astype("string").fillna("")
    return features.loc[names.str.contains(name, case=False, regex=False)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hydrography", default="data/raw/usgs_3dhp_monroe.gpkg")
    parser.add_argument("--county", default="data/raw/census_monroe_county_2025.geojson")
    parser.add_argument("--output-stem", default="outputs/figures/poster_feature_extent")
    args = parser.parse_args()

    cache_path = REPOSITORY_ROOT / args.hydrography
    county_path = REPOSITORY_ROOT / args.county
    for path in (cache_path, county_path):
        if not path.exists():
            raise SystemExit(f"missing input: {path}")

    features = load_features(cache_path)
    county = gpd.read_file(county_path).to_crs(DISTANCE_CRS)
    diagonal_m = bounding_box_diagonal(features)
    features = features.assign(bbox_diagonal_m=diagonal_m)

    positive = diagonal_m[diagonal_m > 0]
    print(f"features loaded            {len(features):,}")
    print(f"  flowlines                {int((features['layer'] == 'flowlines').sum()):,}")
    print(f"  waterbodies              {int((features['layer'] == 'waterbodies').sum()):,}")
    print(f"zero-extent features       {int((diagonal_m <= 0).sum()):,} (excluded from the log axis)")
    print(f"bbox diagonal median       {np.median(positive):,.1f} m")
    print(f"bbox diagonal mean         {positive.mean():,.1f} m")
    print(f"bbox diagonal max          {positive.max():,.1f} m")
    print(f"99th percentile            {np.percentile(positive, 99):,.1f} m")

    located: dict[str, float] = {}
    for name in NAMED_FEATURES:
        matches = find_named(features, name)
        if matches.empty:
            print(f"NOT FOUND in source_name   {name!r} — label it by rank or drop it")
            continue
        largest = matches.loc[matches["bbox_diagonal_m"].idxmax()]
        located[name] = float(largest["bbox_diagonal_m"])
        print(
            f"{name:24}   {located[name]:>12,.1f} m diagonal   "
            f"{len(matches)} matching feature(s)   "
            f"{located[name] / positive.mean():>7,.1f}x the mean"
        )

    if BOX_FEATURE not in located:
        raise SystemExit(f"cannot draw the box: {BOX_FEATURE!r} not found in source_name")
    box_rows = find_named(features, BOX_FEATURE)
    box_geometry = box_rows.loc[box_rows["bbox_diagonal_m"].idxmax()].geometry
    minx, miny, maxx, maxy = box_geometry.bounds
    county_minx, county_miny, county_maxx, county_maxy = county.total_bounds
    print(
        f"\n{BOX_FEATURE} cached bbox   "
        f"{(maxx - minx) / 1000:,.1f} km x {(maxy - miny) / 1000:,.1f} km"
    )
    print(
        f"Monroe County bbox         "
        f"{(county_maxx - county_minx) / 1000:,.1f} km x "
        f"{(county_maxy - county_miny) / 1000:,.1f} km"
    )
    print(
        "\nCAPTION MUST SAY: the cache was retrieved for the county plus a "
        "20,000 m buffer,\nso this is the bounding box of the CACHED feature, "
        "not of the whole lake."
    )

    with plt.rc_context(style.rc_params()):
        figure, (left, right) = plt.subplots(
            1, 2, figsize=FIGSIZE_LANDSCAPE, gridspec_kw={"width_ratios": [1.25, 1.0]}
        )

        # -- left: the distribution -------------------------------------------
        bins = np.logspace(np.log10(positive.min()), np.log10(positive.max()), 60)
        left.hist(positive, bins=bins, color=style.PRIMARY, alpha=style.PRIMARY_ALPHA)
        left.set_xscale("log")
        left.set_xlabel("Bounding-box diagonal (m, log scale)", fontsize=style.SIZE_AXIS_LABEL)
        left.set_ylabel("Water features", fontsize=style.SIZE_AXIS_LABEL)
        left.grid(axis="y", color=style.GRID, linewidth=style.LINEWIDTH_GRID)
        left.set_axisbelow(True)
        for spine in ("top", "right"):
            left.spines[spine].set_visible(False)

        ceiling = left.get_ylim()[1]
        for offset, (name, value) in enumerate(sorted(located.items(), key=lambda kv: -kv[1])):
            left.axvline(
                value, color=style.ACCENT, linewidth=style.LINEWIDTH_DASHED,
                dashes=style.DASHES,
            )
            left.annotate(
                f"{name}\n{value / 1000:,.0f} km",
                xy=(value, ceiling * (0.92 - 0.20 * offset)),
                xytext=(-8, 0), textcoords="offset points",
                ha="right", va="top", fontsize=style.SIZE_ANNOTATION,
                fontweight="bold", color=style.ACCENT,
            )

        # -- right: the box over the county -----------------------------------
        county.boundary.plot(ax=right, color=style.INK, linewidth=1.2)
        right.add_patch(
            Rectangle(
                (minx, miny), maxx - minx, maxy - miny,
                facecolor=style.ACCENT, alpha=0.16,
                edgecolor=style.ACCENT, linewidth=style.LINEWIDTH_DASHED,
                dashes=style.DASHES,
            )
        )
        pad = 0.04 * max(maxx - minx, maxy - miny)
        right.set_xlim(min(minx, county_minx) - pad, max(maxx, county_maxx) + pad)
        right.set_ylim(min(miny, county_miny) - pad, max(maxy, county_maxy) + pad)
        right.set_aspect("equal")
        right.set_xticks([])
        right.set_yticks([])
        for spine in right.spines.values():
            spine.set_visible(False)
        right.annotate(
            f"{BOX_FEATURE}\nbounding box",
            xy=(minx + 0.02 * (maxx - minx), maxy - 0.02 * (maxy - miny)),
            ha="left", va="top", fontsize=style.SIZE_ANNOTATION,
            fontweight="bold", color=style.ACCENT,
        )
        right.annotate(
            "Monroe County",
            xy=((county_minx + county_maxx) / 2, county_miny - pad * 0.5),
            ha="center", va="top", fontsize=style.SIZE_ANNOTATION, color=style.INK,
        )

        figure.tight_layout()
        stem = REPOSITORY_ROOT / args.output_stem
        stem.parent.mkdir(parents=True, exist_ok=True)
        for extension in ("png", "svg"):
            path = stem.with_suffix(f".{extension}")
            figure.savefig(path, dpi=style.DPI, bbox_inches="tight",
                           facecolor=style.BACKGROUND)
            print(f"wrote {path}")
        plt.close(figure)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())