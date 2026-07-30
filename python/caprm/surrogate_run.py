"""One protocol, run over whichever partition it is handed.

C2's headline is not a number, it is a CONTRAST: the same model, the same
optimizer, the same stopping rule and the same aggregation, under a blocked
partition and under a random one. That contrast is only evidence if nothing
differs between the two runs except the partition, so the protocol lives here
once and both partitions are passed through it — the rule ``split_gate`` states
for the leakage gate, applied to training.

Aggregation
-----------
A seed's headline is computed over the UNION of its folds' test sets, with each
property predicted at most once, exactly as
``caprm.spatial_kfold._aggregate_baseline`` computed the declared floor. An
average of per-fold RMSEs would weight a 4,000-property fold like a
40,000-property one and would not be the same quantity the floor is stated in.

Comparison against the floor
----------------------------
Two statistics are reported and they are not the same claim:

``beats_floor_per_seed``   the surrogate's aggregate beats the floor's aggregate
                          at the SAME seed, for every seed
``ranges_are_disjoint``    the worst surrogate seed beats the best floor seed

The second is the one C2 may call beating the floor. Nucleus 18.32 is explicit
that the comparison which survives a seed-dependent partition is between
non-overlapping ranges, not between two point estimates, and the weaker
statistic is reported beside it rather than in place of it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from caprm.surrogate import (
    CoordinateNormalizer,
    FourierConfig,
    MLPConfig,
    TrainConfig,
    TrainedModel,
    load_model,
    regression_metrics,
    save_model,
    train_surrogate,
)
from caprm.surrogate_data import EvaluationSplit, FoldPredictions, PartitionInputs


@dataclass(frozen=True)
class RunConfig:
    """The knobs a run is allowed to have, all recorded in the manifest."""

    fourier: FourierConfig = FourierConfig()
    mlp: MLPConfig = MLPConfig()
    train: TrainConfig = TrainConfig()

    def to_dict(self) -> dict[str, Any]:
        return {
            "fourier": self.fourier.to_dict(),
            "mlp": self.mlp.to_dict(),
            "train": self.train.to_dict(),
        }


def fit_split(
    inputs: PartitionInputs,
    split: EvaluationSplit,
    normalizer: CoordinateNormalizer,
    config: RunConfig,
    provenance: dict[str, Any] | None = None,
) -> tuple[TrainedModel, np.ndarray, dict[str, Any]]:
    """Fit one (train, val, test) triple and score its test rows.

    The seed handed to :func:`caprm.surrogate.train_surrogate` is derived from
    the SPLIT's identity, so fold 3 of seed 20260725 always initialises the same
    way and no two folds share an initialisation by accident.
    """
    if split.test_index.size == 0:
        raise ValueError(f"{split.label} has no surviving test rows")

    record_provenance = dict(provenance or {})
    record_provenance.update(
        {
            "partition": split.partition,
            "split_seed": split.seed,
            "fold": split.fold,
            "counts": split.counts(),
        }
    )
    model = train_surrogate(
        inputs.x,
        inputs.y,
        inputs.target,
        split.train_index,
        split.val_index,
        normalizer,
        fourier=config.fourier,
        mlp=config.mlp,
        train_config=config.train,
        seed=_split_seed(split),
        provenance=record_provenance,
    )
    predicted = model.predict(
        inputs.x[split.test_index], inputs.y[split.test_index]
    )
    metrics = regression_metrics(predicted, inputs.target[split.test_index])
    fold_record = {
        "label": split.label,
        "partition": split.partition,
        "seed": split.seed,
        "fold": split.fold,
        "counts": split.counts(),
        "epochs_run": model.provenance["epochs_run"],
        "best_epoch": model.provenance["best_epoch"],
        "early_stopped": model.provenance["early_stopped"],
        "best_val_rmse_label_units": model.provenance["best_val_rmse_label_units"],
        "test": metrics,
        "weights_sha256": model.weights_sha256(),
        "seeds": dict(model.seeds),
    }
    return model, predicted, fold_record


def _split_seed(split: EvaluationSplit) -> int:
    """A stable integer identity for a split, used to seed its fit."""
    key = f"{split.partition}:{split.seed}:{split.fold}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big") >> 1


def run_seed(
    inputs: PartitionInputs,
    splits: Sequence[EvaluationSplit],
    normalizer: CoordinateNormalizer,
    config: RunConfig,
    model_dir: str | Path | None = None,
    provenance: dict[str, Any] | None = None,
    verify_reload: bool = True,
) -> dict[str, Any]:
    """Fit every fold of one seed, aggregate over the union of its test sets."""
    if not splits:
        raise ValueError("no splits to run")
    predictions = FoldPredictions.empty(inputs.n_properties)
    constant = FoldPredictions.empty(inputs.n_properties)
    fold_records: list[dict[str, Any]] = []
    fold_of_property = np.full(inputs.n_properties, -1, dtype=np.int64)

    for split in splits:
        model, predicted, record = fit_split(
            inputs, split, normalizer, config, provenance
        )
        predictions.add(split.test_index, predicted)
        # Rung 0, scored on the identical rows through the identical
        # aggregation: predict this fold's own TRAINING mean. It uses no label
        # the model was not given, so it is a legitimate predictor, and the C1
        # floor's negative R^2 means it is expected to beat that floor. Scoring
        # it here makes that comparison a measurement in the artifact rather
        # than an argument in a document.
        train_mean = float(inputs.target[split.train_index].mean())
        constant.add(
            split.test_index, np.full(split.test_index.size, train_mean)
        )
        record["train_mean"] = train_mean
        fold_of_property[split.test_index] = split.fold

        if model_dir is not None:
            path = Path(model_dir) / f"c2_surrogate_{split.label}.npz"
            save_model(model, path)
            record["model_path"] = str(path)
            if verify_reload:
                reloaded = load_model(path)
                # B4's standard: the digest is checked on the artifact as
                # reloaded, not on the object that was in memory when it was
                # written. A model that cannot be read back is not an artifact.
                record["weights_sha256_after_reload"] = reloaded.weights_sha256()
                if record["weights_sha256_after_reload"] != record["weights_sha256"]:
                    raise RuntimeError(
                        f"{split.label}: the reloaded model does not reproduce "
                        "its own weight checksum"
                    )
        fold_records.append(record)

    tested = predictions.tested
    aggregate = regression_metrics(
        predictions.predicted[tested], inputs.target[tested]
    )
    constant_aggregate = regression_metrics(
        constant.predicted[tested], inputs.target[tested]
    )
    digest = hashlib.sha256()
    for record in fold_records:
        digest.update(record["weights_sha256"].encode("utf-8"))

    return {
        "partition": splits[0].partition,
        "seed": int(splits[0].seed),
        "n_folds_run": len(fold_records),
        "folds": fold_records,
        "aggregate": aggregate,
        "constant_aggregate": constant_aggregate,
        "test_coverage_fraction": predictions.coverage_fraction(),
        "seed_weights_sha256": digest.hexdigest(),
        "_predictions": predictions.predicted,
        "_tested": tested,
        "_fold_of_property": fold_of_property,
    }


def summarise_partition(
    seed_results: Sequence[dict[str, Any]], key: str = "aggregate"
) -> dict[str, Any]:
    """Range across seeds. A single-seed figure is a diagnostic (Nucleus 18.32).

    ``key`` selects which rung is summarised, so the surrogate and the constant
    baseline are reduced by the same code rather than by two functions that
    could drift.
    """
    if not seed_results:
        raise ValueError("no seed results to summarise")
    rmse = [float(r[key]["rmse"]) for r in seed_results]
    r2 = [float(r[key]["r2"]) for r in seed_results]
    coverage = [float(r["test_coverage_fraction"]) for r in seed_results]
    return {
        "n_seeds": len(seed_results),
        "seeds": [int(r["seed"]) for r in seed_results],
        "rmse_min": min(rmse),
        "rmse_max": max(rmse),
        "rmse_range": max(rmse) - min(rmse),
        "r2_min": min(r2),
        "r2_max": max(r2),
        "coverage_min": min(coverage),
        "coverage_max": max(coverage),
        "per_seed": {
            str(r["seed"]): {
                "rmse": float(r[key]["rmse"]),
                "r2": float(r[key]["r2"]),
                "n": int(r[key]["n"]),
                "coverage": float(r["test_coverage_fraction"]),
                "seed_weights_sha256": r["seed_weights_sha256"],
            }
            for r in seed_results
        },
    }


def compare_to_floor(
    summary: dict[str, Any],
    floor: dict[str, Any],
    constant_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Judge the surrogate against the floor C1 declared before it existed."""
    blocked = floor["blocked_kfold"]
    per_seed = {}
    for seed, values in summary["per_seed"].items():
        declared = blocked["per_seed"].get(seed)
        if declared is None:
            continue
        per_seed[seed] = {
            "surrogate_rmse": values["rmse"],
            "floor_rmse": declared["rmse"],
            "surrogate_r2": values["r2"],
            "floor_r2": declared["r2"],
            "surrogate_beats_floor": bool(values["rmse"] < declared["rmse"]),
        }
    beats_every_seed = bool(per_seed) and all(
        v["surrogate_beats_floor"] for v in per_seed.values()
    )
    disjoint = bool(summary["rmse_max"] < blocked["rmse_min"])
    rungs = {
        "rung_0_constant_train_mean": (
            [constant_summary["rmse_min"], constant_summary["rmse_max"]]
            if constant_summary
            else None
        ),
        "rung_1_nearest_training_neighbour": [
            blocked["rmse_min"],
            blocked["rmse_max"],
        ],
        "rung_2_surrogate": [summary["rmse_min"], summary["rmse_max"]],
    }
    constant_block = None
    if constant_summary:
        constant_block = {
            "rmse_range": [constant_summary["rmse_min"], constant_summary["rmse_max"]],
            "r2_range": [constant_summary["r2_min"], constant_summary["r2_max"]],
            "constant_beats_declared_floor_as_a_range": bool(
                constant_summary["rmse_max"] < blocked["rmse_min"]
            ),
            "surrogate_beats_constant_as_a_range": bool(
                summary["rmse_max"] < constant_summary["rmse_min"]
            ),
            "why_this_rung_exists": (
                "The declared floor's R^2 is negative on every seed, so the "
                "floor is beaten by predicting a constant. Clearing it is "
                "therefore not by itself evidence that the surrogate learned "
                "spatial structure, and the rung that shows this is reported "
                "beside the floor rather than left for a reader to derive."
            ),
        }
    return {
        "floor_source": floor["source"],
        "rmse_rungs": rungs,
        "constant_baseline": constant_block,
        "floor_predictor": floor["predictor"],
        "per_seed": per_seed,
        "beats_floor_per_seed": beats_every_seed,
        "ranges_are_disjoint": disjoint,
        "surrogate_rmse_range": [summary["rmse_min"], summary["rmse_max"]],
        "floor_rmse_range": [blocked["rmse_min"], blocked["rmse_max"]],
        "verdict": (
            "beats the declared floor: the ranges do not overlap"
            if disjoint
            else (
                "does not beat the declared floor as a range; it beats it at "
                "every seed individually, which Nucleus 18.32 does not accept "
                "as beating it"
                if beats_every_seed
                else "does not beat the declared floor"
            )
        ),
    }


