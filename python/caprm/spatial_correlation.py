"""Measure the spatial correlation length of a field over the property workload.

C1 requires the spatial-block edge length to be justified against a correlation
length ESTIMATED FROM THE DATA. This module estimates it and, equally
importantly, measures how much the estimate depends on how it is estimated.

Method
------
The empirical semivariogram

    gamma(h) = 0.5 * E[(z_i - z_j)^2]  over pairs separated by h

is estimated in two passes because one pass cannot cover both ends of the range
at this workload size (267,362 points, ~3.6e10 pairs):

    short pass  KD-tree ball queries from sampled centres against ALL points.
                Resolves lags at parcel spacing, where the near-duplicate
                problem lives.
    long pass   chunked exhaustive pairwise over a random subsample. Resolves
                lags out to county scale, where a subsample is sufficient
                because pairs at long lags are abundant.

Both passes are seeded and deterministic: the same seed reproduces the same
bins, and ``python/scripts/measure_spatial_correlation.py`` verifies this by
rerunning.

Reported quantities
-------------------
``first_lag_at_ratio``  model-free. The smallest lag at which gamma reaches a
                        stated fraction of the sample variance. This is what
                        the block size is chosen against.
``fit_exponential``     a fitted range parameter, reported as a DIAGNOSTIC and
                        swept across fit windows, because on this field the
                        fitted range moves by more than an order of magnitude
                        with the fit window while R^2 stays above 0.94. A
                        number that depends that strongly on an unreported
                        parameter cannot carry a design decision (Nucleus
                        18.27).
``polynomial_detrend``  removes a low-order spatial trend so the local
                        correlation length can be separated from the regional
                        gradient. The variogram of a non-stationary field does
                        not plateau, and its long-lag behaviour describes the
                        trend rather than the correlation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

_MIN_PAIRS_FOR_FIT = 500


@dataclass(frozen=True)
class Variogram:
    """Binned empirical semivariogram."""

    lag_centre_m: np.ndarray
    semivariance: np.ndarray
    pair_count: np.ndarray
    bin_width_m: float
    sill: float
    method: str
    seed: int
    n_centres: int

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in ("lag_centre_m", "semivariance", "pair_count"):
            d[key] = np.asarray(d[key]).tolist()
        return d


def accumulate_bins(
    distances: np.ndarray,
    squared_differences: np.ndarray,
    bin_width_m: float,
    n_bins: int,
    sums: np.ndarray,
    counts: np.ndarray,
) -> None:
    """Add a batch of pairs into fixed-width lag bins, in place.

    Pairs at or beyond ``n_bins * bin_width_m`` are discarded rather than piled
    into the last bin: a bin whose width is not ``bin_width_m`` would be a
    different quantity wearing the same name.
    """
    if distances.shape != squared_differences.shape:
        raise ValueError("distances and squared_differences must have equal shape")
    finite = np.isfinite(distances) & np.isfinite(squared_differences)
    distances = distances[finite]
    squared_differences = squared_differences[finite]
    bin_index = (distances / bin_width_m).astype(np.int64)
    keep = (bin_index >= 0) & (bin_index < n_bins)
    bin_index = bin_index[keep]
    sums += np.bincount(bin_index, weights=squared_differences[keep], minlength=n_bins)[:n_bins]
    counts += np.bincount(bin_index, minlength=n_bins)[:n_bins]


def _finish(
    sums: np.ndarray,
    counts: np.ndarray,
    bin_width_m: float,
    sill: float,
    method: str,
    seed: int,
    n_centres: int,
) -> Variogram:
    with np.errstate(invalid="ignore", divide="ignore"):
        gamma = 0.5 * np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
    lags = (np.arange(len(counts)) + 0.5) * bin_width_m
    return Variogram(
        lag_centre_m=lags,
        semivariance=gamma,
        pair_count=counts.astype(np.int64),
        bin_width_m=float(bin_width_m),
        sill=float(sill),
        method=method,
        seed=int(seed),
        n_centres=int(n_centres),
    )


def variogram_short_range(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    max_lag_m: float = 3000.0,
    bin_width_m: float = 25.0,
    n_centres: int = 6000,
    seed: int = 20260730,
    batch: int = 250,
) -> Variogram:
    """Semivariogram at short lags: sampled centres against every point.

    Sampling centres rather than points keeps the estimator unbiased at every
    lag while bounding cost; each centre contributes all of its true neighbours,
    so the short-lag bins are computed at full workload density rather than at
    subsample density.
    """
    points = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
    z = np.asarray(z, float)
    if len(points) != len(z):
        raise ValueError("coordinate and value arrays must have equal length")
    n_centres = min(n_centres, len(points))
    tree = cKDTree(points)
    rng = np.random.default_rng(seed)
    centres = np.sort(rng.choice(len(points), size=n_centres, replace=False))

    n_bins = int(np.ceil(max_lag_m / bin_width_m))
    sums = np.zeros(n_bins)
    counts = np.zeros(n_bins)
    for start in range(0, n_centres, batch):
        block = centres[start : start + batch]
        neighbour_lists = tree.query_ball_point(points[block], r=max_lag_m)
        for centre, neighbours in zip(block, neighbour_lists):
            neighbours = np.asarray(neighbours, dtype=np.int64)
            neighbours = neighbours[neighbours != centre]
            if neighbours.size == 0:
                continue
            d = np.hypot(
                points[neighbours, 0] - points[centre, 0],
                points[neighbours, 1] - points[centre, 1],
            )
            sq = (z[neighbours] - z[centre]) ** 2
            accumulate_bins(d, sq, bin_width_m, n_bins, sums, counts)
        del neighbour_lists
    return _finish(sums, counts, bin_width_m, float(np.var(z, ddof=1)),
                   "short_range_ball_query", seed, n_centres)


def variogram_long_range(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    max_lag_m: float = 25000.0,
    bin_width_m: float = 250.0,
    n_sample: int = 20000,
    seed: int = 20260730,
    chunk: int = 1000,
) -> Variogram:
    """Semivariogram to county scale: exhaustive pairwise over a subsample."""
    points = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
    z = np.asarray(z, float)
    if len(points) != len(z):
        raise ValueError("coordinate and value arrays must have equal length")
    n_sample = min(n_sample, len(points))
    rng = np.random.default_rng(seed)
    sample = np.sort(rng.choice(len(points), size=n_sample, replace=False))
    p = points[sample]
    v = z[sample]

    n_bins = int(np.ceil(max_lag_m / bin_width_m))
    sums = np.zeros(n_bins)
    counts = np.zeros(n_bins)
    for start in range(0, n_sample, chunk):
        a = p[start : start + chunk]
        av = v[start : start + chunk]
        d = np.hypot(a[:, 0:1] - p[None, :, 0], a[:, 1:2] - p[None, :, 1])
        sq = (av[:, None] - v[None, :]) ** 2
        np.fill_diagonal(d[:, start : start + a.shape[0]], np.inf)
        accumulate_bins(d.ravel(), sq.ravel(), bin_width_m, n_bins, sums, counts)
    # every unordered pair was counted twice; the ratio sums/counts is unchanged
    return _finish(sums, counts, bin_width_m, float(np.var(z, ddof=1)),
                   "long_range_subsample_pairwise", seed, n_sample)


def first_lag_at_ratio(variogram: Variogram, ratio: float) -> float | None:
    """Smallest lag centre where gamma >= ratio * sill, or None if never.

    Model-free, and therefore the quantity the block edge is chosen against.
    Bins with no pairs are skipped rather than treated as zero.
    """
    gamma = np.asarray(variogram.semivariance, float)
    counts = np.asarray(variogram.pair_count)
    target = ratio * variogram.sill
    hit = np.where((counts > 0) & (gamma >= target))[0]
    if hit.size == 0:
        return None
    return float(variogram.lag_centre_m[hit[0]])


def fit_exponential(
    variogram: Variogram,
    max_lag_m: float,
    min_pairs: int = _MIN_PAIRS_FOR_FIT,
) -> dict[str, float]:
    """Fit gamma(h) = nugget + psill * (1 - exp(-h/a)) over [0, max_lag_m].

    DIAGNOSTIC ONLY. On this field the fitted ``a`` moves by more than an order
    of magnitude with ``max_lag_m`` at high R^2, so it is reported as a curve
    over fit windows and never quoted as a single range.
    """
    from scipy.optimize import curve_fit

    lags = np.asarray(variogram.lag_centre_m, float)
    gamma = np.asarray(variogram.semivariance, float)
    counts = np.asarray(variogram.pair_count)
    mask = (counts >= min_pairs) & (lags <= max_lag_m) & np.isfinite(gamma)
    if mask.sum() < 4:
        raise ValueError(f"not enough populated bins below {max_lag_m} m to fit")

    def model(h, nugget, psill, a):
        return nugget + psill * (1.0 - np.exp(-h / a))

    params, _ = curve_fit(
        model,
        lags[mask],
        gamma[mask],
        p0=[float(gamma[mask][0]), float(variogram.sill), float(max_lag_m / 3.0)],
        maxfev=60000,
    )
    predicted = model(lags[mask], *params)
    residual_ss = float(((gamma[mask] - predicted) ** 2).sum())
    total_ss = float(((gamma[mask] - gamma[mask].mean()) ** 2).sum())
    return {
        "fit_max_lag_m": float(max_lag_m),
        "nugget": float(params[0]),
        "partial_sill": float(params[1]),
        "range_parameter_a_m": float(params[2]),
        "practical_range_3a_m": float(3.0 * params[2]),
        "fitted_sill": float(params[0] + params[1]),
        "sample_variance": float(variogram.sill),
        "r_squared": float(1.0 - residual_ss / total_ss) if total_ss > 0 else float("nan"),
        "n_bins": int(mask.sum()),
    }


def polynomial_detrend(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, degree: int = 3
) -> tuple[np.ndarray, float]:
    """Remove a 2-D polynomial trend. Returns ``(residual, r_squared)``.

    Coordinates are centred and expressed in kilometres before the design
    matrix is built, so a degree-3 term does not overflow the condition number
    at EPSG:26918 easting magnitudes (~2.8e5).
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    z = np.asarray(z, float)
    xs = (x - x.mean()) / 1000.0
    ys = (y - y.mean()) / 1000.0
    columns = [
        (xs**i) * (ys**j)
        for i in range(degree + 1)
        for j in range(degree + 1 - i)
    ]
    design = np.column_stack(columns)
    beta, *_ = np.linalg.lstsq(design, z, rcond=None)
    residual = z - design @ beta
    total = float(np.var(z))
    r_squared = float(1.0 - np.var(residual) / total) if total > 0 else float("nan")
    return residual, r_squared


def nearest_neighbour_spacing(
    x: np.ndarray, y: np.ndarray, percentiles: tuple[float, ...] = (0, 1, 5, 25, 50, 75, 95, 100)
) -> dict[str, float]:
    """Distance from each property to its nearest other property, summarised.

    This sets the scale of the near-duplicate problem: it is the separation a
    RANDOM split leaves between a test row and its closest training row.
    """
    points = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
    tree = cKDTree(points)
    distances, _ = tree.query(points, k=2)
    nn = distances[:, 1]
    out = {f"p{p:g}_m": float(np.percentile(nn, p)) for p in percentiles}
    out["mean_m"] = float(nn.mean())
    out["zero_distance_rows"] = int((nn == 0.0).sum())
    return out