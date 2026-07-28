"""Print the ``--rmi-probes`` argument for ``water_distance_hilbert``.

The C++ inference path asserts the model manifest's probe records at load: each
record pins one stored key at a fixed position and then requires the full
inference chain -- normalization, root, leaf, floor -- to reproduce ``x``
bit-for-bit, the routed leaf, and the predicted position. That is how the
``uint64`` to ``double`` float contract becomes a checked condition rather than
an inherited assumption (Nucleus 18.20).

Those records must be DERIVED from the manifest at run time, never transcribed.
A hand-copied constant in a shell command is precisely the provenance the
working standard's section 8 forbids, and quoting Python at a PowerShell prompt
mangles it in ways that fail silently or confusingly. B6 needs the string
programmatically in any case.

Example (PowerShell, from the repository root)::

    $P = (.\\.venv\\Scripts\\python.exe python\\scripts\\rmi_probe_args.py)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_MANIFEST = Path("outputs/validation/water_hilbert_rmi_manifest.json")

REQUIRED_FIELDS = ("index", "key", "x_hex", "leaf", "predicted_position")


def probe_argument(manifest_path: Path) -> str:
    """Return the semicolon-separated ``index,key,x_hex,leaf,position`` string."""
    manifest = json.loads(Path(manifest_path).read_text())
    records = manifest.get("probe_records")
    if not records:
        raise ValueError(f"{manifest_path}: probe_records is missing or empty.")
    parts = []
    for record in records:
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            raise ValueError(
                f"{manifest_path}: probe record is missing {missing}."
            )
        parts.append(",".join([
            str(record["index"]),
            str(record["key"]),
            str(record["x_hex"]),
            str(record["leaf"]),
            str(record["predicted_position"]),
        ]))
    return ";".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--expect-records",
        type=int,
        default=None,
        help="Fail unless the manifest holds exactly this many probe records.",
    )
    arguments = parser.parse_args()

    try:
        argument = probe_argument(arguments.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    count = len(argument.split(";"))
    if arguments.expect_records is not None and count != arguments.expect_records:
        print(
            f"Error: {arguments.manifest} holds {count} probe records; "
            f"--expect-records is {arguments.expect_records}.",
            file=sys.stderr,
        )
        return 1

    print(argument)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())