from __future__ import annotations

import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


INTEGER_PREFIXES = {
    "Properties": "property_count",
    "Water features": "water_feature_count",
    "Vertices": "vertex_count",
    "Segments": "segment_count",
    "BVH nodes": "bvh_node_count",
    "Total segment checks": "total_segment_checks",
    "Total index node visits": "total_index_node_visits",
    "Total candidate feature checks":
        "total_candidate_feature_checks",
}

FLOAT_PREFIXES = {
    "Input loading seconds": "input_loading_seconds",
    "Index construction seconds":
        "index_construction_seconds",
    "Brute-force computation seconds":
        "computation_seconds",
    "Indexed computation seconds":
        "computation_seconds",
    "Properties per second":
        "properties_per_second",
    "Average segment checks per property":
        "average_segment_checks_per_property",
    "Average node visits per property":
        "average_node_visits_per_property",
    "Average candidate features per property":
        "average_candidate_features_per_property",
}

COMMON_REQUIRED_FIELDS = {
    "property_count",
    "water_feature_count",
    "vertex_count",
    "segment_count",
    "input_loading_seconds",
    "computation_seconds",
    "properties_per_second",
    "total_segment_checks",
    "average_segment_checks_per_property",
}

INDEXED_REQUIRED_FIELDS = {
    "bvh_node_count",
    "index_construction_seconds",
    "total_index_node_visits",
    "average_node_visits_per_property",
    "total_candidate_feature_checks",
    "average_candidate_features_per_property",
}

TIMING_METRICS = [
    "input_loading_seconds",
    "index_construction_seconds",
    "computation_seconds",
    "total_process_seconds",
    "properties_per_second",
    "average_segment_checks_per_property",
    "average_node_visits_per_property",
    "average_candidate_features_per_property",
]


def parse_cpp_benchmark_output(
    standard_output: str,
    algorithm: str,
) -> dict[str, Any]:
    if algorithm not in {
        "brute_force",
        "feature_bvh",
    }:
        raise ValueError(
            f"Unsupported benchmark algorithm: {algorithm}"
        )

    metrics: dict[str, Any] = {
        "algorithm": algorithm,
    }

    for raw_line in standard_output.splitlines():
        line = raw_line.strip()

        if not line or ":" not in line:
            continue

        prefix, raw_value = line.split(":", maxsplit=1)

        prefix = prefix.strip()
        raw_value = raw_value.strip()

        integer_name = INTEGER_PREFIXES.get(prefix)

        if integer_name is not None:
            try:
                metrics[integer_name] = int(raw_value)
            except ValueError as error:
                raise ValueError(
                    f"Invalid integer benchmark metric "
                    f"{prefix!r}: {raw_value!r}"
                ) from error

            continue

        float_name = FLOAT_PREFIXES.get(prefix)

        if float_name is not None:
            try:
                metrics[float_name] = float(raw_value)
            except ValueError as error:
                raise ValueError(
                    f"Invalid floating benchmark metric "
                    f"{prefix!r}: {raw_value!r}"
                ) from error

    required = set(COMMON_REQUIRED_FIELDS)

    if algorithm == "feature_bvh":
        required.update(INDEXED_REQUIRED_FIELDS)

    missing = sorted(required - set(metrics))

    if missing:
        raise ValueError(
            "C++ benchmark output is missing required metrics: "
            f"{missing}\n\n"
            f"Captured output:\n{standard_output}"
        )

    return metrics


