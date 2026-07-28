"""Acceptance check for the Hilbert seed seam.

Two runs of ``water_distance_hilbert`` that differ only in ``--seed`` must emit
identical evidence. The seam is correctness-neutral by construction (Nucleus
18.22): ``d_seed`` is the minimum over a window of REAL segments of an ACHIEVED
point-to-segment distance, so ``d_seed >= d_true`` for any window at any
position, the resolve radius always covers the true answer, and the final
candidate set is rebuilt by an independent descent that never references the
seed. This script turns that argument into a test at countywide scale.

Only ``cpp_seed_probes`` and ``seed_mode`` may differ. Every other column is
compared as TEXT, with ``dtype=str``, so the check is on the bytes the program
wrote rather than on floats pandas re-parsed and might round back into
agreement.

Optionally digests any number of further files, which is how a chunk shows that
an additive change left the control path untouched, and how a determinism rerun
is checked.

Example (PowerShell, from the repository root)::

    .\\.venv\\Scripts\\python.exe python\\scripts\\compare_seed_modes.py `
        --left  outputs/cpp/cpp_nearest_water_hilbert_countywide_b5c_binary.csv `
        --right outputs/cpp/cpp_nearest_water_hilbert_countywide_b5c_rmi.csv
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

SEED_INSTRUMENTATION_COLUMNS = ("cpp_seed_probes", "seed_mode")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def compare(left_path: Path, right_path: Path) -> bool:
    left = pd.read_csv(left_path, dtype=str)
    right = pd.read_csv(right_path, dtype=str)

    if list(left.columns) != list(right.columns):
        print("FAIL: column sets differ")
        print(f"  left : {list(left.columns)}")
        print(f"  right: {list(right.columns)}")
        return False
    if len(left) != len(right):
        print(f"FAIL: row counts differ, {len(left)} vs {len(right)}")
        return False

    compared = [c for c in left.columns
                if c not in SEED_INSTRUMENTATION_COLUMNS]
    identical = left[compared].equals(right[compared])

    print(f"rows                {len(left)}")
    print(f"columns compared    {len(compared)} of {len(left.columns)} "
          f"(excluded: {', '.join(SEED_INSTRUMENTATION_COLUMNS)})")
    print(f"identical           {identical}")

    if not identical:
        for column in compared:
            bad = int((left[column] != right[column]).sum())
            if bad:
                print(f"  MISMATCH {column}: {bad} rows")

    for label, frame in (("left", left), ("right", right)):
        modes = sorted(frame["seed_mode"].dropna().unique())
        probes = sorted(frame["cpp_seed_probes"].dropna().unique())
        head = probes[:3] + (["..."] if len(probes) > 3 else [])
        print(f"{label:19s} seed_mode {modes}, cpp_seed_probes {head}")

    return identical


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument(
        "--digest",
        type=Path,
        nargs="*",
        default=(),
        help="Additional files to SHA-256, for control-path and determinism checks.",
    )
    arguments = parser.parse_args()

    identical = compare(arguments.left, arguments.right)

    paths = [arguments.left, arguments.right, *arguments.digest]
    if paths:
        print()
        for path in paths:
            print(f"{sha256_file(path)}  {path}")

    if not identical:
        print("\nACCEPTANCE FAILED: the seed seam changed an emitted field.")
        return 1
    print("\nACCEPTANCE MET: seed mode changed no emitted field.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())