"""Unit tests for the B6 analysis derivations.

The analysis is where a wrong number becomes a wrong sentence in a report, so
the derivations are tested rather than eyeballed. Fixtures are small frames
carrying real B6c values where a real value makes the assertion meaningful.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

from caprm.ladder_analysis import (  # noqa: E402
    B5C_NANOSECONDS_PER_RESOLVE_ENTRY,
    adjacent_comparisons,
    cell_statistics,
    check_invariants,
    cost_model,
    memory_table,
    per_property_curve,
    window_curve,
)

COLUMNS = [
    "cell_key", "algorithm", "rung", "workload", "seed_window_build",
    "property_count", "computation_seconds", "session_id", "output_sha256",
    "average_segment_checks_per_property",
    "average_candidate_features_per_property",
    "average_seed_probes_per_property", "resolve_entries_per_property",
    "tight_entries_per_property", "n_true_r_per_property",
    "n_disk_infl_per_property", "geometric_inflation_capped",
    "fraction_window_missed", "mean_d_seed_over_d_best",
    "max_d_seed_over_d_best", "index_bytes", "key_array_bytes",
    "rmi_model_bytes", "peak_working_set_bytes", "peak_commit_bytes",
    "average_node_visits_per_property", "resolve_nodes_per_property",
]


def run(cell, algorithm, rung, workload, window, properties, seconds, **extra):
    record = {name: None for name in COLUMNS}
    record.update(
        cell_key=cell, algorithm=algorithm, rung=rung, workload=workload,
        seed_window_build=window, property_count=properties,
        computation_seconds=seconds, session_id="s1", output_sha256="abc",
    )
    record.update(extra)
    return record


def frame(records):
    return pd.DataFrame(records, columns=COLUMNS)


# ---------------------------------------------------------------------------
# direction
# ---------------------------------------------------------------------------

def _ladder_frame():
    """Countywide medians from B6c invocation A."""
    records = []
    for seconds in (9.0, 9.1167, 9.2):
        records.append(run(
            "segment_bvh@countywide", "segment_bvh", 3, "countywide", None,
            267362, seconds, average_segment_checks_per_property=9407.617649,
            average_candidate_features_per_property=1.466237,
            index_bytes=119768836.0, peak_working_set_bytes=185774080,
            peak_commit_bytes=342327296))
    for seconds in (17.6, 17.75, 17.9):
        records.append(run(
            "hilbert_binary@countywide@w64", "hilbert_binary", 4, "countywide",
            64, 267362, seconds,
            average_segment_checks_per_property=11021.825858,
            resolve_entries_per_property=141.174168,
            tight_entries_per_property=47.59262348426478,
            average_seed_probes_per_property=20.23764,
            fraction_window_missed=0.38615061227848385,
            mean_d_seed_over_d_best=1.1716919272505513,
            max_d_seed_over_d_best=32.23319399612495,
            key_array_bytes=9516712, peak_working_set_bytes=232591360,
            peak_commit_bytes=285212672))
    for seconds in (18.8, 18.9003, 19.0):
        records.append(run(
            "hilbert_rmi@countywide@w64", "hilbert_rmi", 5, "countywide",
            64, 267362, seconds,
            average_segment_checks_per_property=11021.825858,
            resolve_entries_per_property=352.515432,
            tight_entries_per_property=47.59262348426478,
            average_seed_probes_per_property=0.0,
            fraction_window_missed=0.4600915612540301,
            mean_d_seed_over_d_best=1.5388433412534919,
            max_d_seed_over_d_best=517.3435071130551,
            key_array_bytes=9516712, rmi_model_bytes=4194400,
            peak_working_set_bytes=232501248, peak_commit_bytes=285212672))
    return cell_statistics(frame(records))


def test_a_slower_upper_rung_is_reported_as_slower():
    """4 v 3 is a loss and 3 v 2 is a win; a bare ratio invites misreading."""
    comparisons = {c.label: c for c in adjacent_comparisons(_ladder_frame())}
    assert comparisons["4 v 3"].direction == "slower"
    assert comparisons["4 v 3"].factor == pytest.approx(1.947, abs=1e-3)
    assert comparisons["5 v 4"].direction == "slower"
    assert comparisons["5 v 4"].factor == pytest.approx(1.0648, abs=1e-3)


def test_comparison_carries_the_counter_beside_the_clock():
    """Nucleus 18.22: never infer a speedup from counts, so report both."""
    comparisons = {c.label: c for c in adjacent_comparisons(_ladder_frame())}
    assert comparisons["4 v 3"].counter_ratio == pytest.approx(
        9407.617649 / 11021.825858, abs=1e-6
    )


def test_five_versus_three_is_never_emitted():
    labels = {c.label for c in adjacent_comparisons(_ladder_frame())}
    assert "5 v 3" not in labels
    assert labels <= {"2 v 1", "3 v 2", "4 v 3", "5 v 4"}


# ---------------------------------------------------------------------------
# the NaN trap
# ---------------------------------------------------------------------------

def test_rungs_without_a_seed_window_survive_into_the_curve():
    """None must not become NaN: NaN != None silently drops rungs 1-3."""
    curve = per_property_curve(_ladder_frame())
    algorithms = {row["algorithm"] for row in curve
                  if row["seed_window"] in (None, 64)}
    assert "segment_bvh" in algorithms


def test_structure_bytes_are_not_poisoned_by_absent_counters():
    rows = {row["cell_key"]: row for row in memory_table(_ladder_frame())}
    assert rows["hilbert_rmi@countywide@w64"][
        "persistent_structure_bytes"] == 9516712 + 4194400
    assert rows["segment_bvh@countywide"][
        "persistent_structure_bytes"] == 119768836.0


# ---------------------------------------------------------------------------
# cost model
# ---------------------------------------------------------------------------

def test_cost_model_recovers_the_constant_from_exact_data():
    """Synthesise gaps that ARE entries x constant; the slope must return it."""
    records = []
    for window, binary_entries, rmi_entries in (
        (64, 141.174168, 352.515432), (512, 87.909441, 150.062529),
    ):
        delta = rmi_entries - binary_entries
        gap = delta * B5C_NANOSECONDS_PER_RESOLVE_ENTRY / 1e9 * 267362
        for seconds, algorithm, rung, entries in (
            (18.0, "hilbert_binary", 4, binary_entries),
            (18.0 + gap, "hilbert_rmi", 5, rmi_entries),
        ):
            records.append(run(
                f"{algorithm}@countywide@w{window}", algorithm, rung,
                "countywide", window, 267362, seconds,
                resolve_entries_per_property=entries,
                average_seed_probes_per_property=(
                    20.23764 if rung == 4 else 0.0),
            ))
    model = cost_model(cell_statistics(frame(records)))
    assert model["fitted_slope_nanoseconds_per_entry_all"] == pytest.approx(
        B5C_NANOSECONDS_PER_RESOLVE_ENTRY, abs=1e-6
    )
    for point in model["points"]:
        assert point["measured_over_predicted"] == pytest.approx(1.0, abs=1e-6)


def test_cost_model_flags_a_gap_inside_the_noise():
    records = []
    for seconds in (17.0, 18.0, 19.0):
        records.append(run("hilbert_binary@countywide@w64", "hilbert_binary",
                           4, "countywide", 64, 267362, seconds,
                           resolve_entries_per_property=141.174168,
                           average_seed_probes_per_property=20.23764))
    for seconds in (17.1, 18.05, 19.1):
        records.append(run("hilbert_rmi@countywide@w64", "hilbert_rmi",
                           5, "countywide", 64, 267362, seconds,
                           resolve_entries_per_property=352.515432,
                           average_seed_probes_per_property=0.0))
    model = cost_model(cell_statistics(frame(records)))
    assert model["points"][0]["resolvable_against_full_range"] is False


# ---------------------------------------------------------------------------
# invariants
# ---------------------------------------------------------------------------

def test_a_drifting_counter_inside_one_cell_raises():
    records = [
        run("segment_bvh@countywide", "segment_bvh", 3, "countywide", None,
            267362, 9.1, average_segment_checks_per_property=9407.617649),
        run("segment_bvh@countywide", "segment_bvh", 3, "countywide", None,
            267362, 9.2, average_segment_checks_per_property=9407.7),
    ]
    with pytest.raises(ValueError, match="varied across repetitions"):
        cell_statistics(frame(records))


def test_invariants_catch_a_seed_dependent_counter():
    statistics = _ladder_frame()
    statistics.loc[
        statistics["algorithm"] == "hilbert_rmi", "tight_entries_per_property"
    ] = 99.0
    failed = [c for c in check_invariants(statistics) if not c["passed"]]
    assert any("tight_entries_per_property" in c["check"] for c in failed)


def test_invariants_pass_on_clean_data():
    assert all(c["passed"] for c in check_invariants(_ladder_frame()))


def test_brute_force_check_count_is_asserted():
    records = [
        run("brute_force@countywide", "brute_force", 1, "countywide", None,
            267362, 1067.0, average_segment_checks_per_property=999.0),
    ]
    checks = check_invariants(cell_statistics(frame(records)))
    assert any(not c["passed"] for c in checks)


# ---------------------------------------------------------------------------
# window curve
# ---------------------------------------------------------------------------

def test_window_curve_reports_the_uncounted_scan():
    """2W distance computations per query appear in no counter."""
    rows = window_curve(_ladder_frame())
    assert rows[0]["uncounted_window_scan_entries"] == 128
    assert rows[0]["exchange_rate_entries_per_probe"] == pytest.approx(
        (352.515432 - 141.174168) / 20.23764, abs=1e-4
    )