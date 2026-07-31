"""Tests for the C4 item 1 analysis.

The load-bearing test here is ``test_overlapping_ranges_are_not_resolved``. The
sweep produced relative spreads up to 18.6 percent, which is wide enough that
several differences a reader would take from the table do not survive it, so
the rule that suppresses those claims needs a test that fails if the rule is
weakened.
"""

from __future__ import annotations

import json

import pytest

from caprm import c4_analysis as c4a


def timing(seconds):
    ordered = sorted(seconds)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {
        "n_warmup": 1,
        "n_repeat": len(seconds),
        "seconds": list(seconds),
        "median_s": median,
        "min_s": ordered[0],
        "max_s": ordered[-1],
        "mean_s": sum(ordered) / len(ordered),
        "stdev_s": 0.0,
        "relative_spread": (ordered[-1] - ordered[0]) / median,
    }


def sweep_row(label, size, seconds, n=1000):
    block = timing(seconds)
    return {
        "batch_label": label,
        "batch_size": size,
        "is_full_array": label == "full",
        "n_properties": n,
        "n_batches": (n + size - 1) // size,
        "timing": block,
        "properties_per_second_median": n / block["median_s"],
        "properties_per_second_fastest": n / block["min_s"],
        "microseconds_per_property_median": block["median_s"] * 1e6 / n,
        "microseconds_per_property_fastest": block["min_s"] * 1e6 / n,
    }


def run(threads, scale=1.0, breach_batch="1"):
    return {
        "schema_version": "c4_inference_v1",
        "environment": {"thread_environment": {"OPENBLAS_NUM_THREADS": str(threads)}},
        "inputs": {"n_properties": 1000},
        "batch_sweep": [
            sweep_row("1", 1, [0.90 * scale, 0.95 * scale, 1.00 * scale]),
            sweep_row("65536", 65536, [0.10 * scale, 0.11 * scale, 0.12 * scale]),
            sweep_row("full", 1000, [0.105 * scale, 0.115 * scale, 0.125 * scale]),
        ],
        "batch_agreement": {
            "tolerance_index_points": 3.87e-06,
            "max_abs_deviation_index_points": 1.865e-05,
            "per_batch": {
                "1": {"max_abs_deviation": 1.865e-05, "within_tolerance": False},
                "65536": {"max_abs_deviation": 0.0, "within_tolerance": True},
                "full": {"max_abs_deviation": 0.0, "within_tolerance": True},
            },
        },
        "stage_split": {
            "fourier_encoding": timing([0.06 * scale, 0.062 * scale, 0.064 * scale]),
            "mlp_forward": timing([0.02 * scale, 0.021 * scale, 0.022 * scale]),
            "full_predict": timing([0.10 * scale, 0.11 * scale, 0.12 * scale]),
            "fourier_microseconds_per_property": 62.0 * scale,
            "mlp_microseconds_per_property": 21.0 * scale,
            "fourier_over_mlp_ratio": 62.0 / 21.0,
            "parts_minus_whole_fraction_of_whole": -0.026,
        },
    }


# --- the resolution rule ----------------------------------------------------


def test_disjoint_ranges_are_resolved():
    comparison = c4a.compare_samples("a", [1.0, 1.1, 1.2], "b", [0.5, 0.55, 0.6])
    assert comparison.resolved
    assert comparison.verdict == "b faster"
    assert comparison.speedup_median == pytest.approx(1.1 / 0.55)


def test_overlapping_ranges_are_not_resolved():
    """The gap sits inside the cells' range, so no claim is printed."""
    comparison = c4a.compare_samples("a", [1.00, 1.10, 1.30], "b", [0.95, 1.05, 1.25])
    assert not comparison.resolved
    assert comparison.verdict == "NOT RESOLVED"
    low, high = comparison.speedup_low, comparison.speedup_high
    assert low <= 1.0 <= high


def test_resolution_matches_the_range_overlap_it_claims_to_implement():
    """One rule, stated two ways, must agree on every case."""
    cases = [
        ([1.0, 2.0], [3.0, 4.0]),
        ([3.0, 4.0], [1.0, 2.0]),
        ([1.0, 3.0], [2.0, 4.0]),
        ([1.0, 1.0], [1.0, 1.0]),
        ([1.0, 4.0], [2.0, 3.0]),
    ]
    for sample_a, sample_b in cases:
        comparison = c4a.compare_samples("a", sample_a, "b", sample_b)
        disjoint = max(sample_a) < min(sample_b) or max(sample_b) < min(sample_a)
        assert comparison.resolved is disjoint, (sample_a, sample_b)


