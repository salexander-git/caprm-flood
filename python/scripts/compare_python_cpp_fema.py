from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.validate import compare_fema_files


def repository_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return REPOSITORY_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare CAPRM-Flood Python and C++ FEMA membership outputs."
        )
    )

    parser.add_argument(
        "--python-baseline",
        default="outputs/baseline/python_fema_membership.csv",
        help="Python FEMA baseline CSV.",
    )

    parser.add_argument(
        "--cpp-output",
        default="outputs/cpp/cpp_fema_membership_1000.csv",
        help="C++ FEMA membership CSV.",
    )

    parser.add_argument(
        "--detail-output",
        default=(
            "outputs/validation/"
            "fema_pip_1000_agreement_report.csv"
        ),
        help="Detailed comparison CSV.",
    )

    parser.add_argument(
        "--summary-output",
        default="outputs/validation/fema_pip_1000_summary.json",
        help="Comparison summary JSON.",
    )

    parser.add_argument(
        "--scope",
        choices=["union", "cpp"],
        default="union",
        help=(
            "'union' requires complete matching ID sets. "
            "'cpp' validates only properties present in the C++ output, "
            "which is appropriate for development fixtures."
        ),
    )

    args = parser.parse_args()

    detail, summary = compare_fema_files(
        python_baseline_path=repository_path(
            args.python_baseline
        ),
        cpp_output_path=repository_path(
            args.cpp_output
        ),
        detail_output_path=repository_path(
            args.detail_output
        ),
        summary_output_path=repository_path(
            args.summary_output
        ),
        comparison_scope=args.scope,
    )

    print(json.dumps(summary, indent=2))

    disagreements = detail[
        ~detail["all_fields_agree"]
    ]

    if not disagreements.empty:
        print("\nDisagreements:")
        print(
            disagreements[
                [
                    "property_id",
                    "python_matched_fema_polygon",
                    "cpp_matched_fema_polygon",
                    "python_is_sfha",
                    "cpp_is_sfha",
                    "python_fema_zone",
                    "cpp_fema_zone",
                    "python_fema_feature_index",
                    "cpp_fema_feature_index",
                    "missing_python_result",
                    "missing_cpp_result",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()