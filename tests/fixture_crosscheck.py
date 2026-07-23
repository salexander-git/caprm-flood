"""Generate an export-schema water fixture, run the three C++ programs, and
cross-check the segment-BVH output against the brute-force oracle field-for-field
through the real CSV IO path (not just the in-memory functions)."""

from __future__ import annotations

import argparse
import csv
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXE = ".exe" if os.name == "nt" else ""


def default_binary(stem: str) -> Path:
    """Prefer a build/ binary, else one beside the repository root."""
    candidates = [
        REPOSITORY_ROOT / "cpp" / "spatial_core" / "build" / (stem + EXE),
        REPOSITORY_ROOT / (stem + EXE),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", default=None)
    parser.add_argument("--bruteforce", default=None)
    parser.add_argument("--indexed", default=None)
    parser.add_argument("--segment-bvh", default=None)
    return parser.parse_args()


_ARGS = parse_arguments()

WORK = Path(
    _ARGS.work_dir
    if _ARGS.work_dir
    else Path(tempfile.gettempdir()) / "caprm_water_fixture"
)
WORK.mkdir(parents=True, exist_ok=True)

BRUTEFORCE = str(
    Path(_ARGS.bruteforce) if _ARGS.bruteforce else default_binary("water_distance_bruteforce")
)
INDEXED = str(
    Path(_ARGS.indexed) if _ARGS.indexed else default_binary("water_distance_indexed")
)
SEGMENT_BVH = str(
    Path(_ARGS.segment_bvh) if _ARGS.segment_bvh else default_binary("water_distance_segment_bvh")
)

# Shared fields that must agree across implementations (instrumentation counters
# and algorithm are intentionally excluded).
SHARED_FIELDS = [
    "cpp_nearest_water_distance_m",
    "cpp_nearest_water_feature_id",
    "cpp_nearest_water_feature_class",
    "cpp_nearest_water_feature_type",
    "cpp_nearest_water_source_id",
    "cpp_nearest_water_source_object_id",
    "cpp_nearest_water_name",
    "cpp_nearest_water_tie_count",
    "distance_crs",
]


def fmt(value: float) -> str:
    return format(float(value), ".17g")


def closed_square(min_x, min_y, side):
    mx, my = min_x + side, min_y + side
    return [
        (min_x, min_y), (mx, min_y), (mx, my), (min_x, my), (min_x, min_y)
    ]


def build_features_and_vertices():
    """Return (feature_rows, vertex_rows). Exercises: a 6000 m single-segment
    line, a multi-segment line, two solid waterbody squares, and one waterbody
    with an interior hole (to exercise the hole branch of distance_to_feature)."""
    features = []
    vertices = []

    def add_feature(idx, fid, cls, ftype, kind):
        features.append({
            "water_feature_index": idx,
            "water_feature_id": fid,
            "water_feature_class": cls,
            "water_feature_type": ftype,
            "source_feature_id": f"src:{fid}",
            "source_object_id": idx,
            "source_gnis_id": "",
            "source_name": fid,
            "geometry_kind": kind,
        })

    def add_ring(idx, part, ring, coords):
        for vi, (x, y) in enumerate(coords):
            vertices.append([idx, part, ring, vi, fmt(x), fmt(y)])

    # 0: long single-segment flowline (6000 m, exceeds real max L).
    add_feature(0, "flow:long", "flowline", "channel", "line")
    add_ring(0, 0, 0, [(280000.0, 4780000.0), (286000.0, 4780000.0)])

    # 1: zigzag flowline.
    add_feature(1, "flow:zig", "flowline", "canal", "line")
    add_ring(1, 0, 0, [
        (281000.0, 4782000.0), (281500.0, 4782300.0),
        (282000.0, 4782100.0), (282600.0, 4782800.0),
    ])

    # 2: solid 150 m square waterbody.
    add_feature(2, "body:one", "waterbody", "lake", "polygon")
    add_ring(2, 0, 0, closed_square(283000.0, 4781000.0, 150.0))

    # 3: solid 400 m square waterbody.
    add_feature(3, "body:two", "waterbody", "lake", "polygon")
    add_ring(3, 0, 0, closed_square(284000.0, 4783000.0, 400.0))

    # 4: 600 m square waterbody with a 100 m square hole (island) in the middle.
    add_feature(4, "body:holed", "waterbody", "lake", "polygon")
    add_ring(4, 0, 0, closed_square(278000.0, 4777000.0, 600.0))
    add_ring(4, 0, 1, closed_square(278250.0, 4777250.0, 100.0))

    return features, vertices


def build_properties():
    """Query points: a deterministic grid plus specific interior/boundary/tie
    points."""
    props = []

    def add(x, y):
        props.append((len(props), f"p{len(props):05d}", x, y))

    # Interior of body:one -> distance 0.
    add(283075.0, 4781075.0)
    # On an edge of body:one -> distance 0.
    add(283075.0, 4781000.0)
    # Inside the hole of body:holed -> NOT zero (distance to hole boundary).
    add(278300.0, 4777300.0)
    # Inside body:holed but outside the hole -> distance 0.
    add(278100.0, 4777100.0)
    # Tie: mirror geometry is not present here, so use the grid for coverage.

    # Deterministic coverage grid.
    x = 279000.0
    while x <= 287000.0:
        y = 4776000.0
        while y <= 4784000.0:
            add(x, y)
            y += 250.0
        x += 250.0

    return props


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def run(binary, out_path, cap=None):
    args = [
        binary,
        str(WORK / "properties.csv"),
        str(WORK / "features.csv"),
        str(WORK / "vertices.csv"),
        str(out_path),
        "EPSG:26918",
    ]
    if cap is not None:
        args.append(str(cap))
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"{binary} failed")
    return result.stdout