def test_comparison_rejects_an_empty_sample():
    with pytest.raises(c4a.C4AnalysisError):
        c4a.compare_samples("a", [], "b", [1.0])


def test_identical_samples_are_never_resolved():
    comparison = c4a.compare_samples("a", [1.0, 1.1], "b", [1.0, 1.1])
    assert not comparison.resolved


# --- reading runs -----------------------------------------------------------


def test_load_run_rejects_a_foreign_schema(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"schema_version": "b6_ladder_v1"}), encoding="utf-8")
    with pytest.raises(c4a.C4AnalysisError):
        c4a.load_run(path)


def test_an_unpinned_run_is_refused_rather_than_averaged_in():
    unpinned = run(8)
    unpinned["environment"]["thread_environment"]["OPENBLAS_NUM_THREADS"] = None
    with pytest.raises(c4a.C4AnalysisError, match="not comparable"):
        c4a.thread_count(unpinned)


def test_thread_count_is_read_from_the_artifact():
    assert c4a.thread_count(run(8)) == 8


# --- tables -----------------------------------------------------------------


def test_batch_table_compares_every_batch_to_the_shipped_default():
    rows = c4a.batch_table(run(8))
    labels = [row["batch_label"] for row in rows]
    assert labels == ["1", "65536", "full"]
    default = next(r for r in rows if r["batch_label"] == "65536")
    assert default["is_reference"]
    assert not default["vs_reference"]["resolved"]  # a cell against itself
    slow = next(r for r in rows if r["batch_label"] == "1")
    assert slow["vs_reference"]["resolved"]
    assert slow["vs_reference"]["verdict"] == "b faster"


def test_batch_table_rejects_a_missing_reference():
    with pytest.raises(c4a.C4AnalysisError):
        c4a.batch_table(run(8), reference_label="1024")


def test_thread_table_pairs_shared_batches():
    rows = c4a.thread_table({1: run(1, scale=2.0), 8: run(8, scale=1.0)})
    assert {row["batch_label"] for row in rows} == {"1", "65536", "full"}
    for row in rows:
        assert row["threads_low"] == 1 and row["threads_high"] == 8
        assert row["threading_speedup"]["verdict"] == "b faster"


def test_thread_table_needs_two_runs():
    with pytest.raises(c4a.C4AnalysisError):
        c4a.thread_table({8: run(8)})


def test_split_table_reports_each_stage_separately():
    table = c4a.split_table({1: run(1, scale=2.0), 8: run(8, scale=1.0)})
    assert set(table["stages"]) == {"fourier_encoding", "mlp_forward", "full_predict"}
    assert table["ratio_at_8_threads"]["fourier_over_mlp_ratio"] == pytest.approx(62.0 / 21.0)


def test_agreement_summary_identifies_a_thread_invariant_deviation():
    summary = c4a.agreement_summary({1: run(1), 8: run(8)})
    assert summary["same_batches_breach_at_every_thread_count"]
    assert summary["deviation_identical_across_thread_counts"]["1"] is True
    assert summary["per_thread_count"]["8"]["breaching_batches"] == ["1"]


def test_agreement_summary_flags_a_thread_dependent_deviation():
    moved = run(8)
    moved["batch_agreement"]["per_batch"]["1"]["max_abs_deviation"] = 9.9e-05
    summary = c4a.agreement_summary({1: run(1), 8: moved})
    assert summary["deviation_identical_across_thread_counts"]["1"] is False


# --- rendering --------------------------------------------------------------


def test_markdown_carries_the_verdicts_and_the_caveat():
    analysis = c4a.analyse({1: run(1, scale=2.0), 8: run(8, scale=1.0)})
    text = c4a.markdown_tables(analysis)
    assert "NOT RESOLVED" in text
    assert "reference" in text
    assert "one scalar" in text
    assert "us/prop" in text


def test_analyse_needs_exactly_two_thread_counts():
    with pytest.raises(c4a.C4AnalysisError):
        c4a.analyse({8: run(8)})