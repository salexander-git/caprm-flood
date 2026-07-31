"""C4 item 1. Surrogate inference throughput and latency.

    python python/scripts/benchmark_c4_inference.py --blas-threads 8 `
        --cpu-name "AMD Ryzen 7 7700X 8-Core Processor" --physical-cores 8

Reads only generated artifacts and modifies none of them. Writes one new file,
``outputs/validation/c4_inference_benchmark.json``, which is NOT
``water_cpp_benchmark_summary.json`` and shares no schema with it.

No randomness is used anywhere in this section, so there is no seed to record.

**Why every import that touches numpy lives inside main().** OpenBLAS reads
``OPENBLAS_NUM_THREADS`` once, when the shared library loads, which happens on
the first numpy import in the process. Setting the variable afterwards changes
nothing and produces a manifest that records a thread count the run did not
use. The preamble below therefore fixes the thread environment before any
numpy-importing import executes, and ``tests/test_c4_benchmark.py`` asserts
that ordering from the source rather than trusting this comment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

THREAD_VARIABLES = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure C2 surrogate inference cost over the countywide coordinate set."
    )
    parser.add_argument(
        "--blas-threads",
        type=int,
        required=True,
        help=(
            "Pinned BLAS thread count, written to the environment before numpy "
            "loads and recorded in the manifest. Run once at the physical core "
            "count and once at 1; a throughput figure without this is not "
            "comparable to anything."
        ),
    )
    parser.add_argument("--cpu-name", default=None, help="Operator-declared, recorded verbatim.")
    parser.add_argument("--physical-cores", type=int, default=None, help="Operator-declared.")
    parser.add_argument(
        "--dataset", default="outputs/training/supervised_dataset_v2.csv"
    )
    parser.add_argument(
        "--surrogate-manifest", default="outputs/validation/c2_surrogate_manifest.json"
    )
    parser.add_argument(
        "--batch-sizes",
        nargs="+",
        default=["1", "64", "4096", "65536", "full"],
        help="Integers and/or the literal 'full' for one batch over every row.",
    )
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--split-batch",
        default="65536",
        help="Batch size for the Fourier/MLP split. Integer or 'full'.",
    )
    parser.add_argument(
        "--model-label",
        default=None,
        help=(
            "Which of the 30 verified models to time. Defaults to the first in "
            "manifest order. Architecture is asserted identical across all 30, "
            "which is what licenses timing one of them."
        ),
    )
    parser.add_argument("--output", default="outputs/validation/c4_inference_benchmark.json")
    return parser


def _parse_batch(token: str) -> int | None:
    return None if token.strip().lower() == "full" else int(token)


def main() -> int:
    args = build_parser().parse_args()

    if args.blas_threads < 1:
        raise SystemExit("--blas-threads must be at least 1")

    # PIN BEFORE NUMPY LOADS. Nothing above this line may import numpy.
    for variable in THREAD_VARIABLES:
        os.environ[variable] = str(args.blas_threads)

    sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

    import datetime as dt

    import numpy as np
    import pandas as pd

    from caprm import c4_benchmark as c4

    dataset_path = REPOSITORY_ROOT / args.dataset
    manifest_path = REPOSITORY_ROOT / args.surrogate_manifest
    output_path = REPOSITORY_ROOT / args.output

    surrogate_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_dataset_sha = surrogate_manifest["inputs"]["dataset_sha256"]
    observed_dataset_sha = c4.sha256_file(dataset_path)
    if observed_dataset_sha != expected_dataset_sha:
        raise SystemExit(
            "supervised dataset does not match the digest C2 trained against:\n"
            f"  expected {expected_dataset_sha}\n  observed {observed_dataset_sha}"
        )

    frame = pd.read_csv(dataset_path, dtype={"property_id": str}, float_precision="round_trip")
    for column in ("x", "y"):
        if column not in frame.columns:
            raise SystemExit(f"dataset is missing the {column!r} column")
    x = frame["x"].to_numpy(dtype=np.float64)
    y = frame["y"].to_numpy(dtype=np.float64)

    print(f"verifying {args.surrogate_manifest} against the model files on disk ...")
    records, models = c4.verify_models(manifest_path, REPOSITORY_ROOT)
    architecture = c4.assert_identical_architecture(records)
    print(f"  {len(records)} models verified, architecture identical")

    label = args.model_label or records[0].label
    if label not in models:
        raise SystemExit(f"--model-label {label!r} is not one of the verified models")
    model = models[label]

    batch_sizes = [_parse_batch(token) for token in args.batch_sizes]
    print(f"timing {len(batch_sizes)} batch sizes over {len(x):,} properties ...")
    sweep, predictions = c4.batch_sweep(
        model, x, y, batch_sizes=batch_sizes, n_warmup=args.warmups, n_repeat=args.repeats
    )
    for row in sweep:
        print(
            f"  batch {row['batch_label']:>7}  "
            f"{row['properties_per_second_median']:>14,.0f} prop/s  "
            f"{row['microseconds_per_property_median']:>8.3f} us/prop  "
            f"spread {row['timing']['relative_spread']:.3f}"
        )

    reference = "full" if any(b is None for b in batch_sizes) else sweep[-1]["batch_label"]
    agreement = c4.agreement_report(predictions, reference_label=reference)
    print(
        f"  batch agreement: max deviation {agreement['max_abs_deviation_index_points']:.3e} "
        f"index points against a tolerance of {agreement['tolerance_index_points']:.3e}"
    )

    print("splitting Fourier encoding from the MLP forward pass ...")
    split = c4.stage_split(
        model,
        x,
        y,
        batch_size=_parse_batch(args.split_batch),
        n_warmup=args.warmups,
        n_repeat=args.repeats,
    )
    print(
        f"  fourier {split['fourier_microseconds_per_property']:.3f} us/prop  "
        f"mlp {split['mlp_microseconds_per_property']:.3f} us/prop  "
        f"ratio {split['fourier_over_mlp_ratio']:.2f}x  "
        f"(parts exceed the whole by "
        f"{split['parts_minus_whole_fraction_of_whole']:+.1%}; not a decomposition)"
    )

    one = c4.model_size_record(model, records[0].path)
    payload = {
        "task": "C4_item1_surrogate_inference_cost",
        "schema_version": "c4_inference_v1",
        "tool_version": c4.TOOL_VERSION,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "randomness": "none used in this section; no seed to record",
        "environment": c4.environment_record(
            cpu_name=args.cpu_name, physical_cores=args.physical_cores
        ),
        "inputs": {
            "dataset": args.dataset,
            "dataset_sha256": observed_dataset_sha,
            "n_properties": int(len(frame)),
            "surrogate_manifest": args.surrogate_manifest,
            "surrogate_manifest_sha256": c4.sha256_file(manifest_path),
            "models_verified": len(records),
            "timed_model_label": label,
        },
        "architecture": architecture,
        "batch_sweep": sweep,
        "batch_agreement": agreement,
        "stage_split": split,
        "model_size": {
            "one_model": one,
            "model_set": {
                "n_models": len(records),
                "why_thirty": "the C2 protocol fits one model per fold per seed",
                "disk_bytes_total": sum(r.disk_bytes for r in records),
                "memory_bytes_total": sum(r.memory_bytes for r in records),
            },
            "models": [record.to_dict() for record in records],
        },
        "cannot_produce": (
            "The surrogate emits one scalar. It does not produce the four "
            "components, their provenance, or the source-feature identifiers "
            "the pipeline produces, and no ratio in this file should be read "
            "without that sentence beside it."
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(f"wrote {output_path}")

    if not agreement["all_within_tolerance"]:
        # The artifact is written first on purpose: the evidence for a breach
        # must survive the failure that reports it.
        print(
            "BATCH AGREEMENT BREACHED. This is a finding about float32 GEMM at "
            "these shapes, not a tolerance to widen. See batch_agreement.per_batch.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())