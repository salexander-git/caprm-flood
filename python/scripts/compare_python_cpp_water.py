from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(
    0,
    str(PYTHON_SOURCE_DIRECTORY),
)

from caprm.ingest import repository_path
from caprm.water_validate import compare_water_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the Python nearest-water reference with a "
            "C++ nearest-water result."
        )
    )

    parser.add_argument(
        "--python-reference",
        default=(
            "outputs/baseline/"
            "python_nearest_water.csv"
        ),
    )

    parser.add_argument(
        "--cpp-output",
        required=True,
    )

    parser.add_argument(
        "--detail-output",
        default=(
            "outputs/validation/"
            "water_bruteforce_agreement.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        default=(
            "outputs/validation/"
            "water_bruteforce_summary.json"
        ),
    )

    parser.add_argument(
        "--distance-tolerance-meters",
        type=float,
        default=1e-6,
    )

    args = parser.parse_args()

    python_reference_path = repository_path(
        args.python_reference
    )

    cpp_output_path = repository_path(
        args.cpp_output
    )

    detail_output_path = repository_path(
        args.detail_output
    )

    summary_output_path = repository_path(
        args.summary_output
    )

    detail, summary = compare_water_files(
        python_reference_path=(
            python_reference_path
        ),
        cpp_output_path=cpp_output_path,
        distance_tolerance_meters=(
            args.distance_tolerance_meters
        ),
        path_display_root=REPOSITORY_ROOT,
    )

    detail_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    detail.to_csv(
        detail_output_path,
        index=False,
        float_format="%.12f",
    )

    summary_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_output_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))

    if (
        summary["missing_python_rows"] != 0
        or summary["missing_cpp_rows"] != 0
        or summary["all_fields_agree"]
        != summary["total_union_rows"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()