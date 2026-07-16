from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from caprm.scoring import (
    COMPONENT_COLUMNS,
    COMPONENT_NAMES,
    calculate_sha256,
    percentile_score,
)


PASS = "pass"
WARN = "warn"
FAIL = "fail"

# A derived column recomputed from its inputs should agree to within
# float noise. Artifacts are written at 12 decimal places, so the rounding
# floor is around 1e-12.
DERIVATION_TOLERANCE = 1e-9

# Recomputing a rank from a rounded score can shift a percentile slightly
# when two scores round into a tie that did not exist before rounding.
# This is a property of the CSV representation, not of the ranking, so the
# tolerance is looser and a breach warns rather than fails.
PERCENTILE_TOLERANCE = 1e-6

TERRAIN_EXPECTED_COLUMNS = [
    "property_id",
    "terrain_elevation_m",
    "terrain_local_mean_elevation_m",
    "terrain_relative_elevation_m",
    "terrain_slope_degrees",
    "terrain_sample_radius_m",
    "terrain_crs",
]

INDEX_EXPECTED_COLUMNS = [
    "property_id",
    *[COMPONENT_COLUMNS[name] for name in COMPONENT_NAMES],
    "exposure_index_0_100",
    "exposure_percentile",
    "scoring_policy_version",
]

# Plausibility bounds. These flag values that are valid but surprising, so
# a person can decide whether they are real. They are judgement calls with
# no external standard and must never fail a run: suspicious is not the
# same as invalid.
PLAUSIBILITY_BOUNDS = {
    "terrain_elevation_m": {
        "minimum": 70.0,
        "maximum": 400.0,
        "rationale": (
            "Lake Ontario's low-water datum is roughly 74.2 m, so a land "
            "elevation materially below 70 m suggests nodata leakage rather "
            "than terrain. Monroe County is a lake plain; 400 m is generous."
        ),
    },
    "terrain_slope_degrees": {
        "minimum": 0.0,
        "maximum": 70.0,
        "rationale": (
            "The county is flat apart from the Genesee gorge, whose walls "
            "are the steepest real terrain present. A slope beyond 70 "
            "degrees would suggest a DEM artifact."
        ),
    },
}

# Manifests do not share one schema. The Milestone 2 evidence manifest
# predates the convention used by the terrain and index manifests. Reading
# both is deliberate: unifying them would require regenerating a validated
# upstream product.
MANIFEST_SUMMARY_KEYS = ("summary", "evidence_summary")
MANIFEST_OUTPUT_KEYS = ("output", "output_csv")


def record(
    name: str,
    status: str,
    detail: str,
    **extra: Any,
) -> dict[str, Any]:
    return {"check": name, "status": status, "detail": detail, **extra}


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest does not exist: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def manifest_field(
    manifest: dict[str, Any],
    candidates: tuple[str, ...],
    description: str,
) -> tuple[Any, str]:
    """
    Read a field that different manifest generations name differently.

    Returns the value and the key it was found under, so the audit can
    report which convention an artifact uses rather than hiding the
    divergence.
    """
    for key in candidates:
        if key in manifest:
            return manifest[key], key

    raise ValueError(
        f"Manifest has no {description}. Tried: {list(candidates)}"
    )


