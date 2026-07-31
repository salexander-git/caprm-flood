"""C3: where the C2 surrogate fails, and why.

C3 explains a result. It does not improve one. Nothing here trains, retunes,
re-selects an operating point, or touches ``caprm.scoring``, the frozen v2
index, the C1 partition, or a C2 model. Every function is a pure array
transform; all file I/O lives in ``python/scripts/analyze_c3_residuals.py``.

The prediction under test, fixed in writing before C2 trained and stored in
``outputs/validation/c2_surrogate_manifest.json``:

    FEMA zones are discontinuities. 98.1 percent of properties sit at the same
    FEMA component and the index steps sharply across a zone boundary. A smooth
    network cannot represent a step, only a ramp. Residuals should therefore
    spike along zone boundaries and stay small elsewhere.

That sentence contains two separable claims and this module measures them
separately, because they can come apart:

    CLASS effect       the residual is large ON properties whose FEMA component
                       differs from the majority, whatever their position
    PROXIMITY effect   the residual is large NEAR a boundary, on properties
                       that are themselves in the majority class

A ramp fitted to a step produces both. A model that has simply never learned to
emit the minority level produces only the first. ``class_decomposition`` and
``bin_residuals`` restricted to the majority class answer the two questions, and
they are not the same question.

The boundary proxy
------------------
``boundary_distance_by_class`` gives, for each property, the metric distance to
the nearest property carrying a DIFFERENT FEMA component. Its limits, which
belong beside every number derived from it:

  * it is bounded below by property spacing, measured at C1 as a 24.4 m median
    nearest-neighbour distance, so a property sitting exactly on a polygon edge
    reads as tens of metres from a boundary rather than zero;
  * it locates a boundary only as precisely as the parcels sample it, so in
    unparcelled terrain — water, parkland, the rural north — it overstates;
  * it is a distance to a CHANGE IN CLASS, not to a polygon. Where an SFHA
    polygon contains no parcels at all, the proxy sees no boundary.

The exact alternative is distance to the NFHL polygon boundary. It is not used
here because the C3 inputs are declared as the four generated artifacts listed
in the chunk brief, and reaching back to the FEMA source would reintroduce an
ingestion dependency into an analysis chunk. The proxy is stated as a proxy and
its floor is reported beside it.

Controls
--------
A finding that has not been tested against a competitor is a hypothesis
(Nucleus 18.25). Four competitors are computed by the same estimator so they
are directly comparable:

  * label magnitude — the mandatory one. Residual magnitude tracks label
    magnitude, and without this control the finding degenerates to "the index
    is large near water", which is already known.
  * local neighbourhood range of the water and terrain components, by the same
    k-nearest-neighbour estimator applied to the FEMA component. FEMA gets no
    privileged estimator.
  * distance to the county edge, as the convex hull of the property set.
  * distance to the nearest TRAINING property, when the C1 split files are
    supplied. This is the competitor for anything that varies with the
    partition rather than with the field.

Aggregation
-----------
Pooled across the five seeds, on TEST ROWS ONLY. A single seed is a diagnostic
(Nucleus 18.32) and the blocked seed spread is 3.76 RMSE points, larger than
most effects C3 examines, so every headline table is also emitted per seed and
the pooled figure is never quoted without that spread.

Uncertainty is a CLUSTER bootstrap over property_id, not over rows: a property
appears in up to five pooled seeds and resampling rows would treat those five
appearances as five independent observations and understate the interval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

TOOL_VERSION = "caprm.error_analysis/c3.0"

#: Bin edges in metres for distance-to-boundary tables. Geometric from the C1
#: property-spacing floor (24.4 m median nearest-neighbour distance) upward, so
#: the first bin sits at the proxy's resolution limit rather than below it, and
#: the last bin is open because the blocked far field is a reported region and
#: not a tail to be truncated.
DEFAULT_DISTANCE_EDGES_M: tuple[float, ...] = (
    0.0, 25.0, 50.0, 100.0, 200.0, 400.0, 800.0, 1600.0, 3200.0, np.inf
)

#: The coarse bins used for the stratified label-decile x distance table, where
#: a nine-column table over ten deciles would be too thin per cell to read.
DEFAULT_COARSE_EDGES_M: tuple[float, ...] = (0.0, 100.0, 400.0, 1600.0, np.inf)

#: The majority FEMA component. 98.1 percent of the countywide workload sits
#: here; it is asserted from the data rather than assumed by
#: :func:`majority_class`.
MAJORITY_TOLERANCE = 0.5


class ErrorAnalysisError(RuntimeError):
    """Raised when an input cannot support the statistic being asked of it."""


# ---------------------------------------------------------------------------
# geometry: the boundary proxy and its competitors
# ---------------------------------------------------------------------------


def boundary_distance_by_class(
    x: np.ndarray, y: np.ndarray, class_value: np.ndarray
) -> np.ndarray:
    """Distance from each point to the nearest point of a DIFFERENT class.

    One cKDTree per class, then for each class the minimum over the trees of
    every other class. The alternative — one tree over the complement of each
    class — builds ``C`` trees of size ``n`` instead of ``C`` trees whose sizes
    sum to ``n``, and on this workload the complement of the majority class is
    the whole county five times over.

    A point whose class is the only class present has no different-class
    neighbour and returns ``inf`` rather than a sentinel that would average.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    class_value = np.asarray(class_value)
    if not (x.shape == y.shape == class_value.shape) or x.ndim != 1:
        raise ErrorAnalysisError("x, y and class_value must be 1-D and the same length")
    if x.size == 0:
        raise ErrorAnalysisError("no points")

    points = np.column_stack((x, y))
    classes = np.unique(class_value)
    trees = {c: cKDTree(points[class_value == c]) for c in classes}

    out = np.full(x.size, np.inf, dtype=np.float64)
    for c in classes:
        mask = class_value == c
        best = np.full(int(mask.sum()), np.inf, dtype=np.float64)
        for other in classes:
            if other == c:
                continue
            distance, _ = trees[other].query(points[mask], k=1, workers=-1)
            best = np.minimum(best, distance)
        out[mask] = best
    return out


