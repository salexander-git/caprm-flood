from __future__ import annotations

import pandas as pd
import pytest

from caprm.hilbert_inflation import (
    GATE_TAIL_RATIO_MAX,
    box_vs_disk_gate,
    describe_ratio,
    inflation_by_distance_decile,
    summarize_counters,
)


def make_frame(
    n_true_r,
    n_disk_infl,
    n_decomp,
    n_disk_unc=None,
    n_disk_r=None,
    region_mode="disk_bbox",
    distances=None,
):
    size = len(n_true_r)
    return pd.DataFrame({
        "property_id": [f"p{index:05d}" for index in range(size)],
        "cpp_nearest_water_distance_m": (
            distances if distances is not None else list(range(size))
        ),
        "cpp_entries_scanned": n_decomp,
        "cpp_n_disk_r": n_disk_r if n_disk_r is not None else [0] * size,
        "cpp_n_true_r": n_true_r,
        "cpp_n_disk_infl": n_disk_infl,
        "cpp_n_disk_unc": (
            n_disk_unc if n_disk_unc is not None else [0] * size
        ),
        "cpp_seed_probes": [20] * size,
        "region_mode": [region_mode] * size,
        "seed_mode": ["binary"] * size,
        "verification_mode": ["original"] * size,
    })


def test_aggregate_ratio_is_sum_over_sum_not_mean_of_ratios():
    """A property admitting 2000 entries must not be weighted like one
    admitting 2. The headline ratio is the workload's cost ratio."""
    summary = describe_ratio(
        pd.Series([2000, 2]), pd.Series([1000, 1])
    )
    assert summary["aggregate_ratio"] == pytest.approx(2002 / 1001)
    assert summary["per_property_mean"] == pytest.approx(2.0)


def test_summarize_counters_reports_ratios_and_totals():
    frame = make_frame(
        n_true_r=[1, 2, 1, 4],
        n_disk_infl=[4, 6, 3, 8],
        n_decomp=[8, 12, 9, 16],
        n_disk_unc=[40, 60, 30, 80],
    )
    summary = summarize_counters(frame, "disk_bbox")

    assert summary["rows"] == 4
    assert summary["unique_property_ids"] == 4
    assert summary["ordering_holds"] is True
    assert summary["uncapped_counterfactual_measured"] is True
    assert summary["geometric_inflation_capped"]["aggregate_ratio"] == (
        pytest.approx(21 / 8)
    )
    assert summary["geometric_inflation_uncapped"]["aggregate_ratio"] == (
        pytest.approx(210 / 8)
    )
    assert summary["split_gain_uncapped_over_capped"]["aggregate_ratio"] == (
        pytest.approx(10.0)
    )
    assert summary["box_vs_disk_inflation"]["aggregate_ratio"] == (
        pytest.approx(45 / 21)
    )


def test_uncapped_absent_is_reported_as_not_measured():
    frame = make_frame([1, 1], [2, 2], [4, 4])
    summary = summarize_counters(frame, "disk_bbox")
    assert summary["uncapped_counterfactual_measured"] is False
    assert "geometric_inflation_uncapped" not in summary


def test_ordering_violations_are_counted_not_hidden():
    """n_true_r > n_disk_infl is geometrically impossible; if the artifact says
    otherwise the summary must fail loudly rather than average it away."""
    frame = make_frame(
        n_true_r=[5, 1], n_disk_infl=[2, 3], n_decomp=[9, 9]
    )
    summary = summarize_counters(frame, "disk_bbox")
    assert summary["ordering_holds"] is False
    assert summary["ordering_violations"]["n_true_r_gt_n_disk_infl"] == 1


def test_n_true_r_below_one_is_a_violation():
    frame = make_frame(n_true_r=[0, 1], n_disk_infl=[2, 3], n_decomp=[9, 9])
    summary = summarize_counters(frame, "disk_bbox")
    assert summary["ordering_violations"]["n_true_r_lt_1"] == 1
    assert summary["ordering_holds"] is False


def test_degenerate_b3a_denominator_is_recorded():
    frame = make_frame(
        n_true_r=[1, 1, 1, 1],
        n_disk_infl=[3, 3, 3, 3],
        n_decomp=[6, 6, 6, 6],
        n_disk_r=[0, 0, 1, 0],
    )
    summary = summarize_counters(frame, "disk_bbox")
    degenerate = summary["degenerate_b3a_denominator"]
    assert degenerate["properties_with_nonzero_n_disk_r"] == 1
    assert degenerate["fraction_nonzero"] == pytest.approx(0.25)


def test_missing_column_names_the_pre_b3b_cause():
    frame = make_frame([1], [2], [4]).drop(columns=["cpp_n_true_r"])
    with pytest.raises(ValueError, match="cpp_n_true_r"):
        summarize_counters(frame, "disk_bbox")


def test_duplicate_property_ids_rejected():
    frame = make_frame([1, 1], [2, 2], [4, 4])
    frame["property_id"] = ["p1", "p1"]
    with pytest.raises(ValueError, match="duplicate"):
        summarize_counters(frame, "disk_bbox")


def test_mixed_region_mode_rejected():
    frame = make_frame([1, 1], [2, 2], [4, 4])
    frame.loc[0, "region_mode"] = "disk"
    with pytest.raises(ValueError, match="not single-valued"):
        summarize_counters(frame, "disk_bbox")


def test_gate_stays_off_below_declared_threshold():
    ratio = GATE_TAIL_RATIO_MAX / 2.0
    frame = make_frame(
        n_true_r=[1] * 100,
        n_disk_infl=[10] * 100,
        n_decomp=[int(10 * ratio)] * 100,
    )
    gate = box_vs_disk_gate(summarize_counters(frame, "disk_bbox"), None)
    assert gate["verdict"] == "disk_predicate_stays_off"


def test_gate_enables_disk_above_declared_threshold():
    frame = make_frame(
        n_true_r=[1] * 100,
        n_disk_infl=[10] * 100,
        n_decomp=[int(10 * (GATE_TAIL_RATIO_MAX + 2))] * 100,
    )
    gate = box_vs_disk_gate(summarize_counters(frame, "disk_bbox"), None)
    assert gate["verdict"] == "enable_disk_predicate"


def test_gate_reports_work_reduction_when_disk_run_supplied():
    box = make_frame([1] * 10, [10] * 10, [40] * 10)
    disk = make_frame(
        [1] * 10, [10] * 10, [20] * 10, region_mode="disk"
    )
    gate = box_vs_disk_gate(
        summarize_counters(box, "disk_bbox"),
        summarize_counters(disk, "disk"),
    )
    assert gate["work_reduction_if_enabled"] == pytest.approx(2.0)


def test_distance_deciles_cover_every_property():
    frame = make_frame(
        n_true_r=[1] * 100,
        n_disk_infl=[5] * 100,
        n_decomp=[10] * 100,
        distances=[float(index) for index in range(100)],
    )
    deciles = inflation_by_distance_decile(frame)
    assert len(deciles) == 10
    assert sum(row["properties"] for row in deciles) == 100
    assert deciles[0]["geometric_inflation_capped"] == pytest.approx(5.0)