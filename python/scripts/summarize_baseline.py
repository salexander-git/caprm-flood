import json
from pathlib import Path

import pandas as pd


INPUT = Path("outputs/baseline/python_fema_membership.csv")
OUTPUT = Path("outputs/validation/python_baseline_summary.json")


def bool_counts(series: pd.Series) -> dict[str, int]:
    return {
        str(k): int(v)
        for k, v in series.value_counts(dropna=False).items()
    }


def value_counts(series: pd.Series) -> dict[str, int]:
    return {
        str(k): int(v)
        for k, v in series.value_counts(dropna=False).items()
    }


def main() -> None:
    df = pd.read_csv(INPUT)

    required_columns = [
        "property_id",
        "latitude",
        "longitude",
        "projected_x",
        "projected_y",
        "fema_zone",
        "sfha_flag",
        "is_sfha",
        "source_geometry_id",
        "matched_fema_polygon",
        "python_sfha_result",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise RuntimeError(f"Missing expected columns: {missing_columns}")

    summary = {
        "input_file": str(INPUT),
        "total_properties": int(len(df)),
        "matched_fema_polygon": int(df["matched_fema_polygon"].astype(bool).sum()),
        "unmatched_fema_polygon": int((~df["matched_fema_polygon"].astype(bool)).sum()),
        "is_sfha_true": int(df["is_sfha"].astype(bool).sum()),
        "is_sfha_false": int((~df["is_sfha"].astype(bool)).sum()),
        "python_sfha_true": int(df["python_sfha_result"].astype(bool).sum()),
        "python_sfha_false": int((~df["python_sfha_result"].astype(bool)).sum()),
        "matched_fema_polygon_counts": bool_counts(df["matched_fema_polygon"]),
        "is_sfha_counts": bool_counts(df["is_sfha"]),
        "python_sfha_result_counts": bool_counts(df["python_sfha_result"]),
        "sfha_flag_counts": value_counts(df["sfha_flag"]),
        "fema_zone_counts": value_counts(df["fema_zone"]),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()