def local_neighbourhood_range(
    x: np.ndarray, y: np.ndarray, values: np.ndarray, k: int = 9
) -> np.ndarray:
    """Range of ``values`` over the ``k`` nearest points, self included.

    The common-currency roughness estimator. Applied identically to the FEMA,
    water and terrain components so that "the FEMA field is rough here" and
    "the water field is rough here" are the same measurement on different
    inputs rather than two measurements that cannot be compared.

    ``k`` is clamped to the number of points, so the estimator degrades to the
    global range on a tiny input instead of raising inside a KD-tree.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if not (x.shape == y.shape == values.shape) or x.ndim != 1:
        raise ErrorAnalysisError("x, y and values must be 1-D and the same length")
    if k < 1:
        raise ErrorAnalysisError("k must be at least 1")
    k = min(int(k), x.size)
    tree = cKDTree(np.column_stack((x, y)))
    _, neighbours = tree.query(np.column_stack((x, y)), k=k, workers=-1)
    if neighbours.ndim == 1:
        neighbours = neighbours[:, None]
    sampled = values[neighbours]
    return sampled.max(axis=1) - sampled.min(axis=1)


def _point_segment_distance(
    px: np.ndarray, py: np.ndarray, ax: float, ay: float, bx: float, by: float
) -> np.ndarray:
    """Distance from points to one segment AB. Vectorised over points."""
    abx, aby = bx - ax, by - ay
    denominator = abx * abx + aby * aby
    if denominator == 0.0:
        return np.hypot(px - ax, py - ay)
    t = np.clip(((px - ax) * abx + (py - ay) * aby) / denominator, 0.0, 1.0)
    return np.hypot(px - (ax + t * abx), py - (ay + t * aby))


def distance_to_convex_hull(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Distance from each point to the convex hull boundary of the point set.

    The county-edge competitor. This is a data-derived stand-in for the county
    boundary and is deliberately NOT the study-area polygon: C3's inputs are the
    generated artifacts, and Monroe County's northern edge is Lake Ontario, so a
    hull over the parcels and the administrative boundary differ. The competitor
    only has to be able to fail, and this one can.

    The point-to-segment kernel here is local and exists to measure a hull. It
    is not a second implementation of the nearest-water kernel, whose exactness
    claim rests on the C++/Python comparison harness and which this must not be
    confused with.
    """
    from scipy.spatial import ConvexHull

    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 3:
        raise ErrorAnalysisError("a convex hull needs at least three points")
    points = np.column_stack((x, y))
    hull = ConvexHull(points)
    vertices = points[hull.vertices]
    closed = np.vstack([vertices, vertices[:1]])

    out = np.full(x.size, np.inf, dtype=np.float64)
    for a, b in zip(closed[:-1], closed[1:]):
        np.minimum(out, _point_segment_distance(x, y, a[0], a[1], b[0], b[1]), out=out)
    return out