def run_cpp_algorithm(
    executable_path: Path,
    properties_path: Path,
    features_path: Path,
    vertices_path: Path,
    output_path: Path,
    algorithm: str,
) -> dict[str, Any]:
    executable_path = executable_path.resolve()

    if not executable_path.exists():
        raise FileNotFoundError(
            f"C++ benchmark executable does not exist: "
            f"{executable_path}"
        )

    for input_path in (
        properties_path,
        features_path,
        vertices_path,
    ):
        if not input_path.exists():
            raise FileNotFoundError(
                f"Benchmark input does not exist: {input_path}"
            )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.unlink(missing_ok=True)

    command = [
        str(executable_path),
        str(properties_path.resolve()),
        str(features_path.resolve()),
        str(vertices_path.resolve()),
        str(output_path.resolve()),
    ]

    process_start = time.perf_counter()

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    total_process_seconds = (
        time.perf_counter() - process_start
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"C++ benchmark failed for {algorithm} with "
            f"exit code {completed.returncode}.\n\n"
            f"Standard output:\n{completed.stdout}\n\n"
            f"Standard error:\n{completed.stderr}"
        )

    if not output_path.exists():
        raise RuntimeError(
            f"C++ benchmark did not create its output: "
            f"{output_path}"
        )

    metrics = parse_cpp_benchmark_output(
        completed.stdout,
        algorithm,
    )

    metrics.update(
        {
            "total_process_seconds":
                total_process_seconds,
            "output_size_bytes":
                output_path.stat().st_size,
        }
    )

    return metrics


def require_consistent_integer_metric(
    runs: pd.DataFrame,
    column: str,
) -> int:
    values = (
        pd.to_numeric(
            runs[column],
            errors="raise",
        )
        .dropna()
        .astype("int64")
        .unique()
    )

    if len(values) != 1:
        raise ValueError(
            f"Benchmark runs disagree on {column}: "
            f"{values.tolist()}"
        )

    return int(values[0])


def metric_statistics(
    values: Iterable[float],
) -> dict[str, float]:
    numeric = [
        float(value)
        for value in values
        if pd.notna(value)
    ]

    if not numeric:
        raise ValueError(
            "Cannot summarize an empty benchmark metric."
        )

    return {
        "minimum": min(numeric),
        "median": statistics.median(numeric),
        "mean": statistics.fmean(numeric),
        "maximum": max(numeric),
    }


def summarize_benchmark_runs(
    runs: pd.DataFrame,
) -> dict[str, Any]:
    required_columns = {
        "algorithm",
        "repetition",
        "execution_order",
        "property_count",
        "water_feature_count",
        "vertex_count",
        "segment_count",
        "input_loading_seconds",
        "computation_seconds",
        "properties_per_second",
        "total_segment_checks",
        "average_segment_checks_per_property",
        "total_process_seconds",
    }

    missing = sorted(
        required_columns - set(runs.columns)
    )

    if missing:
        raise ValueError(
            f"Benchmark runs are missing columns: {missing}"
        )

    algorithms = set(
        runs["algorithm"].astype("string")
    )

    expected_algorithms = {
        "brute_force",
        "feature_bvh",
    }

    if algorithms != expected_algorithms:
        raise ValueError(
            "Benchmark must contain brute_force and feature_bvh "
            f"runs; received {sorted(algorithms)}"
        )

    property_count = require_consistent_integer_metric(
        runs,
        "property_count",
    )

    water_feature_count = (
        require_consistent_integer_metric(
            runs,
            "water_feature_count",
        )
    )

    vertex_count = require_consistent_integer_metric(
        runs,
        "vertex_count",
    )

    segment_count = require_consistent_integer_metric(
        runs,
        "segment_count",
    )

    algorithm_summaries: dict[str, Any] = {}

    for algorithm in sorted(expected_algorithms):
        group = runs.loc[
            runs["algorithm"].eq(algorithm)
        ].copy()

        summary: dict[str, Any] = {
            "run_count": int(len(group)),
            "total_segment_checks": (
                require_consistent_integer_metric(
                    group,
                    "total_segment_checks",
                )
            ),
        }

        for metric in TIMING_METRICS:
            if metric not in group.columns:
                continue

            nonmissing = group[metric].dropna()

            if nonmissing.empty:
                continue

            summary[metric] = metric_statistics(
                nonmissing
            )

        if (
            "total_candidate_feature_checks"
            in group.columns
            and group[
                "total_candidate_feature_checks"
            ].notna().any()
        ):
            summary[
                "total_candidate_feature_checks"
            ] = require_consistent_integer_metric(
                group,
                "total_candidate_feature_checks",
            )

        if (
            "total_index_node_visits"
            in group.columns
            and group[
                "total_index_node_visits"
            ].notna().any()
        ):
            summary[
                "total_index_node_visits"
            ] = require_consistent_integer_metric(
                group,
                "total_index_node_visits",
            )

        if (
            "bvh_node_count" in group.columns
            and group["bvh_node_count"].notna().any()
        ):
            summary["bvh_node_count"] = (
                require_consistent_integer_metric(
                    group,
                    "bvh_node_count",
                )
            )

        algorithm_summaries[algorithm] = summary

    brute = algorithm_summaries["brute_force"]
    indexed = algorithm_summaries["feature_bvh"]

    brute_computation = brute[
        "computation_seconds"
    ]["median"]

    indexed_computation = indexed[
        "computation_seconds"
    ]["median"]

    brute_process = brute[
        "total_process_seconds"
    ]["median"]

    indexed_process = indexed[
        "total_process_seconds"
    ]["median"]

    brute_segment_checks = int(
        brute["total_segment_checks"]
    )

    indexed_segment_checks = int(
        indexed["total_segment_checks"]
    )

    candidate_checks = int(
        indexed["total_candidate_feature_checks"]
    )

    comparison = {
        "median_computation_speedup": (
            brute_computation
            / indexed_computation
        ),
        "median_total_process_speedup": (
            brute_process / indexed_process
        ),
        "segment_check_reduction_rate": (
            1.0
            - indexed_segment_checks
            / brute_segment_checks
        ),
        "segment_check_speedup_factor": (
            brute_segment_checks
            / indexed_segment_checks
        ),
        "average_candidate_features_per_property": (
            candidate_checks / property_count
        ),
        "candidate_feature_fraction": (
            candidate_checks
            / (
                property_count
                * water_feature_count
            )
        ),
    }

    return {
        "property_count": property_count,
        "water_feature_count": water_feature_count,
        "vertex_count": vertex_count,
        "segment_count": segment_count,
        "algorithms": algorithm_summaries,
        "comparison": comparison,
    }


