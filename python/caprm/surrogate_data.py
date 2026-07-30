"""Consume the C1 partition. Do not rebuild it, and do not trust it unchecked.

``caprm.spatial_kfold`` BUILDS the partition and ``caprm.split_gate`` JUDGES it.
This module only READS what those two produced, verifies that what is on disk is
what the manifest says is on disk, and hands C2 a list of index triples.

Three verifications, all measured rather than assumed
-----------------------------------------------------
1. The dataset's SHA-256 against ``c1_kfold_manifest.json``. A surrogate trained
   on a dataset that is not the one the partition was built over is not
   evaluated under that partition, however identical the filenames look.
2. The split CSVs' SHA-256 against the same manifest.
3. Row alignment. The split file stores ``property_id``, ``fold`` and
   ``dropped_mask`` and nothing else; the roles are rebuilt with
   ``caprm.spatial_kfold.roles_from_codes``, which is tested to be exact. The
   two files are compared row for row on ``property_id`` rather than assumed to
   share an order. A silent reordering would produce a plausible number and no
   error, which is the Nucleus 18.29 defect shape.

Both partitions go through one code path
----------------------------------------
The blocked K-fold partition yields five (train, val, test) triples per seed;
the random control yields one. Everything downstream — training, aggregation,
scoring — sees the same :class:`EvaluationSplit` structure, so the memorization
gap C2 publishes is a comparison between two partitions rather than between two
pieces of code. That is the rule ``split_gate`` states for the leakage gate,
applied here to the evaluation.

The random control is REGENERATED from ``caprm.split_gate.random_split`` rather
than read out of its CSV, and the regeneration is then checked against the
persisted file at the recorded seed. Reading it would make the control's own
provenance unverifiable; regenerating it without checking would make it a
different control.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd

from caprm.spatial_kfold import SPLIT_DROPPED, roles_from_codes
from caprm.spatial_split import SPLIT_TEST, SPLIT_TRAIN, SPLIT_VAL
from caprm.split_gate import random_split

KEY_COLUMN = "property_id"
LABEL_COLUMN = "exposure_index_0_100"
EXPECTED_MANIFEST_SCHEMA = "c1_kfold_v1"
PARTITION_BLOCKED = "blocked_kfold"
PARTITION_RANDOM = "random_control"


class PartitionVerificationError(RuntimeError):
    """Raised when what is on disk is not what the manifest describes."""


def sha256_file(path: str | Path, chunk_bytes: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationSplit:
    """One (train, val, test) triple, whatever partition produced it."""

    partition: str
    seed: int
    fold: int
    train_index: np.ndarray
    val_index: np.ndarray
    test_index: np.ndarray

    @property
    def label(self) -> str:
        return f"{self.partition}_seed{self.seed}_fold{self.fold}"

    def counts(self) -> dict[str, int]:
        return {
            "train": int(self.train_index.size),
            "val": int(self.val_index.size),
            "test": int(self.test_index.size),
        }


@dataclass
class PartitionInputs:
    """The dataset and the verified manifest, loaded once and shared."""

    dataset_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    property_id: np.ndarray
    x: np.ndarray
    y: np.ndarray
    target: np.ndarray
    verification: dict[str, Any] = field(default_factory=dict)

    @property
    def n_properties(self) -> int:
        return int(len(self.property_id))

    @property
    def seeds(self) -> list[int]:
        return [int(s) for s in self.manifest["operating_point"]["seeds"]]

    @property
    def n_folds(self) -> int:
        return int(self.manifest["operating_point"]["n_folds"])

    @property
    def buffer_m(self) -> float:
        return float(self.manifest["operating_point"]["buffer_m"])


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def read_dataset(path: str | Path) -> pd.DataFrame:
    """Read the supervised dataset with the two dtype hazards C1 closed.

    ``dtype={property_id: str}`` because 267,361 IDs are zero-padded and one is
    alphanumeric; ``float_precision="round_trip"`` because pandas' default CSV
    float parser is not correctly rounded and disagrees with the round-trip
    parser on tens of thousands of the countywide coordinates by up to
    9.31e-10 m. Both are recorded in Current Status's C1 subsection.
    """
    frame = pd.read_csv(path, dtype={KEY_COLUMN: str}, float_precision="round_trip")
    missing = [c for c in (KEY_COLUMN, "x", "y", LABEL_COLUMN) if c not in frame.columns]
    if missing:
        raise PartitionVerificationError(f"dataset missing columns: {missing}")
    return frame


def load_partition_inputs(
    dataset_csv: str | Path, kfold_manifest_json: str | Path
) -> PartitionInputs:
    """Load the dataset and verify it against the partition manifest."""
    dataset_path = Path(dataset_csv)
    manifest_path = Path(kfold_manifest_json)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    schema = manifest.get("schema_version")
    if schema != EXPECTED_MANIFEST_SCHEMA:
        raise PartitionVerificationError(
            f"partition manifest schema_version={schema!r}, expected "
            f"{EXPECTED_MANIFEST_SCHEMA!r}"
        )
    if not manifest.get("acceptance", {}).get("blocked_gate_passed_every_fold_every_seed"):
        raise PartitionVerificationError(
            "the partition manifest does not record a passing gate on every "
            "fold and seed; it must not be trained under"
        )

    measured = sha256_file(dataset_path)
    declared = manifest["inputs"]["dataset_sha256"]
    if measured != declared:
        raise PartitionVerificationError(
            "dataset does not match the partition manifest: "
            f"manifest={declared} measured={measured}"
        )

    frame = read_dataset(dataset_path)
    declared_rows = int(manifest["inputs"]["rows"])
    if len(frame) != declared_rows:
        raise PartitionVerificationError(
            f"dataset has {len(frame)} rows, manifest declares {declared_rows}"
        )
    if frame[KEY_COLUMN].nunique() != len(frame):
        raise PartitionVerificationError("property_id is not unique in the dataset")

    return PartitionInputs(
        dataset_path=dataset_path,
        manifest_path=manifest_path,
        manifest=manifest,
        property_id=frame[KEY_COLUMN].to_numpy(dtype=object),
        x=frame["x"].to_numpy(dtype=np.float64),
        y=frame["y"].to_numpy(dtype=np.float64),
        target=frame[LABEL_COLUMN].to_numpy(dtype=np.float64),
        verification={
            "dataset_sha256": measured,
            "dataset_sha256_matches_manifest": True,
            "rows": int(len(frame)),
        },
    )


def _seed_record(inputs: PartitionInputs, seed: int) -> dict[str, Any]:
    for record in inputs.manifest["per_seed"]:
        if int(record["seed"]) == int(seed):
            return record
    raise PartitionVerificationError(
        f"seed {seed} is not one of the recorded seeds {inputs.seeds}"
    )


def load_blocked_roles(
    inputs: PartitionInputs, seed: int, split_dir: str | Path
) -> np.ndarray:
    """Rebuild the (n_properties, K) role matrix for one recorded seed.

    The split CSV's own path is taken from the manifest, not constructed from a
    naming convention, and its digest is checked before it is read.
    """
    record = _seed_record(inputs, seed)
    filename = Path(str(record["split_path"]).replace("\\", "/")).name
    path = Path(split_dir) / filename
    if not path.exists():
        raise PartitionVerificationError(f"split file not found: {path}")

    measured = sha256_file(path)
    if measured != record["split_sha256"]:
        raise PartitionVerificationError(
            f"split file {path} does not match the manifest: "
            f"manifest={record['split_sha256']} measured={measured}"
        )

    frame = pd.read_csv(path, dtype={KEY_COLUMN: str})
    for column in (KEY_COLUMN, "fold", "dropped_mask"):
        if column not in frame.columns:
            raise PartitionVerificationError(f"split file missing column {column!r}")
    if len(frame) != inputs.n_properties:
        raise PartitionVerificationError(
            f"split file has {len(frame)} rows, dataset has {inputs.n_properties}"
        )
    if not np.array_equal(frame[KEY_COLUMN].to_numpy(dtype=object), inputs.property_id):
        raise PartitionVerificationError(
            "split file property_id column does not match the dataset row for "
            "row; the split is not aligned to the dataset and joining by "
            "position would produce a plausible number and no error"
        )

    return roles_from_codes(
        frame["fold"].to_numpy(dtype=np.int64),
        frame["dropped_mask"].to_numpy(dtype=np.int64),
        inputs.n_folds,
    )


def blocked_splits(
    inputs: PartitionInputs, seed: int, split_dir: str | Path
) -> list[EvaluationSplit]:
    """The K (train, val, test) triples for one recorded seed."""
    roles = load_blocked_roles(inputs, seed, split_dir)
    splits: list[EvaluationSplit] = []
    for k in range(inputs.n_folds):
        column = roles[:, k]
        splits.append(
            EvaluationSplit(
                partition=PARTITION_BLOCKED,
                seed=int(seed),
                fold=k,
                train_index=np.flatnonzero(column == SPLIT_TRAIN),
                val_index=np.flatnonzero(column == SPLIT_VAL),
                test_index=np.flatnonzero(column == SPLIT_TEST),
            )
        )
    dropped = int((roles == SPLIT_DROPPED).sum())
    if dropped == 0:
        raise PartitionVerificationError(
            "no property is dropped in any fold: the buffer did not carve "
            "anything, so this is not the buffered partition of record"
        )
    return splits


def random_control_split(
    inputs: PartitionInputs, seed: int, split_csv: str | Path | None = None
) -> EvaluationSplit:
    """The positive control, regenerated and then checked against its artifact.

    ``caprm.split_gate.random_split`` is the same function C1 used, so the
    control is reproduced rather than reinterpreted.

    C1 persisted the control at ONE seed — ``build_spatial_kfold.py`` drew it at
    ``seeds[0]`` — so only that seed has a file to be checked against. At that
    seed the regenerated labels are compared to the file row for row and a
    mismatch raises; at the other recorded seeds the control is a redraw of the
    same construction with no persisted counterpart, and this function says so
    rather than comparing against a file that describes a different draw.

    The comparison is a live check, not a formality: it fires when the seeds
    differ, which is the property Nucleus 18.25 requires of any gate before its
    passing means anything.
    """
    labels = random_split(inputs.n_properties, seed=int(seed))
    persisted_seed = inputs.seeds[0] if inputs.seeds else None
    if split_csv is not None and persisted_seed is not None and int(seed) == int(persisted_seed):
        frame = pd.read_csv(split_csv, dtype={KEY_COLUMN: str})
        if not np.array_equal(
            frame[KEY_COLUMN].to_numpy(dtype=object), inputs.property_id
        ):
            raise PartitionVerificationError(
                "random control property_id column does not match the dataset"
            )
        persisted = frame["split"].to_numpy(dtype=object)
        if not np.array_equal(persisted, labels):
            raise PartitionVerificationError(
                f"regenerated random control at seed {seed} does not reproduce "
                f"{split_csv}; the control is not the one C1 recorded"
            )
    return EvaluationSplit(
        partition=PARTITION_RANDOM,
        seed=int(seed),
        fold=0,
        train_index=np.flatnonzero(labels == SPLIT_TRAIN),
        val_index=np.flatnonzero(labels == SPLIT_VAL),
        test_index=np.flatnonzero(labels == SPLIT_TEST),
    )


def iter_splits(
    inputs: PartitionInputs,
    partition: str,
    seed: int,
    split_dir: str | Path,
    random_control_csv: str | Path | None = None,
) -> list[EvaluationSplit]:
    """One entry point for both partitions, so C2 runs one protocol."""
    if partition == PARTITION_BLOCKED:
        return blocked_splits(inputs, seed, split_dir)
    if partition == PARTITION_RANDOM:
        return [random_control_split(inputs, seed, random_control_csv)]
    raise ValueError(f"unknown partition {partition!r}")


# ---------------------------------------------------------------------------
# the declared floor, read rather than typed
# ---------------------------------------------------------------------------


def declared_floor(inputs: PartitionInputs) -> dict[str, Any]:
    """The nearest-training-neighbour floor, taken from the C1 manifest.

    C1 declared it before any model existed. C2 reads it out of the artifact
    instead of quoting it from a document, so the comparison cannot drift from
    the measurement it claims to be against.
    """
    per_seed = {}
    for record in inputs.manifest["per_seed"]:
        aggregate = record["stats"]["aggregate_baseline"]
        per_seed[str(record["seed"])] = {
            "rmse": float(aggregate["rmse"]),
            "r2": float(aggregate["r2"]),
            "n": int(aggregate["n"]),
        }
    rmse = [v["rmse"] for v in per_seed.values()]
    r2 = [v["r2"] for v in per_seed.values()]
    control = inputs.manifest["controls"]["random"]["baseline"]
    return {
        "source": str(inputs.manifest_path),
        "predictor": "nearest training neighbour, declared at C1 before any model",
        "blocked_kfold": {
            "per_seed": per_seed,
            "rmse_min": float(min(rmse)),
            "rmse_max": float(max(rmse)),
            "r2_min": float(min(r2)),
            "r2_max": float(max(r2)),
        },
        "random_control": {
            "rmse": float(control["rmse"]),
            "r2": float(control["r2"]),
            "n": int(control["n_holdout"]),
        },
    }


# ---------------------------------------------------------------------------
# aggregation over folds
# ---------------------------------------------------------------------------


@dataclass
class FoldPredictions:
    """Predictions accumulated over a seed's folds, each property tested once."""

    n_properties: int
    predicted: np.ndarray
    tested: np.ndarray

    @classmethod
    def empty(cls, n_properties: int) -> "FoldPredictions":
        return cls(
            n_properties=n_properties,
            predicted=np.full(n_properties, np.nan),
            tested=np.zeros(n_properties, dtype=bool),
        )

    def add(self, test_index: np.ndarray, predicted: np.ndarray) -> None:
        test_index = np.asarray(test_index, dtype=np.int64)
        if test_index.size != np.asarray(predicted).size:
            raise ValueError("index and prediction lengths differ")
        if self.tested[test_index].any():
            raise RuntimeError(
                "a property was tested in more than one fold; the aggregate "
                "would then weight it twice and would not be a clean sample"
            )
        self.tested[test_index] = True
        self.predicted[test_index] = np.asarray(predicted, dtype=np.float64)

    def coverage_fraction(self) -> float:
        return float(self.tested.sum() / self.n_properties)


def iter_fold_labels(splits: Iterator[EvaluationSplit]) -> list[str]:
    return [split.label for split in splits]
