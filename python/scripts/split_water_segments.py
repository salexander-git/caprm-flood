"""Pre-index pass for the segment-BVH nearest-water path.

Measures the exported water-segment length distribution, reports L before and
after a distance-exact length-capping split, and writes a provenance manifest.
Optionally emits the split-vertices CSV.

This pass is decoupled from ``water_export.py``: it consumes the already-exported
``water_vertices*.csv`` and does not modify the export or its manifests. The
geometric split it implements (divide each segment into ``ceil(length / cap)``
equal collinear pieces) is the same rule the C++ ``water_distance_segment_bvh``
program applies in memory when building its BVH. The split is distance-exact:
for any query point, the minimum point-to-segment distance over the pieces equals
the point-to-segment distance to the original segment, because every piece lies
on the original segment. Splitting therefore only tightens bounding boxes for the
index; it never changes a reported nearest-water distance.

Usage (from the repository root, PowerShell or POSIX)::

    python python/scripts/split_water_segments.py \
        --vertices outputs/cpp_input/water_vertices_countywide.csv \
        --max-segment-length-m 100 \
        --manifest-output outputs/validation/water_segment_split_countywide_manifest.json

Add ``--split-vertices-output <path>`` to also write the split geometry.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.hydrography import calculate_sha256  # noqa: E402
from caprm.ingest import repository_path  # noqa: E402

VERTEX_COLUMNS = [
    "water_feature_index",
    "part_index",
    "ring_index",
    "vertex_index",
    "x",
    "y",
]

TAIL_THRESHOLDS_M = [100.0, 200.0, 500.0, 1000.0]


def split_piece_count(length: float, cap: float) -> int:
    """Pieces an original segment is divided into so none exceeds ``cap``.

    Matches ``split_piece_count`` in water_distance_segment_bvh.cpp: a
    non-positive cap, a non-finite length, or a length at/under the cap yields a
    single piece.
    """
    if cap <= 0.0 or not math.isfinite(length) or length <= cap:
        return 1
    return int(math.ceil(length / cap))


def interpolate(start: tuple[float, float],
                end: tuple[float, float],
                pieces: int) -> list[tuple[float, float]]:
    """Return the ``pieces + 1`` vertices splitting ``start``..``end`` into
    ``pieces`` equal collinear pieces (endpoints preserved exactly)."""
    if pieces <= 1:
        return [start, end]
    out = [start]
    for piece in range(1, pieces):
        fraction = piece / pieces
        out.append((
            start[0] + fraction * (end[0] - start[0]),
            start[1] + fraction * (end[1] - start[1]),
        ))
    out.append(end)
    return out


class SplitAccumulator:
    """Streams the vertex file, computing per-segment lengths and split
    statistics without loading the whole table into memory. Relies on the
    export's guarantee that vertices are contiguous and ordered within each
    (feature, part, ring)."""

    def __init__(self, cap: float) -> None:
        self.cap = cap
        self.original_segments = 0
        self.split_segments = 0
        self.added_segments = 0
        self.max_original_length = 0.0
        self.max_split_length = 0.0
        self.length_sum = 0.0
        self.tail_counts = {threshold: 0 for threshold in TAIL_THRESHOLDS_M}
        self._key = None
        self._prev_vertex_index = None
        self._prev_xy = None

    def add_vertex(self, feature_index, part_index, ring_index,
                   vertex_index, x, y) -> None:
        key = (feature_index, part_index, ring_index)
        xy = (x, y)

        if key == self._key and vertex_index == self._prev_vertex_index + 1:
            length = math.hypot(x - self._prev_xy[0], y - self._prev_xy[1])
            self._record_segment(length)
        elif key == self._key:
            raise ValueError(
                f"Non-contiguous vertex_index in ring {key}: "
                f"{self._prev_vertex_index} -> {vertex_index}"
            )

        self._key = key
        self._prev_vertex_index = vertex_index
        self._prev_xy = xy

    def _record_segment(self, length: float) -> None:
        self.original_segments += 1
        self.length_sum += length
        self.max_original_length = max(self.max_original_length, length)

        for threshold in TAIL_THRESHOLDS_M:
            if length > threshold:
                self.tail_counts[threshold] += 1

        pieces = split_piece_count(length, self.cap)
        self.split_segments += pieces
        self.added_segments += pieces - 1
        self.max_split_length = max(self.max_split_length, length / pieces)


def stream_vertices(path: Path, accumulator: SplitAccumulator,
                    split_writer=None) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        index = {name: pos for pos, name in enumerate(header)}
        missing = [c for c in VERTEX_COLUMNS if c not in index]
        if missing:
            raise ValueError(f"Vertices file missing columns: {missing}")

        prev_key = None
        prev_out_vertex = 0
        prev_xy = None

        for row in reader:
            if not row:
                continue
            feature_index = int(row[index["water_feature_index"]])
            part_index = int(row[index["part_index"]])
            ring_index = int(row[index["ring_index"]])
            vertex_index = int(row[index["vertex_index"]])
            x = float(row[index["x"]])
            y = float(row[index["y"]])

            accumulator.add_vertex(
                feature_index, part_index, ring_index, vertex_index, x, y
            )

            if split_writer is None:
                continue

            key = (feature_index, part_index, ring_index)
            if key != prev_key:
                # First vertex of a ring: emit it as-is.
                split_writer.writerow([
                    feature_index, part_index, ring_index, 0,
                    format(x, ".17g"), format(y, ".17g"),
                ])
                prev_key = key
                prev_out_vertex = 0
                prev_xy = (x, y)
                continue

            length = math.hypot(x - prev_xy[0], y - prev_xy[1])
            pieces = split_piece_count(length, accumulator.cap)
            points = interpolate(prev_xy, (x, y), pieces)
            for point in points[1:]:  # skip the shared start vertex
                prev_out_vertex += 1
                split_writer.writerow([
                    feature_index, part_index, ring_index, prev_out_vertex,
                    format(point[0], ".17g"), format(point[1], ".17g"),
                ])
            prev_xy = (x, y)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure and manifest the distance-exact segment split used by the "
            "segment-BVH nearest-water index."
        )
    )
    parser.add_argument(
        "--vertices",
        default="outputs/cpp_input/water_vertices.csv",
    )
    parser.add_argument(
        "--max-segment-length-m",
        type=float,
        default=100.0,
    )
    parser.add_argument(
        "--distance-crs",
        default="EPSG:26918",
    )
    parser.add_argument(
        "--manifest-output",
        default="outputs/validation/water_segment_split_manifest.json",
    )
    parser.add_argument(
        "--split-vertices-output",
        default=None,
        help="Optional: also write the split-vertices CSV to this path.",
    )
    args = parser.parse_args()

    if args.max_segment_length_m <= 0:
        raise SystemExit("--max-segment-length-m must be positive.")

    vertices_path = repository_path(args.vertices)
    if not vertices_path.exists():
        raise SystemExit(f"Vertices file does not exist: {vertices_path}")

    accumulator = SplitAccumulator(args.max_segment_length_m)

    split_output_path = None
    split_handle = None
    split_writer = None
    if args.split_vertices_output is not None:
        split_output_path = repository_path(args.split_vertices_output)
        split_output_path.parent.mkdir(parents=True, exist_ok=True)
        split_handle = split_output_path.open("w", encoding="utf-8", newline="")
        split_writer = csv.writer(split_handle)
        split_writer.writerow(VERTEX_COLUMNS)

    try:
        stream_vertices(vertices_path, accumulator, split_writer)
    finally:
        if split_handle is not None:
            split_handle.close()

    def display_path(path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(REPOSITORY_ROOT).as_posix()
        except ValueError:
            return str(resolved)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "distance_crs": args.distance_crs,
        "split_rule": (
            "each segment divided into ceil(length / cap) equal collinear "
            "pieces; distance-exact (min piece distance == original distance)"
        ),
        "vertices_input": display_path(vertices_path),
        "vertices_input_sha256": calculate_sha256(vertices_path),
        "max_segment_length_cap_m": args.max_segment_length_m,
        "original_segment_count": accumulator.original_segments,
        "split_segment_count": accumulator.split_segments,
        "added_segment_count": accumulator.added_segments,
        "max_original_segment_length_m": accumulator.max_original_length,
        "max_split_segment_length_m": accumulator.max_split_length,
        "mean_segment_length_m": (
            accumulator.length_sum / accumulator.original_segments
            if accumulator.original_segments else 0.0
        ),
        "segment_count_over_threshold": {
            f"{int(threshold)}m": count
            for threshold, count in accumulator.tail_counts.items()
        },
    }

    if split_output_path is not None:
        manifest["split_vertices_output"] = display_path(split_output_path)
        manifest["split_vertices_sha256"] = calculate_sha256(split_output_path)

    manifest_output = repository_path(args.manifest_output)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()