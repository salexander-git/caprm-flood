"""The PHASE C neural surrogate: coordinates in, exposure index out.

What this module is
-------------------
A small multilayer perceptron over a random Fourier feature encoding of
position, implemented directly in numpy: forward pass, analytic backward pass,
Adam, early stopping. It approximates the project's own deterministic scoring
function ``preliminary_exposure_index_v2`` as a function of ``(x, y)`` in
EPSG:26918. It does not replace that function and it is never trained on flood
outcomes (Roadmap C2, "Do not").

Why numpy and not a framework
-----------------------------
Three reasons, in order of weight.

1. ``requirements.txt`` is a pinned reproducibility artifact. A framework is a
   multi-hundred-megabyte dependency with its own BLAS, its own RNG streams and
   its own nondeterminism controls, added to reproduce a model with roughly
   30,000 parameters. The trade is not worth it here.
2. The gradient becomes testable rather than trusted. ``test_surrogate.py``
   checks every analytic gradient against a central finite difference in
   float64. A framework's autodiff is correct, but the project would then be
   asserting a dependency's correctness instead of its own, which is the same
   substitution Nucleus 18.15 refuses elsewhere.
3. Precision is explicit at every step rather than inherited from a default.
   See the dtype note below; it is the trap the C2 kickoff named.

The dtype contract, stated because it was declared before training
------------------------------------------------------------------
EPSG:26918 eastings are ~2.6e5 m and the project's boundary epsilon is 1e-9 m.
float32 holds ~7.2 decimal digits, so a raw easting cast to float32 is quantised
at ~0.03 m and the epsilon discipline is destroyed silently.

This module therefore normalizes in float64 and casts afterwards. The
normalizer maps the county bounding box into [-1, 1] with a SINGLE isotropic
scale, and only then is the feature matrix cast to the training dtype. The
resulting input quantisation is reported by
:meth:`CoordinateNormalizer.quantisation_m` — at float32 and the countywide box
it is on the order of millimetres, which is far coarser than 1e-9 m and far
finer than the 2,125 m separation the error is measured at. The model is an
approximator, not the exact kernel; that resolution is adequate and it is
recorded rather than assumed.

Isotropy is not cosmetic. The county box is 50,851 m by 48,223 m. Per-axis
normalization would make one metre in easting a different number of feature
cycles than one metre in northing, so a swept Fourier scale would have no single
metric meaning. With one scale, a scale value ``s`` corresponds to a
characteristic wavelength of ``scale_m / s`` METRES, and the sweep can be read
directly against C1's measured variogram lags (gamma/sill = 0.25 at 625 m, 0.50
at 2,125 m, 0.75 at 6,125 m).

What is a model artifact here (Nucleus 18.20)
---------------------------------------------
Architecture, the seeds that produced it, the digest of the split manifest it
was trained under, the loss curve, and a checksum of the weights. The checksum
is computed over the WEIGHT ARRAYS' bytes, not over the ``.npz`` file, because
``np.savez`` writes a zip and a zip records a modification timestamp: a digest
of the file would attest to when it was written, not what it contains. This is
the same defect Nucleus 18.25 records for MinGW's PE link timestamp, in a new
place, and it is avoided the same way — hash the content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

DISTANCE_CRS = "EPSG:26918"
INIT_NAMESPACE = "c2:init:"
FEATURE_NAMESPACE = "c2:features:"
SHUFFLE_NAMESPACE = "c2:shuffle:"
ARTIFACT_SCHEMA = "c2_surrogate_v1"


# ---------------------------------------------------------------------------
# seeds
# ---------------------------------------------------------------------------


def derived_seed(namespace: str, *parts: Any) -> int:
    """A reproducible 63-bit seed from a namespace and any identifying parts.

    Namespaced for the same reason ``caprm.spatial_kfold.block_fold`` is: the
    split seed already drives fold assignment, and reusing it directly for
    weight initialisation would tie which blocks are held out to which weights
    are drawn. They must be independent, and the independence must come from
    construction rather than from the caller remembering to offset the integer.
    """
    key = (namespace + ":".join(str(p) for p in parts)).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big") >> 1


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoordinateNormalizer:
    """Map projected metres into [-1, 1] with one isotropic scale.

    The bounding box is a property of the county workload, not of a training
    fold, and it carries no label information, so it is taken from the frozen
    dataset manifest and held fixed across every fold and seed. Deriving it from
    each fold's training rows instead would make the Fourier scale mean a
    different metric wavelength in every fold, and the sweep would then be
    comparing configurations that are not the same configuration.
    """

    center_x_m: float
    center_y_m: float
    scale_m: float

    @classmethod
    def from_bounds(
        cls, x_min: float, x_max: float, y_min: float, y_max: float
    ) -> "CoordinateNormalizer":
        if not (x_max > x_min and y_max > y_min):
            raise ValueError("bounds must be non-degenerate in both axes")
        half_x = (float(x_max) - float(x_min)) / 2.0
        half_y = (float(y_max) - float(y_min)) / 2.0
        return cls(
            center_x_m=(float(x_max) + float(x_min)) / 2.0,
            center_y_m=(float(y_max) + float(y_min)) / 2.0,
            scale_m=max(half_x, half_y),
        )

    @classmethod
    def from_dataset_manifest(cls, path: str | Path) -> "CoordinateNormalizer":
        """Read the box out of ``supervised_dataset_v2_manifest.json``.

        Read, never typed in: the same rule C1 applied when it took the buffer
        width from the variogram artifact instead of hard-coding 2,125.
        """
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        verification = payload["verification"]
        return cls.from_bounds(
            verification["x_min"],
            verification["x_max"],
            verification["y_min"],
            verification["y_max"],
        )

    def transform(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """(n, 2) float64 normalized coordinates. Always float64 at this step."""
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if x.shape != y.shape:
            raise ValueError("x and y must have the same shape")
        return np.column_stack(
            [(x - self.center_x_m) / self.scale_m, (y - self.center_y_m) / self.scale_m]
        )

    def quantisation_m(self, dtype: Any) -> float:
        """Metric resolution of a normalized coordinate once cast to ``dtype``.

        Reported with every run. It is the number that says whether the cast
        that makes training affordable has damaged anything that matters.
        """
        return float(np.finfo(np.dtype(dtype)).eps * self.scale_m)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# random Fourier features
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FourierConfig:
    """Gaussian random Fourier features over normalized position.

    ``scale`` is the standard deviation of the frequency draw in cycles per
    normalized unit. The characteristic wavelength it induces, in metres, is
    ``normalizer.scale_m / scale``; that conversion is what makes the sweep
    legible against C1's variogram rather than a list of unitless numbers.

    ``n_features`` frequencies produce ``2 * n_features`` columns (a cosine and
    a sine per frequency), plus the two raw normalized coordinates when
    ``include_raw`` is set. The raw pair is kept by default because the target
    has a strong low-frequency trend — C1 fitted a degree-3 polynomial to it at
    R^2 = 0.2527 — and a Gaussian frequency draw represents an almost-linear
    trend only by cancellation between high-frequency terms.
    """

    n_features: int = 64
    scale: float = 8.0
    include_raw: bool = True

    def __post_init__(self) -> None:
        if self.n_features < 1:
            raise ValueError("n_features must be positive")
        if not (self.scale > 0.0):
            raise ValueError("scale must be positive")

    @property
    def n_columns(self) -> int:
        return 2 * self.n_features + (2 if self.include_raw else 0)

    def wavelength_m(self, normalizer: CoordinateNormalizer) -> float:
        return float(normalizer.scale_m / self.scale)

    def draw(self, seed: int) -> np.ndarray:
        """The frequency matrix B, shape (2, n_features), float64."""
        rng = np.random.default_rng(seed)
        return rng.normal(0.0, float(self.scale), size=(2, self.n_features))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fourier_features(
    coords_norm: np.ndarray,
    frequencies: np.ndarray,
    include_raw: bool,
    dtype: Any = np.float32,
) -> np.ndarray:
    """Encode normalized coordinates; float64 throughout, cast once at the end."""
    coords_norm = np.asarray(coords_norm, dtype=np.float64)
    if coords_norm.ndim != 2 or coords_norm.shape[1] != 2:
        raise ValueError("coords_norm must have shape (n, 2)")
    projection = 2.0 * np.pi * (coords_norm @ np.asarray(frequencies, dtype=np.float64))
    blocks = [np.cos(projection), np.sin(projection)]
    if include_raw:
        blocks.insert(0, coords_norm)
    return np.concatenate(blocks, axis=1).astype(dtype, copy=False)


# ---------------------------------------------------------------------------
# the network
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MLPConfig:
    hidden: tuple[int, ...] = (256, 256)
    dtype: str = "float32"

    def __post_init__(self) -> None:
        if not self.hidden or any(h < 1 for h in self.hidden):
            raise ValueError("hidden must be a non-empty tuple of positive widths")
        if self.dtype not in ("float32", "float64"):
            raise ValueError("dtype must be 'float32' or 'float64'")

    def to_dict(self) -> dict[str, Any]:
        return {"hidden": list(self.hidden), "dtype": self.dtype}


def init_parameters(
    n_inputs: int, config: MLPConfig, seed: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """He initialisation, biases at zero, in the training dtype."""
    rng = np.random.default_rng(seed)
    dtype = np.dtype(config.dtype)
    sizes = [n_inputs, *config.hidden, 1]
    parameters: list[tuple[np.ndarray, np.ndarray]] = []
    for fan_in, fan_out in zip(sizes[:-1], sizes[1:]):
        scale = np.sqrt(2.0 / fan_in)
        weight = (rng.normal(0.0, scale, size=(fan_in, fan_out))).astype(dtype)
        bias = np.zeros(fan_out, dtype=dtype)
        parameters.append((weight, bias))
    return parameters


def forward(
    features: np.ndarray, parameters: Sequence[tuple[np.ndarray, np.ndarray]]
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Return the (n,) prediction and the activations needed by the backward pass.

    ReLU on every layer but the last, which is linear.
    """
    activations = [features]
    current = features
    last = len(parameters) - 1
    for depth, (weight, bias) in enumerate(parameters):
        current = current @ weight + bias
        if depth != last:
            current = np.maximum(current, 0.0)
            activations.append(current)
    return current[:, 0], activations


