from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from caprm.water_benchmark import (
    FROZEN_BENCHMARK_ALGORITHMS,
    build_cpp_command,
    cap_label,
    format_cap_argument,
    parse_cpp_benchmark_output,
    summarize_benchmark_runs,
    summarize_cap_sweep_runs,
)


BRUTE_OUTPUT = """
Properties: 1000
Water features: 4159
Vertices: 700379
Segments: 695820
Input loading seconds: 0.800000
Brute-force computation seconds: 2.000000
Properties per second: 500.000000
Total segment checks: 695820000
Average segment checks per property: 695820.000000
"""


INDEXED_OUTPUT = """
Properties: 1000
Water features: 4159
Vertices: 700379
Segments: 695820
BVH nodes: 1149
Input loading seconds: 0.810000
Index construction seconds: 0.001300
Indexed computation seconds: 0.100000
Properties per second: 10000.000000
Total index node visits: 25000
Average node visits per property: 25.000000
Total candidate feature checks: 7000
Average candidate features per property: 7.000000
Total segment checks: 35000000
Average segment checks per property: 35000.000000
"""


# Verbatim shape of water_distance_segment_bvh.exe stdout, with small counts.
SEGMENT_BVH_OUTPUT = """
Properties: 1000
Water features: 4159
Vertices: 700379
Segments (kernel count): 695820
Original segments (split input): 695820
Split segments (BVH leaves): 699000
Added segments: 3180
Max segment length cap (m): 100.000000
Max original segment length (m): 5748.239600
Max split segment length (m): 99.997500
Index entries: 699000
Index bytes: 46134000
Max entry extent (m): 99.997500
BVH nodes: 174749
Verification mode: original
Input loading seconds: 0.820000
Index construction seconds: 1.250000
Segment-BVH computation seconds: 0.050000
Properties per second: 20000.000000
Total index node visits: 28290
Average node visits per property: 28.290000
Total candidate feature checks: 1497
Average candidate features per property: 1.497000
Total segment checks: 9716870
Average segment checks per property: 9716.870000
Total segment box tests: 6490
Average segment box tests per property: 6.490000
Total line candidate segment checks: 1716870
Average line candidate segment checks per property: 1716.870000
Total polygon candidate segment checks: 8000000
Average polygon candidate segment checks per property: 8000.000000
Total containment ring checks: 0
Average containment ring checks per property: 0.000000
Total containment parts tested: 0
Total containment parts skipped: 0
"""


def test_parse_brute_force_output() -> None:
    result = parse_cpp_benchmark_output(
        BRUTE_OUTPUT,
        "brute_force",
    )

    assert result["property_count"] == 1000
    assert result["segment_count"] == 695820

    assert result["computation_seconds"] == 2.0

    assert (
        result["total_segment_checks"]
        == 695820000
    )


def test_parse_indexed_output() -> None:
    result = parse_cpp_benchmark_output(
        INDEXED_OUTPUT,
        "feature_bvh",
    )

    assert result["bvh_node_count"] == 1149

    assert (
        result["index_construction_seconds"]
        == pytest.approx(0.0013)
    )

    assert (
        result["total_candidate_feature_checks"]
        == 7000
    )


def test_parse_segment_bvh_output() -> None:
    result = parse_cpp_benchmark_output(
        SEGMENT_BVH_OUTPUT,
        "segment_bvh",
    )

    # "Segments (kernel count)" must land in segment_count; the frozen
    # "Segments" prefix does not match it.
    assert result["segment_count"] == 695820

    # "Segment-BVH computation seconds" must land in the shared
    # computation_seconds field so the timing statistics are comparable.
    assert result["computation_seconds"] == pytest.approx(0.05)

    assert result["verification_mode"] == "original"
    assert result["index_entry_count"] == 699000
    assert result["index_bytes"] == 46134000

    assert result["max_segment_length_cap_m"] == pytest.approx(
        100.0
    )
    assert result["max_entry_extent_m"] == pytest.approx(99.9975)

    assert result["total_segment_box_tests"] == 6490

    # The decomposition must sum to the total, which is what makes it a bound
    # on what split-geometry verification can remove.
    assert (
        result["total_line_segment_checks"]
        + result["total_polygon_segment_checks"]
        == result["total_segment_checks"]
    )


def test_parse_rejects_unknown_algorithm() -> None:
    with pytest.raises(ValueError):
        parse_cpp_benchmark_output(
            BRUTE_OUTPUT,
            "hilbert_rmi",
        )


def test_parse_segment_bvh_requires_sweep_fields() -> None:
    truncated = "\n".join(
        line
        for line in SEGMENT_BVH_OUTPUT.splitlines()
        if not line.startswith("Verification mode")
    )

    with pytest.raises(ValueError):
        parse_cpp_benchmark_output(truncated, "segment_bvh")


