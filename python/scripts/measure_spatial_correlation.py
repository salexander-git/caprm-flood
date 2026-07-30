"""Measure the spatial correlation length of the v2 exposure index.

    python python/scripts/measure_spatial_correlation.py

Produces the evidence that the C1 block edge is chosen against:

    outputs/validation/spatial_correlation_v2.json          all measured values
    outputs/validation/spatial_correlation_v2_short.csv     short-lag variogram
    outputs/validation/spatial_correlation_v2_long.csv      long-lag variogram

Determinism is verified rather than asserted: with ``--verify-rerun`` the short
pass is recomputed under the same seed and the bin arrays must match exactly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.spatial_correlation import (  # noqa: E402
    Variogram,
    first_lag_at_ratio,
    fit_exponential,
    nearest_neighbour_spacing,
    polynomial_detrend,
    variogram_long_range,
    variogram_short_range,
)

DEFAULT_DATASET = "outputs/training/supervised_dataset_v2.csv"
DEFAULT_JSON = "outputs/validation/spatial_correlation_v2.json"
RATIOS = (0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
SHORT_FIT_WINDOWS_M = (500.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0)
LONG_FIT_WINDOWS_M = (3000.0, 5000.0, 8000.0, 12000.0, 20000.0)


def _variogram_frame(v: Variogram) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "lag_centre_m": v.lag_centre_m,
            "semivariance": v.semivariance,
            "semivariance_over_sill": np.asarray(v.semivariance) / v.sill,
            "pair_count": v.pair_count,
        }
    )


def _summarise(v: Variogram) -> dict:
    return {
        "method": v.method,
        "seed": v.seed,
        "n_centres": v.n_centres,
        "bin_width_m": v.bin_width_m,
        "sill_sample_variance": v.sill,
        "total_pairs": int(np.asarray(v.pair_count).sum()),
        "first_lag_at_ratio_m": {
            f"{r:.2f}": first_lag_at_ratio(v, r) for r in RATIOS
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--json-out", default=DEFAULT_JSON)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--short-max-lag-m", type=float, default=3000.0)
    parser.add_argument("--short-bin-width-m", type=float, default=25.0)
    parser.add_argument("--short-centres", type=int, default=6000)
    parser.add_argument("--long-max-lag-m", type=float, default=25000.0)
    parser.add_argument("--long-bin-width-m", type=float, default=250.0)
    parser.add_argument("--long-sample", type=int, default=20000)
    parser.add_argument("--detrend-degree", type=int, default=3)
    parser.add_argument("--verify-rerun", action="store_true")
    args = parser.parse_args(argv)

    frame = pd.read_csv(args.dataset, dtype={"property_id": str})
    x = frame["x"].to_numpy()
    y = frame["y"].to_numpy()
    z = frame["exposure_index_0_100"].to_numpy()

    residual, trend_r2 = polynomial_detrend(x, y, z, degree=args.detrend_degree)

    short = variogram_short_range(
        x, y, z,
        max_lag_m=args.short_max_lag_m,
        bin_width_m=args.short_bin_width_m,
        n_centres=args.short_centres,
        seed=args.seed,
    )
    short_detrended = variogram_short_range(
        x, y, residual,
        max_lag_m=args.short_max_lag_m,
        bin_width_m=args.short_bin_width_m,
        n_centres=args.short_centres,
        seed=args.seed,
    )
    long = variogram_long_range(
        x, y, z,
        max_lag_m=args.long_max_lag_m,
        bin_width_m=args.long_bin_width_m,
        n_sample=args.long_sample,
        seed=args.seed,
    )

    rerun_identical = None
    if args.verify_rerun:
        again = variogram_short_range(
            x, y, z,
            max_lag_m=args.short_max_lag_m,
            bin_width_m=args.short_bin_width_m,
            n_centres=args.short_centres,
            seed=args.seed,
        )
        rerun_identical = bool(
            np.array_equal(again.pair_count, short.pair_count)
            and np.array_equal(
                np.nan_to_num(again.semivariance), np.nan_to_num(short.semivariance)
            )
        )

    payload = {
        "schema_version": "spatial_correlation_v2",
        "dataset": args.dataset,
        "label_column": "exposure_index_0_100",
        "label_policy_version": "preliminary_exposure_index_v2",
        "crs": "EPSG:26918",
        "rows": int(len(frame)),
        "seed": args.seed,
        "nearest_neighbour_spacing": nearest_neighbour_spacing(x, y),
        "raw": {
            "short": _summarise(short),
            "long": _summarise(long),
            "exponential_fit_window_sweep": {
                "short_pass": [fit_exponential(short, w) for w in SHORT_FIT_WINDOWS_M],
                "long_pass": [fit_exponential(long, w) for w in LONG_FIT_WINDOWS_M],
            },
        },
        "detrended": {
            "polynomial_degree": args.detrend_degree,
            "trend_r_squared": trend_r2,
            "residual_variance": float(np.var(residual, ddof=1)),
            "short": _summarise(short_detrended),
            "exponential_fit_window_sweep": {
                "short_pass": [
                    fit_exponential(short_detrended, w) for w in SHORT_FIT_WINDOWS_M
                ]
            },
        },
        "determinism_rerun_identical": rerun_identical,
        "interpretation": (
            "first_lag_at_ratio is model-free and is what the block edge is "
            "chosen against. The fitted range parameter is a diagnostic only: "
            "it is swept across fit windows here precisely because it is not "
            "stable across them."
        ),
    }

    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _variogram_frame(short).to_csv(
        out.with_name(out.stem + "_short.csv"), index=False, lineterminator="\n"
    )
    _variogram_frame(long).to_csv(
        out.with_name(out.stem + "_long.csv"), index=False, lineterminator="\n"
    )
    _variogram_frame(short_detrended).to_csv(
        out.with_name(out.stem + "_short_detrended.csv"), index=False, lineterminator="\n"
    )

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())