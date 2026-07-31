"""One property, end to end: coordinates to countywide rank, with its evidence.

Two modes.

    python python/scripts/trace_property.py --shortlist
        Rank properties by how much their four components DISAGREE and print
        the top candidates. Pick one.

    python python/scripts/trace_property.py --property-id <id>
        Emit that property's full trace as JSON, as a markdown block ready to
        lay out, and as a stacked contribution bar.

WHY DISAGREEMENT IS THE SELECTION CRITERION. A property whose four components
all read 90 shows a viewer nothing: any one of the four would have produced the
same answer, and the index looks like a relabelling of its inputs. A property
inside a mapped hazard zone, close to a named river, on unremarkable terrain
demonstrates the thing the index actually does — it weighs evidence that
disagrees. The panel's job is to make "evidence" a claim rather than a word, and
disagreement is what gives it something to be a claim about.

WHAT THE TRACE MUST CARRY, because this is the panel that answers "so what":
every value with its source and its units, then the weight applied to it, then
its contribution to the composite, then the countywide rank. A viewer should be
able to follow one number from a coordinate pair to a percentile without being
asked to trust anything in between.

READ-ONLY. This script recomputes nothing. Every component score, the composite
and the percentile are READ from the frozen index; the weighted contributions
are the only arithmetic performed here, and they are checked against the stored
composite before anything is printed. A trace that silently re-derived its own
numbers would be a demonstration of this script, not of the system.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from caprm import chart_style as style  # noqa: E402
from caprm.scoring import COMPONENT_COLUMNS, DEFAULT_WEIGHTS  # noqa: E402

KEY = "property_id"

COMPONENT_LABELS = {
    "fema": "FEMA flood zone",
    "water": "Distance to water",
    "terrain_absolute": "Elevation",
    "terrain_relative": "Relative elevation",
}

EVIDENCE_FOR_COMPONENT = {
    # source_geometry_id is the NFHL polygon this property fell inside. It is
    # the identifier a skeptic uses to look the record up, which is what makes
    # "auditable" a claim rather than an adjective.
    "fema": ("fema_zone", "is_sfha", "matched_fema_polygon", "source_geometry_id"),
    "water": ("nearest_water_distance_m", "nearest_water_name", "nearest_water_source_id"),
    "terrain_absolute": ("terrain_elevation_m",),
    "terrain_relative": ("terrain_relative_elevation_m",),
}

#: The composite read from the index must equal the weighted sum recomputed
#: here. The index is stored rounded to 9 decimals, so this is the tolerance
#: that separates "the weights on the poster are the weights that were applied"
#: from "someone changed a weight and nobody noticed".
COMPOSITE_TOLERANCE = 1e-6


def load(args) -> pd.DataFrame:
    index = pd.read_csv(REPOSITORY_ROOT / args.index, dtype={KEY: "string"})
    evidence = pd.read_csv(REPOSITORY_ROOT / args.evidence, dtype={KEY: "string"})
    terrain = pd.read_csv(REPOSITORY_ROOT / args.terrain, dtype={KEY: "string"})
    coordinates = pd.read_csv(
        REPOSITORY_ROOT / args.coordinates, dtype={KEY: "string"}, float_precision="round_trip"
    )

    merged = (
        index.merge(evidence, on=KEY, how="inner", validate="one_to_one", suffixes=("", "_ev"))
        .merge(terrain, on=KEY, how="inner", validate="one_to_one", suffixes=("", "_tr"))
        .merge(coordinates[[KEY, "x", "y"]], on=KEY, how="left", validate="one_to_one")
    )

    fema_baseline_path = REPOSITORY_ROOT / args.fema_baseline
    if "source_geometry_id" not in merged.columns and fema_baseline_path.exists():
        baseline = pd.read_csv(
            fema_baseline_path, dtype={KEY: "string", "source_geometry_id": "string"}
        )
        if "source_geometry_id" in baseline.columns:
            merged = merged.merge(
                baseline[[KEY, "source_geometry_id"]],
                on=KEY, how="left", validate="one_to_one",
            )
            print(f"recovered source_geometry_id from {args.fema_baseline}")
        else:
            print(f"NOTE: {args.fema_baseline} has no source_geometry_id either")
    if len(merged) != len(index):
        raise SystemExit(f"join lost rows: {len(index)} index, {len(merged)} merged")

    wanted = {column for columns in EVIDENCE_FOR_COMPONENT.values() for column in columns}
    absent = sorted(wanted - set(merged.columns))
    if absent:
        print(f"NOTE: evidence columns not present, they will be omitted: {absent}")
    return merged


def shortlist(frame: pd.DataFrame, n: int, min_percentile: float) -> pd.DataFrame:
    """Candidates ranked by component disagreement, above a percentile floor."""
    scores = frame[[COMPONENT_COLUMNS[name] for name in DEFAULT_WEIGHTS]]
    spread = scores.max(axis=1) - scores.min(axis=1)
    candidates = frame.assign(component_spread=spread)
    candidates = candidates[candidates["exposure_percentile"] >= min_percentile]
    if "nearest_water_name" in candidates.columns:
        named = candidates["nearest_water_name"].astype("string").fillna("").str.strip() != ""
        candidates = candidates[named]
    return candidates.nlargest(n, "component_spread")


def trace(frame: pd.DataFrame, property_id: str) -> dict:
    rows = frame[frame[KEY] == property_id]
    if rows.empty:
        raise SystemExit(f"property {property_id!r} not found")
    row = rows.iloc[0]

    components = []
    total = 0.0
    for name, weight in DEFAULT_WEIGHTS.items():
        score = float(row[COMPONENT_COLUMNS[name]])
        contribution = weight * score
        total += contribution
        evidence = {
            column: (None if pd.isna(row.get(column)) else row.get(column))
            for column in EVIDENCE_FOR_COMPONENT[name]
            if column in frame.columns
        }
        components.append(
            {
                "component": name,
                "label": COMPONENT_LABELS[name],
                "evidence": evidence,
                "score_0_100": score,
                "weight": weight,
                "contribution": contribution,
            }
        )

    stored = float(row["exposure_index_0_100"])
    if abs(total - stored) > COMPOSITE_TOLERANCE:
        raise SystemExit(
            "the weighted sum does not reproduce the stored composite:\n"
            f"  recomputed {total!r}\n  stored     {stored!r}\n"
            "The weights used here are not the weights the index was built with."
        )

    return {
        "property_id": property_id,
        "coordinates": {
            "x_m": None if pd.isna(row.get("x")) else float(row["x"]),
            "y_m": None if pd.isna(row.get("y")) else float(row["y"]),
            "crs": "EPSG:26918",
        },
        "components": components,
        "exposure_index_0_100": stored,
        "exposure_percentile": float(row["exposure_percentile"]),
        "scoring_policy_version": str(row.get("scoring_policy_version", "")),
        "composite_check": {
            "recomputed": total,
            "stored": stored,
            "abs_difference": abs(total - stored),
            "tolerance": COMPOSITE_TOLERANCE,
        },
    }


def markdown(record: dict) -> str:
    lines = [
        f"### Property {record['property_id']}",
        "",
        f"Coordinates {record['coordinates']['x_m']:,.1f} E, "
        f"{record['coordinates']['y_m']:,.1f} N ({record['coordinates']['crs']})",
        "",
        "| Evidence | Value | Score | Weight | Contribution |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for component in record["components"]:
        evidence = ", ".join(
            f"{key} = {value}" for key, value in component["evidence"].items() if value is not None
        )
        lines.append(
            f"| {component['label']} | {evidence} | "
            f"{component['score_0_100']:.1f} | {component['weight']:.2f} | "
            f"{component['contribution']:.2f} |"
        )
    lines += [
        f"| **Exposure index** | | | | **{record['exposure_index_0_100']:.2f}** |",
        "",
        f"Countywide percentile: **{record['exposure_percentile']:.1f}**",
        f"Scoring policy: {record['scoring_policy_version']}",
    ]
    return "\n".join(lines)


def contribution_bar(record: dict, stem: Path) -> None:
    """One horizontal bar: which evidence actually drove this property's index."""
    components = record["components"]
    with plt.rc_context(style.rc_params()):
        figure, axis = plt.subplots(figsize=(9.0, 1.9))
        left = 0.0
        shades = [style.PRIMARY, style.ACCENT, style.NEUTRAL, style.GRID]
        for component, colour in zip(components, shades):
            width = component["contribution"]
            axis.barh(0, width, left=left, color=colour, alpha=style.PRIMARY_ALPHA,
                      edgecolor=style.BACKGROUND, linewidth=1.5)
            if width > 6.0:
                axis.annotate(
                    f"{component['label']}\n{width:.1f}",
                    xy=(left + width / 2, 0), ha="center", va="center",
                    fontsize=style.SIZE_ANNOTATION, fontweight="bold", color=style.BACKGROUND,
                )
            else:
                # Too narrow to label inside. A leader below keeps the small
                # contributions legible, and they are the interesting ones here:
                # a component carrying real weight and contributing almost
                # nothing is the panel's whole point.
                axis.annotate(
                    f"{component['label']}\n{width:.1f}",
                    xy=(left + width / 2, -0.32), ha="center", va="top",
                    fontsize=style.SIZE_ANNOTATION, color=style.INK,
                    arrowprops={"arrowstyle": "-", "color": style.INK, "linewidth": 0.8},
                )
            left += width
        axis.set_xlim(0, 100)
        axis.set_ylim(-0.6, 0.6)
        axis.set_yticks([])
        axis.set_xlabel("Contribution to the exposure index (0-100)",
                        fontsize=style.SIZE_AXIS_LABEL)
        axis.axvline(record["exposure_index_0_100"], color=style.INK,
                     linewidth=style.LINEWIDTH_DASHED, dashes=style.DASHES)
        axis.annotate(
            f"index {record['exposure_index_0_100']:.1f}  "
            f"({record['exposure_percentile']:.0f}th percentile)",
            xy=(record["exposure_index_0_100"], 0.45), xytext=(6, 0),
            textcoords="offset points", ha="left", va="center",
            fontsize=style.SIZE_ANNOTATION, fontweight="bold", color=style.INK,
        )
        for spine in ("top", "right", "left"):
            axis.spines[spine].set_visible(False)
        figure.tight_layout()
        stem.parent.mkdir(parents=True, exist_ok=True)
        for extension in ("png", "svg"):
            path = stem.with_suffix(f".{extension}")
            figure.savefig(path, dpi=style.DPI, bbox_inches="tight",
                           facecolor=style.BACKGROUND)
            print(f"wrote {path}")
        plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", default="outputs/index/property_exposure_index_countywide.csv")
    parser.add_argument("--evidence", default="outputs/evidence/property_flood_evidence_countywide.csv")
    parser.add_argument("--terrain", default="outputs/evidence/property_terrain_evidence_countywide.csv")
    parser.add_argument("--coordinates", default="outputs/training/supervised_dataset_v2.csv")
    # The merged evidence table does not carry the NFHL polygon identifier, but
    # the FEMA baseline it was built from does. Without it the largest single
    # contribution on this property has no record a reader could look up, which
    # is precisely the claim this panel exists to make.
    parser.add_argument(
        "--fema-baseline", default="outputs/baseline/python_fema_membership_countywide.csv"
    )
    parser.add_argument("--shortlist", action="store_true")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--min-percentile", type=float, default=90.0)
    parser.add_argument("--property-id", default=None)
    parser.add_argument("--output-stem", default="outputs/figures/poster_property_trace")
    args = parser.parse_args()

    frame = load(args)
    print(f"joined {len(frame):,} properties\n")

    if args.shortlist or not args.property_id:
        candidates = shortlist(frame, args.top, args.min_percentile)
        columns = [KEY, *[COMPONENT_COLUMNS[n] for n in DEFAULT_WEIGHTS],
                   "exposure_index_0_100", "exposure_percentile", "component_spread"]
        if "nearest_water_name" in candidates.columns:
            columns.insert(1, "nearest_water_name")
        if "fema_zone" in candidates.columns:
            columns.insert(1, "fema_zone")
        with pd.option_context("display.width", 200, "display.max_columns", 20):
            print(candidates[columns].to_string(index=False))
        print("\nPick one and rerun with --property-id <id>")
        return 0

    record = trace(frame, args.property_id)
    stem = REPOSITORY_ROOT / args.output_stem
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(record, indent=2, default=str),
                                         encoding="utf-8")
    print(f"wrote {stem.with_suffix('.json')}\n")
    print(markdown(record))
    print()
    contribution_bar(record, stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())