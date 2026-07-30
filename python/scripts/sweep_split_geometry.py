"""Sweep the C1 split geometry and run the gate ladder on every partition.

    python python/scripts/sweep_split_geometry.py

The operating point is chosen on the SEPARATION axis, declared before the loss
is looked at, and the retained row counts are reported as a consequence. The
sweep publishes the whole frontier so the choice can be argued with rather than
asserted.

Three partitions go through the identical gate, which is the control structure
Phase B's ladder used — adjacent comparisons isolating one variable each:

    random                 expect FAIL   does the gate have teeth at all
    blocked, no buffer     expect FAIL   is the buffer doing work
    blocked, buffered      expect PASS   the partition of record

If the middle row passes, the buffer is unnecessary and the design is
over-built. If it fails, the buffer's contribution is isolated.
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
    SPLIT_VAL,
    SplitConfig,
    apply_buffer,
    assign_block_splits,
    assign_blocks,
)
from caprm.split_gate import (  # noqa: E402
    coordinate_label_ambiguity,
    measure_gate,
    nearest_neighbour_baseline,
    random_split,
)

DEFAULT_DATASET = "outputs/training/supervised_dataset_v2.csv"
DEFAULT_OUT = "outputs/validation/c1_split_geometry_sweep.json"

# The separation ladder is DERIVED from the measured variogram, never typed in.
# Each rung is the lag at which gamma reaches a stated fraction of the sill, so
# the operating point is chosen on the separation axis in units of gamma/sill
# and the retained row count is reported as its consequence.
SEPARATION_RATIOS = (0.10, 0.25, 0.50, 0.75)
BLOCK_SIZES_M = (2000.0, 4000.0, 8000.0)


def separation_ladder(correlation_json: Path) -> dict[str, dict[str, float | None]]:
    """Read gamma/sill crossing lags from the correlation artifact.

    The long pass is used because it is the only one that spans every ratio;
    where the finer short pass also resolves a ratio, both are recorded so the
    estimator disagreement is visible rather than averaged away.
    """
    payload = json.loads(Path(correlation_json).read_text(encoding="utf-8"))
    long_pass = payload["raw"]["long"]["first_lag_at_ratio_m"]
    short_pass = payload["raw"]["short"]["first_lag_at_ratio_m"]
    ladder = {}
    for ratio in SEPARATION_RATIOS:
        key = f"{ratio:.2f}"
        lag = long_pass.get(key)
        if lag is None:
            raise ValueError(
                f"correlation artifact does not resolve gamma/sill = {key}; "
                "the ladder cannot be derived and must not be invented"
            )
        ladder[key] = {"separation_m": float(lag),
                       "short_pass_separation_m": short_pass.get(key)}
    return ladder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--correlation-json", default="outputs/validation/spatial_correlation_v2.json")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    args = parser.parse_args(argv)

    ladder = separation_ladder(Path(args.correlation_json))
    separations = tuple(v["separation_m"] for v in ladder.values())

    frame = pd.read_csv(args.dataset, dtype={"property_id": str}, float_precision="round_trip")
    pid = frame["property_id"].to_numpy(dtype=object)
    x = frame["x"].to_numpy()
    y = frame["y"].to_numpy()
    z = frame["exposure_index_0_100"].to_numpy()

    rows = []
    for block_size in BLOCK_SIZES_M:
        base = SplitConfig(
            block_size_m=block_size,
            buffer_m=0.0,
            seed=args.seed,
            train_fraction=args.train_fraction,
            val_fraction=args.val_fraction,
        )
        block_i, block_j = assign_blocks(x, y, base)
        pre = assign_block_splits(block_i, block_j, base)

        for separation in (0.0,) + separations:
            config = SplitConfig(
                block_size_m=block_size,
                buffer_m=separation,
                seed=args.seed,
                train_fraction=args.train_fraction,
                val_fraction=args.val_fraction,
            )
            split = pre.copy() if separation == 0.0 else apply_buffer(x, y, pre, config)
            partition = (
                f"blocked_b{block_size:.0f}_unbuffered"
                if separation == 0.0
                else f"blocked_b{block_size:.0f}_w{separation:.0f}"
            )
            # The gate is always asked the same question: are holdout points at
            # least `separation` metres from every training point? An unbuffered
            # partition is judged at the SAME separation it would have had to
            # meet, which is what makes it a control rather than a different
            # experiment.
            judged_at = separation if separation > 0 else separations[0]
            for label in (SPLIT_TEST, SPLIT_VAL):
                report = measure_gate(
                    x, y, block_i, block_j, split, label,
                    criterion_separation_m=judged_at,
                    block_size_m=block_size,
                    partition=partition,
                )
                rows.append(report.to_dict())

    # the positive control: geometry ignored entirely
    control_blocks = SplitConfig(block_size_m=BLOCK_SIZES_M[0], buffer_m=0.0, seed=args.seed)
    cbi, cbj = assign_blocks(x, y, control_blocks)
    rnd = random_split(len(pid), seed=args.seed,
                       train_fraction=args.train_fraction, val_fraction=args.val_fraction)
    for label in (SPLIT_TEST, SPLIT_VAL):
        rows.append(
            measure_gate(
                x, y, cbi, cbj, rnd, label,
                criterion_separation_m=separations[0],
                block_size_m=BLOCK_SIZES_M[0],
                partition="random",
            ).to_dict()
        )

    # the declared baseline, on the random control and on every blocked partition
    baselines = []
    b = nearest_neighbour_baseline(x, y, z, rnd, SPLIT_TEST, "random")
    if b is not None:
        baselines.append(b.to_dict())
    for block_size in BLOCK_SIZES_M:
        base = SplitConfig(block_size_m=block_size, buffer_m=0.0, seed=args.seed,
                           train_fraction=args.train_fraction, val_fraction=args.val_fraction)
        bi, bj = assign_blocks(x, y, base)
        pre = assign_block_splits(bi, bj, base)
        for separation in (0.0,) + separations:
            config = SplitConfig(block_size_m=block_size, buffer_m=separation, seed=args.seed,
                                 train_fraction=args.train_fraction, val_fraction=args.val_fraction)
            split = pre.copy() if separation == 0.0 else apply_buffer(x, y, pre, config)
            name = (f"blocked_b{block_size:.0f}_unbuffered" if separation == 0.0
                    else f"blocked_b{block_size:.0f}_w{separation:.0f}")
            r = nearest_neighbour_baseline(x, y, z, split, SPLIT_TEST, name)
            if r is not None:
                baselines.append(r.to_dict())

    payload = {
        "schema_version": "c1_split_geometry_sweep_v1",
        "dataset": args.dataset,
        "rows": int(len(frame)),
        "seed": args.seed,
        "train_fraction": args.train_fraction,
        "val_fraction": args.val_fraction,
        "separation_ladder": ladder,
        "block_sizes_m": list(BLOCK_SIZES_M),
        "coordinate_label_ambiguity": coordinate_label_ambiguity(x, y, z),
        "gate_reports": rows,
        "nearest_neighbour_baselines": baselines,
        "criterion": (
            "a partition passes at separation s when every surviving holdout "
            "property lies at least s metres from every training property; "
            ">= and not >"
        ),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())