def distance_to_nearest_training(
    x: np.ndarray, y: np.ndarray, train_index: np.ndarray, query_index: np.ndarray
) -> np.ndarray:
    """Distance from each queried point to the nearest TRAINING point.

    The partition competitor. Under the C1 blocked partition every test property
    is at least 2,125 m from every training and validation property by
    construction, so this quantity has a floor that the random control does not
    have, and any residual structure that follows it is a property of the
    partition rather than of the field.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    train_index = np.asarray(train_index, dtype=np.int64)
    query_index = np.asarray(query_index, dtype=np.int64)
    if train_index.size == 0:
        raise ErrorAnalysisError("no training rows")
    tree = cKDTree(np.column_stack((x[train_index], y[train_index])))
    distance, _ = tree.query(
        np.column_stack((x[query_index], y[query_index])), k=1, workers=-1
    )
    return np.asarray(distance, dtype=np.float64)


# ---------------------------------------------------------------------------
# residual statistics
# ---------------------------------------------------------------------------


def majority_class(class_value: np.ndarray) -> tuple[float, int, float]:
    """The most common class, its count, and its share. Measured, not assumed."""
    class_value = np.asarray(class_value)
    if class_value.size == 0:
        raise ErrorAnalysisError("no rows")
    values, counts = np.unique(class_value, return_counts=True)
    winner = int(np.argmax(counts))
    return float(values[winner]), int(counts[winner]), float(counts[winner] / class_value.size)


def _residual_stats(residual: np.ndarray, actual: np.ndarray) -> dict[str, float]:
    """Signed and absolute answer different questions; both are reported.

    A smooth ramp across a step is positive on one side and negative on the
    other, so a near-boundary mean signed residual can sit at ~0 while the mean
    absolute residual spikes. Reporting only the signed mean would miss that.
    Reporting only the absolute mean would miss the opposite case, where a
    residual population is entirely one-signed — which is what a model that
    never reaches the minority level produces, and which the signed column is
    the only thing that shows.
    """
    residual = np.asarray(residual, dtype=np.float64)
    actual = np.asarray(actual, dtype=np.float64)
    absolute = np.abs(residual)
    predicted = actual + residual
    return {
        "n": int(residual.size),
        "mean_abs": float(absolute.mean()),
        "median_abs": float(np.median(absolute)),
        "p90_abs": float(np.percentile(absolute, 90)),
        "mean_signed": float(residual.mean()),
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "fraction_under_predicted": float((residual < 0.0).mean()),
        "mean_label": float(actual.mean()),
        # The pair that carries the explanation. A model that has learned the
        # field tracks mean_label across bins; a model that has collapsed emits
        # a flat mean_predicted while mean_label sweeps. RMSE cannot tell those
        # apart (Nucleus 18.37) and neither can the residual columns above,
        # because a flat prediction and a boundary artifact both produce a
        # residual that rises at the extremes.
        "mean_predicted": float(predicted.mean()),
        "std_label": float(actual.std(ddof=1)) if actual.size > 1 else 0.0,
        "std_predicted": float(predicted.std(ddof=1)) if predicted.size > 1 else 0.0,
    }


def label_recovery(binned: pd.DataFrame) -> dict[str, float]:
    """How much of the label's across-bin sweep the prediction reproduces.

    The ratio of the predicted bin-mean range to the actual bin-mean range,
    over occupied bins. 1.0 is a model that tracks the field; 0.0 is a constant.
    This is the across-bin analogue of C2's variance ratio, and it is the
    statistic that separates "the residual spikes near boundaries" from "the
    prediction is flat and the truth is not", which produce the same residual
    curve and are not the same finding.

    Not a correlation: a model could track the sweep with the wrong slope and
    still score 1.0 here. It is reported beside the bin means, not instead.
    """
    occupied = binned[binned["n"] > 0]
    if len(occupied) < 2:
        raise ErrorAnalysisError("label recovery needs at least two occupied bins")
    label_span = float(occupied["mean_label"].max() - occupied["mean_label"].min())
    predicted_span = float(occupied["mean_predicted"].max() - occupied["mean_predicted"].min())
    return {
        "label_span": label_span,
        "predicted_span": predicted_span,
        "recovery_ratio": float(predicted_span / label_span) if label_span > 0 else float("nan"),
        "n_bins": int(len(occupied)),
    }


def bin_residuals(
    distance: np.ndarray,
    residual: np.ndarray,
    actual: np.ndarray,
    edges: Sequence[float] = DEFAULT_DISTANCE_EDGES_M,
) -> pd.DataFrame:
    """Residual statistics per distance bin, with ``n`` beside every statistic.

    98.1 percent of properties carry one FEMA component, so the near-boundary
    set is small. A spike over 40 properties is not the claim a spike over 4,000
    would be, and the count column is not optional decoration.
    """
    distance = np.asarray(distance, dtype=np.float64)
    residual = np.asarray(residual, dtype=np.float64)
    actual = np.asarray(actual, dtype=np.float64)
    if not (distance.shape == residual.shape == actual.shape):
        raise ErrorAnalysisError("distance, residual and actual must be the same length")

    edges = list(edges)
    codes = np.digitize(distance, edges[1:-1], right=False)
    rows = []
    for i in range(len(edges) - 1):
        mask = codes == i
        row = {"bin_index": i, "lower_m": edges[i], "upper_m": edges[i + 1], "n": 0}
        if mask.any():
            row.update(_residual_stats(residual[mask], actual[mask]))
        rows.append(row)
    return pd.DataFrame(rows)


def class_decomposition(
    class_value: np.ndarray, residual: np.ndarray, actual: np.ndarray
) -> pd.DataFrame:
    """Per-class residual statistics and share of squared error.

    The row share against the squared-error share is the whole class effect in
    two columns: if 1.9 percent of rows carry 30 percent of the squared error,
    the model's problem is a population, not a neighbourhood.
    """
    class_value = np.asarray(class_value)
    residual = np.asarray(residual, dtype=np.float64)
    actual = np.asarray(actual, dtype=np.float64)
    total_sse = float(np.sum(residual**2))
    rows = []
    for c in np.unique(class_value):
        mask = class_value == c
        stats = _residual_stats(residual[mask], actual[mask])
        stats["class_value"] = float(c)
        stats["row_share"] = float(mask.mean())
        sse = float(np.sum(residual[mask] ** 2))
        stats["sse"] = sse
        stats["sse_share"] = float(sse / total_sse) if total_sse > 0 else float("nan")
        rows.append(stats)
    frame = pd.DataFrame(rows)
    ordered = ["class_value", "n", "row_share", "sse_share"]
    return frame[ordered + [c for c in frame.columns if c not in ordered]]


def stratified_table(
    distance: np.ndarray,
    residual: np.ndarray,
    actual: np.ndarray,
    n_label_bins: int = 10,
    edges: Sequence[float] = DEFAULT_COARSE_EDGES_M,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mean absolute residual by (label quantile, distance bin), and its counts.

    This is the control the whole chunk turns on. Residual magnitude tracks
    label magnitude, and distance-to-boundary tracks label magnitude too, so a
    marginal table showing large residuals near boundaries is consistent with
    the boundary explaining nothing at all. Holding the label roughly fixed and
    then varying distance is what separates the two.

    Returns ``(mean_abs, counts)`` on the same index and columns.
    """
    distance = np.asarray(distance, dtype=np.float64)
    residual = np.asarray(residual, dtype=np.float64)
    actual = np.asarray(actual, dtype=np.float64)
    if residual.size == 0:
        raise ErrorAnalysisError("no rows to stratify")
    frame = pd.DataFrame(
        {
            "label_bin": pd.qcut(actual, n_label_bins, labels=False, duplicates="drop"),
            "distance_bin": pd.cut(distance, bins=list(edges), right=False),
            "abs_residual": np.abs(residual),
        }
    )
    grouped = frame.groupby(["label_bin", "distance_bin"], observed=False)["abs_residual"]
    mean_abs = grouped.mean().unstack("distance_bin")
    counts = grouped.size().unstack("distance_bin")
    return mean_abs, counts