def compare(reference_path, candidate_path, label):
    ref = pd.read_csv(reference_path, dtype={
        "property_id": "string",
        "cpp_nearest_water_feature_id": "string",
        "cpp_nearest_water_source_id": "string",
    }).sort_values("property_id").reset_index(drop=True)
    cand = pd.read_csv(candidate_path, dtype={
        "property_id": "string",
        "cpp_nearest_water_feature_id": "string",
        "cpp_nearest_water_source_id": "string",
    }).sort_values("property_id").reset_index(drop=True)

    assert list(ref["property_id"]) == list(cand["property_id"]), \
        f"{label}: property_id sets differ"

    max_dist_err = float(
        (ref["cpp_nearest_water_distance_m"]
         - cand["cpp_nearest_water_distance_m"]).abs().max()
    )

    mismatches = 0
    for field in SHARED_FIELDS:
        if field == "cpp_nearest_water_distance_m":
            bad = ((ref[field] - cand[field]).abs() > 0).sum()
        else:
            a = ref[field].astype("string").fillna("")
            b = cand[field].astype("string").fillna("")
            bad = (a != b).sum()
        if bad:
            mismatches += int(bad)
            print(f"  {label}: field {field} has {bad} mismatches")

    print(f"  {label}: max abs distance error = {max_dist_err:.3e} m, "
          f"field mismatches = {mismatches}")
    return mismatches, max_dist_err


def main():
    features, vertices = build_features_and_vertices()
    props = build_properties()

    write_csv(
        WORK / "features.csv",
        ["water_feature_index", "water_feature_id", "water_feature_class",
         "water_feature_type", "source_feature_id", "source_object_id",
         "source_gnis_id", "source_name", "geometry_kind"],
        [[f["water_feature_index"], f["water_feature_id"],
          f["water_feature_class"], f["water_feature_type"],
          f["source_feature_id"], f["source_object_id"],
          f["source_gnis_id"], f["source_name"], f["geometry_kind"]]
         for f in features],
    )
    write_csv(
        WORK / "vertices.csv",
        ["water_feature_index", "part_index", "ring_index",
         "vertex_index", "x", "y"],
        vertices,
    )
    write_csv(
        WORK / "properties.csv",
        ["sample_order", "property_id", "projected_x", "projected_y"],
        props,
    )

    print(f"fixture: {len(features)} features, {len(vertices)} vertices, "
          f"{len(props)} properties")

    run(BRUTEFORCE, WORK / "out_bruteforce.csv")
    run(INDEXED, WORK / "out_indexed.csv")
    seg_stdout = run(SEGMENT_BVH, WORK / "out_segment_bvh.csv", cap=100.0)
    run(SEGMENT_BVH, WORK / "out_segment_bvh_nosplit.csv", cap=1e12)

    # Echo the split lines from the segment-BVH stdout.
    for line in seg_stdout.splitlines():
        if ("segment" in line.lower() or "Added" in line
                or "cap" in line.lower()):
            print("  [segbvh] " + line)

    print("field-for-field comparisons (reference = brute force):")
    total = 0
    m1, e1 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_segment_bvh.csv", "segment_bvh(cap=100)")
    m2, e2 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_segment_bvh_nosplit.csv",
                     "segment_bvh(no split)")
    m3, e3 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_indexed.csv", "feature_bvh")
    total = m1 + m2 + m3

    # Structural checks on the segment-BVH output.
    seg = pd.read_csv(WORK / "out_segment_bvh.csv",
                      dtype={"property_id": "string"})
    assert len(seg) == len(props), "row count mismatch"
    assert seg["property_id"].is_unique, "property_id not unique"
    assert seg.notna().all().all(), "nulls present"
    assert (seg["cpp_nearest_water_distance_m"] >= 0).all(), "negative distance"
    assert set(seg["algorithm"].unique()) == {"segment_bvh"}, "algorithm value"
    for col in ["cpp_segment_checks", "cpp_candidate_feature_checks",
                "cpp_index_node_visits", "cpp_segment_box_tests"]:
        assert (seg[col] >= 0).all(), f"{col} negative"

    # Specific behavior checks.
    def row(pid):
        return seg.loc[seg["property_id"] == pid].iloc[0]

    assert math.isclose(row("p00000")["cpp_nearest_water_distance_m"], 0.0,
                        abs_tol=0.0), "interior not exactly 0"
    assert row("p00000")["cpp_nearest_water_feature_id"] == "body:one"
    assert math.isclose(row("p00001")["cpp_nearest_water_distance_m"], 0.0,
                        abs_tol=0.0), "on-boundary not exactly 0"
    assert row("p00003")["cpp_nearest_water_distance_m"] == 0.0, \
        "point inside holed polygon (outside hole) not 0"
    assert row("p00002")["cpp_nearest_water_distance_m"] > 0.0, \
        "point inside hole should be nonzero"

    print("structural + behavior checks passed")

    if total != 0:
        raise SystemExit(f"FIELD MISMATCHES: {total}")
    print("\nALL CROSS-CHECKS PASSED")


if __name__ == "__main__":
    main()