def benchmark_water_algorithms(
    brute_force_executable: Path,
    indexed_executable: Path,
    properties_path: Path,
    features_path: Path,
    vertices_path: Path,
    temporary_output_directory: Path,
    repetitions: int,
    warmups: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if repetitions <= 0:
        raise ValueError(
            "Benchmark repetitions must be greater than zero."
        )

    if warmups < 0:
        raise ValueError(
            "Benchmark warmups cannot be negative."
        )

    temporary_output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    algorithms = {
        "brute_force": brute_force_executable,
        "feature_bvh": indexed_executable,
    }

    for warmup_index in range(warmups):
        for algorithm, executable in algorithms.items():
            output_path = (
                temporary_output_directory
                / (
                    f"warmup_{warmup_index + 1}_"
                    f"{algorithm}.csv"
                )
            )

            run_cpp_algorithm(
                executable_path=executable,
                properties_path=properties_path,
                features_path=features_path,
                vertices_path=vertices_path,
                output_path=output_path,
                algorithm=algorithm,
            )

            output_path.unlink(missing_ok=True)

    records: list[dict[str, Any]] = []

    for repetition in range(1, repetitions + 1):
        order = [
            "brute_force",
            "feature_bvh",
        ]

        if repetition % 2 == 0:
            order.reverse()

        for execution_order, algorithm in enumerate(
            order,
            start=1,
        ):
            output_path = (
                temporary_output_directory
                / (
                    f"measured_{repetition}_"
                    f"{algorithm}.csv"
                )
            )

            metrics = run_cpp_algorithm(
                executable_path=algorithms[algorithm],
                properties_path=properties_path,
                features_path=features_path,
                vertices_path=vertices_path,
                output_path=output_path,
                algorithm=algorithm,
            )

            metrics.update(
                {
                    "repetition": repetition,
                    "execution_order":
                        execution_order,
                }
            )

            records.append(metrics)

            output_path.unlink(missing_ok=True)

    runs = pd.DataFrame.from_records(records)

    summary = summarize_benchmark_runs(runs)

    summary.update(
        {
            "repetitions": repetitions,
            "warmups_per_algorithm": warmups,
        }
    )

    return runs, summary