"""Build the C1 blocked K-fold partition of record, with its controls.

    python python/scripts/build_spatial_kfold.py

Operating point, declared on the separation axis before any loss was looked at:

    buffer w = 2,125 m   the lag at which gamma reaches 0.50 of the sill,
                         read from outputs/validation/spatial_correlation_v2.json
                         rather than typed in
    block  b = 10,000 m  chosen so a block retains an interior after erosion by w
                         on every side, and so folds stay balanced
    K = 5                every occupied block is test exactly once, val once
    5 seeds              because K-fold reduces but does not remove the seed's
                         leverage; C2 reports across these five, not one

Three partitions go through one gate. The blocked, buffered partition must PASS;
the random partition and the blocked, UNBUFFERED partition must both FAIL, or
the gate is not measuring anything (Nucleus 18.25).

Writes:
    outputs/splits/spatial_kfold_countywide_seed<seed>.csv   one per seed
    outputs/splits/random_control_countywide.csv             the positive control
    outputs/validation/c1_kfold_manifest.json                everything measured
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.spatial_kfold import (  # noqa: E402
    KFoldConfig,
    build_kfold,
    dropped_mask_codes,
    roles_for_fold,
    roles_from_codes,
)
from caprm.spatial_split import (  # noqa: E402
    SPLIT_TEST,
    SPLIT_VAL,
    SplitConfig,
    assign_blocks,
)
from caprm.split_gate import (  # noqa: E402
    coordinate_label_ambiguity,
    measure_gate,
    nearest_neighbour_baseline,
    random_split,
)

TOOL_VERSION = "caprm.spatial_kfold/c1.0"
DEFAULT_SEEDS = (20260722, 20260723, 20260724, 20260725, 20260726)
SEPARATION_RATIO = "0.50"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def separation_from_correlation(path: Path, ratio: str) -> float:
    """Read the declared separation out of the measured variogram."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    lag = payload["raw"]["long"]["first_lag_at_ratio_m"].get(ratio)
    if lag is None:
        raise ValueError(
            f"correlation artifact does not resolve gamma/sill = {ratio}; "
            "the separation cannot be derived and must not be invented"
        )
    return float(lag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="outputs/training/supervised_dataset_v2.csv")
    parser.add_argument(
        "--correlation-json", default="outputs/validation/spatial_correlation_v2.json"
    )
    parser.add_argument("--block-size", type=float, default=10000.0)
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--split-dir", default="outputs/splits")
    parser.add_argument("--manifest", default="outputs/validation/c1_kfold_manifest.json")
    parser.add_argument(
        "--separation-ratio", default=SEPARATION_RATIO,
        help="gamma/sill at which the buffer is set; read from the variogram",
    )
    args = parser.parse_args(argv)

    buffer_m = separation_from_correlation(Path(args.correlation_json), args.separation_ratio)

    frame = pd.read_csv(args.dataset, dtype={"property_id": str}, float_precision="round_trip")
    pid = frame["property_id"].to_numpy(dtype=object)
    x = frame["x"].to_numpy()
    y = frame["y"].to_numpy()
    z = frame["exposure_index_0_100"].to_numpy()

    split_dir = Path(args.split_dir)
    split_dir.mkdir(parents=True, exist_ok=True)

    per_seed = []
    for seed in args.seeds:
        config = KFoldConfig(
            block_size_m=args.block_size,
            buffer_m=buffer_m,
            n_folds=args.n_folds,
            seed=seed,
        )
        result = build_kfold(pid, x, y, z, config)
        codes = dropped_mask_codes(result.roles, config.n_folds)

        # the encoding must reproduce the roles it replaces, checked here rather
        # than trusted, because the split file IS the encoding
        if not (roles_from_codes(result.fold, codes, config.n_folds) == result.roles).all():
            raise RuntimeError("role encoding does not round-trip; refusing to write")

        out = split_dir / f"spatial_kfold_countywide_seed{seed}.csv"
        pd.DataFrame(
            {
                "property_id": result.property_id,
                "block_i": result.block_i,
                "block_j": result.block_j,
                "block_id": [f"{int(i)}_{int(j)}" for i, j in zip(result.block_i, result.block_j)],
                "fold": result.fold,
                "dropped_mask": codes,
            }
        ).to_csv(out, index=False, lineterminator="\n")

        # determinism: rebuild and require an identical assignment
        rerun = build_kfold(pid, x, y, z, config)
        deterministic = bool(
            np.array_equal(rerun.fold, result.fold)
            and (rerun.roles == result.roles).all()
        )

        per_seed.append(
            {
                "seed": seed,
                "split_path": str(out),
                "split_sha256": sha256(out),
                "deterministic_on_rerun": deterministic,
                "stats": result.stats,
            }
        )

    # ---- controls, through the identical gate -----------------------------
    control_config = KFoldConfig(
        block_size_m=args.block_size, buffer_m=buffer_m,
        n_folds=args.n_folds, seed=args.seeds[0],
    )
    block_i, block_j = assign_blocks(x, y, control_config.as_split_config())

    unbuffered = build_kfold(
        pid, x, y, z,
        KFoldConfig(block_size_m=args.block_size, buffer_m=0.0,
                    n_folds=args.n_folds, seed=args.seeds[0]),
    )
    unbuffered_gates = [
        measure_gate(
            x, y, block_i, block_j, unbuffered.roles[:, k], SPLIT_TEST,
            criterion_separation_m=buffer_m, block_size_m=args.block_size,
            partition=f"blocked_unbuffered_fold{k}",
        ).to_dict()
        for k in range(args.n_folds)
    ]

    rnd = random_split(len(pid), seed=args.seeds[0])
    random_gate = measure_gate(
        x, y, block_i, block_j, rnd, SPLIT_TEST,
        criterion_separation_m=buffer_m, block_size_m=args.block_size,
        partition="random",
    )
    random_baseline = nearest_neighbour_baseline(x, y, z, rnd, SPLIT_TEST, "random")
    random_path = split_dir / "random_control_countywide.csv"
    pd.DataFrame({"property_id": pid, "split": rnd}).to_csv(
        random_path, index=False, lineterminator="\n"
    )

    blocked_passed = all(
        f["gate_test"]["passed"] and f["gate_val"]["passed"]
        for s in per_seed for f in s["stats"]["folds"]
    )
    unbuffered_failed = all(not g["passed"] for g in unbuffered_gates)
    random_failed = not random_gate.passed

    aggregate_rmse = [s["stats"]["aggregate_baseline"]["rmse"] for s in per_seed]
    aggregate_r2 = [s["stats"]["aggregate_baseline"]["r2"] for s in per_seed]

    manifest = {
        "task": "C1_blocked_kfold_partition",
        "schema_version": "c1_kfold_v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tool_version": TOOL_VERSION,
        "crs": "EPSG:26918",
        "operating_point": {
            "buffer_m": buffer_m,
            "buffer_chosen_as": f"lag at gamma/sill = {args.separation_ratio}",
            "buffer_source": str(args.correlation_json),
            "block_size_m": args.block_size,
            "n_folds": args.n_folds,
            "seeds": list(args.seeds),
            "grid_origin_x_m": 0.0,
            "grid_origin_y_m": 0.0,
            "isolate_test_from_val": True,
            "fold_hash": "blake2b(f'{seed}:fold:{i}:{j}') % n_folds",
        },
        "inputs": {
            "dataset": args.dataset,
            "dataset_sha256": sha256(Path(args.dataset)),
            "rows": int(len(frame)),
            "correlation_artifact": str(args.correlation_json),
            "correlation_sha256": sha256(Path(args.correlation_json)),
        },
        "coordinate_label_ambiguity": coordinate_label_ambiguity(x, y, z),
        "per_seed": per_seed,
        "controls": {
            "blocked_unbuffered": {
                "expected": "FAIL",
                "failed_as_expected": unbuffered_failed,
                "gates": unbuffered_gates,
            },
            "random": {
                "expected": "FAIL",
                "failed_as_expected": random_failed,
                "gate": random_gate.to_dict(),
                "baseline": random_baseline.to_dict() if random_baseline else None,
                "split_path": str(random_path),
                "split_sha256": sha256(random_path),
            },
        },
        "acceptance": {
            "blocked_gate_passed_every_fold_every_seed": blocked_passed,
            "unbuffered_control_failed": unbuffered_failed,
            "random_control_failed": random_failed,
            "deterministic_every_seed": all(s["deterministic_on_rerun"] for s in per_seed),
            "aggregate_baseline_rmse_range": float(max(aggregate_rmse) - min(aggregate_rmse)),
            "aggregate_baseline_r2_min": float(min(aggregate_r2)),
            "aggregate_baseline_r2_max": float(max(aggregate_r2)),
        },
        "interpretation": (
            "Test properties are separated from every training AND validation "
            "property by at least the recorded buffer, at which the field "
            "retains gamma/sill = " + args.separation_ratio + ". The field is "
            "non-stationary and still climbing at 8 km, so this is a stated "
            "residual dependence, not decorrelation. Error measured on this "
            "partition is error at separation >= buffer, not countywide error."
        ),
    }

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(manifest["acceptance"], indent=2))
    print(f"\nwrote {manifest_path}")
    ok = (
        blocked_passed
        and unbuffered_failed
        and random_failed
        and manifest["acceptance"]["deterministic_every_seed"]
    )
    print("ACCEPTANCE OK" if ok else "ACCEPTANCE FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())