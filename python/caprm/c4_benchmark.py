"""C4. What the C2 surrogate costs at inference time.

Measurement only. Nothing here trains, retunes, re-selects an operating point,
or writes to any Milestone 3 path. Every model this module touches is opened
read-only and verified against ``outputs/validation/c2_surrogate_manifest.json``
before it is timed: a benchmark of an unverified artifact measures an unknown
model.

Three things this module exists to keep honest.

**A single run is a diagnostic, not a measurement.** Every timed quantity here
is a median over repeats with its spread reported beside it, after a discarded
warm-up. :class:`TimingResult` has no accessor that returns a bare number
without the sample it came from.

**A throughput sweep that changes the answer is not a throughput sweep.** C2
recorded that float32 GEMM is not invariant to operand shape: batches of 37 and
of 10,000 differed by 3.87e-06 index points. Batching is therefore both the
independent variable of the sweep and a thing the sweep can silently break, so
:func:`agreement_report` runs on the sweep's own outputs and the caller is
expected to treat a breach as a finding rather than as a tolerance to widen.

**A throughput figure without its thread count cannot be compared to anything.**
numpy's matmul is multi-threaded by default. This module records the thread
environment it observed; it cannot set it, because OpenBLAS reads those
variables once when the shared library loads, which is before any module here
is imported. Pinning is the CLI's job and happens in its preamble.

The Fourier/MLP split is worth more than its cost to obtain. The encoding runs a
float64 ``(n, 2) @ (2, 64)`` product plus a cosine and a sine over ``(n, 64)``;
the network runs float32 over 130 input columns. Which dominates is not obvious
from the shapes alone, and the dtype asymmetry is the reason.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

import numpy as np

from caprm.surrogate import TrainedModel, forward, load_model

TOOL_VERSION = "caprm.c4_benchmark/c4.0"

#: C2's recorded shape-sensitivity of float32 GEMM, in index points. The sweep
#: asserts against this rather than against a value chosen after seeing the
#: result. A breach is reported and raised, never absorbed.
C2_BATCH_AGREEMENT_TOLERANCE = 3.87e-06

#: ``None`` denotes one batch containing every row.
DEFAULT_BATCH_SIZES: tuple[int | None, ...] = (1, 64, 4096, 65_536, None)

#: Read, never written, by this module. The CLI writes them before numpy loads.
THREAD_ENVIRONMENT_VARIABLES = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


class C4BenchmarkError(RuntimeError):
    """Raised when a benchmark input cannot be trusted or a contract fails."""


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------


def sha256_file(path: str | Path, chunk_bytes: int = 1 << 20) -> str:
    """SHA-256 of a file's bytes, streamed."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def thread_environment() -> dict[str, str | None]:
    """The thread-count variables as observed, unset ones included as ``None``.

    An unset variable is not the same as a variable set to the core count: it
    means OpenBLAS chose, and what it chose is not recorded anywhere. Reporting
    the ``None`` is the point.
    """
    return {name: os.environ.get(name) for name in THREAD_ENVIRONMENT_VARIABLES}


def environment_record(
    cpu_name: str | None = None, physical_cores: int | None = None
) -> dict[str, Any]:
    """Everything needed to reproduce or reject a timing figure.

    ``cpu_name`` and ``physical_cores`` are operator-declared and labelled as
    such: Python cannot read either portably, and inventing a dependency to
    read them would buy less than declaring them and saying who declared them.
    """
    try:
        blas_config: Any = np.show_config(mode="dicts")
    except TypeError:  # pragma: no cover - numpy < 1.25
        blas_config = None

    build = (blas_config or {}).get("Build Dependencies", {})
    blas = build.get("blas", {}) if isinstance(build, dict) else {}

    return {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor_string": platform.processor(),
        "processor_identifier_env": os.environ.get("PROCESSOR_IDENTIFIER"),
        "logical_cores_os_cpu_count": os.cpu_count(),
        "operator_declared": {
            "cpu_name": cpu_name,
            "physical_cores": physical_cores,
            "source": "operator-declared, not read by this process",
        },
        "blas": {
            "name": blas.get("name"),
            "version": blas.get("version"),
            "openblas_configuration": blas.get("openblas configuration"),
        },
        "thread_environment": thread_environment(),
        "thread_environment_note": (
            "Set before numpy import by the CLI preamble. A null value means "
            "OpenBLAS selected a thread count that this process did not record."
        ),
    }