def audit_manifest_conventions(
    manifests: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Report which key convention each manifest uses.

    Divergence is a warning, not a failure. It is a documented consequence
    of preserving the validated Milestone 2 product rather than
    regenerating it for cosmetic consistency.
    """
    conventions: dict[str, dict[str, str]] = {}

    for label, manifest in manifests.items():
        _, summary_key = manifest_field(
            manifest, MANIFEST_SUMMARY_KEYS, "summary block"
        )
        _, output_key = manifest_field(
            manifest, MANIFEST_OUTPUT_KEYS, "output path"
        )

        conventions[label] = {
            "summary_key": summary_key,
            "output_key": output_key,
        }

    distinct = {
        (value["summary_key"], value["output_key"])
        for value in conventions.values()
    }

    if len(distinct) <= 1:
        return [
            record(
                "manifest_schema_consistency",
                PASS,
                "All manifests use the same key convention.",
                conventions=conventions,
            )
        ]

    return [
        record(
            "manifest_schema_consistency",
            WARN,
            (
                f"{len(distinct)} manifest key conventions are in use. Any "
                "tool reading manifests generically must handle each."
            ),
            conventions=conventions,
        )
    ]


def audit_checksum(
    path: Path,
    expected_sha256: str | None,
    label: str,
) -> dict[str, Any]:
    """
    Confirm a manifest's recorded hash still matches the file on disk.

    This is the check that catches an artifact regenerated without its
    manifest. Nothing else in the pipeline notices that drift, and once it
    happens every provenance claim about the artifact is false.
    """
    if not path.exists():
        return record(
            f"{label}_checksum",
            FAIL,
            f"File recorded in the manifest does not exist: {path}",
        )

    if not expected_sha256:
        return record(
            f"{label}_checksum",
            FAIL,
            "Manifest records no checksum for this artifact.",
        )

    actual = calculate_sha256(path)

    if actual == expected_sha256:
        return record(
            f"{label}_checksum",
            PASS,
            "Manifest checksum matches the file on disk.",
            sha256=actual,
        )

    return record(
        f"{label}_checksum",
        FAIL,
        (
            "Manifest checksum does not match the file on disk. The "
            "artifact was regenerated without its manifest, or the manifest "
            "describes a different file."
        ),
        manifest_sha256=expected_sha256,
        actual_sha256=actual,
    )


def audit_columns(
    frame: pd.DataFrame,
    expected: list[str],
    label: str,
) -> dict[str, Any]:
    missing = [column for column in expected if column not in frame.columns]

    if missing:
        return record(
            f"{label}_schema",
            FAIL,
            f"Missing expected columns: {missing}",
        )

    unexpected = [
        column for column in frame.columns if column not in expected
    ]

    if unexpected:
        return record(
            f"{label}_schema",
            WARN,
            f"Columns present but not expected: {unexpected}",
        )

    return record(
        f"{label}_schema",
        PASS,
        f"Schema matches the expected {len(expected)} columns.",
    )


def audit_property_ids(
    frame: pd.DataFrame,
    label: str,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    identifiers = frame["property_id"]
    null_count = int(identifiers.isna().sum())

    checks.append(
        record(
            f"{label}_property_ids_present",
            PASS if null_count == 0 else FAIL,
            f"{null_count} null property IDs.",
            null_count=null_count,
        )
    )

    duplicate_count = int(identifiers.duplicated().sum())

    checks.append(
        record(
            f"{label}_property_ids_unique",
            PASS if duplicate_count == 0 else FAIL,
            f"{duplicate_count} duplicate property IDs.",
            row_count=int(len(frame)),
            unique_count=int(identifiers.nunique()),
        )
    )

    return checks


def audit_nulls(
    frame: pd.DataFrame,
    columns: list[str],
    label: str,
    allow_null: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    for column in columns:
        if column not in frame.columns:
            continue

        null_count = int(frame[column].isna().sum())

        if null_count == 0:
            status = PASS
        elif column in allow_null:
            status = WARN
        else:
            status = FAIL

        checks.append(
            record(
                f"{label}_{column}_nulls",
                status,
                f"{null_count} null values.",
                null_count=null_count,
            )
        )

    return checks


def audit_plausibility(
    frame: pd.DataFrame,
    label: str,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    for column, bounds in PLAUSIBILITY_BOUNDS.items():
        if column not in frame.columns:
            continue

        values = pd.to_numeric(frame[column], errors="coerce").dropna()

        if values.empty:
            continue

        below = int(values.lt(bounds["minimum"]).sum())
        above = int(values.gt(bounds["maximum"]).sum())

        status = PASS if (below == 0 and above == 0) else WARN

        checks.append(
            record(
                f"{label}_{column}_plausibility",
                status,
                (
                    f"{below} below {bounds['minimum']}, "
                    f"{above} above {bounds['maximum']}."
                ),
                observed_minimum=float(values.min()),
                observed_maximum=float(values.max()),
                rationale=bounds["rationale"],
            )
        )

    return checks


def audit_terrain_product(
    terrain: pd.DataFrame,
    manifest: dict[str, Any],
    raster_path: Path | None = None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = [
        audit_columns(terrain, TERRAIN_EXPECTED_COLUMNS, "terrain")
    ]

    checks.extend(audit_property_ids(terrain, "terrain"))

    checks.extend(
        audit_nulls(
            terrain,
            [
                "terrain_elevation_m",
                "terrain_local_mean_elevation_m",
                "terrain_relative_elevation_m",
                "terrain_slope_degrees",
                "terrain_sample_radius_m",
            ],
            "terrain",
            # Slope is undefined at a raster edge, where no 3x3 window
            # exists. A null is legitimate; the count is worth seeing.
            allow_null=("terrain_slope_degrees",),
        )
    )

    # The relative elevation is derived, so it can be checked against the
    # two fields it came from. This audits the stored artifact, which is a
    # different question from whether the code is correct.
    if {
        "terrain_elevation_m",
        "terrain_local_mean_elevation_m",
        "terrain_relative_elevation_m",
    }.issubset(terrain.columns):
        recomputed = (
            terrain["terrain_elevation_m"]
            - terrain["terrain_local_mean_elevation_m"]
        )

        difference = (
            recomputed - terrain["terrain_relative_elevation_m"]
        ).abs()

        maximum = float(difference.max())

        checks.append(
            record(
                "terrain_relative_elevation_derivation",
                PASS if maximum <= DERIVATION_TOLERANCE else FAIL,
                (
                    "terrain_relative_elevation_m must equal elevation minus "
                    f"local mean. Maximum difference {maximum:.3e}."
                ),
                maximum_absolute_difference=maximum,
                tolerance=DERIVATION_TOLERANCE,
            )
        )

    radii = terrain["terrain_sample_radius_m"].dropna().unique()

    manifest_radius = manifest.get("sample_radius_meters")

    if len(radii) != 1:
        checks.append(
            record(
                "terrain_sample_radius_consistency",
                FAIL,
                f"Expected one sample radius, found {sorted(radii.tolist())}.",
            )
        )
    else:
        observed = float(radii[0])
        agrees = (
            manifest_radius is not None
            and abs(observed - float(manifest_radius)) <= DERIVATION_TOLERANCE
        )

        checks.append(
            record(
                "terrain_sample_radius_consistency",
                PASS if agrees else FAIL,
                (
                    f"Artifact radius {observed}; manifest radius "
                    f"{manifest_radius}."
                ),
                artifact_value=observed,
                manifest_value=manifest_radius,
            )
        )

    crs_values = sorted(
        terrain["terrain_crs"].astype("string").dropna().unique().tolist()
    )
    manifest_crs = manifest.get("terrain_crs")

    checks.append(
        record(
            "terrain_crs_consistency",
            PASS
            if crs_values == [manifest_crs]
            else FAIL,
            f"Artifact CRS {crs_values}; manifest CRS {manifest_crs!r}.",
            artifact_values=crs_values,
            manifest_value=manifest_crs,
        )
    )

    checks.extend(audit_plausibility(terrain, "terrain"))

    if raster_path is not None:
        checks.append(
            audit_checksum(
                raster_path,
                manifest.get("terrain_raster_sha256"),
                "terrain_source_raster",
            )
        )

    summary, _ = manifest_field(
        manifest, MANIFEST_SUMMARY_KEYS, "summary block"
    )

    manifest_count = summary.get("property_count")

    checks.append(
        record(
            "terrain_manifest_count_agreement",
            PASS if manifest_count == len(terrain) else FAIL,
            (
                f"Manifest reports {manifest_count} properties; artifact "
                f"holds {len(terrain)}."
            ),
            manifest_value=manifest_count,
            artifact_value=int(len(terrain)),
        )
    )

    return checks


def audit_index_product(
    index: pd.DataFrame,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = [
        audit_columns(index, INDEX_EXPECTED_COLUMNS, "index")
    ]

    checks.extend(audit_property_ids(index, "index"))

    bounded = [
        *[COMPONENT_COLUMNS[name] for name in COMPONENT_NAMES],
        "exposure_index_0_100",
        "exposure_percentile",
    ]

    checks.extend(audit_nulls(index, bounded, "index"))

    for column in bounded:
        if column not in index.columns:
            continue

        values = pd.to_numeric(index[column], errors="coerce")
        outside = int((values.lt(0.0) | values.gt(100.0)).sum())

        checks.append(
            record(
                f"index_{column}_range",
                PASS if outside == 0 else FAIL,
                f"{outside} values outside 0-100.",
                minimum=float(values.min()),
                maximum=float(values.max()),
            )
        )

    weights = manifest.get("weights")

    if weights and set(weights) == set(COMPONENT_NAMES):
        recomputed = sum(
            float(weights[name]) * index[COMPONENT_COLUMNS[name]]
            for name in COMPONENT_NAMES
        )

        difference = (recomputed - index["exposure_index_0_100"]).abs()
        maximum = float(difference.max())

        checks.append(
            record(
                "index_composite_derivation",
                PASS if maximum <= DERIVATION_TOLERANCE else FAIL,
                (
                    "The manifest's weights applied to the artifact's "
                    "component columns must reproduce the stored index. "
                    f"Maximum difference {maximum:.3e}."
                ),
                maximum_absolute_difference=maximum,
                tolerance=DERIVATION_TOLERANCE,
                weights=weights,
            )
        )
    else:
        checks.append(
            record(
                "index_composite_derivation",
                FAIL,
                (
                    "Manifest weights are absent or do not match the "
                    f"component set {sorted(COMPONENT_NAMES)}. The index "
                    "cannot be reproduced from its manifest."
                ),
                weights=weights,
            )
        )

    recomputed_percentile = percentile_score(
        index["exposure_index_0_100"],
        higher_value_is_higher_exposure=True,
    )

    percentile_difference = float(
        (recomputed_percentile - index["exposure_percentile"]).abs().max()
    )

    checks.append(
        record(
            "index_percentile_derivation",
            PASS if percentile_difference <= PERCENTILE_TOLERANCE else WARN,
            (
                "Ranking the stored index must reproduce the stored "
                f"percentile. Maximum difference {percentile_difference:.3e}."
            ),
            maximum_absolute_difference=percentile_difference,
            tolerance=PERCENTILE_TOLERANCE,
        )
    )

    ordered = bool(index["property_id"].is_monotonic_increasing)

    checks.append(
        record(
            "index_deterministic_ordering",
            PASS if ordered else FAIL,
            (
                "Output must be sorted by property_id so that row order is "
                "independent of input order."
            ),
        )
    )

    tie_count = int(
        len(index) - index["exposure_percentile"].nunique()
    )

    checks.append(
        record(
            "index_percentile_ties",
            PASS,
            (
                f"{tie_count} properties share a percentile with at least "
                "one other. Ties take an average rank, so tied properties "
                "are neither split nor ordered arbitrarily."
            ),
            tied_property_count=tie_count,
            distinct_percentile_count=int(
                index["exposure_percentile"].nunique()
            ),
        )
    )

    versions = sorted(
        index["scoring_policy_version"]
        .astype("string")
        .dropna()
        .unique()
        .tolist()
    )

    manifest_version = manifest.get("scoring_policy_version") or manifest.get(
        "schema_version"
    )

    checks.append(
        record(
            "index_policy_version_consistency",
            PASS if versions == [manifest_version] else FAIL,
            f"Artifact version {versions}; manifest version "
            f"{manifest_version!r}.",
            artifact_values=versions,
            manifest_value=manifest_version,
        )
    )

    summary, _ = manifest_field(
        manifest, MANIFEST_SUMMARY_KEYS, "summary block"
    )

    manifest_count = summary.get("property_count")

    checks.append(
        record(
            "index_manifest_count_agreement",
            PASS if manifest_count == len(index) else FAIL,
            (
                f"Manifest reports {manifest_count} properties; artifact "
                f"holds {len(index)}."
            ),
            manifest_value=manifest_count,
            artifact_value=int(len(index)),
        )
    )

    return checks


def audit_population_consistency(
    populations: dict[str, set[str]],
    reference: str,
) -> list[dict[str, Any]]:
    """
    Compare property-ID sets across the product chain.

    Each product validates itself, but nothing compares them. Two products
    can hold the same number of rows and disagree about which properties
    those rows describe, so counts alone are not sufficient.
    """
    if reference not in populations:
        raise ValueError(f"Reference population {reference!r} is absent.")

    reference_ids = populations[reference]

    checks: list[dict[str, Any]] = [
        record(
            "population_reference",
            PASS,
            (
                f"Comparing every product against {reference}, which holds "
                f"{len(reference_ids)} property IDs."
            ),
            reference=reference,
            property_count=len(reference_ids),
        )
    ]

    for label, identifiers in populations.items():
        if label == reference:
            continue

        missing = reference_ids - identifiers
        unexpected = identifiers - reference_ids

        if not missing and not unexpected:
            checks.append(
                record(
                    f"population_{label}",
                    PASS,
                    (
                        f"{label} holds exactly the same {len(identifiers)} "
                        "property IDs as the reference."
                    ),
                    property_count=len(identifiers),
                )
            )
            continue

        checks.append(
            record(
                f"population_{label}",
                FAIL,
                (
                    f"{label} differs from the reference: "
                    f"{len(missing)} missing, {len(unexpected)} unexpected."
                ),
                property_count=len(identifiers),
                missing_count=len(missing),
                unexpected_count=len(unexpected),
                missing_examples=sorted(missing)[:10],
                unexpected_examples=sorted(unexpected)[:10],
            )
        )

    return checks


def overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {check["status"] for check in checks}

    if FAIL in statuses:
        return FAIL

    if WARN in statuses:
        return WARN

    return PASS


def status_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        status: sum(1 for check in checks if check["status"] == status)
        for status in (PASS, WARN, FAIL)
    }