def test_build_cpp_command_defaults_to_four_arguments() -> None:
    command = build_cpp_command(
        executable_path=Path("build/water.exe"),
        properties_path=Path("in/properties.csv"),
        features_path=Path("in/features.csv"),
        vertices_path=Path("in/vertices.csv"),
        output_path=Path("out/result.csv"),
    )

    # The frozen Milestone 2/3 benchmark must keep issuing exactly the command
    # line it always has: executable plus four positional paths.
    assert len(command) == 5


def test_build_cpp_command_appends_extra_arguments() -> None:
    command = build_cpp_command(
        executable_path=Path("build/segment.exe"),
        properties_path=Path("in/properties.csv"),
        features_path=Path("in/features.csv"),
        vertices_path=Path("in/vertices.csv"),
        output_path=Path("out/result.csv"),
        extra_arguments=["EPSG:26918", "100", "split"],
    )

    assert command[-3:] == ["EPSG:26918", "100", "split"]


def test_cap_argument_formatting() -> None:
    assert format_cap_argument(100.0) == "100"
    assert format_cap_argument(12.5) == "12.5"

    # Zero is how the sweep expresses "do not split", which is unlimited
    # extent rather than zero extent.
    assert format_cap_argument(0.0) == "0"

    assert cap_label(100.0) == "100m"
    assert cap_label(0.0) == "unlimited"


def test_benchmark_summary_calculates_speedups() -> None:
    brute = parse_cpp_benchmark_output(
        BRUTE_OUTPUT,
        "brute_force",
    )

    indexed = parse_cpp_benchmark_output(
        INDEXED_OUTPUT,
        "feature_bvh",
    )

    records = []

    for repetition in (1, 2):
        brute_record = {
            **brute,
            "repetition": repetition,
            "execution_order": 1,
            "total_process_seconds": 3.0,
        }

        indexed_record = {
            **indexed,
            "repetition": repetition,
            "execution_order": 2,
            "total_process_seconds": 1.0,
        }

        records.extend(
            [
                brute_record,
                indexed_record,
            ]
        )

    summary = summarize_benchmark_runs(
        pd.DataFrame.from_records(records)
    )

    comparison = summary["comparison"]

    assert (
        comparison["median_computation_speedup"]
        == pytest.approx(20.0)
    )

    assert (
        comparison["median_total_process_speedup"]
        == pytest.approx(3.0)
    )

    assert (
        comparison[
            "segment_check_reduction_rate"
        ]
        == pytest.approx(
            1.0
            - 35000000 / 695820000
        )
    )

    assert (
        comparison[
            "average_candidate_features_per_property"
        ]
        == pytest.approx(7.0)
    )


def test_frozen_benchmark_summary_rejects_segment_bvh() -> None:
    """The Milestone 2/3 summary must stay a two-algorithm artefact.

    build_property_evidence.py raises ValueError unless that summary's
    algorithm set equals {brute_force, feature_bvh}. This test pins the
    invariant on the producing side so a future chunk cannot widen it by
    accident.
    """
    assert FROZEN_BENCHMARK_ALGORITHMS == {
        "brute_force",
        "feature_bvh",
    }

    segment = parse_cpp_benchmark_output(
        SEGMENT_BVH_OUTPUT,
        "segment_bvh",
    )

    records = [
        {
            **segment,
            "repetition": 1,
            "execution_order": 1,
            "total_process_seconds": 2.0,
        }
    ]

    with pytest.raises(ValueError):
        summarize_benchmark_runs(
            pd.DataFrame.from_records(records)
        )


def _sweep_record(
    cap_meters: float,
    verification_mode: str,
    repetition: int,
    *,
    index_entry_count: int,
    max_entry_extent_m: float,
    total_segment_checks: int,
    total_line_segment_checks: int,
    total_polygon_segment_checks: int,
    total_containment_ring_checks: int,
    total_containment_parts_tested: int,
    total_containment_parts_skipped: int,
    computation_seconds: float,
) -> dict[str, object]:
    return {
        "algorithm": "segment_bvh",
        "verification_mode": verification_mode,
        "max_segment_length_cap_m": cap_meters,
        "repetition": repetition,
        "execution_order": 1,
        "property_count": 1000,
        "water_feature_count": 4159,
        "vertex_count": 700379,
        "segment_count": 695820,
        "index_entry_count": index_entry_count,
        "index_bytes": index_entry_count * 66,
        "bvh_node_count": 1149,
        "max_entry_extent_m": max_entry_extent_m,
        "input_loading_seconds": 0.8,
        "index_construction_seconds": 1.2,
        "computation_seconds": computation_seconds,
        "properties_per_second": (
            1000.0 / computation_seconds
        ),
        "total_segment_checks": total_segment_checks,
        "total_segment_box_tests": 6490,
        "total_index_node_visits": 28290,
        "total_candidate_feature_checks": 1497,
        "total_line_segment_checks": (
            total_line_segment_checks
        ),
        "total_polygon_segment_checks": (
            total_polygon_segment_checks
        ),
        "total_containment_ring_checks": (
            total_containment_ring_checks
        ),
        "total_containment_parts_tested": (
            total_containment_parts_tested
        ),
        "total_containment_parts_skipped": (
            total_containment_parts_skipped
        ),
        "total_process_seconds": computation_seconds + 2.0,
    }