# ---------------------------------------------------------------------------
# timing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimingResult:
    """A sample of wall-clock durations, never a single number.

    Warm-up calls are executed and discarded; only ``seconds`` is reported, and
    every derived statistic is computed from it so a reader can recompute any
    of them from the artifact.
    """

    n_warmup: int
    seconds: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.seconds:
            raise C4BenchmarkError("a timing result needs at least one repeat")
        if any(s < 0.0 for s in self.seconds):
            raise C4BenchmarkError("negative duration")

    @property
    def n_repeat(self) -> int:
        return len(self.seconds)

    @property
    def median(self) -> float:
        return float(statistics.median(self.seconds))

    @property
    def minimum(self) -> float:
        return float(min(self.seconds))

    @property
    def maximum(self) -> float:
        return float(max(self.seconds))

    @property
    def mean(self) -> float:
        return float(statistics.fmean(self.seconds))

    @property
    def stdev(self) -> float:
        return float(statistics.stdev(self.seconds)) if self.n_repeat > 1 else 0.0

    @property
    def relative_spread(self) -> float:
        """(max - min) / median. The one number that says whether to believe it."""
        median = self.median
        return float((self.maximum - self.minimum) / median) if median > 0 else math.nan

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_warmup": self.n_warmup,
            "n_repeat": self.n_repeat,
            "seconds": list(self.seconds),
            "median_s": self.median,
            "min_s": self.minimum,
            "max_s": self.maximum,
            "mean_s": self.mean,
            "stdev_s": self.stdev,
            "relative_spread": self.relative_spread,
        }


def timed_repeats(
    call: Callable[[], Any], n_warmup: int = 1, n_repeat: int = 5
) -> tuple[TimingResult, Any]:
    """Warm up, then time ``n_repeat`` calls with ``perf_counter``.

    Returns the timing and the value produced by the first *timed* call, so a
    caller can check what was computed without paying for it again.
    """
    if n_warmup < 0:
        raise C4BenchmarkError("n_warmup must be non-negative")
    if n_repeat < 1:
        raise C4BenchmarkError("n_repeat must be at least 1")

    for _ in range(n_warmup):
        call()

    durations: list[float] = []
    first: Any = None
    for repeat in range(n_repeat):
        start = time.perf_counter()
        value = call()
        durations.append(time.perf_counter() - start)
        if repeat == 0:
            first = value
    return TimingResult(n_warmup=n_warmup, seconds=tuple(durations)), first


# ---------------------------------------------------------------------------
# the models, verified before anything is timed
# ---------------------------------------------------------------------------


def batch_label(batch_size: int | None) -> str:
    return "full" if batch_size is None else str(int(batch_size))


@dataclass(frozen=True)
class ModelRecord:
    """One C2 model, verified, sized, and located."""

    label: str
    partition: str
    seed: int
    fold: int
    path: str
    expected_weights_sha256: str
    observed_weights_sha256: str
    n_mlp_parameters: int
    n_stored_values: int
    layer_shapes: tuple[tuple[int, ...], ...]
    disk_bytes: int
    memory_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "partition": self.partition,
            "seed": self.seed,
            "fold": self.fold,
            "path": self.path,
            "expected_weights_sha256": self.expected_weights_sha256,
            "observed_weights_sha256": self.observed_weights_sha256,
            "n_mlp_parameters": self.n_mlp_parameters,
            "n_stored_values": self.n_stored_values,
            "layer_shapes": [list(shape) for shape in self.layer_shapes],
            "disk_bytes": self.disk_bytes,
            "memory_bytes": self.memory_bytes,
        }