def backward(
    activations: list[np.ndarray],
    parameters: Sequence[tuple[np.ndarray, np.ndarray]],
    prediction: np.ndarray,
    target: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Analytic gradient of mean squared error. Checked against finite differences."""
    n = len(target)
    delta = (2.0 / n) * (prediction - target).astype(prediction.dtype)[:, None]
    gradients: list[tuple[np.ndarray, np.ndarray]] = [None] * len(parameters)  # type: ignore[list-item]
    for depth in range(len(parameters) - 1, -1, -1):
        activation = activations[depth]
        weight, _ = parameters[depth]
        gradients[depth] = (activation.T @ delta, delta.sum(axis=0))
        if depth > 0:
            delta = (delta @ weight.T) * (activations[depth] > 0)
    return gradients


class Adam:
    """Adam, written out so the update is inspectable and the state is ours."""

    def __init__(
        self,
        parameters: Sequence[tuple[np.ndarray, np.ndarray]],
        learning_rate: float = 1e-3,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
    ) -> None:
        self.learning_rate = float(learning_rate)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.step_count = 0
        self._m = [(np.zeros_like(w), np.zeros_like(b)) for w, b in parameters]
        self._v = [(np.zeros_like(w), np.zeros_like(b)) for w, b in parameters]

    def step(
        self,
        parameters: list[tuple[np.ndarray, np.ndarray]],
        gradients: Sequence[tuple[np.ndarray, np.ndarray]],
    ) -> None:
        self.step_count += 1
        bias1 = 1.0 - self.beta1**self.step_count
        bias2 = 1.0 - self.beta2**self.step_count
        for depth, ((weight, bias), (grad_w, grad_b)) in enumerate(
            zip(parameters, gradients)
        ):
            for slot, (param, grad) in enumerate(((weight, grad_w), (bias, grad_b))):
                m = self._m[depth][slot]
                v = self._v[depth][slot]
                m *= self.beta1
                m += (1.0 - self.beta1) * grad
                v *= self.beta2
                v += (1.0 - self.beta2) * (grad * grad)
                param -= (
                    self.learning_rate * (m / bias1) / (np.sqrt(v / bias2) + self.epsilon)
                ).astype(param.dtype)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


def regression_metrics(predicted: np.ndarray, actual: np.ndarray) -> dict[str, float]:
    """RMSE, MAE, max absolute error and R^2, in the label's own units.

    ``r2`` is computed against the variance of the HOLDOUT actuals, matching
    ``caprm.split_gate.nearest_neighbour_baseline`` exactly. The declared floor
    was produced by that function, and a comparison against it is only a
    comparison if the denominator is the same one.
    """
    predicted = np.asarray(predicted, dtype=np.float64)
    actual = np.asarray(actual, dtype=np.float64)
    if predicted.shape != actual.shape:
        raise ValueError("predicted and actual must have the same shape")
    if predicted.size == 0:
        raise ValueError("no rows to score")
    error = predicted - actual
    denominator = float(np.var(actual))
    return {
        "n": int(predicted.size),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mae": float(np.mean(np.abs(error))),
        "max_abs_error": float(np.max(np.abs(error))),
        "r2": float(1.0 - np.mean(error**2) / denominator)
        if denominator > 0
        else float("nan"),
        "mean_label": float(actual.mean()),
        "std_label": float(actual.std(ddof=1)) if actual.size > 1 else 0.0,
        "predicted_mean": float(predicted.mean()),
        "predicted_std": float(predicted.std(ddof=1)) if predicted.size > 1 else 0.0,
        # The diagnostic that separates "learned the function" from "collapsed
        # to the mean". A predictor that emits a constant scores RMSE equal to
        # the holdout standard deviation, which on this blocked partition BEATS
        # the declared nearest-neighbour floor. Without this ratio a collapsing
        # model and a learning one are indistinguishable from RMSE alone.
        "variance_ratio": float(np.var(predicted) / denominator)
        if denominator > 0
        else float("nan"),
    }


# ---------------------------------------------------------------------------
# the trained model, as an artifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrainConfig:
    """Everything that determines a fit, and nothing that does not."""

    learning_rate: float = 1e-3
    batch_size: int = 4096
    max_epochs: int = 200
    patience: int = 20
    min_epochs: int = 10

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrainedModel:
    normalizer: CoordinateNormalizer
    fourier: FourierConfig
    frequencies: np.ndarray
    parameters: list[tuple[np.ndarray, np.ndarray]]
    mlp: MLPConfig
    target_mean: float
    target_std: float
    seeds: dict[str, int]
    history: dict[str, list[float]] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    # -- inference ---------------------------------------------------------

    def predict(self, x: np.ndarray, y: np.ndarray, batch_size: int = 65_536) -> np.ndarray:
        """Predict the index at arbitrary coordinates, in label units.

        Batched so that scoring all 267,362 properties does not materialise a
        single feature matrix an order of magnitude larger than the dataset.
        """
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        out = np.empty(len(x), dtype=np.float64)
        for start in range(0, len(x), batch_size):
            stop = min(start + batch_size, len(x))
            features = self.features_for(x[start:stop], y[start:stop])
            standardized, _ = forward(features, self.parameters)
            out[start:stop] = standardized.astype(np.float64) * self.target_std + self.target_mean
        return out

    def features_for(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return fourier_features(
            self.normalizer.transform(x, y),
            self.frequencies,
            self.fourier.include_raw,
            dtype=np.dtype(self.mlp.dtype),
        )

    # -- provenance --------------------------------------------------------

    def weights_sha256(self) -> str:
        """SHA-256 over the weight arrays' bytes, in a fixed order.

        Not over the ``.npz`` file: a zip carries a modification timestamp, so a
        file digest records when the model was written rather than what it
        contains. Nucleus 18.25's link-timestamp corollary, in a new place.
        """
        digest = hashlib.sha256()
        for name, array in self.named_arrays():
            digest.update(name.encode("utf-8"))
            digest.update(str(array.shape).encode("utf-8"))
            digest.update(str(array.dtype).encode("utf-8"))
            digest.update(np.ascontiguousarray(array).tobytes())
        return digest.hexdigest()

    def named_arrays(self) -> list[tuple[str, np.ndarray]]:
        arrays: list[tuple[str, np.ndarray]] = [("frequencies", self.frequencies)]
        for depth, (weight, bias) in enumerate(self.parameters):
            arrays.append((f"W{depth}", weight))
            arrays.append((f"b{depth}", bias))
        return arrays

    def n_parameters(self) -> int:
        return int(sum(w.size + b.size for w, b in self.parameters))

    def header(self) -> dict[str, Any]:
        """The artifact header. A model without this did not happen (18.20)."""
        return {
            "schema_version": ARTIFACT_SCHEMA,
            "crs": DISTANCE_CRS,
            "architecture": {
                "encoding": "gaussian_random_fourier",
                "fourier": self.fourier.to_dict(),
                "fourier_wavelength_m": self.fourier.wavelength_m(self.normalizer),
                "n_input_columns": int(self.parameters[0][0].shape[0]),
                "hidden": list(self.mlp.hidden),
                "n_parameters": self.n_parameters(),
                "training_dtype": self.mlp.dtype,
            },
            "normalizer": self.normalizer.to_dict(),
            "input_quantisation_m": self.normalizer.quantisation_m(self.mlp.dtype),
            "target_standardization": {
                "mean": self.target_mean,
                "std": self.target_std,
                "fitted_on": "training rows only",
            },
            "seeds": dict(self.seeds),
            "weights_sha256": self.weights_sha256(),
            "history": {k: list(v) for k, v in self.history.items()},
            "provenance": dict(self.provenance),
        }


def save_model(model: TrainedModel, path: str | Path) -> Path:
    """Write weights and header together. Returns the path written."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: array for name, array in model.named_arrays()}
    payload["header_json"] = np.array(json.dumps(model.header(), sort_keys=False))
    np.savez(out, **payload)
    return out


def load_model(path: str | Path) -> TrainedModel:
    """Reload a model and rebuild it exactly, header included.

    The caller is expected to assert that ``weights_sha256()`` of the reloaded
    model equals the digest recorded in its header — B4 established that a
    provenance chain is closed by checking the artifact AS RELOADED, not the
    object that was in memory when it was written.
    """
    with np.load(Path(path), allow_pickle=False) as data:
        header = json.loads(str(data["header_json"]))
        frequencies = data["frequencies"]
        parameters: list[tuple[np.ndarray, np.ndarray]] = []
        depth = 0
        while f"W{depth}" in data:
            parameters.append((data[f"W{depth}"], data[f"b{depth}"]))
            depth += 1
    architecture = header["architecture"]
    return TrainedModel(
        normalizer=CoordinateNormalizer(**header["normalizer"]),
        fourier=FourierConfig(**architecture["fourier"]),
        frequencies=frequencies,
        parameters=parameters,
        mlp=MLPConfig(
            hidden=tuple(architecture["hidden"]), dtype=architecture["training_dtype"]
        ),
        target_mean=header["target_standardization"]["mean"],
        target_std=header["target_standardization"]["std"],
        seeds=dict(header["seeds"]),
        history={k: list(v) for k, v in header["history"].items()},
        provenance=dict(header["provenance"]),
    )


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------


def train_surrogate(
    x: np.ndarray,
    y: np.ndarray,
    target: np.ndarray,
    train_index: np.ndarray,
    val_index: np.ndarray,
    normalizer: CoordinateNormalizer,
    fourier: FourierConfig = FourierConfig(),
    mlp: MLPConfig = MLPConfig(),
    train_config: TrainConfig = TrainConfig(),
    seed: int = 0,
    provenance: dict[str, Any] | None = None,
    progress: Any | None = None,
) -> TrainedModel:
    """Fit one model on ``train_index``, selecting the epoch on ``val_index``.

    Selection is on validation, never on test. The C1 partition isolates test
    from validation as well as from training precisely so that this selection is
    not a leak (Nucleus 18.33); using test here would spend that guarantee.

    Determinism: every random decision — the frequency draw, the weight init,
    and the per-epoch shuffle — comes from a seed derived by
    :func:`derived_seed` from ``seed`` and a namespace. Two runs with the same
    ``seed`` on the same machine produce the same weight checksum, and the CLI
    verifies that by retraining rather than asserting it.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    train_index = np.asarray(train_index, dtype=np.int64)
    val_index = np.asarray(val_index, dtype=np.int64)
    if train_index.size == 0:
        raise ValueError("empty training set")
    if val_index.size == 0:
        raise ValueError("empty validation set: the epoch cannot be selected")
    if np.intersect1d(train_index, val_index).size:
        raise ValueError("train and validation indices overlap")

    dtype = np.dtype(mlp.dtype)
    feature_seed = derived_seed(FEATURE_NAMESPACE, seed)
    init_seed = derived_seed(INIT_NAMESPACE, seed)
    shuffle_seed = derived_seed(SHUFFLE_NAMESPACE, seed)

    frequencies = fourier.draw(feature_seed)
    coords = normalizer.transform(x, y)
    train_features = fourier_features(
        coords[train_index], frequencies, fourier.include_raw, dtype
    )
    val_features = fourier_features(
        coords[val_index], frequencies, fourier.include_raw, dtype
    )

    # The target standardization IS label information, so unlike the coordinate
    # box it is fitted on training rows only.
    target_mean = float(target[train_index].mean())
    target_std = float(target[train_index].std(ddof=0))
    if target_std <= 0.0:
        raise ValueError("training target has zero variance")
    train_standardized = ((target[train_index] - target_mean) / target_std).astype(dtype)
    val_actual = target[val_index]

    parameters = init_parameters(train_features.shape[1], mlp, init_seed)
    optimizer = Adam(parameters, learning_rate=train_config.learning_rate)
    rng = np.random.default_rng(shuffle_seed)

    history: dict[str, list[float]] = {
        "epoch": [],
        "train_mse_standardized": [],
        "train_rmse_label_units": [],
        "val_rmse_label_units": [],
    }
    best_rmse = np.inf
    best_epoch = -1
    best_parameters = [(w.copy(), b.copy()) for w, b in parameters]
    n_train = len(train_index)

    for epoch in range(train_config.max_epochs):
        order = rng.permutation(n_train)
        epoch_loss = 0.0
        for start in range(0, n_train, train_config.batch_size):
            batch = order[start : start + train_config.batch_size]
            features = train_features[batch]
            actual = train_standardized[batch]
            prediction, activations = forward(features, parameters)
            gradients = backward(activations, parameters, prediction, actual)
            optimizer.step(parameters, gradients)
            epoch_loss += float(np.mean((prediction - actual) ** 2)) * len(batch)
        epoch_loss /= n_train

        val_prediction, _ = forward(val_features, parameters)
        val_rmse = float(
            np.sqrt(
                np.mean(
                    (val_prediction.astype(np.float64) * target_std + target_mean - val_actual)
                    ** 2
                )
            )
        )
        history["epoch"].append(epoch)
        history["train_mse_standardized"].append(epoch_loss)
        history["train_rmse_label_units"].append(float(np.sqrt(epoch_loss) * target_std))
        history["val_rmse_label_units"].append(val_rmse)
        if progress is not None:
            progress(epoch, epoch_loss, val_rmse)

        if val_rmse < best_rmse:
            best_rmse = val_rmse
            best_epoch = epoch
            best_parameters = [(w.copy(), b.copy()) for w, b in parameters]
        elif (
            epoch + 1 >= train_config.min_epochs
            and epoch - best_epoch >= train_config.patience
        ):
            break

    record = dict(provenance or {})
    record.update(
        {
            "train_config": train_config.to_dict(),
            "n_train": int(n_train),
            "n_val": int(len(val_index)),
            "epochs_run": int(len(history["epoch"])),
            "best_epoch": int(best_epoch),
            "best_val_rmse_label_units": float(best_rmse),
            "early_stopped": bool(len(history["epoch"]) < train_config.max_epochs),
        }
    )
    return TrainedModel(
        normalizer=normalizer,
        fourier=fourier,
        frequencies=frequencies,
        parameters=best_parameters,
        mlp=mlp,
        target_mean=target_mean,
        target_std=target_std,
        seeds={
            "seed": int(seed),
            "feature_seed": int(feature_seed),
            "init_seed": int(init_seed),
            "shuffle_seed": int(shuffle_seed),
        },
        history=history,
        provenance=record,
    )