def _sweep_runs() -> pd.DataFrame:
    records = []

    for repetition in (1, 2):
        records.append(
            _sweep_record(
                100.0,
                "original",
                repetition,
                index_entry_count=699000,
                max_entry_extent_m=99.9975,
                total_segment_checks=10000,
                total_line_segment_checks=2500,
                total_polygon_segment_checks=7500,
                total_containment_ring_checks=0,
                total_containment_parts_tested=0,
                total_containment_parts_skipped=0,
                computation_seconds=0.10,
            )
        )

        records.append(
            _sweep_record(
                100.0,
                "split",
                repetition,
                index_entry_count=699000,
                max_entry_extent_m=99.9975,
                total_segment_checks=3000,
                total_line_segment_checks=0,
                total_polygon_segment_checks=0,
                total_containment_ring_checks=3000,
                total_containment_parts_tested=400,
                total_containment_parts_skipped=600,
                computation_seconds=0.05,
            )
        )

        records.append(
            _sweep_record(
                0.0,
                "original",
                repetition,
                index_entry_count=695820,
                max_entry_extent_m=5748.2396,
                total_segment_checks=11000,
                total_line_segment_checks=2500,
                total_polygon_segment_checks=8500,
                total_containment_ring_checks=0,
                total_containment_parts_tested=0,
                total_containment_parts_skipped=0,
                computation_seconds=0.11,
            )
        )

    return pd.DataFrame.from_records(records)


def test_cap_sweep_summary_reports_the_tradeoff() -> None:
    summary = summarize_cap_sweep_runs(_sweep_runs())

    assert summary["property_count"] == 1000
    assert summary["swept_parameter"] == (
        "max_segment_length_cap_m"
    )

    # Entry count is the independent variable and must vary.
    assert summary["entry_count_varies"] is True
    assert summary["distinct_entry_counts"] == [695820, 699000]

    points = {
        (
            point["max_segment_length_cap_m"],
            point["verification_mode"],
        ): point
        for point in summary["points"]
    }

    original = points[(100.0, "original")]

    assert original["per_property"][
        "segment_checks"
    ] == pytest.approx(10.0)

    # The line share is the ceiling on what split-geometry verification can
    # remove, because polygon candidates need the ring walk either way.
    assert original[
        "line_share_of_verification"
    ] == pytest.approx(0.25)

    assert original[
        "polygon_share_of_verification"
    ] == pytest.approx(0.75)

    split = points[(100.0, "split")]

    assert split[
        "containment_prefilter_skip_rate"
    ] == pytest.approx(0.6)

    # Implied, not measured: B1's index has no midpoint ordering, so search
    # radius inflation does not exist in it yet.
    unlimited = points[(0.0, "original")]

    assert unlimited[
        "implied_b3_inflation_radius_m"
    ] == pytest.approx(2874.1198)


def test_cap_sweep_summary_compares_verification_modes() -> None:
    summary = summarize_cap_sweep_runs(_sweep_runs())

    comparisons = {
        comparison["max_segment_length_cap_m"]: comparison
        for comparison in summary[
            "verification_mode_comparisons"
        ]
    }

    # Only the cap present in both modes is comparable.
    assert set(comparisons) == {100.0}

    comparison = comparisons[100.0]

    assert comparison[
        "verification_check_reduction_rate"
    ] == pytest.approx(0.7)

    # 3000 containment ring checks against 7500 polygon segment checks the
    # original mode had to walk: the bounding-box pre-filter removed 60%.
    assert comparison[
        "containment_prefilter_saving_rate"
    ] == pytest.approx(0.6)

    assert comparison[
        "median_computation_seconds_speedup"
    ] == pytest.approx(2.0)


def test_cap_sweep_summary_records_grouping_scope() -> None:
    summary = summarize_cap_sweep_runs(_sweep_runs())

    # B6 inherits this note. The fewer-entries half of the entry-extent axis is
    # not measured by a cap-only sweep and must not be claimed.
    assert "UNMEASURED" in summary["grouping_scope_note"]


def test_cap_sweep_summary_rejects_nondeterministic_counters() -> None:
    runs = _sweep_runs()

    mask = runs["verification_mode"].eq("split") & runs[
        "repetition"
    ].eq(2)

    runs.loc[mask, "total_segment_checks"] = 3001

    with pytest.raises(ValueError):
        summarize_cap_sweep_runs(runs)