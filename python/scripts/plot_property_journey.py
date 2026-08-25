"""One property's journey: from a coordinate pair to a ranked member of the index.

    python python/scripts/plot_property_journey.py --trace outputs/figures/poster_property_trace.json

Four stages, read left to right, because that is the claim:

    WHERE IT IS        the county, the property, its identifier and coordinates
    WHAT WAS MEASURED  four evidence values, each with the dataset AND THE RECORD
                       IDENTIFIER WITHIN IT that produced the value
    HOW IT SCORED      four component scores, with the weight applied to each
    WHERE IT LANDS     all 267,362 index values, with this property marked

...and an audit strip beneath all four, because the question this panel exists
to answer is not "what is this property's score" but "why should I believe it".

NAMING A DATASET IS NOT PROVENANCE. "FEMA NFHL" tells a reader where the value
came from in the loosest sense; the NFHL polygon identifier tells them which
record to open. The first invites trust, the second makes trust unnecessary.
Every value in stage 2 therefore carries the identifier that would let someone
retrieve it, and where no such identifier exists — a DEM sample has no record
id, only a raster and a sampling radius — the figure says that instead of
inventing one.

The audit strip carries the claim the rest of the poster earns: the
nearest-water distance was computed by two independently written
implementations, in two languages, which agreed field-for-field across every
property in the county. That is a stronger answer to "am I supposed to just
believe this" than any label, and it applies to this property because it applied
to all 267,362 of them.

The fourth stage is the one that makes the word "relative" mean something. An
index of 75.8 is not interpretable on its own; 75.8 drawn against the county's
whole distribution is. A trace that stops at the composite has shown the
arithmetic and withheld the claim.

The third stage must distinguish the two kinds of score, because they are not
the same kind of number. The FEMA component is ABSOLUTE — a zone maps to a fixed
severity regardless of what other properties exist. The other three are PURE
RANK INVERSION against the countywide distribution, with magnitude discarded.
"99.6" for distance-to-water does not mean 4.6 m is dangerous; it means this
property is nearer to water than 99.6 percent of Monroe County. Printing both
kinds of number on one axis without saying which is which would be the panel
quietly lying.

READ-ONLY, and it recomputes nothing. Stage 3's numbers come from the trace
JSON, which was itself read from the frozen index and checked against the stored
composite. Stage 4 reads the index only to draw its distribution.
"""

from __future__ import annotations

import argparse
import json
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

from caprm import chart_style as style  # noqa: E402

DISTANCE_CRS = "EPSG:26918"
FIGSIZE = (14.0, 5.6)

#: Component -> (display label, the dataset the evidence came from, colour).
#: The source is on the poster because "evidence" means a value you can trace to
#: a named public dataset, not a number the system asserts.
COMPONENTS = {
    "fema": ("FEMA flood zone", "FEMA NFHL", style.PRIMARY),
    "water": ("Distance to water", "USGS 3DHP", style.ACCENT),
    "terrain_absolute": ("Elevation", "USGS 3DEP", style.NEUTRAL),
    "terrain_relative": ("Relative elevation", "USGS 3DEP", "#a8b5ac"),
}

#: How to name the specific record behind each value. A DEM sample has no record
#: identifier — it is a raster read at a coordinate — so it names the raster and
#: the sampling radius rather than pretending to an id it does not have.
def record_reference(component: str, evidence: dict, raster: str, radius_m: float) -> str:
    if component == "fema":
        identifier = evidence.get("source_geometry_id")
        if identifier in (None, "", "nan"):
            return "polygon id not carried in the evidence table"
        return f"polygon {identifier}"
    if component == "water":
        identifier = evidence.get("nearest_water_source_id")
        if identifier in (None, "", "nan"):
            return "feature id not carried in the evidence table"
        return f"feature {identifier}"
    return f"{raster}, {radius_m:g} m radius"

#: Which components are ranked against the county rather than scored absolutely.
RANKED = {"water", "terrain_absolute", "terrain_relative"}


