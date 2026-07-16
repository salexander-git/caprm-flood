from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCORING_POLICY_VERSION = "preliminary_exposure_index_v2"

# Four independent components, each with a declared weight.
#
# These are the complete set of scoring weights. No component applies an
# internal sub-weight, so this dict plus the evidence tables are sufficient
# to reproduce the index. That property is required: a manifest recording
# these weights must be enough for a third party to recompute the result.
#
# The values are inherited from the retired nested policy, which applied
# 0.25 to a terrain component internally split 0.60 / 0.40:
#
#     0.25 * 0.60 = 0.15    terrain_absolute
#     0.25 * 0.40 = 0.10    terrain_relative
#
# Scoring is linear, so the flat and nested forms are algebraically
# identical. Verified across the countywide workload to a maximum absolute
# difference of 5.1e-13, and locked by
# test_flat_weights_reproduce_legacy_nested_policy.
DEFAULT_WEIGHTS = {
    "fema": 0.40,
    "water": 0.35,
    "terrain_absolute": 0.15,
    "terrain_relative": 0.10,
}

COMPONENT_NAMES = tuple(DEFAULT_WEIGHTS)

# Decimal places the composite is rounded to before it is ranked or stored.
#
# Under any percentile-based weighting the composite lies on a lattice.
# Each percentile component is rank * 100/n with ranks in half steps, so
# with the default weights the composite is 0.40*C_fema plus a multiple of
# 2.5/n, about 9.4e-6 for the countywide workload. Distinct rank triples
# collide on that lattice constantly: many properties have mathematically
# identical composites.
#
# Float arithmetic separates a colliding pair by around 1e-14, depending on
# operation order. Ranking the unrounded value therefore imposes an
# ordering on properties that are tied in substance, and the ordering comes
# from rounding order rather than from evidence. It also means the stored
# percentile cannot be reproduced from the stored index, because writing
# the index at 12 decimal places re-merges the pair.
#
# Rounding at 1e-9 sits four orders of magnitude below the smallest
# distinction the lattice can express and five above float noise. It merges
# only values that are tied in substance, and it makes the artifact
# reproducible from itself.
COMPOSITE_DECIMALS = 9

# Mapped FEMA flood-hazard zones in ascending severity.
#
# A matched property carrying any zone absent from this table raises rather
# than falling through to a default. A silent default would score an
# unmapped-but-real zone below zone X, inverting the severity ordering with
# no error. Extend this table deliberately, after deciding where the new
# zone belongs in the ordering.
FEMA_ZONE_SCORES = {
    "X": 10.0,
    "AO": 80.0,
    "A": 90.0,
    "AE": 95.0,
    "VE": 100.0,
}

# Score for a property no flood-hazard polygon contains. This is an absence
# of evidence, not an assertion of low hazard.
UNMATCHED_FEMA_SCORE = 0.0

EVIDENCE_REQUIRED_COLUMNS = {
    "property_id",
    "matched_fema_polygon",
    "fema_zone",
    "is_sfha",
    "nearest_water_distance_m",
    "distance_crs",
}

# terrain_slope_degrees is deliberately absent. Slope is extracted and
# preserved as terrain evidence but does not enter any component, so
# requiring it here would reject a terrain table over a column the scoring
# layer never reads.
TERRAIN_REQUIRED_COLUMNS = {
    "property_id",
    "terrain_elevation_m",
    "terrain_relative_elevation_m",
    "terrain_crs",
}

COMPONENT_COLUMNS = {
    "fema": "fema_component_0_100",
    "water": "water_component_0_100",
    "terrain_absolute": "terrain_absolute_component_0_100",
    "terrain_relative": "terrain_relative_component_0_100",
}

OUTPUT_COLUMNS = [
    "property_id",
    "fema_component_0_100",
    "water_component_0_100",
    "terrain_absolute_component_0_100",
    "terrain_relative_component_0_100",
    "exposure_index_0_100",
    "exposure_percentile",
    "scoring_policy_version",
]


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def require_columns(
    dataframe: pd.DataFrame,
    required: set[str],
    table_name: str,
) -> None:
    missing = sorted(required - set(dataframe.columns))

    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {missing}"
        )


