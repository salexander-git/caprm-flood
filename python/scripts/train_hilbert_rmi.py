"""Train the two-stage recursive model index over the B3b Hilbert key array.

Sweeps second-stage model counts, verifies each candidate EXHAUSTIVELY over
every key, applies a selection rule declared in ``caprm.rmi`` before any model
is fitted, and writes the selected model plus a provenance manifest.

Python trains; C++ (B5) infers. Nothing here touches the query path: the model
supplies a start position and B3b proved that seam correctness-neutral, so a
bad model costs time and can never cost an answer.

The key array must come from ``water_distance_hilbert --dump-keys``, not from
a Python reconstruction. A reconstruction's checksum would attest to what
Python built, which is not what the index holds, and the two can differ by a
floating-point ULP in the segment split with no way to tell from the outside.

Example (PowerShell, from the repository root)::

    .\\.venv\\Scripts\\python.exe python\\scripts\\train_hilbert_rmi.py `
        --keys outputs/cpp_input/water_hilbert_keys_countywide.bin `
        --index-manifest outputs/validation/water_hilbert_countywide_manifest.json `
        --model-output models/water_hilbert_rmi.bin `
        --manifest-output outputs/validation/water_hilbert_rmi_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))

from caprm.rmi import (  # noqa: E402
    CONTROL_MAX_SEED_PROBES,
    CONTROL_MEAN_SEED_PROBES,
    MODEL_FORMAT_VERSION,
    POSITION_CONVENTION,
    SEED_WINDOW_ENTRIES,
    SELECTION_MAX_MEAN_LAST_MILE_PROBES,
    SELECTION_MAX_MODEL_BYTES,
    deserialize,
    equidepth_reference,
    fit_rmi,
    load_key_array,
    lower_bound_targets,
    probe_records,
    serialize,
    spot_check_gap_bound,
    verify_exhaustive,
)

DEFAULT_LEAF_COUNTS = "256,1024,4096,16384,65536,131072"
DEFAULT_SPOT_CHECKS = 2_000_000
DEFAULT_SPOT_CHECK_SEED = 20260728

# Copied from the B3b index manifest rather than recomputed, and asserted
# against the key array. If the index is rebuilt with different geometry these
# stop matching and training refuses to run.
INHERITED_MANIFEST_FIELDS = (
    "algorithm",
    "distance_crs",
    "hilbert_order_bits_per_axis",
    "normalization_min_x",
    "normalization_min_y",
    "normalization_scale_x_cells_per_m",
    "normalization_scale_y_cells_per_m",
    "max_segment_length_cap_m",
    "max_split_segment_length_m",
    "inflation_half_m",
    "index_entries",
    "key_array_bytes",
    "distinct_cells_at_order",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keys", required=True, type=Path)
    parser.add_argument("--index-manifest", required=True, type=Path)
    parser.add_argument("--model-output", required=True, type=Path)
    parser.add_argument("--manifest-output", required=True, type=Path)
    parser.add_argument("--leaf-counts", default=DEFAULT_LEAF_COUNTS)
    parser.add_argument(
        "--expect-index-manifest-sha256",
        default=None,
        help=(
            "Refuse to train unless the index manifest hashes to this value. "
            "Pins the model to one index BUILD rather than to any index that "
            "happens to have the same entry count."
        ),
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=0,
        help=(
            "Recorded in the model manifest for contract compliance. Training "
            "is closed-form least squares and consults no RNG; the seed exists "
            "so a future stochastic variant is reproducible, not because this "
            "one is stochastic."
        ),
    )
    parser.add_argument(
        "--gap-bound-spot-checks", type=int, default=DEFAULT_SPOT_CHECKS
    )
    parser.add_argument(
        "--gap-bound-seed", type=int, default=DEFAULT_SPOT_CHECK_SEED
    )
    parser.add_argument(
        "--skip-equidepth-reference",
        action="store_true",
        help="Omit the perfect-router diagnostic from the sweep.",
    )
    return parser.parse_args()


def check_against_index_manifest(
    manifest: dict, keys: np.ndarray, keys_path: Path
) -> None:
    entries = manifest.get("index_entries")
    if entries is None:
        raise ValueError(
            f"{keys_path}: index manifest has no index_entries field."
        )
    if int(entries) != int(keys.size):
        raise ValueError(
            f"Key array holds {keys.size} keys but the B3b index manifest "
            f"records index_entries = {entries}. The model would be trained "
            "on an array the index does not contain."
        )
    key_bytes = manifest.get("key_array_bytes")
    if key_bytes is not None and int(key_bytes) != int(keys.nbytes):
        raise ValueError(
            f"Key array is {keys.nbytes} bytes; manifest records "
            f"key_array_bytes = {key_bytes}."
        )
    distinct = manifest.get("distinct_cells_at_order")
    if distinct is not None:
        measured = int(np.unique(keys).size)
        if measured != int(distinct):
            raise ValueError(
                f"Key array has {measured} distinct keys; the B3b manifest "
                f"records {distinct} distinct cells at order. The Hilbert map "
                "is a bijection on cells, so these must agree."
            )


def duplicate_report(keys: np.ndarray, targets: np.ndarray) -> dict:
    distinct = int(np.unique(keys).size)
    run_start = targets == np.arange(keys.size, dtype=np.int64)
    run_lengths = np.diff(np.append(np.flatnonzero(run_start), keys.size))
    return {
        "keys": int(keys.size),
        "distinct_keys": distinct,
        "duplicate_entries": int(keys.size) - distinct,
        "longest_run": int(run_lengths.max()),
        "runs_longer_than_one": int((run_lengths > 1).sum()),
        "position_convention": POSITION_CONVENTION,
    }


def main() -> int:
    arguments = parse_arguments()
    leaf_counts = [
        int(token) for token in arguments.leaf_counts.split(",") if token.strip()
    ]
    if not leaf_counts:
        print("Error: --leaf-counts is empty.", file=sys.stderr)
        return 1

    index_manifest_sha256 = sha256_file(arguments.index_manifest)
    if (
        arguments.expect_index_manifest_sha256
        and arguments.expect_index_manifest_sha256 != index_manifest_sha256
    ):
        print(
            "Error: index manifest hashes to "
            f"{index_manifest_sha256}, not the expected "
            f"{arguments.expect_index_manifest_sha256}.",
            file=sys.stderr,
        )
        return 1

    keys, keys_sha256 = load_key_array(arguments.keys)
    index_manifest = json.loads(
        arguments.index_manifest.read_text(encoding="utf-8")
    )
    check_against_index_manifest(index_manifest, keys, arguments.keys)

    targets = lower_bound_targets(keys)
    duplicates = duplicate_report(keys, targets)

    print(f"Keys: {keys.size} from {display_path(arguments.keys)}")
    print(f"  key array sha256      {keys_sha256}")
    print(f"  index manifest sha256 {index_manifest_sha256}")
    print(f"  distinct              {duplicates['distinct_keys']}")
    print(f"  duplicate rows        {duplicates['duplicate_entries']}")
    print(f"  longest run           {duplicates['longest_run']}")
    print(f"  convention            {POSITION_CONVENTION}")
    print(
        f"Control to beat: {CONTROL_MEAN_SEED_PROBES} mean probes, "
        f"{CONTROL_MAX_SEED_PROBES} max"
    )
    print(
        "Selection rule (declared before training): lowest mean last-mile "
        f"probes among leaf counts within {SELECTION_MAX_MODEL_BYTES} bytes; "
        f"target is <= {SELECTION_MAX_MEAN_LAST_MILE_PROBES}."
    )
    print()

    sweep = []
    models = {}
    print(
        f"{'leaves':>8} {'occupied':>9} {'maxload':>9} {'max_err':>9} "
        f"{'mean|err|':>11} {'lastmile':>9} {'in64':>8} {'gap_err':>9} "
        f"{'bytes':>10}  equidepth"
    )
    for count in leaf_counts:
        model = fit_rmi(keys, targets, count, keys_sha256)
        reloaded = deserialize(serialize(model))
        report = verify_exhaustive(reloaded, keys, targets)
        if not (
            report["bound_holds_asymmetric"]
            and report["bound_holds_symmetric"]
            and report["gap_bound_covers_stored_keys"]
        ):
            print(
                "Error: a recorded bound does not contain the true position "
                f"at {count} leaves.",
                file=sys.stderr,
            )
            return 1
        if not arguments.skip_equidepth_reference:
            report["equidepth_reference"] = equidepth_reference(
                keys, targets, count
            )
        sweep.append(report)
        models[count] = model
        equi = report.get("equidepth_reference")
        equi_text = (
            f"err {equi['max_error']}, probes "
            f"{equi['mean_last_mile_probes']:.3f}"
            if equi
            else "-"
        )
        print(
            f"{count:>8} {report['leaves_occupied']:>9} "
            f"{report['leaf_load_max']:>9} "
            f"{report['per_model_max_error']['max']:>9} "
            f"{report['per_key_absolute_error']['mean']:>11.2f} "
            f"{report['last_mile_probes']['mean']:>9.3f} "
            f"{report['fraction_within_seed_window'] * 100:>7.2f}% "
            f"{report['domain_bound']['per_model_max_error']['max']:>9} "
            f"{report['model_bytes']:>10}  {equi_text}"
        )

    affordable = [
        report
        for report in sweep
        if report["model_bytes"] <= SELECTION_MAX_MODEL_BYTES
    ]
    if not affordable:
        print(
            "Error: every swept leaf count exceeds the declared "
            f"{SELECTION_MAX_MODEL_BYTES}-byte size cap.",
            file=sys.stderr,
        )
        return 1
    selected = min(
        affordable,
        key=lambda report: (
            report["last_mile_probes"]["mean"],
            report["n_leaves"],
        ),
    )
    met = (
        selected["last_mile_probes"]["mean"]
        <= SELECTION_MAX_MEAN_LAST_MILE_PROBES
    )
    verdict = "target_met" if met else "target_not_met"
    rationale = (
        f"{selected['n_leaves']} second-stage models minimise mean last-mile "
        f"probes ({selected['last_mile_probes']['mean']:.3f}) among swept "
        f"configurations within the {SELECTION_MAX_MODEL_BYTES}-byte cap. "
        + (
            "That clears the declared target of "
            f"{SELECTION_MAX_MEAN_LAST_MILE_PROBES}."
            if met
            else "No swept configuration reached the declared target of "
            f"{SELECTION_MAX_MEAN_LAST_MILE_PROBES}; reported as a measured "
            "shortfall rather than relaxed after the fact (Nucleus 18.12, "
            "18.18)."
        )
    )

    chosen = models[selected["n_leaves"]]
    payload = serialize(chosen)

    # Determinism: refit from scratch and require byte equality. Training is
    # closed form, so this is a check that no incidental ordering or RNG has
    # crept in, not a hope.
    refit = serialize(fit_rmi(keys, targets, selected["n_leaves"], keys_sha256))
    if refit != payload:
        print("Error: retraining produced different bytes.", file=sys.stderr)
        return 1

    arguments.model_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.model_output.write_bytes(payload)
    model_sha256 = sha256_file(arguments.model_output)

    # The gate that matters: verify the artifact as it now exists on disk.
    on_disk = deserialize(arguments.model_output.read_bytes())
    final = verify_exhaustive(on_disk, keys, targets)
    if not (
        final["bound_holds_asymmetric"]
        and final["bound_holds_symmetric"]
        and final["gap_bound_covers_stored_keys"]
    ):
        print(
            "Error: the written model does not satisfy its own bound.",
            file=sys.stderr,
        )
        return 1

    spot_check = spot_check_gap_bound(
        on_disk, keys, arguments.gap_bound_spot_checks, arguments.gap_bound_seed
    )
    if not spot_check["holds"]:
        print(
            f"Error: the domain bound failed on {spot_check['violations']} of "
            f"{spot_check['samples']} random keys. The candidate-set argument "
            "in domain_candidate_keys is incomplete.",
            file=sys.stderr,
        )
        return 1

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "chunk": "B4",
        "model_format_version": MODEL_FORMAT_VERSION,
        "architecture": "two_stage_rmi_linear_linear",
        "trainer": "numpy_least_squares",
        "random_seed": arguments.random_seed,
        "training_is_deterministic": True,
        "determinism_check": "refit_bytes_identical",
        "pinned_index": {
            "index_manifest": display_path(arguments.index_manifest),
            "index_manifest_sha256": index_manifest_sha256,
            "key_array": display_path(arguments.keys),
            "key_array_sha256": keys_sha256,
            "key_array_producer": "water_distance_hilbert --dump-keys",
            "note": (
                "The model is valid only for the index build these two "
                "digests describe. A key array reconstructed in Python is "
                "not an acceptable substitute: its checksum would attest to "
                "what Python built, not to what the index holds."
            ),
        },
        "inherited_from_index_manifest": {
            field: index_manifest[field]
            for field in INHERITED_MANIFEST_FIELDS
            if field in index_manifest
        },
        "training_array": duplicates,
        "float_contract": {
            "normalization": (
                "(double(key) - double(key_min)) * "
                "(1.0 / (double(key_max) - double(key_min)))"
            ),
            "key_min": int(chosen.key_min),
            "key_max": int(chosen.key_max),
            "prediction_rounding": "clamp_to_[0, n_keys-1]_then_floor",
            "uint64_to_double": {
                "assumption": "round_to_nearest_even",
                "numpy": "guaranteed",
                "cpp": (
                    "NOT guaranteed. [conv.fpint] permits either adjacent "
                    "representable value when the integer is not exactly "
                    "representable in double. x86-64/SSE2 rounds to nearest "
                    "under the default MXCSR mode, which is the target every "
                    "measurement in this project was taken on."
                ),
                "how_b5_checks_it": (
                    "Assert the probe records below at model load rather than "
                    "inheriting the assumption."
                ),
            },
        },
        "probe_records": probe_records(on_disk, keys),
        "selection": {
            "declared_max_mean_last_mile_probes": (
                SELECTION_MAX_MEAN_LAST_MILE_PROBES
            ),
            "declared_max_model_bytes": SELECTION_MAX_MODEL_BYTES,
            "leaf_counts_swept": leaf_counts,
            "selected_n_leaves": selected["n_leaves"],
            "verdict": verdict,
            "rationale": rationale,
        },
        "sweep": sweep,
        "selected_model": final,
        "gap_bound_spot_check": spot_check,
        "bound_scope": {
            "stored_key_bound": (
                "err_min / err_max. Exhaustive over every key in the training "
                f"array under the {POSITION_CONVENTION} convention. This is "
                "the acceptance criterion and the academic deliverable."
            ),
            "domain_bound": (
                "gap_err_min / gap_err_max. Measured over the whole 64-bit "
                "key domain via the candidate set in domain_candidate_keys "
                "and re-tested on random keys. It covers query keys, which "
                "are property-point keys and are not index keys."
            ),
            "neither_gates_correctness": (
                "Nucleus 18.22: the seed seam is correctness-neutral and the "
                "current query path uses a fixed "
                f"+/-{SEED_WINDOW_ENTRIES} window with no bound at all. B5 "
                "should not build machinery as though these bounds gate "
                "anything."
            ),
        },
        "outputs": [
            {
                "path": display_path(arguments.model_output),
                "sha256": model_sha256,
                "bytes": len(payload),
            }
        ],
    }

    arguments.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.manifest_output.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print()
    print(f"Selected {selected['n_leaves']} second-stage models ({verdict}).")
    print(
        f"  max error per model      "
        f"{final['per_model_max_error']['max']}"
    )
    print(
        f"  mean |error|             "
        f"{final['per_key_absolute_error']['mean']:.3f}"
    )
    print(
        f"  mean last-mile probes    "
        f"{final['last_mile_probes']['mean']:.3f}  "
        f"(control {CONTROL_MEAN_SEED_PROBES:.4f})"
    )
    print(
        f"  within the {SEED_WINDOW_ENTRIES}-entry seed window  "
        f"{final['fraction_within_seed_window'] * 100:.3f}%"
    )
    print(
        f"  domain bound, max per model  "
        f"{final['domain_bound']['per_model_max_error']['max']}  "
        f"({final['domain_bound']['leaves_reachable']} leaves reachable, "
        f"{final['domain_bound']['leaves_unreachable']} not)"
    )
    print(
        f"  domain spot check        {spot_check['samples']} random keys, "
        f"{spot_check['violations']} violations"
    )
    print(f"  model bytes              {len(payload)}")
    print(f"  model sha256             {model_sha256}")
    print(f"Model    -> {display_path(arguments.model_output)}")
    print(f"Manifest -> {display_path(arguments.manifest_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())