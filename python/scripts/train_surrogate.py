"""Train the PHASE C surrogate under the C1 partition, and under its control.

    python python/scripts/train_surrogate.py --tag headline

What this runs, once per recorded seed:

    blocked_kfold   K models, one per fold, aggregated over the union of the
                    folds' test sets, each property predicted at most once
    random_control  one model on the partition C1 rejected, so C2 can publish
                    the memorization gap rather than assert it

Nothing here rebuilds the partition, recomputes a label, or touches
``scoring.py``. The dataset and every split file are verified against
``c1_kfold_manifest.json`` before a single model is fitted, and the floor the
result is judged against is READ out of that manifest rather than quoted from a
document.

Writes:
    outputs/models/c2_surrogate_<partition>_seed<seed>_fold<k>.npz
    outputs/validation/c2_surrogate_manifest.json
    outputs/training/c2_predictions_<partition>_seed<seed>.csv   (--write-predictions)
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
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.surrogate import (  # noqa: E402
    CoordinateNormalizer,
    FourierConfig,
    MLPConfig,
    TrainConfig,
)
from caprm.surrogate_data import (  # noqa: E402
    PARTITION_BLOCKED,
    PARTITION_RANDOM,
    declared_floor,
    iter_splits,
    load_partition_inputs,
    sha256_file,
)
from caprm.surrogate_run import (  # noqa: E402
    RunConfig,
    compare_to_floor,
    memorization_gap,
    run_seed,
    summarise_partition,
)

TOOL_VERSION = "caprm.surrogate/c2.0"

# Declared BEFORE training and recorded in every manifest this script writes,
# so C3 confirms or refutes a prediction that is on disk with a timestamp
# rather than one remembered afterwards.
DECLARED_PREDICTION = (
    "FEMA zones are discontinuities. 98.1 percent of properties sit at the same "
    "FEMA component and the index steps sharply across a zone boundary. A smooth "
    "network cannot represent a step, only a ramp, so residuals should spike "
    "along zone boundaries and stay small elsewhere. Confirming or refuting this "
    "is C3's result and the prediction is not to be adjusted afterwards."
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="outputs/training/supervised_dataset_v2.csv")
    parser.add_argument(
        "--dataset-manifest",
        default="outputs/training/supervised_dataset_v2_manifest.json",
        help="source of the coordinate bounding box; read, never typed in",
    )
    parser.add_argument(
        "--partition-manifest", default="outputs/validation/c1_kfold_manifest.json"
    )
    parser.add_argument("--split-dir", default="outputs/splits")
    parser.add_argument(
        "--random-control", default="outputs/splits/random_control_countywide.csv"
    )
    parser.add_argument(
        "--partition",
        choices=[PARTITION_BLOCKED, PARTITION_RANDOM, "both"],
        default="both",
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument(
        "--folds", type=int, nargs="+", default=None,
        help="fold subset, for diagnostics only; a headline run uses every fold",
    )
    parser.add_argument("--features", type=int, default=64)
    parser.add_argument("--scale", type=float, default=8.0)
    parser.add_argument("--no-raw-coordinates", action="store_true")
    parser.add_argument("--hidden", type=int, nargs="+", default=[256, 256])
    parser.add_argument("--dtype", choices=["float32", "float64"], default="float32")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--batch", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--model-dir", default="outputs/models")
    parser.add_argument("--manifest", default="outputs/validation/c2_surrogate_manifest.json")
    parser.add_argument("--predictions-dir", default="outputs/training")
    parser.add_argument("--write-predictions", action="store_true")
    parser.add_argument(
        "--verify-determinism", action="store_true",
        help="refit the first fold of the first seed and compare weight digests",
    )
    parser.add_argument("--tag", default="headline")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    inputs = load_partition_inputs(args.dataset, args.partition_manifest)
    normalizer = CoordinateNormalizer.from_dataset_manifest(args.dataset_manifest)
    floor = declared_floor(inputs)
    seeds = args.seeds if args.seeds is not None else inputs.seeds

    config = RunConfig(
        fourier=FourierConfig(
            n_features=args.features,
            scale=args.scale,
            include_raw=not args.no_raw_coordinates,
        ),
        mlp=MLPConfig(hidden=tuple(args.hidden), dtype=args.dtype),
        train=TrainConfig(
            learning_rate=args.lr,
            batch_size=args.batch,
            max_epochs=args.epochs,
            patience=args.patience,
        ),
    )

    partitions = (
        [PARTITION_BLOCKED, PARTITION_RANDOM]
        if args.partition == "both"
        else [args.partition]
    )
    provenance = {
        "partition_manifest": str(args.partition_manifest),
        "partition_manifest_sha256": sha256_file(args.partition_manifest),
        "dataset_sha256": inputs.verification["dataset_sha256"],
        "tool_version": TOOL_VERSION,
        "run_tag": args.tag,
    }

    results: dict[str, list[dict]] = {}
    started = time.perf_counter()
    for partition in partitions:
        seed_results = []
        for seed in seeds:
            splits = iter_splits(
                inputs, partition, seed, args.split_dir, args.random_control
            )
            if args.folds is not None:
                splits = [s for s in splits if s.fold in set(args.folds)]
                if not splits:
                    raise SystemExit(f"--folds {args.folds} selected nothing")
            result = run_seed(
                inputs, splits, normalizer, config,
                model_dir=args.model_dir, provenance=provenance,
            )
            if not args.quiet:
                print(
                    f"{partition} seed {seed}: "
                    f"rmse {result['aggregate']['rmse']:.4f} "
                    f"r2 {result['aggregate']['r2']:.4f} "
                    f"n {result['aggregate']['n']} "
                    f"coverage {result['test_coverage_fraction']:.4f}"
                )
            if args.write_predictions:
                _write_predictions(inputs, result, partition, seed, args.predictions_dir)
            seed_results.append(result)
        results[partition] = seed_results
    elapsed = time.perf_counter() - started

    summaries = {p: summarise_partition(r) for p, r in results.items()}
    constant_summaries = {
        p: summarise_partition(r, key="constant_aggregate") for p, r in results.items()
    }
    manifest = {
        "task": "C2_neural_surrogate",
        "schema_version": "c2_surrogate_run_v1",
        "run_tag": args.tag,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tool_version": TOOL_VERSION,
        "crs": "EPSG:26918",
        "complete_run": args.folds is None and args.partition == "both",
        "inputs": {
            "dataset": str(args.dataset),
            "dataset_sha256": inputs.verification["dataset_sha256"],
            "rows": inputs.n_properties,
            "dataset_manifest": str(args.dataset_manifest),
            "dataset_manifest_sha256": sha256_file(args.dataset_manifest),
            "partition_manifest": str(args.partition_manifest),
            "partition_manifest_sha256": provenance["partition_manifest_sha256"],
            "buffer_m": inputs.buffer_m,
            "n_folds": inputs.n_folds,
            "seeds": [int(s) for s in seeds],
            "folds_run": args.folds,
        },
        "architecture": {
            "encoding": "gaussian_random_fourier",
            "n_frequencies": args.features,
            "fourier_scale": args.scale,
            "fourier_wavelength_m": config.fourier.wavelength_m(normalizer),
            "include_raw_coordinates": not args.no_raw_coordinates,
            "hidden": list(args.hidden),
            "training_dtype": args.dtype,
            "input_quantisation_m": normalizer.quantisation_m(args.dtype),
            "normalizer": normalizer.to_dict(),
        },
        "train_config": config.train.to_dict(),
        "declared_floor": floor,
        "declared_prediction_for_c3": DECLARED_PREDICTION,
        "results": {p: _strip_private(results[p]) for p in results},
        "summary": summaries,
        "summary_constant_baseline": constant_summaries,
        "wall_clock_seconds": elapsed,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "platform": platform.platform(),
            "note": (
                "BLAS chooses its blocking from operand shape and thread count, "
                "so bit-identical weights are claimed for a rerun on this "
                "machine and configuration, verified by --verify-determinism, "
                "not across machines."
            ),
        },
    }

    if PARTITION_BLOCKED in summaries:
        manifest["comparison_to_floor"] = compare_to_floor(
            summaries[PARTITION_BLOCKED],
            floor,
            constant_summaries[PARTITION_BLOCKED],
        )
    if PARTITION_BLOCKED in summaries and PARTITION_RANDOM in summaries:
        manifest["memorization_gap"] = memorization_gap(
            summaries[PARTITION_BLOCKED], summaries[PARTITION_RANDOM], floor
        )

    if args.verify_determinism:
        manifest["determinism"] = _verify_determinism(
            inputs, normalizer, config, partitions[0], seeds[0],
            args.split_dir, args.random_control, results[partitions[0]][0],
        )

    manifest["acceptance"] = _acceptance(manifest, args)

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(manifest["acceptance"], indent=2))
    if "comparison_to_floor" in manifest:
        rungs = manifest["comparison_to_floor"]["rmse_rungs"]
        print("\nblocked K-fold, aggregate RMSE across seeds:")
        for name, span in rungs.items():
            if span is not None:
                print(f"  {name:<38} {span[0]:8.4f} … {span[1]:8.4f}")
        print("\n" + manifest["comparison_to_floor"]["verdict"])
        constant_block = manifest["comparison_to_floor"]["constant_baseline"]
        if constant_block:
            print(
                "surrogate beats the constant rung as a range: "
                f"{constant_block['surrogate_beats_constant_as_a_range']}"
            )
    print(f"\nwrote {manifest_path}")
    return 0 if manifest["acceptance"]["run_completed"] else 1


def _strip_private(seed_results: list[dict]) -> list[dict]:
    """Drop the in-memory prediction arrays; a manifest carries measurements."""
    return [
        {k: v for k, v in record.items() if not k.startswith("_")}
        for record in seed_results
    ]


def _write_predictions(inputs, result, partition, seed, directory) -> Path:
    """Per-property predictions for the rows this seed tested. C3's input."""
    tested = result["_tested"]
    frame = pd.DataFrame(
        {
            "property_id": inputs.property_id[tested],
            "x": inputs.x[tested],
            "y": inputs.y[tested],
            "fold": result["_fold_of_property"][tested],
            "actual": inputs.target[tested],
            "predicted": result["_predictions"][tested],
        }
    )
    frame["residual"] = frame["predicted"] - frame["actual"]
    out = Path(directory) / f"c2_predictions_{partition}_seed{seed}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False, lineterminator="\n", float_format="%.17g")
    return out


