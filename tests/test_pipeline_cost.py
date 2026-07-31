"""Tests for C4 item 2a.

The boundary tests are not decoration. ``TIMING_BOUNDARY`` is the thing that
makes the item-2 wall clocks measurements rather than numbers, and it is exactly
the kind of constant that gets quietly edited once results are in. These tests
pin its four declared choices and, more importantly, pin the requirement that
every skipped stage carries a stated reason.
"""

from __future__ import annotations

import pandas as pd
import pytest

from caprm import pipeline_cost as pc


def evidence_frame(ids, extra_column="water_distance_m"):
    return pd.DataFrame(
        {
            pc.KEY_COLUMN: pd.Series(list(ids), dtype="string"),
            extra_column: [float(i) for i in range(len(ids))],
            "is_sfha": [i % 2 == 0 for i in range(len(ids))],
        }
    )


def index(values):
    return pd.Index(pd.Series(list(values), dtype="string"))


# --- the nesting gate -------------------------------------------------------


def test_assert_nested_accepts_a_true_subset():
    record = pc.assert_nested(index(["a", "b"]), index(["a", "b", "c"]), "small", "big")
    assert record["nested"]
    assert record["n_missing_from_superset"] == 0
    assert record["n_subset"] == 2 and record["n_superset"] == 3


def test_assert_nested_raises_and_names_the_absent_ids():
    with pytest.raises(pc.PipelineCostError, match="not contained"):
        pc.assert_nested(index(["a", "z"]), index(["a", "b"]), "small", "big")


def test_nesting_report_checks_the_risky_link_first():
    """100000-within-countywide is the link with no construction guarantee."""
    id_sets = {
        "10000": index(["a", "b"]),
        "100000": index(["a", "b", "c"]),
        "countywide": index(["a", "b", "c", "d"]),
    }
    report = pc.nesting_report(id_sets)
    keys = list(report)
    assert keys[0] == "checked_first_because_it_can_fail"
    assert report["checked_first_because_it_can_fail"]["subset"] == "100000"
    assert report["checked_first_because_it_can_fail"]["superset"] == "countywide"
    assert report["guaranteed_by_construction_checked_anyway"]["subset"] == "10000"
    assert "sample_order" in report["never_subset_by"]


def test_nesting_report_fails_when_the_risky_link_fails():
    id_sets = {
        "10000": index(["a"]),
        "100000": index(["a", "rogue"]),
        "countywide": index(["a", "b"]),
    }
    with pytest.raises(pc.PipelineCostError, match="100000 is not contained in countywide"):
        pc.nesting_report(id_sets)


def test_nesting_report_needs_all_three_workloads():
    with pytest.raises(pc.PipelineCostError, match="10000"):
        pc.nesting_report({"countywide": index(["a"])})


def test_property_ids_refuses_duplicates():
    frame = evidence_frame(["a", "a", "b"])
    with pytest.raises(pc.PipelineCostError, match="duplicated"):
        pc.property_ids(frame, "test")


def test_property_ids_names_the_missing_column():
    with pytest.raises(pc.PipelineCostError, match="property_id"):
        pc.property_ids(pd.DataFrame({"other": [1]}), "test")


# --- subsetting -------------------------------------------------------------


def test_subset_preserves_columns_and_source_row_order():
    frame = evidence_frame(["a", "b", "c", "d"])
    subset = pc.subset_by_ids(frame, index(["c", "a"]), "test")
    assert list(subset.columns) == list(frame.columns)
    assert list(subset[pc.KEY_COLUMN]) == ["a", "c"]  # source order, not id order
    assert len(subset) == 2


def test_subset_raises_when_an_id_is_absent():
    frame = evidence_frame(["a", "b"])
    with pytest.raises(pc.PipelineCostError, match="absent"):
        pc.subset_by_ids(frame, index(["a", "missing"]), "test")


def test_subset_rejects_a_duplicated_id_request():
    frame = evidence_frame(["a", "b"])
    with pytest.raises(pc.PipelineCostError, match="duplicates"):
        pc.subset_by_ids(frame, ["a", "a"], "test")