def iter_manifest_folds(manifest: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every fold entry in the C2 manifest, in manifest order."""
    for runs in manifest["results"].values():
        for run in runs:
            for fold in run["folds"]:
                yield fold


def _resolve(repository_root: Path, recorded: str) -> Path:
    """Manifest paths were written on Windows and carry backslashes."""
    return repository_root / Path(recorded.replace("\\", "/"))


def model_size_record(model: TrainedModel, path: str | Path) -> dict[str, Any]:
    """Bytes on disk, bytes in memory, and the parameter count both ways.

    ``TrainedModel.n_parameters`` counts the MLP only: it sums over
    ``self.parameters`` and excludes the ``(2, n_features)`` Fourier frequency
    matrix, which ``named_arrays`` does store and ``weights_sha256`` does
    digest. Both counts are reported because only one of them is the number of
    values you must ship to reproduce a prediction.
    """
    arrays = model.named_arrays()
    per_array = [
        {
            "name": name,
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "bytes": int(array.nbytes),
            "values": int(array.size),
        }
        for name, array in arrays
    ]
    memory_bytes = sum(int(entry["bytes"]) for entry in per_array)
    disk_bytes = int(Path(path).stat().st_size)
    return {
        "path": str(path),
        "disk_bytes": disk_bytes,
        "memory_bytes": memory_bytes,
        "disk_to_memory_ratio": disk_bytes / memory_bytes if memory_bytes else math.nan,
        "n_mlp_parameters": int(model.n_parameters()),
        "n_stored_values": sum(int(entry["values"]) for entry in per_array),
        "arrays": per_array,
    }


def verify_models(
    manifest_path: str | Path, repository_root: str | Path
) -> tuple[list[ModelRecord], dict[str, TrainedModel]]:
    """Load every C2 model and check it against its recorded digest.

    B4's rule: a provenance chain closes on the artifact AS RELOADED. The
    manifest records ``weights_sha256`` from training and
    ``weights_sha256_after_reload`` from its own check; this recomputes the
    digest from disk today and compares to the former. Any mismatch raises,
    because a benchmark of an unverified artifact measures an unknown model.
    """
    manifest_path = Path(manifest_path)
    repository_root = Path(repository_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    records: list[ModelRecord] = []
    models: dict[str, TrainedModel] = {}
    mismatches: list[str] = []

    for entry in iter_manifest_folds(manifest):
        path = _resolve(repository_root, entry["model_path"])
        if not path.exists():
            raise C4BenchmarkError(f"model recorded in the manifest is missing: {path}")
        model = load_model(path)
        observed = model.weights_sha256()
        expected = entry["weights_sha256"]
        if observed != expected:
            mismatches.append(f"{entry['label']}: expected {expected}, observed {observed}")
        size = model_size_record(model, path)
        label = entry["label"]
        records.append(
            ModelRecord(
                label=label,
                partition=entry["partition"],
                seed=int(entry["seed"]),
                fold=int(entry["fold"]),
                path=str(path),
                expected_weights_sha256=expected,
                observed_weights_sha256=observed,
                n_mlp_parameters=int(size["n_mlp_parameters"]),
                n_stored_values=int(size["n_stored_values"]),
                layer_shapes=tuple(tuple(w.shape) for w, _ in model.parameters),
                disk_bytes=int(size["disk_bytes"]),
                memory_bytes=int(size["memory_bytes"]),
            )
        )
        models[label] = model

    if mismatches:
        raise C4BenchmarkError(
            "model weights do not match the C2 manifest:\n  " + "\n  ".join(mismatches)
        )
    return records, models


def assert_identical_architecture(records: Sequence[ModelRecord]) -> dict[str, Any]:
    """All 30 models must share one architecture, or cost is not shared.

    C4 times one model and reports the figure for the operating point. That is
    only legitimate if inference cost is determined by architecture rather than
    by weights, which requires the shapes to be identical. C2's seed spread of
    3.76 RMSE points is an accuracy fact and says nothing about cost; this check
    is what licenses the separation.
    """
    if not records:
        raise C4BenchmarkError("no models to compare")
    shapes = {record.layer_shapes for record in records}
    if len(shapes) != 1:
        raise C4BenchmarkError(
            f"models do not share one architecture; found {len(shapes)} distinct shape sets"
        )
    reference = records[0]
    return {
        "n_models": len(records),
        "layer_shapes": [list(shape) for shape in reference.layer_shapes],
        "n_mlp_parameters": reference.n_mlp_parameters,
        "n_stored_values": reference.n_stored_values,
        "identical_across_models": True,
        "licenses": (
            "inference cost is architecture-determined, so one model may be timed "
            "for the set; accuracy is not, and is reported per seed"
        ),
    }


# ---------------------------------------------------------------------------
# the sweep
# ---------------------------------------------------------------------------


def batch_sweep(
    model: TrainedModel,
    x: np.ndarray,
    y: np.ndarray,
    batch_sizes: Sequence[int | None] = DEFAULT_BATCH_SIZES,
    n_warmup: int = 1,
    n_repeat: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    """Throughput as a function of batch size, with the predictions retained.

    Throughput is a function of batching, and one number hides that. The
    predictions come back so the caller can assert the sweep did not change the
    answer while it was changing the shape.
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    if x.shape != y.shape:
        raise C4BenchmarkError("x and y must have the same length")
    n = int(x.size)
    if n == 0:
        raise C4BenchmarkError("no coordinates to score")

    rows: list[dict[str, Any]] = []
    predictions: dict[str, np.ndarray] = {}

    for batch_size in batch_sizes:
        size = n if batch_size is None else int(batch_size)
        if size < 1:
            raise C4BenchmarkError(f"batch size must be positive, got {batch_size}")
        label = batch_label(batch_size)

        def call(size: int = size) -> np.ndarray:
            return model.predict(x, y, batch_size=size)

        timing, prediction = timed_repeats(call, n_warmup=n_warmup, n_repeat=n_repeat)
        predictions[label] = np.asarray(prediction)
        rows.append(
            {
                "batch_label": label,
                "batch_size": size,
                "is_full_array": batch_size is None,
                "n_properties": n,
                "n_batches": math.ceil(n / size),
                "timing": timing.to_dict(),
                "properties_per_second_median": n / timing.median if timing.median else math.inf,
                "properties_per_second_fastest": n / timing.minimum if timing.minimum else math.inf,
                "microseconds_per_property_median": timing.median * 1e6 / n,
                "microseconds_per_property_fastest": timing.minimum * 1e6 / n,
            }
        )
    return rows, predictions


def agreement_report(
    predictions: dict[str, np.ndarray],
    reference_label: str = "full",
    tolerance: float = C2_BATCH_AGREEMENT_TOLERANCE,
) -> dict[str, Any]:
    """Do the sweep's batch sizes agree to within C2's recorded bound?

    The tolerance is C2's measured 3.87e-06 index points between batches of 37
    and 10,000. Applying it across a wider batch range is an extrapolation and
    is labelled as one. If a batch size breaches it, that is a finding about
    float32 GEMM at that shape, and the correct response is to report it, not
    to widen the bound.
    """
    if reference_label not in predictions:
        raise C4BenchmarkError(f"reference batch {reference_label!r} not in the sweep")
    reference = np.asarray(predictions[reference_label], dtype=np.float64)

    per_batch: dict[str, Any] = {}
    for label, values in predictions.items():
        values = np.asarray(values, dtype=np.float64)
        if values.shape != reference.shape:
            raise C4BenchmarkError(f"batch {label!r} produced a different number of predictions")
        deviation = float(np.max(np.abs(values - reference)))
        per_batch[label] = {
            "max_abs_deviation": deviation,
            "within_tolerance": bool(deviation <= tolerance),
        }

    worst = max(entry["max_abs_deviation"] for entry in per_batch.values())
    return {
        "reference_batch": reference_label,
        "tolerance_index_points": tolerance,
        "tolerance_provenance": (
            "C2 measured this between batches of 37 and 10,000; its use across a "
            "wider batch range is an extrapolation"
        ),
        "max_abs_deviation_index_points": worst,
        "all_within_tolerance": bool(all(e["within_tolerance"] for e in per_batch.values())),
        "per_batch": per_batch,
    }


def stage_split(
    model: TrainedModel,
    x: np.ndarray,
    y: np.ndarray,
    batch_size: int | None = 65_536,
    n_warmup: int = 1,
    n_repeat: int = 5,
) -> dict[str, Any]:
    """Split inference cost between Fourier encoding and the MLP forward pass.

    **The two halves do not sum to the whole, and this function reports the gap
    instead of dividing by a total that cannot absorb it.** An earlier version
    expressed each half as a fraction of ``predict``'s wall clock and produced
    101 percent encoding, 27 percent forward, and a negative residual. The
    fractions were arithmetically forced to 1.0 and meant nothing.

    Two mechanisms, both real, push in opposite directions. Timed alone,
    ``features_for`` allocates and discards an ``(n, 130)`` float32 matrix per
    batch with no forward pass interleaved, so it loses the allocator reuse it
    gets inside ``predict``; that OVERSTATES encoding. Timed alone, ``forward``
    runs over blocks already materialised and resident, so it pays no
    construction cost and enjoys a warm cache; that UNDERSTATES the forward
    pass. Reporting either as a share of the total launders both errors into a
    percentage that looks decomposed.

    What survives the objection is the ordering and its magnitude: both halves
    are measured over the same batch decomposition at the same shapes, and the
    ratio between them is far larger than the effects above. That ratio is the
    reportable finding; ``parts_minus_whole_s`` is published beside it so a
    reader can see exactly how non-additive the measurement is.
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    n = int(x.size)
    size = n if batch_size is None else int(batch_size)
    bounds = [(start, min(start + size, n)) for start in range(0, n, size)]

    def encode_only() -> int:
        total = 0
        for start, stop in bounds:
            total += model.features_for(x[start:stop], y[start:stop]).shape[0]
        return total

    encode_timing, _ = timed_repeats(encode_only, n_warmup=n_warmup, n_repeat=n_repeat)

    blocks = [model.features_for(x[start:stop], y[start:stop]) for start, stop in bounds]

    def forward_only() -> int:
        total = 0
        for block in blocks:
            prediction, _ = forward(block, model.parameters)
            total += prediction.shape[0]
        return total

    forward_timing, _ = timed_repeats(forward_only, n_warmup=n_warmup, n_repeat=n_repeat)

    def full() -> np.ndarray:
        return model.predict(x, y, batch_size=size)

    total_timing, _ = timed_repeats(full, n_warmup=n_warmup, n_repeat=n_repeat)

    encode = encode_timing.median
    forward_median = forward_timing.median
    total = total_timing.median
    parts = encode + forward_median

    return {
        "batch_label": batch_label(batch_size),
        "batch_size": size,
        "n_properties": n,
        "fourier_encoding": encode_timing.to_dict(),
        "mlp_forward": forward_timing.to_dict(),
        "full_predict": total_timing.to_dict(),
        "fourier_microseconds_per_property": encode * 1e6 / n,
        "mlp_microseconds_per_property": forward_median * 1e6 / n,
        "full_microseconds_per_property": total * 1e6 / n,
        "fourier_over_mlp_ratio": encode / forward_median if forward_median else math.inf,
        "sum_of_parts_s": parts,
        "full_predict_s": total,
        "parts_minus_whole_s": parts - total,
        "parts_minus_whole_fraction_of_whole": (parts - total) / total if total else math.nan,
        "decomposition_is_not_additive": (
            "Timed in isolation, encoding loses the allocator reuse it gets inside "
            "predict and is overstated; forward runs on resident blocks and is "
            "understated. Read the ratio, not a share of the total."
        ),
        "feature_matrix_bytes": sum(int(block.nbytes) for block in blocks),
        "feature_dtype": str(blocks[0].dtype) if blocks else None,
        "encoding_dtype_note": (
            "fourier_features computes in float64 and casts once at the end; the "
            "MLP runs in float32, so this split is partly a dtype comparison"
        ),
    }