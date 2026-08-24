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


# --- the scratch guard ------------------------------------------------------


def test_scratch_guard_refuses_a_frozen_path(tmp_path):
    """The one failure that cannot be undone by re-running."""
    scratch = tmp_path / "outputs" / "scratch" / "c4"
    scratch.mkdir(parents=True)
    frozen = tmp_path / "outputs" / "index" / "property_exposure_index_countywide.csv"
    with pytest.raises(pc.PipelineCostError, match="refusing to write"):
        pc.assert_under_scratch(frozen, scratch)


def test_scratch_guard_refuses_a_sibling_that_shares_a_prefix(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    with pytest.raises(pc.PipelineCostError):
        pc.assert_under_scratch(tmp_path / "scratch_other" / "f.csv", scratch)


def test_scratch_guard_accepts_a_nested_scratch_path(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert pc.assert_under_scratch(scratch / "cli" / "fema.csv", scratch)


# --- timing contracts -------------------------------------------------------


def test_in_process_timing_refuses_a_single_repeat():
    with pytest.raises(pc.PipelineCostError, match="at least 2 repeats"):
        pc.time_stage_in_process(lambda: 1, lambda x: x, n_setup_repeats=1, n_compute_repeats=3)
    with pytest.raises(pc.PipelineCostError, match="at least 2 repeats"):
        pc.time_stage_in_process(lambda: 1, lambda x: x, n_setup_repeats=2, n_compute_repeats=1)


def test_in_process_timing_reruns_setup_rather_than_hoisting_it():
    setup_calls, compute_calls = [], []

    def setup():
        setup_calls.append(1)
        return [0] * 7

    def compute(inputs):
        compute_calls.append(1)
        return inputs

    result = pc.time_stage_in_process(
        setup, compute, n_setup_repeats=2, n_compute_repeats=3, n_warmup=1
    )
    assert len(setup_calls) == 3  # 1 warm-up + 2 timed
    assert len(compute_calls) == 4  # 1 warm-up + 3 timed
    assert result["setup_s"]["n_repeat"] == 2
    assert result["compute_s"]["n_repeat"] == 3
    assert result["result_rows"] == 7


def test_process_timing_raises_on_a_failing_command(tmp_path):
    import sys as _sys

    with pytest.raises(pc.PipelineCostError, match="failed"):
        pc.time_process_wall_clock(
            [_sys.executable, "-c", "raise SystemExit(3)"], cwd=tmp_path, n_repeats=2, n_warmup=0
        )


def test_process_timing_measures_a_successful_command(tmp_path):
    import sys as _sys

    result = pc.time_process_wall_clock(
        [_sys.executable, "-c", "pass"], cwd=tmp_path, n_repeats=2, n_warmup=1
    )
    assert result["process_wall_clock_s"]["n_repeat"] == 2
    assert result["process_wall_clock_s"]["median_s"] > 0


# --- the fit ----------------------------------------------------------------


def test_fit_recovers_a_and_b_on_exactly_linear_data():
    n = [10_000, 100_000, 267_362]
    a, b = 4.0, 2.5e-05
    fit = pc.fit_linear(n, [a + b * value for value in n])
    assert fit["a_fixed_s"] == pytest.approx(a, rel=1e-9, abs=1e-9)
    assert fit["b_marginal_s_per_property"] == pytest.approx(b, rel=1e-9, abs=1e-15)
    assert fit["max_abs_residual_fraction"] == pytest.approx(0.0, abs=1e-12)
    assert fit["three_points_is_the_minimum"]


def test_fit_reports_a_real_residual_on_curved_data():
    """A stage whose cost is not linear in N must not look like one."""
    n = [10_000, 100_000, 267_362]
    fit = pc.fit_linear(n, [1.0, 40.0, 20.0])
    assert fit["max_abs_residual_fraction"] > 0.05
    assert len(fit["residual_s"]) == 3


def test_fit_refuses_fewer_than_three_points():
    with pytest.raises(pc.PipelineCostError, match="three workload sizes"):
        pc.fit_linear([10_000, 100_000], [1.0, 2.0])


def test_fit_publishes_no_r_squared():
    """R^2 over three points reads as corroboration it cannot supply."""
    fit = pc.fit_linear([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert not any("r2" in key or "r_squared" in key for key in fit)


# --- the run log ------------------------------------------------------------


def test_run_log_appends_and_reads_back(tmp_path):
    path = tmp_path / "runs.jsonl"
    pc.append_run_record(path, {"stage": "scoring", "workload": "10000", "n_properties": 10_000})
    pc.append_run_record(path, {"stage": "scoring", "workload": "countywide", "n_properties": 267_362})
    records = pc.read_run_records(path)
    assert [record["workload"] for record in records] == ["10000", "countywide"]


def test_fit_stage_orders_cells_by_property_count(tmp_path):
    records = [
        {"stage": "scoring", "workload": "countywide", "n_properties": 267_362,
         "compute_s": {"median_s": 7.0}},
        {"stage": "scoring", "workload": "10000", "n_properties": 10_000,
         "compute_s": {"median_s": 1.0}},
        {"stage": "scoring", "workload": "100000", "n_properties": 100_000,
         "compute_s": {"median_s": 3.0}},
    ]
    fit = pc.fit_stage(records, "scoring", "compute_s")
    assert fit["workloads"] == ["10000", "100000", "countywide"]
    assert fit["b_marginal_s_per_property"] > 0


def test_fit_stage_raises_for_an_unmeasured_stage():
    with pytest.raises(pc.PipelineCostError, match="no records"):
        pc.fit_stage([], "terrain_sampling", "compute_s")


def test_fit_stage_raises_when_a_cell_lacks_the_requested_clock():
    records = [
        {"stage": "scoring", "workload": w, "n_properties": n, "compute_s": {"median_s": 1.0}}
        for w, n in (("10000", 10_000), ("100000", 100_000), ("countywide", 267_362))
    ]
    del records[1]["compute_s"]
    with pytest.raises(pc.PipelineCostError, match="no 'compute_s'"):
        pc.fit_stage(records, "scoring", "compute_s")


# --- the corrected boundary -------------------------------------------------


def test_boundary_records_the_dem_correction_made_before_measurement():
    """caprm.terrain.build_terrain_evidence takes a path and opens it itself."""
    inside = pc.TIMING_BOUNDARY["what_is_inside"]
    assert "DEM open" not in inside["setup_s"]
    correction = inside["correction_2026_07_30"]
    assert "compute_s" in correction
    assert "BEFORE any timing run" in correction