"""Unit tests for the pre-index segment split (split_water_segments.py).

Tests the pure split rule (piece count, interpolation, distance-invariance) and
the streaming accumulator. Runs under pytest, or standalone via ``python``.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "python" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from split_water_segments import (  # noqa: E402
    SplitAccumulator,
    interpolate,
    split_piece_count,
)


def point_segment_distance(p, a, b):
    """Reference point-to-segment distance (mirrors the C++ kernel)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    cx, cy = a[0] + t * dx, a[1] + t * dy
    return math.hypot(p[0] - cx, p[1] - cy)


def test_split_piece_count():
    assert split_piece_count(6000.0, 100.0) == 60
    assert split_piece_count(5748.24, 100.0) == 58
    assert split_piece_count(100.0, 100.0) == 1
    assert split_piece_count(50.0, 100.0) == 1
    assert split_piece_count(250.0, 100.0) == 3
    assert split_piece_count(6000.0, 0.0) == 1
    assert split_piece_count(6000.0, -1.0) == 1


def test_interpolate_endpoints_and_collinearity():
    a, b = (280000.0, 4780000.0), (286000.0, 4780000.0)
    pts = interpolate(a, b, 60)
    assert pts[0] == a
    assert pts[-1] == b
    assert len(pts) == 61
    # Collinearity and monotone spacing along a horizontal segment.
    for p in pts:
        assert p[1] == a[1]
    xs = [p[0] for p in pts]
    assert xs == sorted(xs)


def test_split_distance_invariance():
    rng = random.Random(4321)
    worst = 0.0
    for _ in range(20000):
        a = (rng.uniform(270000, 300000), rng.uniform(4770000, 4800000))
        b = (rng.uniform(270000, 300000), rng.uniform(4770000, 4800000))
        p = (rng.uniform(270000, 300000), rng.uniform(4770000, 4800000))
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        pieces = split_piece_count(length, 100.0)
        pts = interpolate(a, b, pieces)
        split_min = min(
            point_segment_distance(p, pts[i], pts[i + 1])
            for i in range(len(pts) - 1)
        )
        original = point_segment_distance(p, a, b)
        worst = max(worst, abs(split_min - original))
    assert worst <= 1e-6, f"worst split-vs-original error {worst:.3e} m"
    print(f"  worst split-vs-original abs error: {worst:.3e} m")


def test_accumulator_matches_manual_counts():
    # Two rings: a 6000 m single segment (60 pieces) and a 3-vertex ring with
    # two 100 m segments (no split).
    acc = SplitAccumulator(cap=100.0)
    # ring (0,0,0): 6000 m horizontal
    acc.add_vertex(0, 0, 0, 0, 280000.0, 4780000.0)
    acc.add_vertex(0, 0, 0, 1, 286000.0, 4780000.0)
    # ring (1,0,0): two 100 m segments
    acc.add_vertex(1, 0, 0, 0, 0.0, 0.0)
    acc.add_vertex(1, 0, 0, 1, 100.0, 0.0)
    acc.add_vertex(1, 0, 0, 2, 100.0, 100.0)
    assert acc.original_segments == 3
    assert acc.split_segments == 60 + 1 + 1
    assert acc.added_segments == 59
    assert acc.max_original_length == 6000.0
    assert math.isclose(acc.max_split_length, 100.0)
    assert acc.tail_counts[1000.0] == 1
    assert acc.tail_counts[100.0] == 1  # only the 6000 m segment exceeds 100


def test_accumulator_rejects_noncontiguous():
    acc = SplitAccumulator(cap=100.0)
    acc.add_vertex(0, 0, 0, 0, 0.0, 0.0)
    try:
        acc.add_vertex(0, 0, 0, 2, 1.0, 0.0)  # skips vertex_index 1
    except ValueError:
        return
    raise AssertionError("expected ValueError on non-contiguous vertex_index")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)