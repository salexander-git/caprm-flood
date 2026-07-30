"""Sweep the Fourier feature scale. A result at one operating point is one point.

    python python/scripts/sweep_surrogate_scale.py

Why this parameter and not another
----------------------------------
The scale is the standard deviation of the random frequency draw, so it sets
the wavelength the encoding can represent. Converted through the normalizer it
is a length in METRES, which means the curve can be read against C1's measured
variogram — gamma/sill = 0.25 at 625 m, 0.50 at 2,125 m, 0.75 at 6,125 m —
rather than against a list of unitless settings. Nucleus 18.27 records that the
reported benefit of a learned method depends on parameters the literature holds
fixed and does not report; this is the one most likely to move C2's headline.

The selection rule, declared before the sweep is run
----------------------------------------------------
The operating point is chosen on MEAN VALIDATION RMSE across the recorded
seeds. Test error at each scale is also recorded and published as a sensitivity
curve, and it is not used to select. Selecting on it would spend the separation
C1 paid 32 percent of its test coverage to obtain.

By default every seed is swept at ONE fold, because the sweep costs
``len(scales) * len(seeds) * len(folds)`` fits and a headline run is
``len(seeds) * K``. The fold used is recorded. The curve is therefore a
diagnostic across seeds at one fold, and the headline is a full run at the
selected scale — the two are different measurements and the manifest says so.

Writes:
    outputs/validation/c2_scale_sweep.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.surrogate import (  # noqa: E402
    CoordinateNormalizer,
    FourierConfig,
    MLPConfig,
    TrainConfig,
)
from caprm.surrogate_data import (  # noqa: E402
    PARTITION_BLOCKED,
    declared_floor,
    iter_splits,
    load_partition_inputs,
    sha256_file,
)
from caprm.surrogate_run import RunConfig, fit_split  # noqa: E402

TOOL_VERSION = "caprm.surrogate/c2.0"
DEFAULT_SCALES = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0)
SELECTION_RULE = "minimum mean validation RMSE across the recorded seeds"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="outputs/training/supervised_dataset_v2.csv")
    parser.add_argument(
        "--dataset-manifest", default="outputs/training/supervised_dataset_v2_manifest.json"
    )
    parser.add_argument(
        "--partition-manifest", default="outputs/validation/c1_kfold_manifest.json"
    )
    parser.add_argument("--split-dir", default="outputs/splits")
    parser.add_argument("--scales", type=float, nargs="+", default=list(DEFAULT_SCALES))
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--folds", type=int, nargs="+", default=[0])
    parser.add_argument("--features", type=int, default=64)
    parser.add_argument("--hidden", type=int, nargs="+", default=[256, 256])
    parser.add_argument("--dtype", choices=["float32", "float64"], default="float32")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--batch", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--manifest", default="outputs/validation/c2_scale_sweep.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    inputs = load_partition_inputs(args.dataset, args.partition_manifest)
    normalizer = CoordinateNormalizer.from_dataset_manifest(args.dataset_manifest)
    seeds = args.seeds if args.seeds is not None else inputs.seeds
    selected_folds = set(args.folds)

    rows: list[dict] = []
    started = time.perf_counter()
    for scale in args.scales:
        config = RunConfig(
            fourier=FourierConfig(n_features=args.features, scale=float(scale)),
            mlp=MLPConfig(hidden=tuple(args.hidden), dtype=args.dtype),
            train=TrainConfig(
                learning_rate=args.lr,
                batch_size=args.batch,
                max_epochs=args.epochs,
                patience=args.patience,
            ),
        )
        wavelength = config.fourier.wavelength_m(normalizer)
        for seed in seeds:
            splits = [
                s
                for s in iter_splits(inputs, PARTITION_BLOCKED, seed, args.split_dir)
                if s.fold in selected_folds
            ]
            if not splits:
                raise SystemExit(f"--folds {sorted(selected_folds)} selected nothing")
            for split in splits:
                _, _, record = fit_split(inputs, split, normalizer, config)
                rows.append(
                    {
                        "scale": float(scale),
                        "wavelength_m": wavelength,
                        "seed": int(seed),
                        "fold": split.fold,
                        "n_train": split.counts()["train"],
                        "n_val": split.counts()["val"],
                        "n_test": split.counts()["test"],
                        "val_rmse": record["best_val_rmse_label_units"],
                        "test_rmse": record["test"]["rmse"],
                        "test_variance_ratio": record["test"]["variance_ratio"],
                        "test_r2": record["test"]["r2"],
                        "epochs_run": record["epochs_run"],
                        "best_epoch": record["best_epoch"],
                        "weights_sha256": record["weights_sha256"],
                    }
                )
                print(
                    f"scale {scale:>7.2f} ({wavelength:9.1f} m) seed {seed} "
                    f"fold {split.fold}: val {record['best_val_rmse_label_units']:.4f} "
                    f"test {record['test']['rmse']:.4f}"
                )
    elapsed = time.perf_counter() - started

    curve = []
    for scale in args.scales:
        subset = [r for r in rows if r["scale"] == float(scale)]
        val = np.array([r["val_rmse"] for r in subset], dtype=float)
        test = np.array([r["test_rmse"] for r in subset], dtype=float)
        ratio = np.array([r["test_variance_ratio"] for r in subset], dtype=float)
        curve.append(
            {
                "scale": float(scale),
                "wavelength_m": subset[0]["wavelength_m"],
                "n_fits": len(subset),
                "val_rmse_mean": float(val.mean()),
                "val_rmse_min": float(val.min()),
                "val_rmse_max": float(val.max()),
                "test_rmse_mean": float(test.mean()),
                "test_rmse_min": float(test.min()),
                "test_rmse_max": float(test.max()),
                "test_rmse_seed_range": float(test.max() - test.min()),
                "test_variance_ratio_mean": float(ratio.mean()),
            }
        )

    best = min(curve, key=lambda row: row["val_rmse_mean"])
    moves = float(
        max(r["test_rmse_mean"] for r in curve) - min(r["test_rmse_mean"] for r in curve)
    )

    manifest = {
        "task": "C2_fourier_scale_sweep",
        "schema_version": "c2_scale_sweep_v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tool_version": TOOL_VERSION,
        "crs": "EPSG:26918",
        "selection_rule": SELECTION_RULE,
        "selection_uses_test_error": False,
        "inputs": {
            "dataset_sha256": inputs.verification["dataset_sha256"],
            "partition_manifest": str(args.partition_manifest),
            "partition_manifest_sha256": sha256_file(args.partition_manifest),
            "seeds": [int(s) for s in seeds],
            "folds": sorted(selected_folds),
            "n_folds_available": inputs.n_folds,
        },
        "architecture": {
            "n_frequencies": args.features,
            "hidden": list(args.hidden),
            "training_dtype": args.dtype,
            "normalizer_scale_m": normalizer.scale_m,
        },
        "train_config": TrainConfig(
            learning_rate=args.lr,
            batch_size=args.batch,
            max_epochs=args.epochs,
            patience=args.patience,
        ).to_dict(),
        "variogram_reference_lags_m": {
            "gamma_over_sill_0.25": 625.0,
            "gamma_over_sill_0.50": 2125.0,
            "gamma_over_sill_0.75": 6125.0,
        },
        "curve": curve,
        "fits": rows,
        "selected": {
            "scale": best["scale"],
            "wavelength_m": best["wavelength_m"],
            "val_rmse_mean": best["val_rmse_mean"],
        },
        "headline_movement_test_rmse_mean": moves,
        "declared_floor": declared_floor(inputs),
        "wall_clock_seconds": elapsed,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "interpretation": (
            "The scale is reported as a metric wavelength so the curve can be "
            "read against the measured variogram. This sweep is one fold per "
            "seed and is a diagnostic; the headline is a full K-fold run at the "
            "selected scale."
        ),
    }

    path = Path(args.manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("\nscale      wavelength_m   val_rmse_mean   test_rmse_mean")
    for row in curve:
        print(
            f"{row['scale']:>8.2f}  {row['wavelength_m']:>12.1f}  "
            f"{row['val_rmse_mean']:>13.4f}  {row['test_rmse_mean']:>14.4f}"
        )
    print(f"\nselected scale {best['scale']} on {SELECTION_RULE}")
    print(f"test RMSE mean moves {moves:.4f} across the swept range")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