# ---------------------------------------------------------------------------
# competitor comparison
# ---------------------------------------------------------------------------


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rho via Pearson on ranks. Ties averaged.

    Written here rather than called from ``scipy.stats`` so the tie handling is
    visible: the candidates include distances with exact ties at the property
    -spacing floor, and average ranks are what makes the comparison across
    candidates fair.
    """
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denominator = float(np.sqrt((ra**2).sum() * (rb**2).sum()))
    return float((ra * rb).sum() / denominator) if denominator > 0 else float("nan")


def competitor_ranking(
    candidates: Mapping[str, np.ndarray],
    residual: np.ndarray,
    actual: np.ndarray,
    n_label_bins: int = 10,
) -> pd.DataFrame:
    """Rank competing explanations of residual magnitude, marginally and net.

    Two columns, and the second is the one that decides:

    ``spearman_abs``          rho between the candidate and |residual| over all
                              rows. A marginal statistic; it cannot separate a
                              candidate from anything correlated with the label.
    ``spearman_within_label`` the same rho computed inside each label decile and
                              averaged with decile weights. A candidate that
                              survives this is explaining something the label
                              magnitude does not already explain.

    ``label_magnitude`` itself is passed in as a candidate. Stratification does
    not annihilate it — within a decile the label still varies, and if the label
    genuinely drives the error it will still rank — but it does remove the
    between-decile variation that inflates the marginal statistic. The tests
    show the attenuation on a fixture where a driver correlated with the label
    is the true cause: the label falls from a marginal 0.92 to a within-label
    0.22 while the driver stays at 1.00 and pure noise stays at 0.01.

    This is a control, not a proof of causation. Stratifying on ten deciles
    cannot separate two variables that are collinear inside every decile, and
    where that is the case the honest reading is that the two explanations are
    not distinguished by this data rather than that one of them won.
    """
    residual = np.asarray(residual, dtype=np.float64)
    actual = np.asarray(actual, dtype=np.float64)
    absolute = np.abs(residual)
    label_bin = pd.qcut(actual, n_label_bins, labels=False, duplicates="drop")

    rows = []
    for name, values in candidates.items():
        values = np.asarray(values, dtype=np.float64)
        if values.shape != absolute.shape:
            raise ErrorAnalysisError(f"candidate {name!r} has the wrong length")
        finite = np.isfinite(values)
        marginal = _spearman(values[finite], absolute[finite]) if finite.any() else float("nan")

        weighted, weight_total = 0.0, 0
        for b in np.unique(label_bin):
            mask = (label_bin == b) & finite
            if int(mask.sum()) < 30:
                continue
            rho = _spearman(values[mask], absolute[mask])
            if np.isfinite(rho):
                weighted += rho * int(mask.sum())
                weight_total += int(mask.sum())
        within = weighted / weight_total if weight_total else float("nan")
        # A candidate with no spread cannot rank, and a ranking table that omits
        # spread invites exactly the error made when reading this one: the
        # blocked test set is >= 2,125 m from training by construction, so
        # training_distance_m is range-compressed there and range-free on the
        # random control. Its rank difference between partitions is partly an
        # artifact of that, and the reader needs the numbers to see it.
        spread = values[finite]
        rows.append(
            {
                "candidate": name,
                "n_finite": int(finite.sum()),
                "spearman_abs": marginal,
                "spearman_within_label": within,
                "candidate_min": float(spread.min()) if spread.size else float("nan"),
                "candidate_p25": float(np.percentile(spread, 25)) if spread.size else float("nan"),
                "candidate_median": float(np.median(spread)) if spread.size else float("nan"),
                "candidate_p75": float(np.percentile(spread, 75)) if spread.size else float("nan"),
                "candidate_max": float(spread.max()) if spread.size else float("nan"),
            }
        )
    frame = pd.DataFrame(rows)
    return frame.reindex(
        frame["spearman_within_label"].abs().sort_values(ascending=False).index
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# uncertainty
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapConfig:
    n_resamples: int = 200
    seed: int = 20260730
    lower_percentile: float = 2.5
    upper_percentile: float = 97.5


def cluster_bootstrap_mean_abs(
    group_key: np.ndarray,
    cluster_key: np.ndarray,
    residual: np.ndarray,
    config: BootstrapConfig = BootstrapConfig(),
) -> pd.DataFrame:
    """Percentile interval on mean |residual| per group, resampling CLUSTERS.

    ``cluster_key`` is ``property_id``. A property appears in up to five pooled
    seeds; resampling rows would treat those appearances as independent and
    return an interval narrower than the data supports. Resampling properties
    and taking every row they own does not.

    Deterministic in ``config.seed``, which is recorded in the run manifest.
    """
    residual = np.asarray(residual, dtype=np.float64)
    absolute = np.abs(residual)
    frame = pd.DataFrame({"group": np.asarray(group_key), "cluster": np.asarray(cluster_key), "abs": absolute})

    clusters, cluster_codes = np.unique(frame["cluster"].to_numpy(), return_inverse=True)
    order = np.argsort(cluster_codes, kind="stable")
    sorted_codes = cluster_codes[order]
    starts = np.searchsorted(sorted_codes, np.arange(clusters.size), side="left")
    ends = np.searchsorted(sorted_codes, np.arange(clusters.size), side="right")

    groups = pd.unique(frame["group"])
    group_codes = pd.Categorical(frame["group"], categories=groups).codes
    absolute_sorted = absolute[order]
    group_sorted = group_codes[order]

    sizes = ends - starts
    rng = np.random.default_rng(config.seed)
    draws = np.empty((config.n_resamples, len(groups)), dtype=np.float64)
    for r in range(config.n_resamples):
        picked = rng.integers(0, clusters.size, clusters.size)
        # ragged expansion without a Python loop: repeat each picked cluster's
        # start by its size, then add a within-cluster offset built from the
        # exclusive cumulative sum of the picked sizes
        lengths = sizes[picked]
        total = int(lengths.sum())
        offsets = np.concatenate(([0], np.cumsum(lengths)[:-1]))
        idx = np.repeat(starts[picked], lengths) + (
            np.arange(total) - np.repeat(offsets, lengths)
        )
        totals = np.bincount(group_sorted[idx], weights=absolute_sorted[idx], minlength=len(groups))
        counts = np.bincount(group_sorted[idx], minlength=len(groups))
        with np.errstate(invalid="ignore", divide="ignore"):
            draws[r] = np.where(counts > 0, totals / np.maximum(counts, 1), np.nan)

    observed = frame.groupby("group", observed=True)["abs"].agg(["size", "mean"]).reindex(groups)
    return pd.DataFrame(
        {
            "group": groups,
            "n": observed["size"].to_numpy(),
            "mean_abs": observed["mean"].to_numpy(),
            "ci_low": np.nanpercentile(draws, config.lower_percentile, axis=0),
            "ci_high": np.nanpercentile(draws, config.upper_percentile, axis=0),
            "n_resamples": config.n_resamples,
            "bootstrap_seed": config.seed,
        }
    )


# ---------------------------------------------------------------------------
# the verdict
# ---------------------------------------------------------------------------


#: The declared decision rule for the proximity clause, fixed before the
#: tables were read: to count as a spatial boundary effect, the boundary
#: candidate must (a) carry the predicted SIGN — residual magnitude falling as
#: distance to a boundary grows — (b) reach at least a conventional small-effect
#: floor, and (c) be the strongest candidate in the field. Any one of these
#: alone is too easy to clear: a rho of -0.05 is not a spike, a rho of +0.11 is
#: the opposite of the prediction, and a candidate that beats label magnitude
#: while losing to water roughness has not explained anything FEMA-specific.
PROXIMITY_RHO_FLOOR = 0.10
BOUNDARY_CANDIDATE = "fema_boundary_distance_m"
LABEL_CANDIDATE = "label_magnitude"


def evaluate_prediction(
    binned_majority: pd.DataFrame,
    classes: pd.DataFrame,
    ranking: pd.DataFrame,
    majority_value: float,
    rho_floor: float = PROXIMITY_RHO_FLOOR,
) -> dict[str, Any]:
    """Turn the tables into an explicit CONFIRMED or REFUTED, by stated rules.

    The rules are arithmetic on the tables above and are declared here rather
    than read off a chart, so the verdict cannot drift with a reader's eye.

    The declared prediction contains three separable claims and each is decided
    on its own, because they can and do come apart:

    ``class_effect``      the MECHANISM. Minority-class RMSE exceeds
                          majority-class RMSE and the minority's share of
                          squared error exceeds its share of rows. This is the
                          discontinuity claim: a smooth network cannot emit a
                          step, so the properties on the far side of one carry
                          error out of all proportion to their number.
    ``proximity_effect``  the SPATIAL claim, "residuals spike along zone
                          boundaries", read as a claim about position rather
                          than about class. Decided inside the majority class,
                          after label stratification, against the full
                          competitor field, and with the predicted sign.
    ``small_elsewhere``   the second half of the sentence, and a real claim.
                          The far-field bin's mean |residual| must not exceed
                          the minimum over the interior bins.

    ``verdict`` is CONFIRMED only if all three hold. ``mechanism_confirmed`` and
    ``spatial_prediction_confirmed`` are reported separately, because a run in
    which the mechanism holds and the spatial reading fails is the informative
    outcome and collapsing it to one word would hide it.
    """
    minority = classes[classes["class_value"] != majority_value]
    majority = classes[classes["class_value"] == majority_value]
    if minority.empty or majority.empty:
        raise ErrorAnalysisError("class decomposition has no minority or no majority")

    minority_rmse = float(np.sqrt(minority["sse"].sum() / minority["n"].sum()))
    majority_rmse = float(majority["rmse"].iloc[0])
    minority_row_share = float(minority["row_share"].sum())
    minority_sse_share = float(minority["sse_share"].sum())
    class_effect = bool(
        minority_rmse > majority_rmse and minority_sse_share > minority_row_share
    )

    occupied = binned_majority[binned_majority["n"] > 0]
    interior = occupied[occupied["upper_m"] < np.inf]
    far = occupied[occupied["upper_m"] == np.inf]
    far_value = float(far["mean_abs"].iloc[0]) if not far.empty else float("nan")
    interior_min = float(interior["mean_abs"].min()) if not interior.empty else float("nan")
    small_elsewhere = bool(np.isfinite(far_value) and far_value <= interior_min)

    def within(name: str) -> float:
        hit = ranking[ranking["candidate"] == name]
        return float(hit["spearman_within_label"].iloc[0]) if not hit.empty else float("nan")

    boundary_within = within(BOUNDARY_CANDIDATE)
    label_within = within(LABEL_CANDIDATE)
    strongest = str(ranking.iloc[0]["candidate"]) if len(ranking) else ""
    correct_sign = bool(np.isfinite(boundary_within) and boundary_within < 0.0)
    clears_floor = bool(np.isfinite(boundary_within) and abs(boundary_within) >= rho_floor)
    is_strongest = bool(strongest == BOUNDARY_CANDIDATE)
    proximity_effect = bool(correct_sign and clears_floor and is_strongest)

    spatial = bool(proximity_effect and small_elsewhere)
    verdict = "CONFIRMED" if (class_effect and spatial) else "REFUTED"
    return {
        "verdict": verdict,
        "mechanism_confirmed": class_effect,
        "spatial_prediction_confirmed": spatial,
        "class_effect": class_effect,
        "proximity_effect": proximity_effect,
        "small_elsewhere": small_elsewhere,
        "proximity_correct_sign": correct_sign,
        "proximity_clears_floor": clears_floor,
        "proximity_is_strongest_candidate": is_strongest,
        "strongest_candidate": strongest,
        "rho_floor": float(rho_floor),
        "minority_rmse": minority_rmse,
        "majority_rmse": majority_rmse,
        "minority_row_share": minority_row_share,
        "minority_sse_share": minority_sse_share,
        "far_field_mean_abs": far_value,
        "interior_min_mean_abs": interior_min,
        "boundary_spearman_within_label": boundary_within,
        "label_spearman_within_label": label_within,
    }