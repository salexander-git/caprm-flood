from __future__ import annotations

import json

import pandas as pd
import pytest

from caprm.audit import (
    FAIL,
    PASS,
    WARN,
    audit_checksum,
    audit_columns,
    audit_index_product,
    audit_manifest_conventions,
    audit_nulls,
    audit_plausibility,
    audit_population_consistency,
    audit_property_ids,
    audit_terrain_product,
    load_manifest,
    manifest_field,
    overall_status,
    record,
    status_counts,
)
from caprm.scoring import (
    COMPONENT_COLUMNS,
    COMPONENT_NAMES,
    DEFAULT_WEIGHTS,
    SCORING_POLICY_VERSION,
    build_exposure_index,
)


def evidence_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["A", "B", "C", "D", "E"],
            "matched_fema_polygon": [True, True, True, True, True],
            "fema_zone": ["X", "AO", "A", "AE", "VE"],
            "is_sfha": [False, True, True, True, True],
            "nearest_water_distance_m": [1000.0, 500.0, 250.0, 100.0, 0.0],
            "distance_crs": ["EPSG:26918"] * 5,
        }
    )


def terrain_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property_id": ["A", "B", "C", "D", "E"],
            "terrain_elevation_m": [200.0, 175.0, 150.0, 100.0, 75.0],
            "terrain_local_mean_elevation_m": [195.0, 170.0, 150.0, 105.0, 85.0],
            "terrain_relative_elevation_m": [5.0, 5.0, 0.0, -5.0, -10.0],
            "terrain_slope_degrees": [1.0, 2.0, 3.0, 4.0, 5.0],
            "terrain_sample_radius_m": [90.0] * 5,
            "terrain_crs": ["EPSG:26918"] * 5,
        }
    )


def terrain_manifest(output_path: str = "terrain.csv") -> dict:
    return {
        "schema_version": "terrain_evidence_v1",
        "output": output_path,
        "output_sha256": "unused",
        "terrain_crs": "EPSG:26918",
        "sample_radius_meters": 90.0,
        "summary": {"property_count": 5},
    }


def index_frame() -> pd.DataFrame:
    return build_exposure_index(
        evidence=evidence_frame(),
        terrain=terrain_frame(),
    )


def index_manifest() -> dict:
    return {
        "schema_version": SCORING_POLICY_VERSION,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "output": "index.csv",
        "output_sha256": "unused",
        "weights": DEFAULT_WEIGHTS,
        "summary": {"property_count": 5},
    }


def statuses(checks: list[dict], name: str) -> str:
    for check in checks:
        if check["check"] == name:
            return check["status"]

    raise AssertionError(f"Check {name!r} was not produced.")


# ----------------------------------------------------------- primitives


def test_record_carries_extra_fields() -> None:
    result = record("thing", PASS, "fine", count=3)

    assert result["check"] == "thing"
    assert result["status"] == PASS
    assert result["count"] == 3


def test_overall_status_prefers_failure() -> None:
    assert overall_status([{"status": PASS}, {"status": WARN}]) == WARN
    assert (
        overall_status([{"status": PASS}, {"status": WARN}, {"status": FAIL}])
        == FAIL
    )
    assert overall_status([{"status": PASS}]) == PASS


def test_status_counts_totals_each_status() -> None:
    counts = status_counts(
        [{"status": PASS}, {"status": PASS}, {"status": FAIL}]
    )

    assert counts[PASS] == 2
    assert counts[FAIL] == 1
    assert counts[WARN] == 0


# ------------------------------------------------------------ manifests


def test_load_manifest_rejects_a_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_manifest(tmp_path / "absent.json")


def test_manifest_field_accepts_either_convention() -> None:
    value, key = manifest_field(
        {"evidence_summary": {"a": 1}}, ("summary", "evidence_summary"), "s"
    )

    assert value == {"a": 1}
    assert key == "evidence_summary"


def test_manifest_field_rejects_an_unknown_convention() -> None:
    with pytest.raises(ValueError, match="has no"):
        manifest_field({"other": 1}, ("summary",), "summary block")


def test_manifest_conventions_pass_when_uniform() -> None:
    checks = audit_manifest_conventions(
        {
            "a": {"summary": {}, "output": "a.csv"},
            "b": {"summary": {}, "output": "b.csv"},
        }
    )

    assert statuses(checks, "manifest_schema_consistency") == PASS


def test_manifest_conventions_warn_when_divergent() -> None:
    """
    The Milestone 2 evidence manifest predates the current convention.
    Divergence warns rather than fails, because unifying it would require
    regenerating a validated upstream product.
    """
    checks = audit_manifest_conventions(
        {
            "old": {"evidence_summary": {}, "output_csv": "a.csv"},
            "new": {"summary": {}, "output": "b.csv"},
        }
    )

    assert statuses(checks, "manifest_schema_consistency") == WARN


