"""Generate an export-schema water fixture, run the three C++ programs, and
cross-check the segment-BVH output against the brute-force oracle field-for-field
through the real CSV IO path (not just the in-memory functions)."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
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
    parser.add_argument("--hilbert", default=None)
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
HILBERT = str(
    Path(_ARGS.hilbert) if _ARGS.hilbert else default_binary("water_distance_hilbert")
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


def run_hilbert(out_path, cap, verification_mode, region_mode=None,
                hilbert_order=None, manifest=None, extra=None):
    args = [
        HILBERT,
        str(WORK / "properties.csv"),
        str(WORK / "features.csv"),
        str(WORK / "vertices.csv"),
        str(out_path),
        "EPSG:26918",
        str(cap),
        verification_mode,
    ]
    # Positional arguments are order-dependent, so stop at the first
    # omitted one: that exercises the program's OWN defaults instead of
    # restating them here, which is the only way a changed default can be
    # caught.
    for value in (region_mode, hilbert_order):
        if value is None:
            break
        args.append(str(value))
    if manifest is not None:
        if region_mode is None or hilbert_order is None:
            raise ValueError(
                "manifest is positional after region_mode and hilbert_order")
        args.append(str(manifest))
    if extra:
        args.extend(extra)
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"{HILBERT} failed")
    return result.stdout


def compare(reference_path, candidate_path, label, dist_tol=0.0):
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
            bad = ((ref[field] - cand[field]).abs() > dist_tol).sum()
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
    seg_stdout = run(SEGMENT_BVH, WORK / "out_segment_bvh.csv", cap=25.0)
    run(SEGMENT_BVH, WORK / "out_segment_bvh_nosplit.csv", cap=1e12)

    # Echo the split lines from the segment-BVH stdout.
    for line in seg_stdout.splitlines():
        if ("segment" in line.lower() or "Added" in line
                or "cap" in line.lower()):
            print("  [segbvh] " + line)

    # Hilbert path (B3a): both verification modes, both region predicates,
    # cap 25 so L/2 = 12.5 m matches the chosen operating point.
    hil_manifest = WORK / "hilbert_manifest.json"
    hil_stdout = run_hilbert(WORK / "out_hilbert_orig_bbox.csv", 25.0,
                             "original", "disk_bbox", 32, hil_manifest)
    run_hilbert(WORK / "out_hilbert_split_bbox.csv", 25.0,
                "split", "disk_bbox", 32)
    run_hilbert(WORK / "out_hilbert_orig_disk.csv", 25.0,
                "original", "disk", 32)

    # B3b: the seed seam. --seed zero returns position 0 for every query (the
    # worst legal hint). Byte-identical output proves the seam is a performance
    # hint only, which is exactly B5's acceptance criterion for the RMI.
    run_hilbert(WORK / "out_hilbert_seed_null.csv", 25.0,
                "original", "disk_bbox", 32, extra=["--seed", "zero"])

    # B3b: uncapped counterfactual (L = 5,748.24 m => L/2 = 2,874.12 m) plus the
    # independent counting-descent cross-check of the disk counters.
    unc_manifest = WORK / "hilbert_manifest_uncapped.json"
    run_hilbert(WORK / "out_hilbert_uncapped.csv", 25.0,
                "original", "disk_bbox", 32, unc_manifest,
                extra=["--uncapped-half", "2874.1198", "--verify-counts"])

    # B4: the default region predicate is now `disk` (B3b gate decision).
    # Omit region_mode entirely so the program's default is what gets
    # tested. Every other call passes it positionally, so without this the
    # default has no coverage at all.
    run_hilbert(WORK / "out_hilbert_default_region.csv", 25.0, "original")
    dflt = pd.read_csv(WORK / "out_hilbert_default_region.csv",
                       dtype={"property_id": "string"})
    assert set(dflt["region_mode"].unique()) == {"disk"}, \
        "default region predicate is not `disk`"
    print("  [hilbert] default region predicate is `disk`")

    # B4: the key dump is the RMI training array, so it is checked against
    # the manifest that describes it here, on the fixture, where it is
    # cheap -- not first discovered countywide.
    fixture_keys = WORK / "hilbert_keys.bin"
    keydump_manifest = WORK / "hilbert_keydump_manifest.json"
    run_hilbert(WORK / "out_hilbert_keydump.csv", 25.0, "original",
                "disk_bbox", 32, keydump_manifest,
                extra=["--dump-keys", str(fixture_keys)])
    keydump_man = json.loads(keydump_manifest.read_text())
    raw_keys = fixture_keys.read_bytes()
    assert len(raw_keys) == keydump_man["key_array_bytes"], \
        "key dump size != manifest key_array_bytes"
    dumped = np.frombuffer(raw_keys, dtype="<u8")
    assert dumped.size == keydump_man["index_entries"], \
        "key dump entry count != manifest index_entries"
    assert np.all(dumped[:-1] <= dumped[1:]), "key dump is not sorted"
    assert np.unique(dumped).size == keydump_man["distinct_cells_at_order"], \
        "key dump distinct count != manifest distinct_cells_at_order"
    print(f"  [hilbert] key dump: {dumped.size} entries, "
          f"{np.unique(dumped).size} distinct, sorted, "
          f"{len(raw_keys)} bytes == manifest")

    for line in hil_stdout.splitlines():
        if any(t in line for t in ("Hilbert order", "Min order", "Distinct",
                                   "Inflation half", "inflation", "Key array",
                                   "Index entries")):
            print("  [hilbert] " + line)

    print("field-for-field comparisons (reference = brute force):")
    total = 0
    m1, e1 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_segment_bvh.csv", "segment_bvh(cap=25)")
    m2, e2 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_segment_bvh_nosplit.csv",
                     "segment_bvh(no split)")
    m3, e3 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_indexed.csv", "feature_bvh")
    m4, e4 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_hilbert_orig_bbox.csv",
                     "hilbert(original, disk_bbox)")
    # Split geometry is exact to ~1e-9 m by construction (matches B2), so the
    # distance field is compared within a tolerance well under the 1e-6 m tie
    # tolerance; every non-distance field must still match exactly.
    m5, e5 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_hilbert_split_bbox.csv",
                     "hilbert(split, disk_bbox)", dist_tol=1e-6)
    assert e5 < 1e-6, f"split-mode distance error {e5:.3e} m exceeds 1e-6 m"
    m6, e6 = compare(WORK / "out_bruteforce.csv",
                     WORK / "out_hilbert_orig_disk.csv",
                     "hilbert(original, disk)")
    total = m1 + m2 + m3 + m4 + m5 + m6

    # Hilbert-specific acceptance: collision check and the stacked-inflation
    # ordering N_disk_r <= N_disk_infl <= N_decomp per property.
    with hil_manifest.open() as handle:
        man = json.load(handle)
    assert man["distinct_cells_at_order"] == man["index_entries"], \
        f"Hilbert cell collisions at order {man['hilbert_order_bits_per_axis']}"
    print(f"  [hilbert] collision check: {man['distinct_cells_at_order']} "
          f"distinct cells == {man['index_entries']} entries at order "
          f"{man['hilbert_order_bits_per_axis']}; min order for distinct = "
          f"{man['min_order_for_distinct_cells']}")

    for tag in ("out_hilbert_orig_bbox.csv", "out_hilbert_split_bbox.csv",
                "out_hilbert_orig_disk.csv"):
        h = pd.read_csv(WORK / tag, dtype={"property_id": "string"})
        # B3b chain: n_disk_r <= n_true_r <= n_disk_infl <= n_decomp, and
        # n_true_r >= 1 (the nearest split segment always satisfies the
        # predicate at the answer radius). n_disk_r is retained but is a
        # degenerate coincidence counter, not a usable denominator.
        assert (h["cpp_n_disk_r"] <= h["cpp_n_true_r"]).all(), \
            f"{tag}: N_disk_r > N_true_r"
        assert (h["cpp_n_true_r"] >= 1).all(), f"{tag}: N_true_r < 1"
        assert (h["cpp_n_true_r"] <= h["cpp_n_disk_infl"]).all(), \
            f"{tag}: N_true_r > N_disk_infl"
        assert (h["cpp_n_disk_infl"] <= h["cpp_entries_scanned"]).all(), \
            f"{tag}: N_disk_infl > N_decomp"
    # disk region must admit no more entries than the box region (tighter prune).
    hb = pd.read_csv(WORK / "out_hilbert_orig_bbox.csv",
                     dtype={"property_id": "string"}).set_index("property_id")
    hd = pd.read_csv(WORK / "out_hilbert_orig_disk.csv",
                     dtype={"property_id": "string"}).set_index("property_id")
    assert (hd["cpp_entries_scanned"] <= hb["cpp_entries_scanned"]).all(), \
        "disk region scanned more entries than disk_bbox"
    # The three disk counters are exact counts over disk(R) and therefore cannot
    # depend on which region predicate drove the descent. This tests the two
    # predicates against each other rather than trusting either.
    for column in ("cpp_n_disk_r", "cpp_n_true_r", "cpp_n_disk_infl"):
        assert (hb[column] == hd[column]).all(), \
            f"{column} differs between disk_bbox and disk regions"
    print("  [hilbert] inflation ordering + region monotonicity + "
          "region-invariance of the disk counters passed")

    # B3b: the seed seam is correctness-neutral. --seed zero is the worst legal
    # hint; every emitted field except the seed instrumentation must be identical.
    base = pd.read_csv(WORK / "out_hilbert_orig_bbox.csv",
                       dtype={"property_id": "string"})
    null = pd.read_csv(WORK / "out_hilbert_seed_null.csv",
                       dtype={"property_id": "string"})
    seam_columns = [c for c in base.columns
                    if c not in ("cpp_seed_probes", "seed_mode")]
    assert base[seam_columns].equals(null[seam_columns]), \
        "seed mode changed an emitted field: the seam is not correctness-neutral"
    assert (base["cpp_seed_probes"] > 0).all(), "binary seed reported 0 probes"
    assert (null["cpp_seed_probes"] == 0).all(), "zero seed reported probes"
    assert set(base["seed_mode"].unique()) == {"binary"}, "seed_mode value"
    assert set(null["seed_mode"].unique()) == {"zero"}, "seed_mode value"
    entries = int(json.loads(hil_manifest.read_text())["index_entries"])
    expected_probes = math.floor(math.log2(entries)) + 1
    assert base["cpp_seed_probes"].max() <= expected_probes, \
        (f"binary seed probes {base['cpp_seed_probes'].max()} exceed "
         f"ceil(log2({entries})) bound {expected_probes}")
    print(f"  [hilbert] seed seam: zero-seed output byte-identical to binary; "
          f"binary probes <= {expected_probes} (log2 of {entries} entries)")

    # B3b: uncapped counterfactual. The larger radius is a superset, so the
    # count cannot fall; --verify-counts already re-derived n_disk_r and
    # n_disk_infl with an independent counting descent inside the binary.
    unc = pd.read_csv(WORK / "out_hilbert_uncapped.csv",
                      dtype={"property_id": "string"})
    assert (unc["cpp_n_disk_unc"] >= unc["cpp_n_disk_infl"]).all(), \
        "uncapped disk admitted fewer midpoints than the capped disk"
    assert (base["cpp_n_disk_unc"] == 0).all(), \
        "uncapped counter nonzero when --uncapped-half was not requested"
    unc_man = json.loads(unc_manifest.read_text())
    assert unc_man["count_cross_check"] is True
    assert unc_man["seed_mode"] == "binary"
    assert unc_man["seed_window_entries"] > 0
    print(f"  [hilbert] uncapped counterfactual: mean N_disk_unc = "
          f"{unc['cpp_n_disk_unc'].mean():.2f} vs capped N_disk_infl = "
          f"{unc['cpp_n_disk_infl'].mean():.2f}; count cross-check passed")

    # The B3a denominator is degenerate by construction, not by fixture
    # sparsity: d_best is a segment distance while n_disk_r tests midpoints.
    # Recorded here so the fact stays measured rather than remembered.
    print(f"  [hilbert] degenerate B3a denominator: N_disk_r nonzero on "
          f"{int((base['cpp_n_disk_r'] > 0).sum())} of {len(base)} properties")

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

    # Same structural + interior/boundary/hole behavior on the Hilbert output.
    hil = pd.read_csv(WORK / "out_hilbert_orig_bbox.csv",
                      dtype={"property_id": "string"})
    assert len(hil) == len(props), "hilbert row count mismatch"
    assert hil["property_id"].is_unique, "hilbert property_id not unique"
    assert hil.notna().all().all(), "hilbert nulls present"
    assert (hil["cpp_nearest_water_distance_m"] >= 0).all(), \
        "hilbert negative distance"
    assert set(hil["algorithm"].unique()) == {"hilbert"}, "hilbert algorithm value"

    def hrow(pid):
        return hil.loc[hil["property_id"] == pid].iloc[0]

    assert hrow("p00000")["cpp_nearest_water_distance_m"] == 0.0, \
        "hilbert interior not exactly 0"
    assert hrow("p00000")["cpp_nearest_water_feature_id"] == "body:one"
    assert hrow("p00001")["cpp_nearest_water_distance_m"] == 0.0, \
        "hilbert on-boundary not exactly 0"
    assert hrow("p00003")["cpp_nearest_water_distance_m"] == 0.0, \
        "hilbert point inside holed polygon (outside hole) not 0"
    assert hrow("p00002")["cpp_nearest_water_distance_m"] > 0.0, \
        "hilbert point inside hole should be nonzero"

    # Interior-zero must also survive split-mode selection.
    hils = pd.read_csv(WORK / "out_hilbert_split_bbox.csv",
                       dtype={"property_id": "string"})
    for pid in ("p00000", "p00001", "p00003"):
        v = hils.loc[hils["property_id"] == pid, "cpp_nearest_water_distance_m"]
        assert float(v.iloc[0]) == 0.0, f"hilbert split interior-zero failed at {pid}"

    print("structural + behavior checks passed")

    if total != 0:
        raise SystemExit(f"FIELD MISMATCHES: {total}")
    print("\nALL CROSS-CHECKS PASSED")


if __name__ == "__main__":
    main()