def memorization_gap(
    blocked: dict[str, Any], random_control: dict[str, Any], floor: dict[str, Any]
) -> dict[str, Any]:
    """What the blocked partition bought, in the units the claim is made in.

    Published beside the same gap for the nearest-neighbour predictor, because
    the interesting quantity is not that the random split flatters a model but
    that it flatters the trivial predictor by about as much.
    """
    return {
        "surrogate": {
            "blocked_rmse_range": [blocked["rmse_min"], blocked["rmse_max"]],
            "random_rmse_range": [random_control["rmse_min"], random_control["rmse_max"]],
            "blocked_r2_range": [blocked["r2_min"], blocked["r2_max"]],
            "random_r2_range": [random_control["r2_min"], random_control["r2_max"]],
            "r2_gap_min": float(random_control["r2_min"] - blocked["r2_max"]),
            "rmse_ratio_max": float(blocked["rmse_max"] / random_control["rmse_min"])
            if random_control["rmse_min"] > 0
            else float("nan"),
        },
        "nearest_training_neighbour": {
            "blocked_rmse_range": [
                floor["blocked_kfold"]["rmse_min"],
                floor["blocked_kfold"]["rmse_max"],
            ],
            "random_rmse": floor["random_control"]["rmse"],
            "blocked_r2_range": [
                floor["blocked_kfold"]["r2_min"],
                floor["blocked_kfold"]["r2_max"],
            ],
            "random_r2": floor["random_control"]["r2"],
        },
        "interpretation": (
            "The random control is the partition C1 rejected. Both rows are the "
            "same predictor evaluated two ways, so the difference between the "
            "columns is the size of the error a random split would have "
            "introduced, not a property of either model."
        ),
    }
