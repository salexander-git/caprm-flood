"""Measure how much a blocked split's reported numbers depend on its seed.

    python python/scripts/measure_split_seed_stability.py

The separation is declared first and held fixed. What varies is only the seed —
that is, which blocks land in which split. If the test-set composition and the
baseline error move materially across seeds, a single blocked holdout cannot
carry a C2 result and the honest structure is blocked K-fold.

Writes outputs/validation/c1_split_seed_stability.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.spatial_split import (  # noqa: E402
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_VAL,
    SplitConfig,
    apply_buffer,
    assign_block_splits,
    assign_blocks,
)
from caprm.split_gate import (  # noqa: E402
    nearest_neighbour_baseline,
    summarise_seed_stability,
)

# (block_size_m, train_fraction, val_fraction, buffer_m)
GEOMETRIES = (
    (2000.0, 0.70, 0.15, 625.0),
    (3000.0, 0.60, 0.20, 625.0),
    (4000.0, 0.50, 0.25, 2125.0),
    (8000.0, 0.60, 0.20, 2125.0),
)
SEEDS = tuple(20260722 + k for k in range(10))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="outputs/training/supervised_dataset_v2.csv")
    parser.add_argument("--out", default="outputs/validation/c1_split_seed_stability.json")
    args = parser.parse_args(argv)

    frame = pd.read_csv(args.dataset, dtype={"property_id": str}, float_precision="round_trip")
    x = frame["x"].to_numpy()
    y = frame["y"].to_numpy()
    z = frame["exposure_index_0_100"].to_numpy()
    population = {
        "n": int(len(z)),
        "mean": float(z.mean()),
        "std": float(z.std(ddof=1)),
    }

    results = []
    for block_size, train_fraction, val_fraction, buffer_m in GEOMETRIES:
        per_seed = []
        for seed in SEEDS:
            config = SplitConfig(
                block_size_m=block_size,
                buffer_m=buffer_m,
                seed=seed,
                train_fraction=train_fraction,
                val_fraction=val_fraction,
            )
            block_i, block_j = assign_blocks(x, y, config)
            pre = assign_block_splits(block_i, block_j, config)
            split = apply_buffer(x, y, pre, config)
            test_mask = split == SPLIT_TEST
            baseline = nearest_neighbour_baseline(x, y, z, split, SPLIT_TEST, "seed_sweep")
            per_seed.append(
                {
                    "seed": seed,
                    "n_train": int((split == SPLIT_TRAIN).sum()),
                    "n_val": int((split == SPLIT_VAL).sum()),
                    "n_test": int(test_mask.sum()),
                    "test_mean_label": float(z[test_mask].mean()) if test_mask.any() else float("nan"),
                    "test_std_label": float(z[test_mask].std(ddof=1)) if test_mask.sum() > 1 else float("nan"),
                    "baseline_rmse": baseline.rmse if baseline else float("nan"),
                    "baseline_r2": baseline.r2 if baseline else float("nan"),
                }
            )
        results.append(
            {
                "geometry": {
                    "block_size_m": block_size,
                    "train_fraction": train_fraction,
                    "val_fraction": val_fraction,
                    "buffer_m": buffer_m,
                },
                "per_seed": per_seed,
                "summary": summarise_seed_stability(per_seed),
            }
        )

    payload = {
        "schema_version": "c1_split_seed_stability_v1",
        "dataset": args.dataset,
        "population": population,
        "seeds": list(SEEDS),
        "geometries": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())