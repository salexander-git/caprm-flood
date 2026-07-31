"""Tests for the PHASE B derivations (Milestone 4, chunk B6d).

Every number in `outputs/validation/b6_benchmark_tables.md` is computed by
`caprm.ladder_analysis` and nowhere else, so an analysis that is not tested here
is not reportable. Two kinds of test live in this file:

  regression   a derivation that PHASE B has already published must keep its
               value, so the mode patch is provably non-destructive
  behaviour     the mode dimension, the population split, and the three new
               sections, each tested on the smallest frame that exercises it

The synthetic frames are built by `_cell` rather than read from an artifact, so
the tests state the arithmetic they expect instead of trusting a CSV.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from caprm import ladder_analysis as la
from caprm import ladder_benchmark as lb


# ---------------------------------------------------------------------------
# the constant this module mirrors rather than imports
# ---------------------------------------------------------------------------

def test_verification_modes_match_the_harness():
    """The duplication in ladder_analysis is deliberate; drift is not."""
    assert la.VERIFICATION_MODES == lb.VERIFICATION_MODES
    assert la.DEFAULT_VERIFICATION_MODE == lb.DEFAULT_VERIFICATION_MODE


def test_two_v_one_is_not_an_adjacent_comparison():
    labels = {label for _, _, label, _ in la.ADJACENT_PAIRS}
    assert labels == {"3 v 2", "4 v 3", "5 v 4"}
    assert {label for _, _, label, _ in la.CONTEXT_PAIRS} == {"2 v 1"}


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("absent", [None, "", "   ", float("nan")])
def test_absent_verification_mode_becomes_original(absent):
    """Rungs 1-2 emit nothing and DO verify over original geometry."""
    frame = pd.DataFrame({"algorithm": ["brute_force"], "verification_mode": [absent]})
    assert la.normalize_verification_mode(frame)["verification_mode"].iloc[0] == "original"


def test_missing_column_becomes_original():
    frame = pd.DataFrame({"algorithm": ["brute_force"]})
    assert la.normalize_verification_mode(frame)["verification_mode"].iloc[0] == "original"


def test_unknown_verification_mode_raises():
    """A renamed positional must fail loudly, not be carried into a groupby."""
    frame = pd.DataFrame({"verification_mode": ["origina1"]})
    with pytest.raises(ValueError, match="Unknown verification mode"):
        la.normalize_verification_mode(frame)


def test_normalization_does_not_mutate_the_caller_frame():
    frame = pd.DataFrame({"verification_mode": [None]})
    la.normalize_verification_mode(frame)
    assert frame["verification_mode"].isna().all()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _cell(algorithm, rung, workload, seconds, checks, *, mode="original",
          window=None, properties=1000, digest="d", entries=None,
          candidates=None, true_r=None, admitted=None, inflation=None,
          probes=None, invocation="test"):
    """One statistics row, spelled out so a test can state its arithmetic."""
    return {
        "cell_key": f"{algorithm}@{workload}"
                    + ("@split" if mode == "split" else "")
                    + (f"@w{window}" if window else ""),
        "algorithm": algorithm,
        "rung": rung,
        "workload": workload,
        "verification_mode": mode,
        "invocation": invocation,
        "seed_window": window,
        "n": 7,
        "minimum_seconds": seconds * 0.999,
        "median_seconds": seconds,
        "maximum_seconds": seconds * 1.001,
        "range_seconds": seconds * 0.002,
        "relative_spread": 0.002,
        "standard_deviation_seconds": seconds * 0.0005,
        "median_standard_error_seconds": seconds * 0.0002,
        "property_count": properties,
        "output_sha256": digest,
        "sessions": ["s1"],
        "microseconds_per_property": seconds / properties * 1e6,
        "average_segment_checks_per_property": checks,
        "average_candidate_features_per_property": candidates,
        "average_node_visits_per_property": None,
        "average_seed_probes_per_property": probes,
        "resolve_entries_per_property": entries,
        "resolve_nodes_per_property": None,
        "tight_entries_per_property": 47.0,
        "n_true_r_per_property": true_r,
        "n_disk_infl_per_property": admitted,
        "geometric_inflation_capped": inflation,
        "fraction_window_missed": 0.3,
        "mean_d_seed_over_d_best": 1.1,
        "max_d_seed_over_d_best": 20.0,
        "index_bytes": None,
        "key_array_bytes": None,
        "rmi_model_bytes": None,
        "peak_working_set_bytes": 1000.0,
        "peak_commit_bytes": 2000.0,
        "peak_working_set_bytes_minimum": 1000.0,
        "peak_working_set_bytes_maximum": 1000.0,
        "peak_commit_bytes_minimum": 2000.0,
        "peak_commit_bytes_maximum": 2000.0,
    }


# The fixture is generated FROM the cost model the code is supposed to recover,
# so search really is mode-invariant in it and a decomposition that fails to
# recover these constants has failed rather than merely disagreed with a guess.
PROPERTIES = 1_000
NS_PER_CHECK = {"original": 4.0, "split": 1.0}
CHECKS = {
    3: {"original": 9_000.0, "split": 6_000.0},
    4: {"original": 10_000.0, "split": 6_800.0},
    5: {"original": 10_000.0, "split": 6_800.0},
}
SEARCH_MICROSECONDS = {3: 0.0, 4: 28.0, 5: 33.0}


def _seconds(rung, mode):
    """Total seconds implied by the planted search and per-check costs."""
    microseconds = (
        SEARCH_MICROSECONDS[rung]
        + CHECKS[rung][mode] * NS_PER_CHECK[mode] / 1000.0
    )
    return microseconds * PROPERTIES / 1e6


@pytest.fixture
def both_modes():
    """Rungs 1-5, countywide, with rungs 3-5 measured in both modes."""
    rows = [
        _cell("brute_force", 1, "countywide", 100.0, 1_063_159.0,
              properties=PROPERTIES),
        _cell("feature_bvh", 2, "countywide", 10.0, 70_000.0, candidates=5.5,
              properties=PROPERTIES),
    ]
    for algorithm, rung, entries, probes in (
        ("segment_bvh", 3, None, None),
        ("hilbert_binary", 4, 100.0, 20.0),
        ("hilbert_rmi", 5, 300.0, 1.0),
    ):
        for mode in ("original", "split"):
            rows.append(_cell(
                algorithm, rung, "countywide", _seconds(rung, mode),
                CHECKS[rung][mode], mode=mode,
                window=64 if rung >= 4 else None,
                candidates=1.5 if rung == 3 else None,
                entries=entries, probes=probes, properties=PROPERTIES,
                digest="e" if mode == "split" else "d",
            ))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# the defect the patch closes
# ---------------------------------------------------------------------------

def test_both_modes_produce_a_full_set_of_comparisons(both_modes):
    """Before the patch, last-write-wins emitted ONE mode and recorded none."""
    got = {(c.verification_mode, c.label) for c in la.adjacent_comparisons(both_modes)}
    assert got == {
        (mode, label)
        for mode in ("original", "split")
        for label in ("3 v 2", "4 v 3", "5 v 4")
    }


def test_three_v_two_exists_in_both_columns(both_modes):
    """Rungs 1-2 have no fork, so they are borrowed into the split column."""
    by_mode = {
        c.verification_mode: c for c in la.adjacent_comparisons(both_modes)
        if c.label == "3 v 2"
    }
    for mode in ("original", "split"):
        assert by_mode[mode].time_ratio == pytest.approx(
            10.0 / _seconds(3, mode)
        )
    # The same rung 2 measurement serves both columns, so the split column
    # reports a LARGER granularity win purely because its rung 3 is cheaper.
    assert by_mode["split"].time_ratio > by_mode["original"].time_ratio


def test_rung_one_absent_unless_context_requested(both_modes):
    assert all(c.label != "2 v 1" for c in la.adjacent_comparisons(both_modes))
    with_context = la.adjacent_comparisons(both_modes, include_context=True)
    context = [c for c in with_context if c.label == "2 v 1"]
    assert context and all(c.is_context for c in context)


def test_differing_digests_across_modes_are_not_a_neutrality_failure(both_modes):
    """Option A and Option B legitimately differ; only WINDOWS are byte-neutral."""
    failures = [c for c in la.check_invariants(both_modes) if not c["passed"]]
    assert failures == []


def test_seed_invariant_counters_still_fail_when_genuinely_violated(both_modes):
    """The check must retain its teeth after the grouping change."""
    broken = both_modes.copy()
    broken.loc[broken["algorithm"] == "hilbert_rmi", "tight_entries_per_property"] = 99.0
    names = {
        c["check"] for c in la.check_invariants(broken) if not c["passed"]
    }
    assert "seed-invariant: tight_entries_per_property" in names


def test_comparison_names_its_mode(both_modes):
    for record in (c.as_dict() for c in la.adjacent_comparisons(both_modes)):
        assert record["verification_mode"] in la.VERIFICATION_MODES


# ---------------------------------------------------------------------------
# cost model populations
# ---------------------------------------------------------------------------

def test_cost_model_separates_the_sweep_from_mixed_workloads():
    """The published 20.33 and the documented 21.02 are different populations."""
    rows = [
        _cell("hilbert_binary", 4, "countywide", 10.0, 100.0, window=w,
              entries=100.0, probes=20.0)
        for w in (8, 64, 512)
    ] + [
        _cell("hilbert_rmi", 5, "countywide", 10.0 + w / 1000, 100.0, window=w,
              entries=200.0, probes=1.0)
        for w in (8, 64, 512)
    ] + [
        _cell("hilbert_binary", 4, "10000", 1.0, 100.0, window=64,
              entries=100.0, probes=20.0),
        _cell("hilbert_rmi", 5, "10000", 1.2, 100.0, window=64,
              entries=200.0, probes=1.0),
    ]
    model = la.cost_model(pd.DataFrame(rows))
    assert model["populations"]["all_points"]["point_count"] == 4
    assert model["populations"]["window_sweep_only"]["point_count"] == 3
    assert model["populations"]["window_sweep_only"][
        "workload_mode_invocation"
    ] == ["countywide@original@test"]
    assert (model["populations"]["all_points"]["slope_nanoseconds_per_entry"]
            != model["populations"]["window_sweep_only"]["slope_nanoseconds_per_entry"])


def test_resolvable_only_is_flagged_as_not_a_fit(both_modes):
    model = la.cost_model(both_modes)
    population = model["populations"]["resolvable_only"]
    assert population["is_a_fit"] is (population["point_count"] >= 5)


def test_cost_model_points_name_their_mode(both_modes):
    modes = {p["verification_mode"] for p in la.cost_model(both_modes)["points"]}
    assert modes == {"original", "split"}


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------

def test_memory_rows_name_their_invocation():
    """Two invocations of one cell are two measurements, and must be labelled."""
    rows = pd.DataFrame([
        _cell("brute_force", 1, "countywide", 100.0, 1_063_159.0),
        _cell("hilbert_rmi", 5, "countywide", 4.0, 10.0, window=64,
              invocation="ladder"),
        _cell("hilbert_rmi", 5, "countywide", 4.1, 10.0, window=64,
              invocation="sweep"),
    ])
    table = la.memory_table(rows)
    learned = [r for r in table if r["algorithm" if False else "cell_key"].startswith("hilbert_rmi")]
    assert len(learned) == 2
    assert {r["invocation"] for r in learned} == {"ladder", "sweep"}


def test_cross_invocation_agreement_refuses_a_concatenation(both_modes):
    doubled = pd.concat([both_modes, both_modes], ignore_index=True)
    with pytest.raises(ValueError, match="one row per cell"):
        la.cross_invocation_agreement(doubled, doubled, "a", "b")


# ---------------------------------------------------------------------------
# search versus verification
# ---------------------------------------------------------------------------

def test_per_check_cost_is_calibrated_per_mode(both_modes):
    result = la.verification_decomposition(both_modes, rung3_search_fraction=0.0)
    by_mode = {r["verification_mode"]: r for r in result["per_check_nanoseconds"]}
    for mode, expected in NS_PER_CHECK.items():
        assert by_mode[mode]["nanoseconds_per_check"] == pytest.approx(expected)
    assert by_mode["split"]["original_over_split_ratio"] == pytest.approx(
        NS_PER_CHECK["original"] / NS_PER_CHECK["split"]
    )


def test_search_cost_is_mode_invariant_out_of_sample(both_modes):
    """Rungs 4-5 never enter the calibration, so their agreement is a test."""
    result = la.verification_decomposition(both_modes, rung3_search_fraction=0.0)
    assert len(result["search_mode_invariance"]) == 2
    for record in result["search_mode_invariance"]:
        assert record["out_of_sample"] is True
        # Exact, because the fixture was built from a mode-invariant search cost.
        assert record["relative_disagreement"] == pytest.approx(0.0, abs=1e-12)
    by_algorithm = {r["algorithm"]: r for r in result["search_mode_invariance"]}
    assert by_algorithm["hilbert_binary"]["search_microseconds_by_mode"][
        "original"
    ] == pytest.approx(SEARCH_MICROSECONDS[4])
    assert by_algorithm["hilbert_rmi"]["search_microseconds_by_mode"][
        "split"
    ] == pytest.approx(SEARCH_MICROSECONDS[5])


def test_negative_search_cost_is_flagged_not_published():
    """A cell the calibration cannot explain must be marked, not printed."""
    rows = pd.DataFrame([
        _cell("segment_bvh", 3, "countywide", 2.0, 9_000.0),
        # Same checks, far LESS time than rung 3: implies negative search.
        _cell("hilbert_binary", 4, "countywide", 1.0, 9_000.0, window=64,
              entries=100.0, probes=20.0),
    ])
    cells = la.verification_decomposition(rows, rung3_search_fraction=0.0)["cells"]
    flagged = [c for c in cells if not c["search_is_physical"]]
    assert flagged and flagged[0]["rung"] == 4


def test_exactly_determined_solve_reports_its_own_unusability(both_modes):
    """Its failure is why the anchored calibration exists; keep it recorded."""
    diagnostics = la.verification_decomposition(both_modes)[
        "exactly_determined_diagnostic"
    ]
    assert diagnostics
    record = diagnostics[0]
    assert record["usable"] is (
        record["implied_rung3_search_microseconds_per_property"] >= 0.0
    )
    if not record["usable"]:
        assert "ill-conditioned" in record["why_not_usable"]


# ---------------------------------------------------------------------------
# inflation
# ---------------------------------------------------------------------------

def test_inflation_recomputes_the_emitted_ratio():
    """The counter is checked against its own definition, not trusted."""
    rows = pd.DataFrame([
        _cell("hilbert_binary", 4, "countywide", 4.0, 11_021.83, window=64,
              entries=141.17, probes=20.0,
              true_r=1.6067, admitted=10.2783, inflation=10.2783 / 1.6067),
    ])
    row = la.inflation_axis(rows)[0]
    assert row["geometric_inflation_recomputed"] == pytest.approx(
        row["geometric_inflation_capped"]
    )


def test_inflation_and_verification_move_in_opposite_directions():
    """Nucleus 18.19: nearer water raises inflation while phase-2 checks fall."""
    rows = pd.DataFrame([
        _cell("hilbert_binary", 4, "countywide", 4.0, 11_021.83, window=64,
              entries=141.17, probes=20.0, true_r=1.6067, admitted=10.2783,
              inflation=6.3972),
        _cell("hilbert_binary", 4, "10000", 0.4, 1_486.11, window=64,
              entries=141.17, probes=20.0, true_r=1.6906, admitted=11.7066,
              inflation=6.9245),
    ])
    by_workload = {r["workload"]: r for r in la.inflation_axis(rows)}
    near, county = by_workload["10000"], by_workload["countywide"]
    assert near["geometric_inflation_capped"] > county["geometric_inflation_capped"]
    assert (near["phase2_segment_checks_per_property"]
            < county["phase2_segment_checks_per_property"])


def test_uncounted_window_scan_is_reported_as_2w():
    rows = pd.DataFrame([
        _cell("hilbert_binary", 4, "countywide", 4.0, 100.0, window=2048,
              entries=72.88, probes=20.0, true_r=1.6, admitted=10.2, inflation=6.4),
    ])
    row = la.inflation_axis(rows)[0]
    assert row["uncounted_window_scan_entries"] == 4096
    assert row["uncounted_over_counted_entries"] == pytest.approx(4096 / 72.88)


def test_cells_without_inflation_counters_are_omitted(both_modes):
    """Rungs 1-3 emit no inflation counters and must not appear as zeros."""
    assert la.inflation_axis(both_modes) == []


# ---------------------------------------------------------------------------
# access-pattern fit
# ---------------------------------------------------------------------------

def test_access_pattern_fit_recovers_planted_coefficients():
    """A fit that cannot recover a known answer cannot be trusted on real data."""
    intercept, window_ns, resolve_ns, properties = 60000.0, 3.0, 24.0, 1000
    rows = []
    for index, window in enumerate((8, 32, 128, 512, 2048)):
        # NOT affine in the window, or the design matrix is singular by
        # construction and the fit cannot identify three coefficients from two
        # independent columns. The first draft of this test made that mistake.
        entries = 400.0 / (1.0 + window / 500.0)
        nanoseconds = intercept + window_ns * 2 * window + resolve_ns * entries
        rows.append(_cell(
            "hilbert_binary" if index % 2 == 0 else "hilbert_rmi",
            4 if index % 2 == 0 else 5, "countywide",
            nanoseconds * properties / 1e9, 100.0,
            window=window, entries=entries, probes=20.0, properties=properties,
        ))
    fit = la.access_pattern_fit(pd.DataFrame(rows))["fits"][0]
    assert fit["window_scan_nanoseconds_per_entry"] == pytest.approx(window_ns, rel=1e-6)
    assert fit["resolve_descent_nanoseconds_per_entry"] == pytest.approx(resolve_ns, rel=1e-6)
    assert fit["locality_premium"] == pytest.approx(resolve_ns / window_ns, rel=1e-6)
    assert fit["r_squared"] == pytest.approx(1.0, abs=1e-9)


def test_access_pattern_fit_is_labelled_exploratory():
    assert la.access_pattern_fit(pd.DataFrame([]).reindex(
        columns=["rung", "workload", "verification_mode", "invocation"]
    ))["is_exploratory"] is True


def test_access_pattern_fit_refuses_too_few_windows(both_modes):
    """Three coefficients need more than two distinct windows to identify."""
    assert la.access_pattern_fit(both_modes)["fits"] == []


def test_least_squares_returns_none_on_a_singular_design():
    assert la._least_squares([[1.0, 1.0, 1.0]] * 3, [1.0, 1.0, 1.0]) is None


def test_absolute_gap_accompanies_every_ratio(both_modes):
    """Nucleus 18.27: the counted absolute is the invariant, the percent is not."""
    for comparison in la.adjacent_comparisons(both_modes):
        record = comparison.as_dict()
        assert record["gap_microseconds_per_property"] == pytest.approx(
            record["gap_seconds"] / PROPERTIES * 1e6
        )


def test_five_v_four_absolute_gap_is_mode_invariant(both_modes):
    """The fixture plants equal per-rung search, so only the denominator moves."""
    gaps = {
        c.verification_mode: c.as_dict()["gap_microseconds_per_property"]
        for c in la.adjacent_comparisons(both_modes) if c.label == "5 v 4"
    }
    expected = SEARCH_MICROSECONDS[5] - SEARCH_MICROSECONDS[4]
    assert gaps["original"] == pytest.approx(expected)
    assert gaps["split"] == pytest.approx(expected)
    # The percentage is NOT invariant, because verification dilutes it.
    ratios = {
        c.verification_mode: c.factor
        for c in la.adjacent_comparisons(both_modes) if c.label == "5 v 4"
    }
    assert ratios["split"] > ratios["original"]


def test_cost_model_populations_do_not_cross_invocations():
    """A W=64 cell measured twice must not join a nine-window sweep population."""
    rows = []
    for window in (8, 64, 512):
        rows += [
            _cell("hilbert_binary", 4, "countywide", 10.0, 100.0, window=window,
                  entries=100.0, probes=20.0, invocation="sweep"),
            _cell("hilbert_rmi", 5, "countywide", 10.0 + window / 1000, 100.0,
                  window=window, entries=200.0, probes=1.0, invocation="sweep"),
        ]
    # The same cell, re-measured in another invocation about one percent apart.
    rows += [
        _cell("hilbert_binary", 4, "countywide", 10.1, 100.0, window=64,
              entries=100.0, probes=20.0, invocation="b6c2"),
        _cell("hilbert_rmi", 5, "countywide", 10.2, 100.0, window=64,
              entries=200.0, probes=1.0, invocation="b6c2"),
    ]
    model = la.cost_model(pd.DataFrame(rows))
    assert model["populations"]["all_points"]["point_count"] == 4
    sweep = model["populations"]["window_sweep_only"]
    assert sweep["point_count"] == 3
    assert sweep["workload_mode_invocation"] == ["countywide@original@sweep"]


def test_decomposition_excludes_rungs_that_verify_differently(both_modes):
    """A brute-force check is not a segment-BVH check (B2)."""
    assert la.DECOMPOSABLE_RUNGS == (3, 4, 5)
    cells = la.verification_decomposition(both_modes)["cells"]
    assert {c["rung"] for c in cells} <= {3, 4, 5}
    assert all(c["search_is_physical"] for c in cells)


def test_comparisons_within_one_invocation_are_not_marked_as_crossing(both_modes):
    for comparison in la.adjacent_comparisons(both_modes):
        assert comparison.crosses_invocation is False


def test_borrowing_rung_two_marks_the_comparison_as_crossing():
    """Rung 2 lives in one invocation, so Option B's 3 v 2 must be labelled."""
    rows = pd.DataFrame([
        _cell("feature_bvh", 2, "countywide", 10.0, 70_000.0, candidates=5.5,
              invocation="ladder"),
        _cell("segment_bvh", 3, "countywide", 1.0, 6_000.0, candidates=1.5,
              mode="split", digest="e", invocation="b6c2"),
    ])
    granularity = [c for c in la.adjacent_comparisons(rows) if c.label == "3 v 2"]
    assert granularity and granularity[0].crosses_invocation is True