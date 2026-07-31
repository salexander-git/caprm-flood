"""Unit tests for the B6 ladder benchmark harness.

These exercise the pure logic: the stdout vocabulary, the eligibility rule, the
blocked schedule, command construction, and the dispersion and determinism
gates. Running the binaries is the harness's job, not a unit test's.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "python"))

from caprm.ladder_benchmark import (  # noqa: E402
    FORBIDDEN_BENCHMARK_FLAGS,
    LADDER,
    LADDER_BY_NAME,
    RungSpec,
    BenchmarkIneligibleError,
    RunRecorder,
    _merge_query_stats,
    split_annotation,
    DEFAULT_VERIFICATION_MODE,
    VERIFICATION_MODES,
    assert_benchmark_eligible,
    assert_expected_digest,
    expected_digest_for,
    blocked_schedule,
    build_command,
    dispersion,
    parse_expected_digests,
    parse_ladder_output,
    summarize_cell,
    verification_positionals,
)


# ---------------------------------------------------------------------------
# stdout samples, transcribed from the binaries' own print statements
# ---------------------------------------------------------------------------

BRUTE_FORCE_STDOUT = """
Properties: 10000
Water features: 8572
Vertices: 1072254
Segments: 1063159
Input loading seconds: 1.618952
Brute-force computation seconds: 42.631200
Properties per second: 234.580712
Total segment checks: 10631590000
Average segment checks per property: 1063159.000000
"""

FEATURE_BVH_STDOUT = """
Properties: 10000
Water features: 8572
Vertices: 1072254
Segments: 1063159
BVH nodes: 2807
Input loading seconds: 1.647932
Index construction seconds: 0.003197
Indexed computation seconds: 2.091000
Properties per second: 4783.581229
Total segment checks: 707706000
Average segment checks per property: 70770.600000
Total index node visits: 250124
Average node visits per property: 25.012358
Total candidate feature checks: 54976
Average candidate features per property: 5.497569
"""

SEGMENT_BVH_STDOUT = """
Properties: 10000
Water features: 8572
Vertices: 1072254
Segments (kernel count): 1063159
Original segments (split input): 1063159
Split segments (BVH leaves): 1189589
Added segments: 126430
Max segment length cap (m): 25.000000
Max original segment length (m): 5748.239600
Max split segment length (m): 24.999998
Max entry extent (m): 25.000000
Index entries: 1189589
Index bytes: 125616000
BVH nodes: 1189589
Verification mode: original
Input loading seconds: 1.700000
Index construction seconds: 1.100000
Segment-BVH computation seconds: 0.359000
Properties per second: 27855.153203
Total segment checks: 97168700
Average segment checks per property: 9716.870000
Average segment box tests per property: 6.490000
Total index node visits: 282900
Average node visits per property: 28.290000
Total candidate feature checks: 14970
Average candidate features per property: 1.497000
"""

HILBERT_STDOUT_TEMPLATE = """
Properties: 10000
Water features: 8572
Vertices: 1072254
Segments (kernel count): 1063159
Split segments (index entries): 1189589
Verification mode: original
Region mode: disk
Seed mode: {seed_mode} (window 64 entries either side)
Index entries: 1189589
Key array bytes: 9516712
Hilbert order (bits/axis): 32
Max split segment length L (m): 24.999998
Inflation half L/2 (m): 12.499999
{rmi_block}Index construction seconds: 1.200000
Hilbert computation seconds: {seconds}
Properties per second: 13729.000000
Average seed probes per property: {seed_probes}
Average range nodes visited per property: 60.319907
Average ranges emitted per property: 12.000000
Average entries scanned per property (N_decomp): 47.592623
Average entries satisfying the predicate (N_true_r): 1.606700
Average midpoints in disk(r+L/2) per property (N_disk_infl): 10.278300
Geometric L/2 inflation, capped (N_disk_infl / N_true_r): 6.397000
Box-vs-disk indexing inflation (N_decomp / N_disk_infl): 4.630000
Average RESOLVE descent nodes per property: {resolve_nodes}
Average RESOLVE descent entries per property: {resolve_entries}
Mean d_seed / d_best: {ratio} (max 25.058606, over 10000 properties with d_best > 0)
Average phase-2 segment checks per property: 11021.825858
Query-stats report: stats.json (benchmark-eligible; these counters are free)
"""

RMI_BLOCK = (
    "RMI model: models/water_hilbert_rmi.bin\n"
    "RMI model bytes: 4194400\n"
    "RMI second-stage models: 131072\n"
    "RMI probe records asserted: 5\n"
)


def hilbert_stdout(seed_mode: str) -> str:
    if seed_mode == "rmi":
        return HILBERT_STDOUT_TEMPLATE.format(
            seed_mode="rmi",
            rmi_block=RMI_BLOCK,
            seconds="0.771000",
            seed_probes="0.000000",
            resolve_nodes="83.168420",
            resolve_entries="352.515432",
            ratio="1.538843",
        )
    return HILBERT_STDOUT_TEMPLATE.format(
        seed_mode="binary",
        rmi_block="",
        seconds="0.728000",
        seed_probes="20.237640",
        resolve_nodes="70.913503",
        resolve_entries="141.174168",
        ratio="1.171692",
    )


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def test_brute_force_stdout_parses():
    metrics = parse_ladder_output(
        BRUTE_FORCE_STDOUT, LADDER_BY_NAME["brute_force"]
    )
    assert metrics["rung"] == 1
    assert metrics["property_count"] == 10000
    assert metrics["computation_seconds"] == pytest.approx(42.6312)
    assert metrics["total_segment_checks"] == 10631590000


def test_feature_bvh_stdout_parses():
    metrics = parse_ladder_output(
        FEATURE_BVH_STDOUT, LADDER_BY_NAME["feature_bvh"]
    )
    assert metrics["computation_seconds"] == pytest.approx(2.091)
    assert metrics["average_candidate_features_per_property"] == pytest.approx(
        5.497569
    )


def test_segment_bvh_stdout_parses_and_reports_index_bytes():
    metrics = parse_ladder_output(
        SEGMENT_BVH_STDOUT, LADDER_BY_NAME["segment_bvh"]
    )
    assert metrics["computation_seconds"] == pytest.approx(0.359)
    assert metrics["index_entries"] == 1189589
    assert metrics["index_bytes"] == 125616000
    assert metrics["verification_mode"] == "original"


@pytest.mark.parametrize("seed_mode", ["binary", "rmi"])
def test_hilbert_stdout_parses(seed_mode):
    rung = LADDER_BY_NAME[
        "hilbert_binary" if seed_mode == "binary" else "hilbert_rmi"
    ]
    metrics = parse_ladder_output(hilbert_stdout(seed_mode), rung)
    assert metrics["seed_mode"] == seed_mode
    assert metrics["region_mode"] == "disk"
    assert metrics["key_array_bytes"] == 9516712
    assert metrics["geometric_inflation_capped"] == pytest.approx(6.397)


def test_hilbert_phase2_label_maps_to_the_shared_segment_check_field():
    """4 vs 3 compares the same quantity under two labels."""
    hilbert = parse_ladder_output(
        hilbert_stdout("binary"), LADDER_BY_NAME["hilbert_binary"]
    )
    segment_bvh = parse_ladder_output(
        SEGMENT_BVH_STDOUT, LADDER_BY_NAME["segment_bvh"]
    )
    assert "average_segment_checks_per_property" in hilbert
    assert "average_segment_checks_per_property" in segment_bvh
    assert hilbert["average_segment_checks_per_property"] == pytest.approx(
        11021.825858
    )


def test_annotated_float_keeps_only_the_value():
    value, annotation = split_annotation(
        "1.252111 (max 25.058606, over 10000 properties with d_best > 0)"
    )
    assert value == "1.252111"
    assert annotation.startswith("max 25.058606")


def test_unannotated_value_is_returned_unchanged():
    assert split_annotation("20.237640") == ("20.237640", None)


def test_annotated_mean_ratio_parses_as_a_float():
    metrics = parse_ladder_output(
        hilbert_stdout("binary"), LADDER_BY_NAME["hilbert_binary"]
    )
    assert metrics["mean_d_seed_over_d_best"] == pytest.approx(1.171692)


def test_seed_mode_annotation_is_stripped_and_the_window_captured():
    metrics = parse_ladder_output(
        hilbert_stdout("binary"), LADDER_BY_NAME["hilbert_binary"]
    )
    assert metrics["seed_mode"] == "binary"
    assert metrics["seed_window_entries_stdout"] == 64


def test_missing_required_metric_is_an_error():
    truncated = "\n".join(BRUTE_FORCE_STDOUT.splitlines()[:4])
    with pytest.raises(ValueError, match="missing required metrics"):
        parse_ladder_output(truncated, LADDER_BY_NAME["brute_force"])


# ---------------------------------------------------------------------------
# eligibility
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag", FORBIDDEN_BENCHMARK_FLAGS)
def test_forbidden_flags_are_refused(flag):
    with pytest.raises(BenchmarkIneligibleError):
        assert_benchmark_eligible(["water_distance_hilbert.exe", flag, "1"])


@pytest.mark.parametrize("flag", FORBIDDEN_BENCHMARK_FLAGS)
def test_forbidden_flags_are_refused_in_equals_form(flag):
    with pytest.raises(BenchmarkIneligibleError):
        assert_benchmark_eligible(["water_distance_hilbert.exe", f"{flag}=1"])


def test_query_stats_is_eligible():
    assert_benchmark_eligible(
        ["water_distance_hilbert.exe", "--query-stats", "stats.json"]
    )


# ---------------------------------------------------------------------------
# command construction
# ---------------------------------------------------------------------------

def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "executable": tmp_path / "water.exe",
        "properties_path": tmp_path / "properties.csv",
        "features_path": tmp_path / "features.csv",
        "vertices_path": tmp_path / "vertices.csv",
        "output_path": tmp_path / "out.csv",
    }


def test_segment_bvh_command_carries_the_operating_point(tmp_path):
    command = build_command(rung=LADDER_BY_NAME["segment_bvh"], **_paths(tmp_path))
    assert command[-3:] == ["EPSG:26918", "25", "original"]


def test_hilbert_binary_command_uses_disk_and_requires_query_stats(tmp_path):
    paths = _paths(tmp_path)
    with pytest.raises(ValueError, match="--query-stats"):
        build_command(
            rung=LADDER_BY_NAME["hilbert_binary"],
            manifest_path=tmp_path / "manifest.json",
            **paths,
        )
    command = build_command(
        rung=LADDER_BY_NAME["hilbert_binary"],
        manifest_path=tmp_path / "manifest.json",
        query_stats_path=tmp_path / "stats.json",
        **paths,
    )
    assert "disk" in command
    assert command[command.index("--seed") + 1] == "binary"


def test_rmi_command_refuses_to_run_without_probe_records(tmp_path):
    paths = _paths(tmp_path)
    with pytest.raises(ValueError, match="rmi-probes"):
        build_command(
            rung=LADDER_BY_NAME["hilbert_rmi"],
            manifest_path=tmp_path / "manifest.json",
            query_stats_path=tmp_path / "stats.json",
            rmi_model_path=tmp_path / "model.bin",
            rmi_probes="",
            **paths,
        )


def test_rmi_command_is_well_formed(tmp_path):
    command = build_command(
        rung=LADDER_BY_NAME["hilbert_rmi"],
        manifest_path=tmp_path / "manifest.json",
        query_stats_path=tmp_path / "stats.json",
        rmi_model_path=tmp_path / "model.bin",
        rmi_probes="0,1,0x1p+0,0,0",
        **_paths(tmp_path),
    )
    assert command[command.index("--seed") + 1] == "rmi"
    assert command[command.index("--rmi-probes") + 1] == "0,1,0x1p+0,0,0"


def test_rungs_4_and_5_differ_only_in_the_seam(tmp_path):
    """The 5-vs-4 comparison is only honest if nothing else differs."""
    shared = dict(
        manifest_path=tmp_path / "manifest.json",
        query_stats_path=tmp_path / "stats.json",
        **_paths(tmp_path),
    )
    binary = build_command(rung=LADDER_BY_NAME["hilbert_binary"], **shared)
    rmi = build_command(
        rung=LADDER_BY_NAME["hilbert_rmi"],
        rmi_model_path=tmp_path / "model.bin",
        rmi_probes="0,1,0x1p+0,0,0",
        **shared,
    )
    seam = {"--seed", "binary", "rmi", "--rmi-model", "--rmi-probes"}
    assert [token for token in binary if token not in seam] == [
        token
        for token in rmi
        if token not in seam
        and not token.endswith("model.bin")
        and token != "0,1,0x1p+0,0,0"
    ]


# ---------------------------------------------------------------------------
# verification mode as a cell dimension (B6c-2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name", ["segment_bvh", "hilbert_binary", "hilbert_rmi"]
)
def test_the_three_forkable_rungs_declare_the_mode_slot(name):
    assert LADDER_BY_NAME[name].verification_mode_position == 2


@pytest.mark.parametrize("name", ["brute_force", "feature_bvh"])
def test_rungs_one_and_two_have_no_mode_slot(name):
    """They verify over original geometry by construction, so there is no fork."""
    assert LADDER_BY_NAME[name].verification_mode_position is None


@pytest.mark.parametrize(
    "name", ["segment_bvh", "hilbert_binary", "hilbert_rmi"]
)
def test_substituting_split_touches_only_the_mode_slot(name):
    rung = LADDER_BY_NAME[name]
    original = verification_positionals(rung, "original")
    split = verification_positionals(rung, "split")
    assert original == rung.trailing_positionals
    assert split[2] == "split"
    assert [a for i, a in enumerate(split) if i != 2] == [
        a for i, a in enumerate(original) if i != 2
    ]


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="Unknown verification mode"):
        verification_positionals(LADDER_BY_NAME["segment_bvh"], "approximate")


def test_split_is_refused_for_a_rung_without_the_fork():
    with pytest.raises(ValueError, match="no verification-mode argument"):
        verification_positionals(LADDER_BY_NAME["feature_bvh"], "split")


def test_the_mode_slot_is_asserted_before_substitution(tmp_path):
    """If the positional order changes, fail rather than rewrite the cap."""
    broken = RungSpec(
        number=3,
        name="segment_bvh",
        executable_key="segment_bvh",
        trailing_positionals=("EPSG:26918", "original", "25"),
        verification_mode_position=2,
    )
    with pytest.raises(ValueError, match="not a verification mode"):
        verification_positionals(broken, "split")


def test_build_command_carries_the_requested_mode(tmp_path):
    command = build_command(
        rung=LADDER_BY_NAME["segment_bvh"],
        verification_mode="split",
        **_paths(tmp_path),
    )
    assert command[-3:] == ["EPSG:26918", "25", "split"]


def test_default_mode_is_option_a():
    assert DEFAULT_VERIFICATION_MODE == "original"
    assert set(VERIFICATION_MODES) == {"original", "split"}


def test_an_unqualified_digest_does_not_span_verification_modes():
    """The bug B6c-2 hit on its first run.

    A bare rung digest legitimately spans all nine seed windows, because the
    window is byte-neutral. It must NOT span verification modes, which change the
    bytes by design.
    """
    expected = {"segment_bvh@countywide": GOOD}
    assert expected_digest_for(
        "segment_bvh", "countywide", expected, "segment_bvh@countywide",
        allow_unqualified=True,
    ) == GOOD
    assert expected_digest_for(
        "segment_bvh", "countywide", expected, "segment_bvh@countywide@split",
        allow_unqualified=False,
    ) is None


def test_a_split_cell_named_explicitly_is_still_gated():
    expected = {"segment_bvh@countywide@split": GOOD}
    assert expected_digest_for(
        "segment_bvh", "countywide", expected, "segment_bvh@countywide@split",
        allow_unqualified=False,
    ) == GOOD
    assert_expected_digest(
        "segment_bvh", GOOD, expected, "countywide",
        cell_key="segment_bvh@countywide@split", allow_unqualified=False,
    )
    with pytest.raises(RuntimeError, match="changed answer"):
        assert_expected_digest(
            "segment_bvh", BAD, expected, "countywide",
            cell_key="segment_bvh@countywide@split", allow_unqualified=False,
        )


def test_an_unqualified_digest_still_spans_seed_windows():
    """B6b proved the window byte-neutral, so one digest gates all nine."""
    expected = {"hilbert_binary": GOOD}
    for window in (8, 64, 2048):
        assert expected_digest_for(
            "hilbert_binary", "countywide", expected,
            f"hilbert_binary@countywide@w{window}", allow_unqualified=True,
        ) == GOOD


def test_a_cell_key_digest_beats_a_rung_digest():
    """Option A and Option B differ in bytes, so a rung-keyed digest is wrong."""
    expected = {
        "hilbert_binary": BAD,
        "hilbert_binary@countywide@w64": GOOD,
    }
    assert expected_digest_for(
        "hilbert_binary", "countywide", expected,
        "hilbert_binary@countywide@w64",
    ) == GOOD
    assert expected_digest_for(
        "hilbert_binary", "countywide", expected,
        "hilbert_binary@countywide@split@w64",
    ) == BAD


# ---------------------------------------------------------------------------
# scheduling
# ---------------------------------------------------------------------------

CELLS = ["brute_force@countywide", "hilbert_binary@countywide@w64"]
REPS = {"brute_force@countywide": 3, "hilbert_binary@countywide@w64": 7}


def test_schedule_is_blocked_by_repetition_not_by_cell():
    schedule = blocked_schedule(CELLS, REPS, warmups=1, rotate=False)
    timed = [entry for entry in schedule if not entry.is_warmup]
    assert [entry.cell_key for entry in timed[:4]] == [
        CELLS[0], CELLS[1], CELLS[0], CELLS[1],
    ]


def test_schedule_honours_per_cell_repetition_counts():
    schedule = blocked_schedule(CELLS, REPS, warmups=1)
    timed = [entry for entry in schedule if not entry.is_warmup]
    assert sum(entry.cell_key == CELLS[0] for entry in timed) == 3
    assert sum(entry.cell_key == CELLS[1] for entry in timed) == 7
    assert sum(entry.is_warmup for entry in schedule) == 2


def test_rotation_moves_each_cell_through_positions():
    """Fixed order confounds position within a block with the cell itself."""
    keys = ["a", "b", "c"]
    schedule = blocked_schedule(keys, {k: 3 for k in keys}, warmups=0)
    positions = {k: set() for k in keys}
    for entry in schedule:
        positions[entry.cell_key].add(entry.position)
    assert all(len(seen) == 3 for seen in positions.values())


def test_rotation_preserves_relative_adjacency():
    """Rungs 4 and 5 must stay neighbours or the ratio argument weakens."""
    keys = ["r1", "r2", "r4", "r5"]
    schedule = blocked_schedule(keys, {k: 4 for k in keys}, warmups=0)
    adjacent = 0
    for block in range(1, 5):
        order = [e.cell_key for e in schedule if e.block == block]
        if abs(order.index("r5") - order.index("r4")) == 1:
            adjacent += 1
    assert adjacent >= 3


def test_no_rotation_when_disabled():
    keys = ["a", "b", "c"]
    schedule = blocked_schedule(keys, {k: 3 for k in keys}, warmups=0, rotate=False)
    for block in range(1, 4):
        assert [e.cell_key for e in schedule if e.block == block] == keys


# ---------------------------------------------------------------------------
# dispersion and determinism
# ---------------------------------------------------------------------------

def test_dispersion_withholds_a_standard_deviation_at_n_equals_three():
    summary = dispersion([19.4, 19.6, 20.1])
    assert summary["n"] == 3
    assert summary["standard_deviation"] is None
    assert "n=3" in summary["standard_deviation_withheld_reason"]
    assert summary["median"] == pytest.approx(19.6)


def test_dispersion_reports_relative_spread_comparable_with_b5c():
    summary = dispersion([20.2278, 19.4774])
    assert summary["relative_spread"] == pytest.approx(0.03779, abs=1e-4)


def test_dispersion_reports_a_standard_deviation_at_n_equals_seven():
    summary = dispersion([20.0, 20.1, 20.2, 20.3, 20.4, 20.5, 20.6])
    assert summary["standard_deviation"] is not None


def _run(digest: str, seconds: float, checks: float = 11021.825858) -> dict:
    return {
        "algorithm": "hilbert_binary",
        "rung": 4,
        "is_warmup": False,
        "output_sha256": digest,
        "computation_seconds": seconds,
        "total_process_seconds": seconds + 1.5,
        "peak_working_set_bytes": 140_000_000,
        "peak_commit_bytes": 152_000_000,
        "peak_memory_method": "psapi:GetProcessMemoryInfo",
        "average_segment_checks_per_property": checks,
    }


def test_summarize_cell_rejects_differing_output_bytes():
    with pytest.raises(RuntimeError, match="different output bytes"):
        summarize_cell([_run("aaa", 19.5), _run("bbb", 19.6)])


def test_summarize_cell_rejects_a_drifting_deterministic_counter():
    with pytest.raises(RuntimeError, match="varied across repetitions"):
        summarize_cell(
            [_run("aaa", 19.5), _run("aaa", 19.6, checks=11021.9)]
        )


def test_summarize_cell_reports_both_memory_peaks():
    """Resident and committed memory are different claims; B6a needs both."""
    summary = summarize_cell([_run("aaa", 19.5), _run("aaa", 19.6)])
    assert summary["peak_working_set_bytes"]["median"] == 140_000_000
    assert summary["peak_commit_bytes"]["median"] == 152_000_000


def test_summarize_cell_refuses_a_cell_spanning_sessions():
    """A median over sessions is a median over machine states."""
    left = dict(_run("aaa", 19.5), session_id="s1")
    right = dict(_run("aaa", 19.6), session_id="s2")
    with pytest.raises(RuntimeError, match="span 2 invocations"):
        summarize_cell([left, right])


def test_summarize_cell_allows_spanning_when_asked_explicitly():
    left = dict(_run("aaa", 19.5), session_id="s1")
    right = dict(_run("aaa", 19.6), session_id="s2")
    summary = summarize_cell([left, right], allow_multiple_sessions=True)
    assert summary["sessions"] == ["s1", "s2"]


def test_recorder_appends_and_reloads(tmp_path):
    recorder = RunRecorder(tmp_path / "runs.jsonl")
    recorder.append({"cell_key": "a@w", "repetition": 1, "computation_seconds": 1.0})
    recorder.append({"cell_key": "a@w", "repetition": 2, "computation_seconds": 1.1})
    reloaded = RunRecorder(tmp_path / "runs.jsonl")
    assert len(reloaded.load_existing()) == 2
    assert reloaded.completed() == {("a@w", 1), ("a@w", 2)}


def test_recorder_reports_a_truncated_line_rather_than_dropping_it(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text('{"cell_key": "a", "repetition": 1}\n{"cell_key": "a", "rep',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="died"):
        RunRecorder(path).load_existing()


def test_recorder_on_a_missing_file_is_empty(tmp_path):
    assert RunRecorder(tmp_path / "absent.jsonl").load_existing() == []


def test_summarize_cell_accepts_a_clean_cell():
    summary = summarize_cell([_run("aaa", 19.5), _run("aaa", 19.6)])
    assert summary["output_sha256"] == "aaa"
    assert summary["computation_seconds"]["n"] == 2
    assert summary["deterministic_counters"][
        "average_segment_checks_per_property"
    ] == pytest.approx(11021.825858)


# ---------------------------------------------------------------------------
# query-stats folding
# ---------------------------------------------------------------------------

QUERY_STATS = {
    "benchmark_eligible": True,
    "seed_mode": "binary",
    "seed_window_entries": 64,
    "query_seconds": 19.477417,
    "resolve_descent": {
        "nodes_per_property": 70.913503,
        "entries_per_property": 141.174168,
    },
    "tight_descent": {
        "nodes_per_property": 60.319907,
        "entries_per_property": 47.592623,
    },
    "seed_quality": {
        "fraction_window_missed": 0.386151,
        "mean_d_seed_over_d_best": 1.171692,
        "max_d_seed_over_d_best": 32.233194,
    },
    "phase2_segment_checks_per_property": 11021.825858,
}


def test_query_stats_are_folded_in(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(QUERY_STATS), encoding="utf-8")
    merged = _merge_query_stats(path, {"computation_seconds": 19.477417})
    assert merged["seed_window_entries"] == 64
    assert merged["tight_entries_per_property"] == pytest.approx(47.592623)
    assert merged["fraction_window_missed"] == pytest.approx(0.386151)


def test_query_stats_clock_disagreement_is_an_error(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(QUERY_STATS), encoding="utf-8")
    with pytest.raises(RuntimeError, match="disagrees with"):
        _merge_query_stats(path, {"computation_seconds": 20.6})


def test_window_disagreement_between_stdout_and_stats_is_an_error(tmp_path):
    """B6b builds one binary per window; running the wrong one must fail loudly."""
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(QUERY_STATS), encoding="utf-8")
    with pytest.raises(RuntimeError, match="disagrees with the 128"):
        _merge_query_stats(
            path,
            {
                "computation_seconds": 19.477417,
                "seed_window_entries_stdout": 128,
            },
        )


def test_matching_windows_are_accepted(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(QUERY_STATS), encoding="utf-8")
    merged = _merge_query_stats(
        path,
        {"computation_seconds": 19.477417, "seed_window_entries_stdout": 64},
    )
    assert merged["seed_window_entries"] == 64


def test_ineligible_query_stats_are_refused(tmp_path):
    path = tmp_path / "stats.json"
    payload = dict(QUERY_STATS, benchmark_eligible=False)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BenchmarkIneligibleError):
        _merge_query_stats(path, {"computation_seconds": 19.477417})


# ---------------------------------------------------------------------------
# expected-digest gate (B6b)
# ---------------------------------------------------------------------------

GOOD = "8ad41e8391f64e683e67ac253dc4d1e4302da7706f893763d0d32a689d6b7e9e"
BAD = "0" * 64


def test_expected_digests_parse():
    parsed = parse_expected_digests([f"hilbert_binary={GOOD.upper()}"])
    assert parsed == {"hilbert_binary": GOOD}


@pytest.mark.parametrize(
    "specification",
    ["hilbert_binary", "not_a_rung=" + GOOD, "hilbert_binary=deadbeef"],
)
def test_malformed_expected_digests_are_rejected(specification):
    with pytest.raises(ValueError):
        parse_expected_digests([specification])


def test_matching_digest_passes():
    assert_expected_digest("hilbert_binary", GOOD, {"hilbert_binary": GOOD})


def test_mismatched_digest_is_a_changed_answer():
    with pytest.raises(RuntimeError, match="changed answer"):
        assert_expected_digest("hilbert_binary", BAD, {"hilbert_binary": GOOD})


def test_workload_qualified_digest_wins_over_the_bare_rung():
    expected = {"hilbert_binary": BAD, "hilbert_binary@countywide": GOOD}
    assert expected_digest_for("hilbert_binary", "countywide", expected) == GOOD
    assert expected_digest_for("hilbert_binary", "10000", expected) == BAD


def test_qualified_digest_specification_parses():
    parsed = parse_expected_digests([f"hilbert_rmi@10000={GOOD}"])
    assert parsed == {"hilbert_rmi@10000": GOOD}


def test_unlisted_rung_is_not_gated():
    assert_expected_digest("segment_bvh", BAD, {"hilbert_binary": GOOD})


# ---------------------------------------------------------------------------
# ladder shape
# ---------------------------------------------------------------------------

def test_the_ladder_has_five_rungs_in_order():
    assert [rung.number for rung in LADDER] == [1, 2, 3, 4, 5]


def test_every_hilbert_rung_runs_under_one_predicate_and_one_mode():
    for name in ("hilbert_binary", "hilbert_rmi"):
        assert "disk" in LADDER_BY_NAME[name].trailing_positionals
        assert "original" in LADDER_BY_NAME[name].trailing_positionals


def test_rungs_3_4_and_5_share_the_verification_mode():
    modes = {
        "original" in LADDER_BY_NAME[name].trailing_positionals
        for name in ("segment_bvh", "hilbert_binary", "hilbert_rmi")
    }
    assert modes == {True}