# ------------------------------------------------------------ checksums


def test_audit_checksum_passes_on_a_match(tmp_path) -> None:
    from caprm.scoring import calculate_sha256

    path = tmp_path / "artifact.csv"
    path.write_text("data", encoding="utf-8")

    check = audit_checksum(path, calculate_sha256(path), "artifact")

    assert check["status"] == PASS


def test_audit_checksum_fails_when_the_file_changed(tmp_path) -> None:
    """
    The check that catches an artifact regenerated without its manifest.
    Nothing else in the pipeline notices that drift.
    """
    path = tmp_path / "artifact.csv"
    path.write_text("data", encoding="utf-8")

    check = audit_checksum(path, "0" * 64, "artifact")

    assert check["status"] == FAIL
    assert check["actual_sha256"] != check["manifest_sha256"]


def test_audit_checksum_fails_on_a_missing_file(tmp_path) -> None:
    check = audit_checksum(tmp_path / "absent.csv", "0" * 64, "artifact")

    assert check["status"] == FAIL


def test_audit_checksum_fails_when_the_manifest_records_none(tmp_path) -> None:
    path = tmp_path / "artifact.csv"
    path.write_text("data", encoding="utf-8")

    check = audit_checksum(path, None, "artifact")

    assert check["status"] == FAIL


# --------------------------------------------------------------- frames


def test_audit_columns_detects_missing() -> None:
    check = audit_columns(pd.DataFrame({"a": [1]}), ["a", "b"], "thing")

    assert check["status"] == FAIL


def test_audit_columns_warns_on_extras() -> None:
    check = audit_columns(pd.DataFrame({"a": [1], "b": [2]}), ["a"], "thing")

    assert check["status"] == WARN


def test_audit_property_ids_detects_duplicates() -> None:
    checks = audit_property_ids(
        pd.DataFrame({"property_id": ["A", "A"]}), "thing"
    )

    assert statuses(checks, "thing_property_ids_unique") == FAIL


def test_audit_property_ids_detects_nulls() -> None:
    checks = audit_property_ids(
        pd.DataFrame({"property_id": ["A", None]}), "thing"
    )

    assert statuses(checks, "thing_property_ids_present") == FAIL


def test_audit_nulls_allows_a_declared_column_to_warn() -> None:
    frame = pd.DataFrame({"a": [1.0, None], "b": [1.0, None]})

    checks = audit_nulls(frame, ["a", "b"], "thing", allow_null=("b",))

    assert statuses(checks, "thing_a_nulls") == FAIL
    assert statuses(checks, "thing_b_nulls") == WARN


def test_audit_plausibility_warns_never_fails() -> None:
    """Suspicious is not invalid. A person resolves these."""
    frame = pd.DataFrame({"terrain_elevation_m": [-500.0, 150.0]})

    checks = audit_plausibility(frame, "terrain")

    assert statuses(checks, "terrain_terrain_elevation_m_plausibility") == WARN


def test_audit_plausibility_passes_inside_bounds() -> None:
    frame = pd.DataFrame({"terrain_elevation_m": [75.0, 296.0]})

    checks = audit_plausibility(frame, "terrain")

    assert statuses(checks, "terrain_terrain_elevation_m_plausibility") == PASS


# -------------------------------------------------------------- terrain


def test_audit_terrain_product_passes_a_clean_artifact() -> None:
    checks = audit_terrain_product(terrain_frame(), terrain_manifest())

    assert not [check for check in checks if check["status"] == FAIL]


def test_audit_terrain_detects_a_broken_relative_elevation() -> None:
    """
    Relative elevation is derived, so it can be checked against the two
    fields it came from. This audits the artifact, not the code.
    """
    terrain = terrain_frame()
    terrain.loc[0, "terrain_relative_elevation_m"] = 99.0

    checks = audit_terrain_product(terrain, terrain_manifest())

    assert statuses(checks, "terrain_relative_elevation_derivation") == FAIL


def test_audit_terrain_detects_a_radius_disagreement() -> None:
    terrain = terrain_frame()
    terrain["terrain_sample_radius_m"] = 30.0

    checks = audit_terrain_product(terrain, terrain_manifest())

    assert statuses(checks, "terrain_sample_radius_consistency") == FAIL


def test_audit_terrain_detects_a_mixed_radius() -> None:
    terrain = terrain_frame()
    terrain.loc[0, "terrain_sample_radius_m"] = 30.0

    checks = audit_terrain_product(terrain, terrain_manifest())

    assert statuses(checks, "terrain_sample_radius_consistency") == FAIL


