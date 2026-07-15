from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCORING_POLICY_VERSION = "preliminary_exposure_index_v1"

DEFAULT_WEIGHTS = {
    "fema": 0.40,
    "water": 0.35,
    "terrain": 0.25,
}

EVIDENCE_REQUIRED_COLUMNS = {
    "property_id",
    "matched_fema_polygon",
    "fema_zone",
    "is_sfha",
    "nearest_water_distance_m",
    "distance_crs",
}

TERRAIN_REQUIRED_COLUMNS = {
    "property_id",
    "terrain_elevation_m",
    "terrain_relative_elevation_m",
    "terrain_slope_degrees",
    "terrain_crs",
}

OUTPUT_COLUMNS = [
    "property_id",
    "fema_component_0_100",
    "water_component_0_100",
    "terrain_component_0_100",
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


def percentile_score(
    series: pd.Series,
    higher_value_is_higher_exposure: bool,
) -> pd.Series:
    numeric = pd.to_numeric(series, errors="raise").astype("float64")

    if (~np.isfinite(numeric)).any():
        raise ValueError("Cannot score nonfinite numeric values.")

    scoring_values = numeric if higher_value_is_higher_exposure else -numeric

    if scoring_values.nunique() == 1:
        return pd.Series(50.0, index=series.index, dtype="float64")

    return (
        scoring_values.rank(method="average", pct=True)
        .astype("float64")
        .mul(100.0)
    )


def fema_component_score(evidence: pd.DataFrame) -> pd.Series:
    is_sfha = strict_bool(evidence["is_sfha"], "is_sfha")
    matched = strict_bool(
        evidence["matched_fema_polygon"],
        "matched_fema_polygon",
    )
    zones = normalize_string(evidence["fema_zone"]).str.upper()

    score = pd.Series(0.0, index=evidence.index, dtype="float64")

    score.loc[matched & zones.eq("X")] = 10.0
    score.loc[matched & zones.eq("AO")] = 80.0
    score.loc[matched & zones.eq("A")] = 90.0
    score.loc[matched & zones.eq("AE")] = 95.0
    score.loc[matched & zones.eq("VE")] = 100.0
    score.loc[is_sfha & score.lt(80.0)] = 90.0

    return score


def water_component_score(evidence: pd.DataFrame) -> pd.Series:
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


def terrain_component_score(terrain: pd.DataFrame) -> pd.Series:
    low_absolute = percentile_score(
        terrain["terrain_elevation_m"],
        higher_value_is_higher_exposure=False,
    )

    low_relative = percentile_score(
        terrain["terrain_relative_elevation_m"],
        higher_value_is_higher_exposure=False,
    )

    return (0.60 * low_absolute) + (0.40 * low_relative)


def validate_weights(weights: dict[str, float]) -> dict[str, float]:
    required = {"fema", "water", "terrain"}

    if set(weights) != required:
        raise ValueError(f"Scoring weights must contain exactly: {sorted(required)}")

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

    merged["fema_component_0_100"] = fema_component_score(merged)
    merged["water_component_0_100"] = water_component_score(merged)
    merged["terrain_component_0_100"] = terrain_component_score(merged)

    merged["exposure_index_0_100"] = (
        scoring_weights["fema"] * merged["fema_component_0_100"]
        + scoring_weights["water"] * merged["water_component_0_100"]
        + scoring_weights["terrain"] * merged["terrain_component_0_100"]
    )

    merged["exposure_percentile"] = percentile_score(
        merged["exposure_index_0_100"],
        higher_value_is_higher_exposure=True,
    )

    merged["scoring_policy_version"] = SCORING_POLICY_VERSION

    for column in [
        "fema_component_0_100",
        "water_component_0_100",
        "terrain_component_0_100",
        "exposure_index_0_100",
        "exposure_percentile",
    ]:
        if merged[column].lt(0).any() or merged[column].gt(100).any():
            raise RuntimeError(f"{column} is outside the 0–100 range.")

    return merged[OUTPUT_COLUMNS].sort_values(
        "property_id",
        kind="stable",
    ).reset_index(drop=True)


def summarize_exposure_index(index: pd.DataFrame) -> dict[str, Any]:
    require_columns(
        index,
        set(OUTPUT_COLUMNS),
        "Exposure index",
    )

    validate_property_ids(index, "Exposure index")

    return {
        "property_count": int(len(index)),
        "unique_property_ids": int(index["property_id"].nunique()),
        "minimum_exposure_index": float(index["exposure_index_0_100"].min()),
        "maximum_exposure_index": float(index["exposure_index_0_100"].max()),
        "mean_exposure_index": float(index["exposure_index_0_100"].mean()),
        "median_exposure_index": float(index["exposure_index_0_100"].median()),
        "minimum_exposure_percentile": float(index["exposure_percentile"].min()),
        "maximum_exposure_percentile": float(index["exposure_percentile"].max()),
        "mean_fema_component": float(index["fema_component_0_100"].mean()),
        "mean_water_component": float(index["water_component_0_100"].mean()),
        "mean_terrain_component": float(index["terrain_component_0_100"].mean()),
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "weights": DEFAULT_WEIGHTS,
    }