def evidence_line(component: str, evidence: dict) -> str:
    """One human-readable line per component, rounded to poster precision."""
    if component == "fema":
        zone = evidence.get("fema_zone", "?")
        return f"Zone {zone}\nmapped hazard polygon"
    if component == "water":
        metres = float(evidence["nearest_water_distance_m"])
        name = evidence.get("nearest_water_name") or "unnamed feature"
        return f"{metres:,.1f} m\nto {name}"
    if component == "terrain_absolute":
        return f"{float(evidence['terrain_elevation_m']):,.1f} m\nground elevation"
    if component == "terrain_relative":
        value = float(evidence["terrain_relative_elevation_m"])
        return f"{value:+,.1f} m\nvs. local surroundings"
    raise ValueError(component)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trace", default="outputs/figures/poster_property_trace.json")
    parser.add_argument("--county", default="data/raw/census_monroe_county_2025.geojson")
    parser.add_argument("--index", default="outputs/index/property_exposure_index_countywide.csv")
    parser.add_argument("--output-stem", default="outputs/figures/poster_property_journey")
    parser.add_argument("--terrain-raster", default="monroe_dem_utm18.tif")
    parser.add_argument("--sample-radius-meters", type=float, default=90.0)
    # These describe the countywide Python/C++ comparison. They are printed
    # loudly below so they are verified against the validation artifacts rather
    # than trusted because they are defaults.
    parser.add_argument("--agreement-n", type=int, default=267_362)
    parser.add_argument("--agreement-max-error-m", type=float, default=4.658e-10)
    args = parser.parse_args()

    record = json.loads((REPOSITORY_ROOT / args.trace).read_text(encoding="utf-8"))
    county = gpd.read_file(REPOSITORY_ROOT / args.county).to_crs(DISTANCE_CRS)
    index = pd.read_csv(
        REPOSITORY_ROOT / args.index, usecols=["exposure_index_0_100"], float_precision="round_trip"
    )

    x = record["coordinates"]["x_m"]
    y = record["coordinates"]["y_m"]
    composite = record["exposure_index_0_100"]
    percentile = record["exposure_percentile"]
    components = {entry["component"]: entry for entry in record["components"]}
    order = list(COMPONENTS)

    print(f"property        {record['property_id']}")
    print(f"index           {composite:.2f}  ({percentile:.1f}th percentile)")
    print(f"index rows      {len(index):,}")
    print(f"index median    {index['exposure_index_0_100'].median():.2f}")
    print(f"properties at or below this one  {int((index['exposure_index_0_100'] <= composite).sum()):,}")

    with plt.rc_context(style.rc_params()):
        figure = plt.figure(figsize=FIGSIZE)
        # Stage 1 is narrow on purpose: Monroe County is taller than it is wide,
        # so an equal-aspect axes any wider than this just letterboxes.
        grid = figure.add_gridspec(
            1, 4, width_ratios=[0.68, 1.15, 1.25, 1.40], wspace=0.30
        )
        locator = figure.add_subplot(grid[0, 0])
        measured = figure.add_subplot(grid[0, 1])
        scored = figure.add_subplot(grid[0, 2])
        landed = figure.add_subplot(grid[0, 3])

        stage_titles = [
            (locator, "1  WHERE IT IS"),
            (measured, "2  WHAT WAS MEASURED"),
            (scored, "3  HOW IT SCORED"),
            (landed, "4  WHERE IT LANDS"),
        ]
        for axis, title in stage_titles:
            axis.set_title(title, fontsize=style.SIZE_PANEL_TITLE, fontweight="bold",
                           color=style.INK, loc="left", pad=10)

        # -- 1. where it is ---------------------------------------------------
        county.boundary.plot(ax=locator, color=style.INK, linewidth=1.1)
        county.plot(ax=locator, color=style.GRID, alpha=0.35)
        locator.plot([x], [y], marker="o", markersize=9, color=style.ACCENT, zorder=5)
        locator.plot([x], [y], marker="o", markersize=20, markerfacecolor="none",
                     markeredgecolor=style.ACCENT, markeredgewidth=1.6, zorder=5)
        locator.set_aspect("equal")
        locator.set_xticks([])
        locator.set_yticks([])
        for spine in locator.spines.values():
            spine.set_visible(False)
        locator.annotate(
            f"Parcel {record['property_id']}\n{x:,.0f} E   {y:,.0f} N\n{DISTANCE_CRS}",
            xy=(0.5, -0.04), xycoords="axes fraction", ha="center", va="top",
            fontsize=style.SIZE_ANNOTATION, color=style.INK, family="monospace",
        )

        # -- 2. what was measured ---------------------------------------------
        measured.set_xlim(0, 1)
        measured.set_ylim(0, len(order))
        measured.axis("off")
        for position, name in enumerate(order):
            top = len(order) - position
            label, source, colour = COMPONENTS[name]
            evidence = components[name]["evidence"]
            measured.add_patch(
                plt.Rectangle((0.0, top - 0.94), 0.045, 0.86, color=colour,
                              alpha=style.PRIMARY_ALPHA)
            )
            measured.annotate(
                source, xy=(0.10, top - 0.10), ha="left", va="top",
                fontsize=style.SIZE_ANNOTATION - 1, color=style.NEUTRAL,
                fontweight="bold",
            )
            measured.annotate(
                evidence_line(name, evidence),
                xy=(0.10, top - 0.34), ha="left", va="top",
                fontsize=style.SIZE_ANNOTATION, color=style.INK,
            )
            measured.annotate(
                record_reference(name, evidence, args.terrain_raster,
                                 args.sample_radius_meters),
                xy=(0.10, top - 0.76), ha="left", va="top",
                fontsize=style.SIZE_ANNOTATION - 2, color=style.NEUTRAL,
                family="monospace",
            )

        # -- 3. how it scored -------------------------------------------------
        positions = np.arange(len(order))[::-1]
        for position, name in zip(positions, order):
            entry = components[name]
            label, _, colour = COMPONENTS[name]
            scored.barh(position, entry["score_0_100"], height=0.52, color=colour,
                        alpha=style.PRIMARY_ALPHA)
            scored.annotate(
                f"{label}   ×{entry['weight']:.2f}",
                xy=(0, position + 0.42), ha="left", va="bottom",
                fontsize=style.SIZE_ANNOTATION, color=style.INK, fontweight="bold",
            )
            scored.annotate(
                f"{entry['score_0_100']:.1f}",
                xy=(entry["score_0_100"] + 3, position), ha="left", va="center",
                fontsize=style.SIZE_ANNOTATION, color=style.INK,
            )
        scored.set_xlim(0, 118)
        scored.set_ylim(-0.7, len(order) - 0.15)
        scored.set_yticks([])
        scored.set_xticks([0, 50, 100])
        scored.set_xlabel("Component score (0-100)", fontsize=style.SIZE_AXIS_LABEL)
        scored.grid(axis="x", color=style.GRID, linewidth=style.LINEWIDTH_GRID)
        scored.set_axisbelow(True)
        for spine in ("top", "right", "left"):
            scored.spines[spine].set_visible(False)
        scored.annotate(
            "FEMA is absolute; the other three rank this\nproperty against all 267,362 in the county",
            xy=(0.0, -0.26), xycoords="axes fraction", ha="left", va="top",
            fontsize=style.SIZE_ANNOTATION - 1, color=style.NEUTRAL, style="italic",
        )

        # -- 4. where it lands ------------------------------------------------
        values = index["exposure_index_0_100"].to_numpy()
        landed.hist(values, bins=90, color=style.NEUTRAL, alpha=0.55)
        landed.axvline(composite, color=style.ACCENT, linewidth=2.2)
        ceiling = landed.get_ylim()[1]
        landed.annotate(
            f"this property\n{composite:.1f}\n{percentile:.1f}th percentile",
            xy=(composite, ceiling * 0.92), xytext=(-10, 0), textcoords="offset points",
            ha="right", va="top", fontsize=style.SIZE_ANNOTATION,
            fontweight="bold", color=style.ACCENT,
        )
        landed.set_xlabel("Exposure index (0-100)", fontsize=style.SIZE_AXIS_LABEL)
        landed.set_ylabel("Properties in Monroe County", fontsize=style.SIZE_AXIS_LABEL)
        landed.yaxis.set_major_formatter(plt.FuncFormatter(style.thousands))
        landed.grid(axis="y", color=style.GRID, linewidth=style.LINEWIDTH_GRID)
        landed.set_axisbelow(True)
        for spine in ("top", "right"):
            landed.spines[spine].set_visible(False)

        # -- the audit strip --------------------------------------------------
        audit = (
            f"AUDIT   "
            f"nearest-water distance computed independently in Python and C++, "
            f"agreeing on {args.agreement_n:,} / {args.agreement_n:,} properties "
            f"to {args.agreement_max_error_m:.3e} m     ·     "
            f"every source dataset checksummed and manifested with its retrieval "
            f"date     ·     all metric work in {DISTANCE_CRS}     ·     "
            f"scoring policy {record['scoring_policy_version']}, weights explicit "
            f"and configurable     ·     deterministic: same inputs, same outputs"
        )
        figure.text(
            0.5, -0.02, audit, ha="center", va="top",
            fontsize=style.SIZE_ANNOTATION - 1, color=style.INK,
        )

        print("\nVERIFY BEFORE PRINTING — these are CLI defaults, not read from artifacts:")
        print(f"  agreement n         {args.agreement_n:,}")
        print(f"  agreement max error {args.agreement_max_error_m:.3e} m")
        print("  Check both against the countywide Python/C++ validation artifacts.")

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