def test_audit_terrain_detects_a_crs_disagreement() -> None:
    terrain = terrain_frame()
    terrain.loc[0, "terrain_crs"] = "EPSG:4326"

    checks = audit_terrain_product(terrain, terrain_manifest())

    assert statuses(checks, "terrain_crs_consistency") == FAIL


def test_audit_terrain_detects_a_manifest_count_disagreement() -> None:
    manifest = terrain_manifest()
    manifest["summary"]["property_count"] = 99

    checks = audit_terrain_product(terrain_frame(), manifest)

    assert statuses(checks, "terrain_manifest_count_agreement") == FAIL


def test_audit_terrain_allows_a_null_slope() -> None:
    """Slope is undefined at a raster edge. A null is legitimate."""
    terrain = terrain_frame()
    terrain.loc[0, "terrain_slope_degrees"] = None

    checks = audit_terrain_product(terrain, terrain_manifest())

    assert statuses(checks, "terrain_terrain_slope_degrees_nulls") == WARN


# ---------------------------------------------------------------- index


def test_audit_index_product_passes_a_clean_artifact() -> None:
    checks = audit_index_product(index_frame(), index_manifest())

    assert not [check for check in checks if check["status"] == FAIL]


def test_audit_index_detects_a_composite_that_does_not_reproduce() -> None:
    """
    The manifest's weights applied to the artifact's components must
    reproduce the stored index, or the manifest cannot reproduce the result
    it claims to describe.
    """
    index = index_frame()
    index.loc[0, "exposure_index_0_100"] = 42.0

    checks = audit_index_product(index, index_manifest())

    assert statuses(checks, "index_composite_derivation") == FAIL


def test_audit_index_detects_weights_that_do_not_match_the_artifact() -> None:
    manifest = index_manifest()
    manifest["weights"] = {
        "fema": 0.25,
        "water": 0.25,
        "terrain_absolute": 0.25,
        "terrain_relative": 0.25,
    }

    checks = audit_index_product(index_frame(), manifest)

    assert statuses(checks, "index_composite_derivation") == FAIL


def test_audit_index_fails_when_the_manifest_has_no_weights() -> None:
    manifest = index_manifest()
    del manifest["weights"]

    checks = audit_index_product(index_frame(), manifest)

    assert statuses(checks, "index_composite_derivation") == FAIL


def test_audit_index_detects_a_value_outside_range() -> None:
    index = index_frame()
    index.loc[0, "water_component_0_100"] = 150.0

    checks = audit_index_product(index, index_manifest())

    assert statuses(checks, "index_water_component_0_100_range") == FAIL


def test_audit_index_detects_unsorted_output() -> None:
    index = index_frame().iloc[::-1].reset_index(drop=True)

    checks = audit_index_product(index, index_manifest())

    assert statuses(checks, "index_deterministic_ordering") == FAIL


def test_audit_index_detects_a_policy_version_disagreement() -> None:
    index = index_frame()
    index["scoring_policy_version"] = "something_else"

    checks = audit_index_product(index, index_manifest())

    assert statuses(checks, "index_policy_version_consistency") == FAIL


def test_audit_index_reports_percentile_ties() -> None:
    checks = audit_index_product(index_frame(), index_manifest())

    assert statuses(checks, "index_percentile_ties") == PASS


# ----------------------------------------------------------- population


def test_population_consistency_passes_on_identical_sets() -> None:
    checks = audit_population_consistency(
        {
            "workload": {"A", "B"},
            "terrain": {"A", "B"},
            "index": {"B", "A"},
        },
        reference="workload",
    )

    assert not [check for check in checks if check["status"] == FAIL]


def test_population_consistency_detects_a_missing_property() -> None:
    checks = audit_population_consistency(
        {"workload": {"A", "B"}, "index": {"A"}},
        reference="workload",
    )

    assert statuses(checks, "population_index") == FAIL


def test_population_consistency_detects_an_unexpected_property() -> None:
    """
    Counts alone are not sufficient. Two products can hold the same number
    of rows and disagree about which properties they describe.
    """
    checks = audit_population_consistency(
        {"workload": {"A", "B"}, "index": {"A", "C"}},
        reference="workload",
    )

    check = [c for c in checks if c["check"] == "population_index"][0]

    assert check["status"] == FAIL
    assert check["missing_count"] == 1
    assert check["unexpected_count"] == 1


def test_population_consistency_requires_a_known_reference() -> None:
    with pytest.raises(ValueError, match="Reference population"):
        audit_population_consistency({"a": {"A"}}, reference="absent")