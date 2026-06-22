from __future__ import annotations

import pandas as pd
import pytest

from caprm.water_benchmark import (
    parse_cpp_benchmark_output,
    summarize_benchmark_runs,
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