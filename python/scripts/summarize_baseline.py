import json
from pathlib import Path

import pandas as pd


INPUT = Path("outputs/baseline/python_fema_membership.csv")
OUTPUT = Path("outputs/validation/python_baseline_summary.json")


def main() -> None:
    df = pd.read_csv(INPUT)

    summary = {
        "input_file": str(INPUT),
        "total_properties": int(len(df)),
        "matched_fema_polygon": int(df["python_result"].sum()),
        "unmatched_fema_polygon": int((~df["python_result"].astype(bool)).sum()),
        "python_result_counts": {
            str(k): int(v)
            for k, v in df["python_result"].value_counts(dropna=False).items()
        },
        "sfha_flag_counts": {
            str(k): int(v)
            for k, v in df["sfha_flag"].value_counts(dropna=False).items()
        },
        "fema_zone_counts": {
            str(k): int(v)
            for k, v in df["fema_zone"].value_counts(dropna=False).items()
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()