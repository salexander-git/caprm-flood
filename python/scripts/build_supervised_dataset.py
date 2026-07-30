"""Build the PHASE C supervised dataset and its manifest.

    python python/scripts/build_supervised_dataset.py

Reads the two frozen upstream products, verifies the join, writes
``outputs/training/supervised_dataset_v2.csv`` and its manifest. Writes nothing
into ``outputs/index/`` or ``outputs/evidence/``: the label is read, never
recomputed, and ``python/caprm/scoring.py`` is not imported.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.supervised_dataset import (  # noqa: E402
    DatasetVerificationError,
    build_supervised_dataset,
    write_dataset,
    write_manifest,
)

DEFAULT_INDEX = "outputs/index/property_exposure_index_countywide.csv"
DEFAULT_MANIFEST = "outputs/validation/property_exposure_index_countywide_manifest.json"
DEFAULT_COORDS = "outputs/cpp_input/water_properties_projected_countywide.csv"
DEFAULT_OUTPUT = "outputs/training/supervised_dataset_v2.csv"
DEFAULT_OUTPUT_MANIFEST = "outputs/training/supervised_dataset_v2_manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--index-manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--coordinates", default=DEFAULT_COORDS)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--output-manifest", default=DEFAULT_OUTPUT_MANIFEST)
    parser.add_argument("--expected-rows", type=int, default=267_362)
    parser.add_argument(
        "--no-manifest-check",
        action="store_true",
        help="skip the index-CSV checksum check against its manifest",
    )
    args = parser.parse_args(argv)

    try:
        dataset, report = build_supervised_dataset(
            index_csv=args.index,
            coordinates_csv=args.coordinates,
            index_manifest_json=None if args.no_manifest_check else args.index_manifest,
            expected_rows=args.expected_rows,
        )
    except DatasetVerificationError as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 2

    output_sha = write_dataset(dataset, args.output)
    write_manifest(args.output_manifest, report, args.output, output_sha)

    print(json.dumps(report.to_dict(), indent=2))
    print(f"\nwrote {args.output}")
    print(f"  sha256 {output_sha}")
    print(f"wrote {args.output_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())