def test_write_subsets_writes_one_file_per_workload_with_digests(tmp_path):
    frame = evidence_frame(["a", "b", "c"])
    written = pc.write_subsets(
        frame,
        {"10000": index(["a"]), "countywide": index(["a", "b", "c"])},
        tmp_path,
        "evidence",
        "test",
    )
    assert set(written) == {"10000", "countywide"}
    assert written["10000"]["rows"] == 1
    assert written["countywide"]["rows"] == 3
    for entry in written.values():
        assert len(entry["sha256"]) == 64
        reread = pd.read_csv(entry["path"], dtype={pc.KEY_COLUMN: "string"})
        assert list(reread.columns) == list(frame.columns)


# --- the declared boundary --------------------------------------------------


def test_boundary_declares_all_four_choices():
    for key in ("warm_or_cold", "what_is_inside", "marginal_or_total", "stages_timed"):
        assert key in pc.TIMING_BOUNDARY


def test_boundary_is_warm_and_says_what_it_does_not_claim():
    assert pc.TIMING_BOUNDARY["warm_or_cold"]["choice"] == "warm"
    assert "Cold start" in pc.TIMING_BOUNDARY["warm_or_cold"]["not_claimed"]


def test_boundary_separates_setup_from_compute():
    inside = pc.TIMING_BOUNDARY["what_is_inside"]
    assert "setup_s" in inside and "compute_s" in inside
    assert "sha256" in inside["setup_s"]


def test_boundary_states_that_three_points_is_the_minimum():
    assert "MINIMUM" in pc.TIMING_BOUNDARY["marginal_or_total"]["caveat"]
    assert "residual" in pc.TIMING_BOUNDARY["marginal_or_total"]["caveat"]


def test_every_timed_stage_names_its_entry_point_and_workload_selection():
    stages = pc.TIMING_BOUNDARY["stages_timed"]
    assert {stage["stage"] for stage in stages} == {
        "fema_point_in_polygon",
        "nearest_water_python",
        "terrain_sampling",
        "scoring",
    }
    for stage in stages:
        assert stage["entry_point"].startswith("caprm.")
        assert stage["workload_selection"]


def test_every_skipped_stage_carries_a_reason():
    """A stage omitted without a stated reason is an undeclared boundary."""
    skipped = pc.TIMING_BOUNDARY["stages_skipped"]
    assert {stage["stage"] for stage in skipped} >= {
        "property_cache_refresh",
        "evidence_merge",
        "cpp_input_export",
    }
    for stage in skipped:
        assert stage["why"], stage


def test_cpp_stage_is_cited_at_the_shipped_operating_point():
    cited = pc.TIMING_BOUNDARY["stages_cited_not_measured"][0]
    assert cited["stage"] == "nearest_water_cpp"
    assert "25 m" in cited["operating_point"]
    assert "cap=100" in cited["why"]


def test_boundary_records_both_clocks():
    clocks = pc.TIMING_BOUNDARY["two_clocks"]
    assert "in_process_s" in clocks and "process_wall_clock_s" in clocks
    assert "geopandas" in clocks["process_wall_clock_s"]


def test_workloads_cover_the_three_sizes_that_exist_on_both_sides():
    assert [w.name for w in pc.WORKLOADS] == ["10000", "100000", "countywide"]
    assert [w.expected_rows for w in pc.WORKLOADS] == [10_000, 100_000, 267_362]
    for workload in pc.WORKLOADS:
        assert workload.config.startswith("configs/")


def test_manifest_lists_the_frozen_paths_it_must_not_write(tmp_path):
    manifest = pc.boundary_manifest(
        nesting={}, subsets={}, inputs={}, generated_utc="2026-07-30T00:00:00+00:00"
    )
    frozen = manifest["frozen_paths_not_written"]
    assert "outputs/index/property_exposure_index_countywide.csv" in frozen
    assert "outputs/validation/property_exposure_index_countywide_manifest.json" in frozen
    assert "outputs/validation/water_cpp_benchmark_summary.json" in frozen
    assert manifest["scratch_directory"].startswith("outputs/scratch")
    assert manifest["schema_version"] == "c4_pipeline_boundary_v1"