def normalize_string(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip()
    return normalized.mask(normalized.eq(""))


def strict_bool(series: pd.Series, column_name: str) -> pd.Series:
    true_values = {"true", "t", "1", "yes", "y"}
    false_values = {"false", "f", "0", "no", "n"}

    parsed: list[bool] = []

    for row_number, value in enumerate(series.tolist(), start=2):
        if pd.isna(value):
            raise ValueError(
                f"{column_name} contains a missing Boolean at row {row_number}."
            )

        if isinstance(value, (bool, np.bool_)):
            parsed.append(bool(value))
            continue

        text = str(value).strip().lower()

        if text in true_values:
            parsed.append(True)
            continue

        if text in false_values:
            parsed.append(False)
            continue

        raise ValueError(
            f"{column_name} contains an invalid Boolean at row "
            f"{row_number}: {value!r}"
        )

    return pd.Series(parsed, index=series.index, dtype="bool")


def validate_property_ids(
    dataframe: pd.DataFrame,
    table_name: str,
) -> None:
    dataframe["property_id"] = normalize_string(dataframe["property_id"])

    if dataframe["property_id"].isna().any():
        raise ValueError(f"{table_name} contains missing property IDs.")

    if dataframe["property_id"].duplicated().any():
        raise ValueError(f"{table_name} contains duplicate property IDs.")


def spearman_correlation(left: pd.Series, right: pd.Series) -> float | None:
    """
    Rank correlation between two series, computed without scipy.

    Spearman's rho is the Pearson correlation of the ranks. Ranking first
    and then taking the default Pearson correlation is exactly equivalent
    to pandas' method="spearman" with average tie handling, which is the
    correct definition when ties are present.

    Computing it explicitly serves two purposes. It avoids adding scipy as
    a dependency for a single statistic, and it avoids relying on a pandas
    asymmetry: DataFrame.corr(method="spearman") uses an internal
    implementation, while Series.corr(method="spearman") routes through
    scipy.stats.spearmanr.

    Returns None when either input is constant, because rank correlation
    against a series with no ordering is undefined rather than zero.
    """
    correlation = left.rank().corr(right.rank())

    return float(correlation) if pd.notna(correlation) else None


def percentile_score(
    series: pd.Series,
    higher_value_is_higher_exposure: bool,
) -> pd.Series:
    """
    Rank a numeric evidence field as a percentile in (0, 100].

    Direction is applied by negating the input rather than reversing the
    rank, which keeps one code path for both directions.

    Ties receive the average of the ranks they span, so the result is
    deterministic and independent of input row order.

    The transform is rank-preserving and magnitude-destroying: only the
    ordering of the input survives. It is also distribution-dependent,
    computed over the rows supplied, so scoring a subset yields different
    scores for the same property.
    """
    numeric = pd.to_numeric(series, errors="raise").astype("float64")

    if (~np.isfinite(numeric)).any():
        raise ValueError("Cannot score nonfinite numeric values.")

    scoring_values = numeric if higher_value_is_higher_exposure else -numeric

    if scoring_values.nunique() == 1:
        # A constant input carries no ranking information. Returning the
        # midpoint is explicit about that rather than asserting a false
        # ordering.
        return pd.Series(50.0, index=series.index, dtype="float64")

    return (
        scoring_values.rank(method="average", pct=True)
        .astype("float64")
        .mul(100.0)
    )


def fema_component_score(evidence: pd.DataFrame) -> pd.Series:
    """
    Score mapped FEMA flood-hazard severity on an absolute scale.

    This is the only component that is not distribution-dependent: a zone
    maps to the same score regardless of what other properties are present.

    is_sfha is validated but does not contribute to the score. Special
    Flood Hazard Area status is implied by the zone, so scoring on both
    would double-count one signal.
    """
    matched = strict_bool(
        evidence["matched_fema_polygon"],
        "matched_fema_polygon",
    )
    is_sfha = strict_bool(evidence["is_sfha"], "is_sfha")
    zones = normalize_string(evidence["fema_zone"]).str.upper()

    # A property cannot be in a Special Flood Hazard Area without being
    # inside a mapped flood-hazard polygon. This is a FEMA invariant, not
    # a property of one dataset.
    invalid_sfha = is_sfha & ~matched

    if invalid_sfha.any():
        examples = evidence.loc[invalid_sfha, "property_id"].head(10).tolist()
        raise ValueError(
            "Evidence marks properties as SFHA that did not match a FEMA "
            f"polygon: {examples}"
        )

    known_zone = (
        zones.isin(set(FEMA_ZONE_SCORES)).fillna(False).astype(bool)
    )

    unrecognized = matched & ~known_zone

    if unrecognized.any():
        observed = sorted(
            zones[unrecognized].dropna().unique().tolist()
        )
        examples = evidence.loc[unrecognized, "property_id"].head(10).tolist()

        raise ValueError(
            "Matched properties carry FEMA zones absent from "
            f"FEMA_ZONE_SCORES: {observed}. Example property IDs: "
            f"{examples}. Extend FEMA_ZONE_SCORES deliberately after "
            "deciding where these zones belong in the severity ordering. "
            "Do not allow them to fall through to the unmatched default, "
            "which would score them below zone X."
        )

    score = pd.Series(
        UNMATCHED_FEMA_SCORE,
        index=evidence.index,
        dtype="float64",
    )

    for zone, value in FEMA_ZONE_SCORES.items():
        zone_matches = zones.eq(zone).fillna(False).astype(bool)
        score.loc[matched & zone_matches] = value

    return score


def water_component_score(evidence: pd.DataFrame) -> pd.Series:
    """
    Rank properties by proximity to the nearest mapped water feature.

    Nearer water implies higher exposure, so the distance rank is inverted.
    There is no threshold, decay curve, or cap: the transform is pure rank
    inversion, and physical magnitude is discarded.
    """
    distances = pd.to_numeric(
        evidence["nearest_water_distance_m"],
        errors="raise",
    ).astype("float64")

    if (~np.isfinite(distances)).any():
        raise ValueError("Nearest-water distances must be finite.")

    if distances.lt(0).any():
        raise ValueError("Nearest-water distances cannot be negative.")

    return percentile_score(
        distances,
        higher_value_is_higher_exposure=False,
    )


def terrain_absolute_component_score(terrain: pd.DataFrame) -> pd.Series:
    """
    Rank properties by absolute ground elevation.

    Lower elevation implies higher exposure, so the rank is inverted.
    """
    return percentile_score(
        terrain["terrain_elevation_m"],
        higher_value_is_higher_exposure=False,
    )


def terrain_relative_component_score(terrain: pd.DataFrame) -> pd.Series:
    """
    Rank properties by elevation relative to their local neighborhood.

    Lower relative elevation means the property sits in a local depression,
    which implies higher exposure, so the rank is inverted.

    This measures something different from absolute elevation: a property
    can sit high in the county and low within its immediate surroundings,
    or the reverse.
    """
    return percentile_score(
        terrain["terrain_relative_elevation_m"],
        higher_value_is_higher_exposure=False,
    )


COMPONENT_SCORERS = {
    "fema": fema_component_score,
    "water": water_component_score,
    "terrain_absolute": terrain_absolute_component_score,
    "terrain_relative": terrain_relative_component_score,
}


def validate_weights(weights: dict[str, float]) -> dict[str, float]:
    required = set(COMPONENT_NAMES)

    if set(weights) != required:
        raise ValueError(
            f"Scoring weights must contain exactly: {sorted(required)}"
        )

    numeric = {key: float(value) for key, value in weights.items()}

    if any(value < 0 for value in numeric.values()):
        raise ValueError("Scoring weights cannot be negative.")

    total = sum(numeric.values())

    if not np.isclose(total, 1.0):
        raise ValueError(f"Scoring weights must sum to 1.0; observed {total}.")

    return numeric


def build_exposure_index(
    evidence: pd.DataFrame,
    terrain: pd.DataFrame,
    expected_distance_crs: str = "EPSG:26918",
    expected_terrain_crs: str = "EPSG:26918",
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    require_columns(
        evidence,
        EVIDENCE_REQUIRED_COLUMNS,
        "Integrated flood evidence",
    )

    require_columns(
        terrain,
        TERRAIN_REQUIRED_COLUMNS,
        "Terrain evidence",
    )

    evidence = evidence.copy()
    terrain = terrain.copy()

    validate_property_ids(evidence, "Integrated flood evidence")
    validate_property_ids(terrain, "Terrain evidence")

    evidence_crs = set(normalize_string(evidence["distance_crs"]).dropna())

    if evidence_crs != {expected_distance_crs}:
        raise ValueError(
            f"Evidence distance CRS mismatch: {sorted(evidence_crs)}"
        )

    terrain_crs = set(normalize_string(terrain["terrain_crs"]).dropna())

    if terrain_crs != {expected_terrain_crs}:
        raise ValueError(
            f"Terrain CRS mismatch: {sorted(terrain_crs)}"
        )

    merged = evidence[sorted(EVIDENCE_REQUIRED_COLUMNS)].merge(
        terrain[sorted(TERRAIN_REQUIRED_COLUMNS)],
        on="property_id",
        how="inner",
        validate="one_to_one",
    )

    if len(merged) != len(evidence):
        raise ValueError("Scoring merge lost property rows.")

    scoring_weights = validate_weights(weights or DEFAULT_WEIGHTS)

    for name in COMPONENT_NAMES:
        merged[COMPONENT_COLUMNS[name]] = COMPONENT_SCORERS[name](merged)

    merged["exposure_index_0_100"] = sum(
        scoring_weights[name] * merged[COMPONENT_COLUMNS[name]]
        for name in COMPONENT_NAMES
    ).round(COMPOSITE_DECIMALS)

    # Ranked from the rounded composite, so properties whose components
    # combine to the same value share a rank rather than being ordered by
    # float noise. This also makes the stored percentile reproducible from
    # the stored index.
    merged["exposure_percentile"] = percentile_score(
        merged["exposure_index_0_100"],
        higher_value_is_higher_exposure=True,
    )

    merged["scoring_policy_version"] = SCORING_POLICY_VERSION

    bounded_columns = [
        *COMPONENT_COLUMNS.values(),
        "exposure_index_0_100",
        "exposure_percentile",
    ]

    for column in bounded_columns:
        # Out of range is treated as a bug, not corrected. A convex
        # combination of values in [0, 100] cannot leave [0, 100], so a
        # violation means a component is misbehaving.
        if merged[column].lt(0).any() or merged[column].gt(100).any():
            raise RuntimeError(f"{column} is outside the 0-100 range.")

    return merged[OUTPUT_COLUMNS].sort_values(
        "property_id",
        kind="stable",
    ).reset_index(drop=True)


def component_influence(
    index: pd.DataFrame,
    weights: dict[str, float],
) -> dict[str, Any]:
    """
    Measure how much each component actually moves the composite.

    Nominal weight is not influence. Influence scales with weight times
    spread, and the components do not have equal spread: percentile
    components are uniform by construction, while the FEMA component is
    concentrated on a small number of values.

    variance_share is Cov(w_i * C_i, I) / Var(I). By linearity of
    covariance, sum_i Cov(w_i * C_i, I) = Cov(I, I) = Var(I), so the
    shares sum to exactly 1.0 without assuming the components are
    uncorrelated.
    """
    composite = index["exposure_index_0_100"]
    composite_variance = float(composite.var())

    records: dict[str, Any] = {}

    for name in COMPONENT_NAMES:
        column = index[COMPONENT_COLUMNS[name]]
        contribution = weights[name] * column

        covariance = float(contribution.cov(composite))

        records[name] = {
            "weight": float(weights[name]),
            "component_standard_deviation": float(column.std()),
            "weighted_standard_deviation": float(contribution.std()),
            "variance_share": (
                float(covariance / composite_variance)
                if composite_variance > 0
                else None
            ),
            "spearman_with_index": spearman_correlation(column, composite),
        }

    return {
        "index_standard_deviation": float(composite.std()),
        "method": (
            "variance_share is Cov(w_i * C_i, I) / Var(I). Shares sum to "
            "1.0 exactly by linearity of covariance and do not assume the "
            "components are uncorrelated. Nominal weight and measured "
            "influence diverge when components have unequal spread."
        ),
        "components": records,
    }


def summarize_exposure_index(
    index: pd.DataFrame,
    weights: dict[str, float],
) -> dict[str, Any]:
    """
    Describe a generated index.

    weights is required rather than defaulted. Reporting DEFAULT_WEIGHTS
    when a caller supplied something else would make every alternative
    scenario claim the default configuration, which is the failure this
    signature exists to prevent.
    """
    require_columns(
        index,
        set(OUTPUT_COLUMNS),
        "Exposure index",
    )

    validate_property_ids(index, "Exposure index")

    scoring_weights = validate_weights(weights)

    return {
        "property_count": int(len(index)),
        "unique_property_ids": int(index["property_id"].nunique()),
        "minimum_exposure_index": float(index["exposure_index_0_100"].min()),
        "maximum_exposure_index": float(index["exposure_index_0_100"].max()),
        "mean_exposure_index": float(index["exposure_index_0_100"].mean()),
        "median_exposure_index": float(index["exposure_index_0_100"].median()),
        "minimum_exposure_percentile": float(
            index["exposure_percentile"].min()
        ),
        "maximum_exposure_percentile": float(
            index["exposure_percentile"].max()
        ),
        "component_means": {
            name: float(index[COMPONENT_COLUMNS[name]].mean())
            for name in COMPONENT_NAMES
        },
        "component_influence": component_influence(index, scoring_weights),
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "weights": scoring_weights,
    }