def _verify_determinism(
    inputs, normalizer, config, partition, seed, split_dir, random_control, original
) -> dict:
    """Refit the first fold and require an identical weight digest.

    Verified rather than asserted, and reported whether it holds or not: a
    determinism claim that is never re-run is a statement about intent.
    """
    splits = iter_splits(inputs, partition, seed, split_dir, random_control)
    repeat = run_seed(inputs, splits[:1], normalizer, config, model_dir=None)
    first = original["folds"][0]["weights_sha256"]
    second = repeat["folds"][0]["weights_sha256"]
    return {
        "refit": f"{partition} seed {seed} fold {splits[0].fold}",
        "weights_sha256_first_run": first,
        "weights_sha256_refit": second,
        "identical": bool(first == second),
        "rmse_first_run": original["folds"][0]["test"]["rmse"],
        "rmse_refit": repeat["folds"][0]["test"]["rmse"],
    }


def _acceptance(manifest: dict, args) -> dict:
    comparison = manifest.get("comparison_to_floor")
    determinism = manifest.get("determinism")
    summary = manifest["summary"]
    return {
        "run_completed": True,
        "complete_run": manifest["complete_run"],
        "partitions_run": sorted(summary),
        "seeds_run": manifest["inputs"]["seeds"],
        "models_written": sum(
            len(seed_record["folds"])
            for records in manifest["results"].values()
            for seed_record in records
        ),
        "scoring_layer_untouched": True,
        "partition_rebuilt": False,
        "beats_declared_floor_as_a_range": (
            comparison["ranges_are_disjoint"] if comparison else None
        ),
        "beats_declared_floor_at_every_seed": (
            comparison["beats_floor_per_seed"] if comparison else None
        ),
        "beats_constant_baseline_as_a_range": (
            comparison["constant_baseline"]["surrogate_beats_constant_as_a_range"]
            if comparison and comparison.get("constant_baseline")
            else None
        ),
        "memorization_gap_measured": "memorization_gap" in manifest,
        "deterministic_on_refit": determinism["identical"] if determinism else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
