import argparse
import json
from pathlib import Path

import pandas as pd


def normalize_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "t", "1", "yes", "y"])


def compare(
    python_baseline_path: Path,
    cpp_output_path: Path,
    detail_output_path: Path,
    summary_output_path: Path,
) -> None:
    python_df = pd.read_csv(python_baseline_path)
    cpp_df = pd.read_csv(cpp_output_path)

    python_df["property_id"] = python_df["property_id"].astype(str)
    cpp_df["property_id"] = cpp_df["property_id"].astype(str)

    merged = cpp_df.merge(
        python_df[
            [
                "property_id",
                "fema_zone",
                "is_sfha",
                "matched_fema_polygon",
                "fema_feature_index",
            ]
        ],
        on="property_id",
        how="left",
        suffixes=("_cpp", "_python"),
    )

    merged["cpp_matched_bool"] = normalize_bool(merged["cpp_matched_fema_polygon"])
    merged["cpp_sfha_bool"] = normalize_bool(merged["cpp_sfha_result"])
    merged["python_matched_bool"] = normalize_bool(merged["matched_fema_polygon"])
    merged["python_sfha_bool"] = normalize_bool(merged["is_sfha"])

    merged["matched_agrees"] = (
        merged["cpp_matched_bool"] == merged["python_matched_bool"]
    )
    merged["sfha_agrees"] = merged["cpp_sfha_bool"] == merged["python_sfha_bool"]
    merged["zone_agrees"] = (
        merged["cpp_fema_zone"].astype(str) == merged["fema_zone"].astype(str)
    )
    merged["feature_index_agrees"] = (
        merged["cpp_fema_feature_index"].astype(int)
        == merged["fema_feature_index"].astype(int)
    )

    all_agree = (
        merged["matched_agrees"]
        & merged["sfha_agrees"]
        & merged["zone_agrees"]
        & merged["feature_index_agrees"]
    )

    summary = {
        "python_baseline": str(python_baseline_path),
        "cpp_output": str(cpp_output_path),
        "total_cpp_rows": int(len(cpp_df)),
        "total_joined_rows": int(len(merged)),
        "missing_python_rows": int(merged["fema_zone"].isna().sum()),
        "matched_agreements": int(merged["matched_agrees"].sum()),
        "sfha_agreements": int(merged["sfha_agrees"].sum()),
        "zone_agreements": int(merged["zone_agrees"].sum()),
        "feature_index_agreements": int(merged["feature_index_agrees"].sum()),
        "all_fields_agree": int(all_agree.sum()),
        "matched_agreement_rate": float(merged["matched_agrees"].mean()),
        "sfha_agreement_rate": float(merged["sfha_agrees"].mean()),
        "zone_agreement_rate": float(merged["zone_agrees"].mean()),
        "feature_index_agreement_rate": float(merged["feature_index_agrees"].mean()),
        "all_fields_agreement_rate": float(all_agree.mean()),
    }

    detail_output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(detail_output_path, index=False)
    summary_output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))

    disagreements = merged[~all_agree]
    if len(disagreements) > 0:
        print("\nDisagreements:")
        print(
            disagreements[
                [
                    "property_id",
                    "cpp_matched_fema_polygon",
                    "matched_fema_polygon",
                    "cpp_sfha_result",
                    "is_sfha",
                    "cpp_fema_zone",
                    "fema_zone",
                    "cpp_fema_feature_index",
                    "fema_feature_index",
                ]
            ]
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare CAPRM-Flood Python and C++ FEMA membership outputs."
    )
    parser.add_argument(
        "--python-baseline",
        default="outputs/baseline/python_fema_membership.csv",
    )
    parser.add_argument(
        "--cpp-output",
        default="outputs/cpp/cpp_fema_membership_1000.csv",
    )
    parser.add_argument(
        "--detail-output",
        default="outputs/validation/fema_pip_1000_agreement_report.csv",
    )
    parser.add_argument(
        "--summary-output",
        default="outputs/validation/fema_pip_1000_summary.json",
    )

    args = parser.parse_args()

    compare(
        python_baseline_path=Path(args.python_baseline),
        cpp_output_path=Path(args.cpp_output),
        detail_output_path=Path(args.detail_output),
        summary_output_path=Path(args.summary_output),
    )


if __name__ == "__main__":
    main()