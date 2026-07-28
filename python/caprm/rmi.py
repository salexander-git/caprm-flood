"""Two-stage recursive model index over the B3b sorted Hilbert key array.

Kraska et al., *The Case for Learned Index Structures*, SIGMOD 2018. A root
linear model routes a key to one of ``n_leaves`` second-stage linear models;
that model predicts a position in the sorted array. Inference is four
multiply-adds, two clamps and two floors — no framework, no nonlinearity.

WHAT THE MODEL PREDICTS
-----------------------
The target is ``lower_bound`` position, matching ``seed_position`` in
``cpp/spatial_core/src/water_distance_hilbert.cpp`` exactly::

    rank(q) = |{i : keys[i] < q}|

For a key value that appears more than once, ``rank`` is the FIRST position of
the run. B3b measured 79 exact duplicate keys in 1,189,589 entries, so the
position mapping is not injective and the convention has to be stated before
an error bound means anything. It is recorded in the manifest as
``position_convention = "lower_bound_first_of_run"``.

TWO BOUNDS, NEITHER OF WHICH GATES CORRECTNESS
----------------------------------------------
``err_min`` / ``err_max``   measured over every key IN THE INDEX. This is the
                            academic deliverable: a model plus a proven error
                            bound is what makes the structure an index in
                            Kraska's sense rather than a heuristic.

``gap_err_min`` / ``gap_err_max``
                            measured over the WHOLE 64-bit key domain, so it
                            covers query keys, which are property-point keys
                            and are not index keys. This is an informative
                            window sizer.

Neither is operationally required. Nucleus 18.22: the seed seam is
correctness-neutral, proved and tested with ``--seed zero``, and the current
query path uses a fixed +/-64 window with no bound at all. A model that
predicts badly widens the first descent and slows the query; it cannot change
an emitted field. B5 should not build machinery as though these bounds gate
anything.

The domain bound is MEASURED, not derived. The argument for why a finite
candidate set suffices is in ``domain_candidate_keys``; the bound itself comes
from evaluating that set, and ``spot_check_gap_bound`` re-tests it on random
keys drawn from outside the candidate set.

THE FLOAT CONTRACT
------------------
Keys are 64-bit; float64 carries 53 bits of mantissa. The model therefore
operates on a rounded key, and Python (training and verification) and C++
(inference, B5) must round identically.

This is a STATED ASSUMPTION, not a proof. numpy guarantees round-to-nearest-
even for ``uint64 -> float64``. C++ does not: [conv.fpint] permits either
adjacent representable value when the integer is not exactly representable.
On x86-64 with SSE2 the conversion rounds to nearest under the default MXCSR
rounding mode, so the two agree in practice, and every measurement in this
project has been taken on that target. It is recorded in the manifest as an
assumption, and B5 should assert it rather than inherit it: the manifest
carries probe keys with their normalized ``x`` as hex bit patterns and their
predicted positions, so a rounding-mode mismatch fails loudly at model load.

The normalization constants are stored as the raw uint64 ``key_min`` and
``key_max`` rather than as decimal doubles, so C++ derives ``key_min_d`` and
``inv_span`` from integers and no decimal round-trip can add a second source
of difference on top of the one above.

Inference, stated once so B5 is transcription rather than design::

    xd   = (double) key
    x    = (xd - key_min_d) * inv_span
    j    = clamp(floor(root_a + root_b * x), 0, n_leaves - 1)
    p    = clamp(leaf_a[j] + leaf_b[j] * x, 0.0, n_keys - 1.0)
    pos  = (size_t) floor(p)
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np


# --------------------------------------------------------------------------
# Selection thresholds, declared BEFORE any model is trained on the real key
# array (Nucleus 18.12).
#
# The control to beat is the B3b binary search: 20.2376 key comparisons per
# query on average, 21 at worst, over 1,189,589 entries. The RMI's last-mile
# search over the recorded window costs ceil(log2(window + 1)) comparisons,
# plus one dependent miss on the leaf array that binary search does not pay.
# Requiring the last mile to be at most HALF the control leaves the total
# dependent-miss count clearly below the control once that extra access is
# charged; anything less is not a defensible win.
#
# The size cap is expressed against a measured project quantity rather than a
# round number: the model must stay under half the 9,516,712-byte Hilbert key
# array it augments (B3b manifest). There is no B-tree here, so against rung 4
# the model only ADDS bytes; the defensible size comparison is rung 5 against
# rung 3 (segment BVH, 119.8 MB at cap 25).
#
# THE RULE: among swept leaf counts within the size cap, take the one with the
# lowest mean last-mile probe count; break ties toward fewer leaves. Report
# separately whether the probe target was met. Minimising the metric under a
# budget is the right shape here — picking the SMALLEST qualifying model would
# trade a large search-side gain for bytes that are negligible against the
# 119.8 MB structure this path is being compared with.
# --------------------------------------------------------------------------
B3B_KEY_ARRAY_BYTES = 9_516_712
SELECTION_MAX_MEAN_LAST_MILE_PROBES = 10.0
SELECTION_MAX_MODEL_BYTES = B3B_KEY_ARRAY_BYTES // 2   # 4,758,356

CONTROL_MEAN_SEED_PROBES = 20.237640352780126   # B3b, countywide, measured
CONTROL_MAX_SEED_PROBES = 21                    # ceil(log2 1,189,589)
SEED_WINDOW_ENTRIES = 64                        # SEED_WINDOW in the C++

MODEL_MAGIC = b"CAPRMRMI"
MODEL_FORMAT_VERSION = 1
LEAF_STRIDE_BYTES = 32
HEADER_BYTES = 96
POSITION_CONVENTION = "lower_bound_first_of_run"

UINT64_MAX = np.uint64(2**64 - 1)
_ONE = np.uint64(1)
_TWO = np.uint64(2)

LEAF_DTYPE = np.dtype(
    [
        ("a", "<f8"),
        ("b", "<f8"),
        ("err_min", "<i4"),
        ("err_max", "<i4"),
        ("gap_err_min", "<i4"),
        ("gap_err_max", "<i4"),
    ],
    align=False,
)


# --------------------------------------------------------------------------
# Key array
# --------------------------------------------------------------------------
def load_key_array(path: Path) -> tuple[np.ndarray, str]:
    """Load the little-endian uint64 key dump and its SHA-256.

    The file is the sorted key array as the C++ index holds it, written by
    ``--dump-keys``, so the digest is the training-set checksum required by
    Nucleus 18.20 rather than a checksum of something reconstructed.
    """
    raw = Path(path).read_bytes()
    if len(raw) % 8 != 0:
        raise ValueError(
            f"{path}: {len(raw)} bytes is not a whole number of uint64 keys."
        )
    keys = np.frombuffer(raw, dtype="<u8")
    if keys.size == 0:
        raise ValueError(f"{path}: empty key array.")
    if not np.all(keys[:-1] <= keys[1:]):
        raise ValueError(
            f"{path}: keys are not sorted ascending. The RMI target is a "
            "monotone CDF; an unsorted array is a producer bug, not a model "
            "problem."
        )
    return keys, hashlib.sha256(raw).hexdigest()


def lower_bound_targets(keys: np.ndarray) -> np.ndarray:
    """Position of the first occurrence of each key: the ``lower_bound`` target.

    Equals ``np.searchsorted(keys, keys, side="left")`` but in O(n): the array
    is sorted, so each distinct value occupies one contiguous run.
    """
    n = keys.size
    is_run_start = np.empty(n, dtype=bool)
    is_run_start[0] = True
    np.not_equal(keys[1:], keys[:-1], out=is_run_start[1:])
    run_index = np.cumsum(is_run_start) - 1
    run_start = np.flatnonzero(is_run_start)
    return run_start[run_index].astype(np.int64, copy=False)


def normalize_keys(
    keys: np.ndarray, key_min: int, key_max: int
) -> np.ndarray:
    """Map uint64 keys onto ``x``, the value both stages consume.

    Mirrors the C++ inference expression exactly: convert to double, subtract
    the double of ``key_min``, multiply by the reciprocal of the span.
    """
    key_min_d = np.float64(np.uint64(key_min))
    key_max_d = np.float64(np.uint64(key_max))
    span = key_max_d - key_min_d
    if not np.isfinite(span) or span <= 0.0:
        raise ValueError("Key span is not positive; the array is degenerate.")
    inv_span = np.float64(1.0) / span
    return (keys.astype(np.float64) - key_min_d) * inv_span


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class RmiModel:
    n_keys: int
    key_min: int
    key_max: int
    root_a: float
    root_b: float
    leaf_a: np.ndarray          # float64[n_leaves]
    leaf_b: np.ndarray          # float64[n_leaves]
    err_min: np.ndarray         # int32[n_leaves], over the training keys
    err_max: np.ndarray         # int32[n_leaves], over the training keys
    gap_err_min: np.ndarray     # int32[n_leaves], over the whole key domain
    gap_err_max: np.ndarray     # int32[n_leaves], over the whole key domain
    keys_sha256: str

    @property
    def n_leaves(self) -> int:
        return int(self.leaf_a.size)

    @property
    def size_bytes(self) -> int:
        return HEADER_BYTES + LEAF_STRIDE_BYTES * self.n_leaves

    def route(self, x: np.ndarray) -> np.ndarray:
        raw = np.floor(self.root_a + self.root_b * x)
        return np.clip(raw, 0.0, float(self.n_leaves - 1)).astype(np.int64)

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(leaf_index, predicted_position)`` as C++ will compute them."""
        leaf = self.route(x)
        raw = self.leaf_a[leaf] + self.leaf_b[leaf] * x
        clamped = np.clip(raw, 0.0, float(self.n_keys - 1))
        return leaf, np.floor(clamped).astype(np.int64)

    def predict_keys(self, keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.predict(normalize_keys(keys, self.key_min, self.key_max))


def _empty_bounds(n_leaves: int) -> np.ndarray:
    return np.zeros(n_leaves, dtype=np.int32)


# --------------------------------------------------------------------------
# Fitting
# --------------------------------------------------------------------------
def _leaf_left_boundary_ranks(
    keys: np.ndarray, root_a: float, root_b: float, n_leaves: int
) -> np.ndarray:
    """True rank at the left key boundary of each leaf.

    Used to fill leaves that no training key routes to. Such a leaf is
    unreachable from the training array but reachable from a query key, so
    leaving it at zero would be a silent trap. A constant equal to the rank at
    its own left boundary is the monotone-consistent fill.
    """
    key_min_d = np.float64(keys[0])
    key_max_d = np.float64(keys[-1])
    span = key_max_d - key_min_d
    index = np.arange(n_leaves, dtype=np.float64)
    x_left = (index - root_a) / root_b
    boundary = np.clip(key_min_d + x_left * span, key_min_d, key_max_d)
    return np.searchsorted(keys, boundary.astype(np.uint64), side="left")


def fit_rmi(
    keys: np.ndarray,
    targets: np.ndarray,
    n_leaves: int,
    keys_sha256: str,
    measure_gap_bound: bool = True,
) -> RmiModel:
    """Fit the two-stage RMI. Deterministic; no RNG is consulted anywhere."""
    if n_leaves < 1:
        raise ValueError("n_leaves must be >= 1.")
    n = int(keys.size)
    key_min = int(keys[0])
    key_max = int(keys[-1])
    x = normalize_keys(keys, key_min, key_max)
    y = targets.astype(np.float64)

    # Stage 1. Least squares of position on x, centred for conditioning, then
    # rescaled so the root predicts a LEAF INDEX directly. Folding n_leaves/n
    # into the stored coefficients saves C++ a constant and a multiply.
    x_mean = float(x.mean())
    y_mean = float(y.mean())
    centred = x - x_mean
    suu = float(np.dot(centred, centred))
    if suu <= 0.0:
        raise ValueError("All keys collapse to one float64 value.")
    slope = float(np.dot(centred, y - y_mean)) / suu
    if slope <= 0.0:
        raise ValueError(
            "Root slope is non-positive; routing would not be monotone."
        )
    scale = float(n_leaves) / float(n)
    root_b = slope * scale
    root_a = (y_mean - slope * x_mean) * scale

    leaf = np.clip(
        np.floor(root_a + root_b * x), 0.0, float(n_leaves - 1)
    ).astype(np.int64)
    if np.any(np.diff(leaf) < 0):
        raise ValueError(
            "Leaf assignment is not monotone along the sorted array; the "
            "contiguity the per-leaf reductions rely on does not hold."
        )

    # Stage 2. One least-squares line per leaf, fitted on centred x so that
    # the normal equations do not cancel: a leaf spans a tiny slice of [0, 1],
    # and the uncentred form loses most of its digits there. Coefficients are
    # converted back to the (a + b*x) form C++ evaluates; that evaluation is
    # safe because the two large terms cancel to a position with absolute
    # error far below one array slot.
    counts = np.bincount(leaf, minlength=n_leaves)
    sum_x = np.bincount(leaf, weights=x, minlength=n_leaves)
    sum_y = np.bincount(leaf, weights=y, minlength=n_leaves)

    occupied = counts > 0
    safe_counts = np.where(occupied, counts, 1).astype(np.float64)
    leaf_x_mean = sum_x / safe_counts
    leaf_y_mean = sum_y / safe_counts

    delta_x = x - leaf_x_mean[leaf]
    delta_y = y - leaf_y_mean[leaf]
    leaf_suu = np.bincount(leaf, weights=delta_x * delta_x, minlength=n_leaves)
    leaf_suv = np.bincount(leaf, weights=delta_x * delta_y, minlength=n_leaves)

    fittable = occupied & (leaf_suu > 0.0)
    leaf_b = np.zeros(n_leaves, dtype=np.float64)
    leaf_b[fittable] = leaf_suv[fittable] / leaf_suu[fittable]
    leaf_a = leaf_y_mean - leaf_b * leaf_x_mean

    empty = ~occupied
    if np.any(empty):
        fill = _leaf_left_boundary_ranks(keys, root_a, root_b, n_leaves)
        leaf_a[empty] = fill[empty].astype(np.float64)
        leaf_b[empty] = 0.0

    unbounded = RmiModel(
        n_keys=n,
        key_min=key_min,
        key_max=key_max,
        root_a=root_a,
        root_b=root_b,
        leaf_a=leaf_a,
        leaf_b=leaf_b,
        err_min=_empty_bounds(n_leaves),
        err_max=_empty_bounds(n_leaves),
        gap_err_min=_empty_bounds(n_leaves),
        gap_err_max=_empty_bounds(n_leaves),
        keys_sha256=keys_sha256,
    )
    return with_measured_bounds(
        unbounded, keys, targets, measure_gap_bound=measure_gap_bound
    )


def with_measured_bounds(
    model: RmiModel,
    keys: np.ndarray,
    targets: np.ndarray,
    measure_gap_bound: bool = True,
) -> RmiModel:
    """Return ``model`` with both bound pairs measured against ``keys``.

    ``fit_rmi`` calls this. It is public so bounds can be re-measured on
    coefficients that came from somewhere else — a perturbed model in a test,
    or a future retune that reuses an existing fit.
    """
    err_min, err_max = _stored_key_bounds(model, keys, targets)
    updated = replace(model, err_min=err_min, err_max=err_max)
    if not measure_gap_bound:
        return updated
    gap_min, gap_max = measure_gap_bounds(updated, keys)
    return replace(updated, gap_err_min=gap_min, gap_err_max=gap_max)


def _per_leaf_extremes(
    leaf: np.ndarray, error: np.ndarray, n_leaves: int
) -> tuple[np.ndarray, np.ndarray]:
    """Per-leaf ``(min, max)`` of ``error``, given ``leaf`` non-decreasing.

    Routing is monotone in the key and every caller passes keys in ascending
    order, so each leaf occupies one contiguous block and ``reduceat`` over the
    block starts is an exact per-leaf reduction. Monotonicity is asserted by
    the callers rather than assumed here.
    """
    counts = np.bincount(leaf, minlength=n_leaves)
    occupied = counts > 0
    low = np.zeros(n_leaves, dtype=np.int64)
    high = np.zeros(n_leaves, dtype=np.int64)
    if np.any(occupied):
        starts = np.concatenate(([0], np.cumsum(counts)[:-1]))[occupied]
        low[occupied] = np.minimum.reduceat(error, starts)
        high[occupied] = np.maximum.reduceat(error, starts)
    return low, high


def _to_int32(values: np.ndarray, what: str) -> np.ndarray:
    limit = np.iinfo(np.int32)
    if values.min() < limit.min or values.max() > limit.max:
        raise ValueError(f"{what} does not fit in int32.")
    return values.astype(np.int32)


def _stored_key_bounds(
    model: RmiModel, keys: np.ndarray, targets: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    leaf, position = model.predict_keys(keys)
    if np.any(np.diff(leaf) < 0):
        raise ValueError("Routing is not monotone over the sorted key array.")
    low, high = _per_leaf_extremes(leaf, position - targets, model.n_leaves)
    return (
        _to_int32(low, "Prediction error"),
        _to_int32(high, "Prediction error"),
    )


# --------------------------------------------------------------------------
# The domain (gap) bound
# --------------------------------------------------------------------------
def leaf_boundary_keys(model: RmiModel) -> np.ndarray:
    """Smallest uint64 key routed to each leaf ``1 .. n_leaves - 1``.

    Found by binary search over the key domain rather than by inverting the
    root algebraically: the inverse would be a float computation whose
    rounding could put the boundary on the wrong side, and the point of this
    section is to measure rather than derive. Routing is monotone in the key
    (``root_b > 0`` is asserted at fit time, and both the double conversion
    and the affine normalization are monotone), so the search is well defined.
    """
    if model.n_leaves <= 1:
        return np.zeros(0, dtype=np.uint64)
    wanted = np.arange(1, model.n_leaves, dtype=np.int64)
    low = np.zeros(wanted.size, dtype=np.uint64)
    high = np.full(wanted.size, UINT64_MAX, dtype=np.uint64)
    for _ in range(65):
        active = low < high
        if not np.any(active):
            break
        middle = low + (high - low) // _TWO
        reached = (
            model.route(normalize_keys(middle, model.key_min, model.key_max))
            >= wanted
        )
        high = np.where(active & reached, middle, high)
        low = np.where(active & ~reached, middle + _ONE, low)
    if np.any(low < high):
        raise ValueError("Leaf-boundary search did not converge.")
    return low


def domain_candidate_keys(model: RmiModel, keys: np.ndarray) -> np.ndarray:
    """Every key at which the domain-wide maximum error can occur.

    Why a finite set suffices — this is the argument, and the measurement that
    follows is what makes it checkable rather than trusted:

      * ``rank`` is a step function that changes only at stored key values;
      * the routed leaf changes only at leaf boundaries;
      * on any maximal integer interval where both are constant, the predicted
        position is a floor of a clamp of an affine function of ``x``, and
        ``x`` is monotone in the key, so the prediction is monotone there and
        the error attains its extremes at the interval's endpoints.

    Those endpoints are exactly: each stored value and its two neighbours,
    each leaf boundary and its predecessor, and the two ends of the domain.

    ``spot_check_gap_bound`` re-tests the resulting bound on keys drawn from
    outside this set, so a missed breakpoint class shows up as a failure
    rather than as a quietly optimistic number.
    """
    distinct = np.unique(keys)
    pieces = [
        distinct,
        distinct[distinct > 0] - _ONE,
        distinct[distinct < UINT64_MAX] + _ONE,
        np.array([0, UINT64_MAX], dtype=np.uint64),
    ]
    boundaries = leaf_boundary_keys(model)
    if boundaries.size:
        pieces.append(boundaries)
        pieces.append(boundaries[boundaries > 0] - _ONE)
    return np.unique(np.concatenate(pieces))


def measure_gap_bounds(
    model: RmiModel, keys: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Per-leaf error extremes over the whole 64-bit key domain.

    Leaves no key can reach — possible when the root's float resolution is
    coarser than a leaf's width, so routing skips an index — get ``(0, 0)``
    and are reported as unreachable. They can never fire, so a bound for them
    is vacuous rather than wrong.
    """
    candidates = domain_candidate_keys(model, keys)
    leaf, position = model.predict_keys(candidates)
    if np.any(np.diff(leaf) < 0):
        raise ValueError("Routing is not monotone over the candidate set.")
    rank = np.searchsorted(keys, candidates, side="left")
    low, high = _per_leaf_extremes(leaf, position - rank, model.n_leaves)
    return (
        _to_int32(low, "Domain prediction error"),
        _to_int32(high, "Domain prediction error"),
    )


def reachable_leaves(model: RmiModel, keys: np.ndarray) -> np.ndarray:
    """Boolean mask of leaves some key in the domain actually routes to."""
    candidates = domain_candidate_keys(model, keys)
    leaf = model.route(
        normalize_keys(candidates, model.key_min, model.key_max)
    )
    return np.bincount(leaf, minlength=model.n_leaves) > 0


def spot_check_gap_bound(
    model: RmiModel, keys: np.ndarray, samples: int, seed: int
) -> dict[str, Any]:
    """Independently re-test the domain bound on uniformly random keys.

    The candidate-set argument is sound but it is an argument. This draws keys
    that are, with overwhelming probability, in none of the candidate classes
    and checks the bound holds anyway.
    """
    if samples <= 0:
        return {"samples": 0, "seed": int(seed), "violations": 0,
                "holds": True}
    generator = np.random.default_rng(seed)
    probes = np.sort(
        generator.integers(0, 2**64, size=samples, dtype=np.uint64)
    )
    leaf, position = model.predict_keys(probes)
    rank = np.searchsorted(keys, probes, side="left")
    error = position - rank
    low = model.gap_err_min[leaf].astype(np.int64)
    high = model.gap_err_max[leaf].astype(np.int64)
    violations = int(np.count_nonzero((error < low) | (error > high)))
    return {
        "samples": int(samples),
        "seed": int(seed),
        "violations": violations,
        "holds": violations == 0,
        "max_absolute_error": int(np.abs(error).max()),
    }


# --------------------------------------------------------------------------
# Exhaustive verification — the acceptance gate
# --------------------------------------------------------------------------
def ceil_log2(values: np.ndarray) -> np.ndarray:
    """``ceil(log2(v))`` for integer ``v >= 1``, exactly, without log rounding.

    ``frexp`` returns ``v = f * 2**e`` with ``f`` in ``[0.5, 1)``, so ``e`` is
    the bit length of ``v``; ``ceil(log2(v)) = bit_length(v - 1)``.
    """
    v = np.asarray(values, dtype=np.int64)
    if np.any(v < 1):
        raise ValueError("ceil_log2 requires values >= 1.")
    below = np.maximum(v - 1, 1).astype(np.float64)
    bits = np.frexp(below)[1].astype(np.int64)
    return np.where(v <= 1, 0, bits)


def _distribution(values: np.ndarray) -> dict[str, Any]:
    return {
        "max": int(values.max()),
        "mean": float(values.mean()),
        "p50": float(np.percentile(values, 50)),
        "p90": float(np.percentile(values, 90)),
        "p99": float(np.percentile(values, 99)),
        "p99.9": float(np.percentile(values, 99.9)),
    }


def verify_exhaustive(
    model: RmiModel, keys: np.ndarray, targets: np.ndarray
) -> dict[str, Any]:
    """Check every key against the recorded bounds and report per-model error.

    Not sampled. The model passed in should be the one round-tripped through
    the serialized artifact, so this also proves the file B5 will read carries
    the coefficients the bound was measured against.
    """
    if model.n_keys != int(keys.size):
        raise ValueError("Model n_keys does not match the key array length.")
    leaf, position = model.predict_keys(keys)
    error = position - targets

    # error = position - target, so target = position - error and the window
    # is [position - err_max, position - err_min]. The sign matters and is the
    # one place this is easy to get backwards, so it is asserted rather than
    # assumed.
    lower = position - model.err_max[leaf].astype(np.int64)
    upper = position - model.err_min[leaf].astype(np.int64)
    asymmetric_ok = bool(np.all((targets >= lower) & (targets <= upper)))

    symmetric = np.maximum(
        np.abs(model.err_min.astype(np.int64)),
        np.abs(model.err_max.astype(np.int64)),
    )
    reach = symmetric[leaf]
    symmetric_ok = bool(
        np.all((targets >= position - reach) & (targets <= position + reach))
    )

    gap_low = position - model.gap_err_max[leaf].astype(np.int64)
    gap_high = position - model.gap_err_min[leaf].astype(np.int64)
    gap_covers_stored = bool(
        np.all((targets >= gap_low) & (targets <= gap_high))
    )

    counts = np.bincount(leaf, minlength=model.n_leaves)
    occupied = counts > 0
    occupied_symmetric = symmetric[occupied]

    window = (
        model.err_max.astype(np.int64) - model.err_min.astype(np.int64) + 1
    )
    last_mile = ceil_log2(window + 1)[leaf]

    gap_window = (
        model.gap_err_max.astype(np.int64)
        - model.gap_err_min.astype(np.int64)
        + 1
    )
    gap_symmetric = np.maximum(
        np.abs(model.gap_err_min.astype(np.int64)),
        np.abs(model.gap_err_max.astype(np.int64)),
    )
    gap_last_mile = ceil_log2(gap_window + 1)[leaf]
    reachable = reachable_leaves(model, keys)

    absolute = np.abs(error)
    within_window = absolute <= SEED_WINDOW_ENTRIES
    return {
        "keys_verified": int(keys.size),
        "exhaustive": True,
        "bound_holds_asymmetric": asymmetric_ok,
        "bound_holds_symmetric": symmetric_ok,
        "gap_bound_covers_stored_keys": gap_covers_stored,
        "n_leaves": model.n_leaves,
        "leaves_occupied": int(occupied.sum()),
        "leaves_empty": int((~occupied).sum()),
        "leaf_load_max": int(counts.max()),
        "leaf_load_p50": float(np.percentile(counts[occupied], 50)),
        "leaf_load_p99": float(np.percentile(counts[occupied], 99)),
        "per_model_max_error": {
            **_distribution(occupied_symmetric),
            "leaves_at_max": int(
                (occupied_symmetric == occupied_symmetric.max()).sum()
            ),
        },
        "per_key_absolute_error": _distribution(absolute),
        "keys_within_seed_window": int(within_window.sum()),
        "fraction_within_seed_window": float(within_window.mean()),
        "seed_window_entries": SEED_WINDOW_ENTRIES,
        "last_mile_probes": {
            "mean": float(last_mile.mean()),
            "max": int(last_mile.max()),
            "p50": float(np.percentile(last_mile, 50)),
            "p99": float(np.percentile(last_mile, 99)),
        },
        "domain_bound": {
            "leaves_reachable": int(reachable.sum()),
            "leaves_unreachable": int((~reachable).sum()),
            "per_model_max_error": _distribution(gap_symmetric[reachable]),
            "last_mile_probes_mean_on_index_keys": float(gap_last_mile.mean()),
        },
        "control_mean_seed_probes": CONTROL_MEAN_SEED_PROBES,
        "control_max_seed_probes": CONTROL_MAX_SEED_PROBES,
        "model_bytes": model.size_bytes,
    }


def probe_records(
    model: RmiModel, keys: np.ndarray
) -> list[dict[str, Any]]:
    """Sentinel keys with their normalized ``x`` and predicted position.

    B5 asserts these at model load. A uint64-to-double rounding difference
    between the training platform and the inference platform changes ``x``,
    and therefore changes at least one of these, so the float assumption in
    the module docstring becomes a checked condition instead of an implicit
    one.
    """
    n = int(keys.size)
    indices = sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1})
    chosen = keys[np.asarray(indices, dtype=np.int64)]
    x = normalize_keys(chosen, model.key_min, model.key_max)
    leaf, position = model.predict(x)
    return [
        {
            "index": int(index),
            "key": int(key),
            "x_hex": float(value).hex(),
            "leaf": int(leaf_index),
            "predicted_position": int(predicted),
        }
        for index, key, value, leaf_index, predicted in zip(
            indices, chosen, x, leaf, position
        )
    ]


def equidepth_reference(
    keys: np.ndarray, targets: np.ndarray, n_leaves: int
) -> dict[str, Any]:
    """Diagnostic: the same leaf models under a PERFECT (equi-depth) router.

    This is NOT a shippable model — equi-depth routing needs stored boundaries,
    which is a lookup table rather than a linear stage. It is measured so the
    sweep can attribute error to the right cause: the gap between this and the
    fitted RMI is the cost of routing with one line, and this number itself is
    the cost of approximating each leaf's local CDF with one line. Reporting
    only the fitted number leaves those two confounded.
    """
    n = int(keys.size)
    x = normalize_keys(keys, int(keys[0]), int(keys[-1]))
    y = targets.astype(np.float64)

    block = (np.arange(n, dtype=np.int64) * n_leaves) // n
    counts = np.bincount(block, minlength=n_leaves)
    occupied = counts > 0
    safe = np.where(occupied, counts, 1).astype(np.float64)
    x_mean = np.bincount(block, weights=x, minlength=n_leaves) / safe
    y_mean = np.bincount(block, weights=y, minlength=n_leaves) / safe

    delta_x = x - x_mean[block]
    delta_y = y - y_mean[block]
    suu = np.bincount(block, weights=delta_x * delta_x, minlength=n_leaves)
    suv = np.bincount(block, weights=delta_x * delta_y, minlength=n_leaves)
    slope = np.zeros(n_leaves, dtype=np.float64)
    fittable = occupied & (suu > 0.0)
    slope[fittable] = suv[fittable] / suu[fittable]
    intercept = y_mean - slope * x_mean

    predicted = np.floor(
        np.clip(intercept[block] + slope[block] * x, 0.0, float(n - 1))
    ).astype(np.int64)
    error = predicted - targets
    low, high = _per_leaf_extremes(block, error, n_leaves)
    probes = ceil_log2((high - low + 2)[occupied])
    return {
        "n_leaves": n_leaves,
        "leaves_occupied": int(occupied.sum()),
        "max_error": int(np.abs(error).max()),
        "mean_last_mile_probes": float(
            np.average(probes, weights=counts[occupied].astype(np.float64))
        ),
    }


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------
_HEADER_STRUCT = struct.Struct("<8sIIQQQQdd32s")


def serialize(model: RmiModel) -> bytes:
    if _HEADER_STRUCT.size != HEADER_BYTES:
        raise AssertionError("Header struct size drifted from HEADER_BYTES.")
    if LEAF_DTYPE.itemsize != LEAF_STRIDE_BYTES:
        raise AssertionError("Leaf dtype size drifted from LEAF_STRIDE_BYTES.")
    header = _HEADER_STRUCT.pack(
        MODEL_MAGIC,
        MODEL_FORMAT_VERSION,
        LEAF_STRIDE_BYTES,
        model.n_keys,
        model.n_leaves,
        model.key_min,
        model.key_max,
        model.root_a,
        model.root_b,
        bytes.fromhex(model.keys_sha256),
    )
    leaves = np.empty(model.n_leaves, dtype=LEAF_DTYPE)
    leaves["a"] = model.leaf_a
    leaves["b"] = model.leaf_b
    leaves["err_min"] = model.err_min
    leaves["err_max"] = model.err_max
    leaves["gap_err_min"] = model.gap_err_min
    leaves["gap_err_max"] = model.gap_err_max
    return header + leaves.tobytes()


def deserialize(payload: bytes) -> RmiModel:
    if len(payload) < HEADER_BYTES:
        raise ValueError("Model file is shorter than its header.")
    (
        magic,
        version,
        stride,
        n_keys,
        n_leaves,
        key_min,
        key_max,
        root_a,
        root_b,
        digest,
    ) = _HEADER_STRUCT.unpack(payload[:HEADER_BYTES])
    if magic != MODEL_MAGIC:
        raise ValueError(f"Bad magic: {magic!r}")
    if version != MODEL_FORMAT_VERSION:
        raise ValueError(f"Unsupported model format version: {version}")
    if stride != LEAF_STRIDE_BYTES:
        raise ValueError(f"Unsupported leaf stride: {stride}")
    expected = HEADER_BYTES + stride * n_leaves
    if len(payload) != expected:
        raise ValueError(
            f"Model file is {len(payload)} bytes; header implies {expected}."
        )
    leaves = np.frombuffer(payload, dtype=LEAF_DTYPE, offset=HEADER_BYTES)
    return RmiModel(
        n_keys=int(n_keys),
        key_min=int(key_min),
        key_max=int(key_max),
        root_a=float(root_a),
        root_b=float(root_b),
        leaf_a=np.ascontiguousarray(leaves["a"]),
        leaf_b=np.ascontiguousarray(leaves["b"]),
        err_min=np.ascontiguousarray(leaves["err_min"]),
        err_max=np.ascontiguousarray(leaves["err_max"]),
        gap_err_min=np.ascontiguousarray(leaves["gap_err_min"]),
        gap_err_max=np.ascontiguousarray(leaves["gap_err_max"]),
        keys_sha256=digest.hex(),
    )