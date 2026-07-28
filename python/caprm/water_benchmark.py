from __future__ import annotations

import shutil
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd


SUPPORTED_ALGORITHMS = {
    "brute_force",
    "feature_bvh",
    "segment_bvh",
}

# Algorithms that participate in the frozen Milestone 2/3 benchmark summary at
# outputs/validation/water_cpp_benchmark_summary.json. build_property_evidence.py
# asserts this exact set, so nothing may be added to it here. segment_bvh and
# every later Milestone 4 implementation write to their own summary paths.
FROZEN_BENCHMARK_ALGORITHMS = {
    "brute_force",
    "feature_bvh",
}

INTEGER_PREFIXES = {
    "Properties": "property_count",
    "Water features": "water_feature_count",
    "Vertices": "vertex_count",
    "Segments": "segment_count",
    "Segments (kernel count)": "segment_count",
    "BVH nodes": "bvh_node_count",
    "Total segment checks": "total_segment_checks",
    "Total index node visits": "total_index_node_visits",
    "Total candidate feature checks":
        "total_candidate_feature_checks",
    # Milestone 4, segment_bvh only. None of these prefixes is emitted by
    # water_distance_bruteforce.cpp or water_distance_indexed.cpp, so adding
    # them cannot change how the two frozen algorithms parse.
    "Original segments (split input)":
        "original_segment_count",
    "Split segments (BVH leaves)": "split_segment_count",
    "Added segments": "added_segment_count",
    "Index entries": "index_entry_count",
    "Index bytes": "index_bytes",
    "Total segment box tests": "total_segment_box_tests",
    "Total line candidate segment checks":
        "total_line_segment_checks",
    "Total polygon candidate segment checks":
        "total_polygon_segment_checks",
    "Total containment ring checks":
        "total_containment_ring_checks",
    "Total containment parts tested":
        "total_containment_parts_tested",
    "Total containment parts skipped":
        "total_containment_parts_skipped",
}

FLOAT_PREFIXES = {
    "Input loading seconds": "input_loading_seconds",
    "Index construction seconds":
        "index_construction_seconds",
    "Brute-force computation seconds":
        "computation_seconds",
    "Indexed computation seconds":
        "computation_seconds",
    "Segment-BVH computation seconds":
        "computation_seconds",
    "Properties per second":
        "properties_per_second",
    "Average segment checks per property":
        "average_segment_checks_per_property",
    "Average node visits per property":
        "average_node_visits_per_property",
    "Average candidate features per property":
        "average_candidate_features_per_property",
    # Milestone 4, segment_bvh only.
    "Max segment length cap (m)":
        "max_segment_length_cap_m",
    "Max original segment length (m)":
        "max_original_segment_length_m",
    "Max split segment length (m)":
        "max_split_segment_length_m",
    "Max entry extent (m)": "max_entry_extent_m",
    "Average segment box tests per property":
        "average_segment_box_tests_per_property",
    "Average line candidate segment checks per property":
        "average_line_segment_checks_per_property",
    "Average polygon candidate segment checks per property":
        "average_polygon_segment_checks_per_property",
    "Average containment ring checks per property":
        "average_containment_ring_checks_per_property",
}

STRING_PREFIXES = {
    "Verification mode": "verification_mode",
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

# Fields the segment-BVH program must emit on top of the indexed set. These are
# the entry-extent sweep's independent variable (the cap and the extent it
# produces), the index-size axes, and the search/verification decomposition.
SEGMENT_BVH_REQUIRED_FIELDS = {
    "verification_mode",
    "max_segment_length_cap_m",
    "max_entry_extent_m",
    "index_entry_count",
    "index_bytes",
    "total_segment_box_tests",
    "average_segment_box_tests_per_property",
    "total_line_segment_checks",
    "total_polygon_segment_checks",
    "total_containment_ring_checks",
    "total_containment_parts_tested",
    "total_containment_parts_skipped",
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
    "average_segment_box_tests_per_property",
    "average_line_segment_checks_per_property",
    "average_polygon_segment_checks_per_property",
    "average_containment_ring_checks_per_property",
]

# Counters that must be bit-identical across repetitions of the same
# configuration. Repetition variance in any of them means the query path is not
# deterministic, which is a correctness failure rather than benchmark noise.
DETERMINISTIC_COUNTERS = [
    "total_segment_checks",
    "total_index_node_visits",
    "total_candidate_feature_checks",
    "total_segment_box_tests",
    "total_line_segment_checks",
    "total_polygon_segment_checks",
    "total_containment_ring_checks",
    "total_containment_parts_tested",
    "total_containment_parts_skipped",
    "index_entry_count",
    "index_bytes",
    "bvh_node_count",
]


def parse_cpp_benchmark_output(
    standard_output: str,
    algorithm: str,
) -> dict[str, Any]:
    if algorithm not in SUPPORTED_ALGORITHMS:
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

            continue

        string_name = STRING_PREFIXES.get(prefix)

        if string_name is not None:
            metrics[string_name] = raw_value

    required = set(COMMON_REQUIRED_FIELDS)

    if algorithm in {"feature_bvh", "segment_bvh"}:
        required.update(INDEXED_REQUIRED_FIELDS)

    if algorithm == "segment_bvh":
        required.update(SEGMENT_BVH_REQUIRED_FIELDS)

    missing = sorted(required - set(metrics))

    if missing:
        raise ValueError(
            "C++ benchmark output is missing required metrics: "
            f"{missing}\n\n"
            f"Captured output:\n{standard_output}"
        )

    return metrics


def build_cpp_command(
    executable_path: Path,
    properties_path: Path,
    features_path: Path,
    vertices_path: Path,
    output_path: Path,
    extra_arguments: Sequence[str] = (),
) -> list[str]:
    """Positional command line for every nearest-water C++ program.

    The four inputs are positional and identical across implementations.
    ``extra_arguments`` carries the optional trailing arguments a specific
    program accepts, which for ``water_distance_segment_bvh`` are
    ``<distance_crs> <max_segment_length_m> [verification_mode]``. It defaults
    to empty, so calls that omit it produce exactly the command line the frozen
    Milestone 2/3 benchmark has always issued.

    Kept separate from :func:`run_cpp_algorithm` so command construction can be
    tested without launching a subprocess.
    """
    return [
        str(executable_path.resolve()),
        str(properties_path.resolve()),
        str(features_path.resolve()),
        str(vertices_path.resolve()),
        str(output_path.resolve()),
        *[str(argument) for argument in extra_arguments],
    ]


def run_cpp_algorithm(
    executable_path: Path,
    properties_path: Path,
    features_path: Path,
    vertices_path: Path,
    output_path: Path,
    algorithm: str,
    extra_arguments: Sequence[str] = (),
    retain_output_path: Path | None = None,
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

    command = build_cpp_command(
        executable_path=executable_path,
        properties_path=properties_path,
        features_path=features_path,
        vertices_path=vertices_path,
        output_path=output_path,
        extra_arguments=extra_arguments,
    )

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

    if retain_output_path is not None:
        retain_output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copyfile(
            output_path,
            retain_output_path,
        )

        metrics["retained_output_path"] = str(
            retain_output_path
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

# ---------------------------------------------------------------------------
# Milestone 4, chunk B2 — entry-extent sweep for the segment BVH.
#
# Deliberately separate from summarize_benchmark_runs and
# benchmark_water_algorithms above. Those two produce the frozen Milestone 2/3
# comparison that build_property_evidence.py validates against the exact
# algorithm set {brute_force, feature_bvh}; nothing below writes to that path or
# changes that behaviour.
# ---------------------------------------------------------------------------


def format_cap_argument(cap_meters: float) -> str:
    """Command-line spelling of an entry-extent cap.

    The C++ program treats any value <= 0 as "do not split", so 0 is how the
    sweep expresses the unlimited-extent endpoint.
    """
    return f"{float(cap_meters):g}"


def cap_label(cap_meters: float) -> str:
    """Filesystem-safe label for a cap value."""
    if float(cap_meters) <= 0.0:
        return "unlimited"

    return f"{float(cap_meters):g}m"


def require_consistent_metric(
    runs: pd.DataFrame,
    column: str,
) -> Any:
    """Exact-equality version of require_consistent_integer_metric.

    Used for values that must not vary across repetitions of the same
    configuration but are not integers, such as the entry extent.
    """
    values = runs[column].dropna().unique().tolist()

    if len(values) != 1:
        raise ValueError(
            f"Benchmark runs disagree on {column}: {values}"
        )

    return values[0]


def summarize_cap_sweep_runs(
    runs: pd.DataFrame,
) -> dict[str, Any]:
    required_columns = {
        "algorithm",
        "verification_mode",
        "max_segment_length_cap_m",
        "repetition",
        "execution_order",
        "property_count",
        "water_feature_count",
        "vertex_count",
        "segment_count",
        "index_entry_count",
        "index_bytes",
        "max_entry_extent_m",
        "input_loading_seconds",
        "index_construction_seconds",
        "computation_seconds",
        "properties_per_second",
        "total_segment_checks",
        "total_segment_box_tests",
        "total_index_node_visits",
        "total_candidate_feature_checks",
        "total_line_segment_checks",
        "total_polygon_segment_checks",
        "total_containment_ring_checks",
        "total_containment_parts_tested",
        "total_containment_parts_skipped",
        "total_process_seconds",
    }

    missing = sorted(
        required_columns - set(runs.columns)
    )

    if missing:
        raise ValueError(
            f"Sweep runs are missing columns: {missing}"
        )

    algorithms = set(
        runs["algorithm"].astype("string")
    )

    if algorithms != {"segment_bvh"}:
        raise ValueError(
            "The entry-extent sweep must contain only segment_bvh "
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

    points: list[dict[str, Any]] = []

    group_keys = sorted(
        {
            (
                float(cap),
                str(mode),
            )
            for cap, mode in zip(
                runs["max_segment_length_cap_m"],
                runs["verification_mode"],
            )
        }
    )

    for cap_meters, verification_mode in group_keys:
        group = runs.loc[
            runs["max_segment_length_cap_m"].eq(cap_meters)
            & runs["verification_mode"].eq(verification_mode)
        ].copy()

        point: dict[str, Any] = {
            "max_segment_length_cap_m": cap_meters,
            "cap_label": cap_label(cap_meters),
            "verification_mode": verification_mode,
            "run_count": int(len(group)),
        }

        for column in DETERMINISTIC_COUNTERS:
            if column not in group.columns:
                continue

            if group[column].notna().any():
                point[column] = (
                    require_consistent_integer_metric(
                        group,
                        column,
                    )
                )

        point["max_entry_extent_m"] = float(
            require_consistent_metric(
                group,
                "max_entry_extent_m",
            )
        )

        # What the measured entry extent WOULD imply for the B3 inflated-disk
        # search radius. B1's index is a 2D box hierarchy with no midpoint
        # ordering, so inflation does not exist in it yet. This is an implied
        # value, not a measured one, and is labelled as such wherever it is
        # reported.
        point["implied_b3_inflation_radius_m"] = (
            point["max_entry_extent_m"] / 2.0
        )

        for metric in TIMING_METRICS:
            if metric not in group.columns:
                continue

            nonmissing = group[metric].dropna()

            if nonmissing.empty:
                continue

            point[metric] = metric_statistics(nonmissing)

        total_checks = int(point.get("total_segment_checks", 0))

        point["per_property"] = {
            "segment_checks": (
                total_checks / property_count
            ),
            "segment_box_tests": (
                int(point.get("total_segment_box_tests", 0))
                / property_count
            ),
            "index_node_visits": (
                int(point.get("total_index_node_visits", 0))
                / property_count
            ),
            "candidate_features": (
                int(
                    point.get(
                        "total_candidate_feature_checks",
                        0,
                    )
                )
                / property_count
            ),
            "line_segment_checks": (
                int(point.get("total_line_segment_checks", 0))
                / property_count
            ),
            "polygon_segment_checks": (
                int(
                    point.get(
                        "total_polygon_segment_checks",
                        0,
                    )
                )
                / property_count
            ),
            "containment_ring_checks": (
                int(
                    point.get(
                        "total_containment_ring_checks",
                        0,
                    )
                )
                / property_count
            ),
        }

        # The share of "original"-mode verification spent on line candidates is
        # the ceiling on what "split" mode can remove, because polygon
        # candidates need the ring walk either way.
        if total_checks > 0:
            point["line_share_of_verification"] = (
                int(point.get("total_line_segment_checks", 0))
                / total_checks
            )
            point["polygon_share_of_verification"] = (
                int(
                    point.get(
                        "total_polygon_segment_checks",
                        0,
                    )
                )
                / total_checks
            )

        parts_tested = int(
            point.get("total_containment_parts_tested", 0)
        )

        parts_skipped = int(
            point.get("total_containment_parts_skipped", 0)
        )

        parts_total = parts_tested + parts_skipped

        if parts_total > 0:
            point["containment_prefilter_skip_rate"] = (
                parts_skipped / parts_total
            )

        points.append(point)

    indexed_points = {
        (
            point["max_segment_length_cap_m"],
            point["verification_mode"],
        ): point
        for point in points
    }

    mode_comparisons: list[dict[str, Any]] = []

    for cap_meters, verification_mode in group_keys:
        if verification_mode != "original":
            continue

        split_point = indexed_points.get(
            (cap_meters, "split")
        )

        if split_point is None:
            continue

        original_point = indexed_points[
            (cap_meters, "original")
        ]

        comparison: dict[str, Any] = {
            "max_segment_length_cap_m": cap_meters,
            "cap_label": cap_label(cap_meters),
        }

        original_checks = int(
            original_point.get("total_segment_checks", 0)
        )

        split_checks = int(
            split_point.get("total_segment_checks", 0)
        )

        if original_checks > 0:
            comparison[
                "verification_check_reduction_rate"
            ] = 1.0 - split_checks / original_checks

        original_polygon_checks = int(
            original_point.get(
                "total_polygon_segment_checks",
                0,
            )
        )

        split_containment_checks = int(
            split_point.get(
                "total_containment_ring_checks",
                0,
            )
        )

        # How much of the polygon ring-walk cost the bounding-box pre-filter
        # actually removed. Without the filter this would be ~0.
        if original_polygon_checks > 0:
            comparison[
                "containment_prefilter_saving_rate"
            ] = (
                1.0
                - split_containment_checks
                / original_polygon_checks
            )

        for metric in (
            "computation_seconds",
            "total_process_seconds",
        ):
            original_metric = original_point.get(metric)
            split_metric = split_point.get(metric)

            if not original_metric or not split_metric:
                continue

            if split_metric["median"] <= 0.0:
                continue

            comparison[f"median_{metric}_speedup"] = (
                original_metric["median"]
                / split_metric["median"]
            )

        mode_comparisons.append(comparison)

    entry_counts = sorted(
        {
            int(point["index_entry_count"])
            for point in points
            if "index_entry_count" in point
        }
    )

    return {
        "property_count": property_count,
        "water_feature_count": water_feature_count,
        "vertex_count": vertex_count,
        "segment_count": segment_count,
        "swept_parameter": "max_segment_length_cap_m",
        "swept_parameter_description": (
            "entry extent cap in metres; 0 disables splitting "
            "(unlimited extent)"
        ),
        "distinct_entry_counts": entry_counts,
        "entry_count_varies": len(entry_counts) > 1,
        "points": points,
        "verification_mode_comparisons": mode_comparisons,
        "grouping_scope_note": (
            "This sweep varies entry extent through the split cap only. "
            "Run grouping, which would move the axis the other way (fewer "
            "entries, larger extent), was measured as out of scope: B1 "
            "recorded search at ~35 operations per property against 9,716.87 "
            "verification checks, so the pruning side of the tradeoff has "
            "almost no headroom, and larger entry extent directly worsens the "
            "B3 inflation radius. The fewer-entries half of the axis is "
            "therefore UNMEASURED and must not be reported as covered."
        ),
    }


def benchmark_segment_bvh_cap_sweep(
    segment_bvh_executable: Path,
    properties_path: Path,
    features_path: Path,
    vertices_path: Path,
    temporary_output_directory: Path,
    caps_m: Sequence[float],
    verification_modes: Sequence[str],
    distance_crs: str,
    repetitions: int,
    warmups: int,
    retained_output_directory: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Sweep the segment-BVH entry-extent cap under both verification modes.

    One configuration is one (cap, verification_mode) pair. Each configuration
    is warmed up, then measured ``repetitions`` times through the same
    repetition protocol the frozen Milestone 2 benchmark uses. The final
    measured run of each configuration is retained when
    ``retained_output_directory`` is given, so the comparison harness can be run
    against the exact artefact that was timed.
    """
    if repetitions <= 0:
        raise ValueError(
            "Benchmark repetitions must be greater than zero."
        )

    if warmups < 0:
        raise ValueError(
            "Benchmark warmups cannot be negative."
        )

    if not caps_m:
        raise ValueError(
            "The entry-extent sweep needs at least one cap value."
        )

    unsupported = sorted(
        set(verification_modes) - {"original", "split"}
    )

    if unsupported:
        raise ValueError(
            "Unsupported verification modes: "
            f"{unsupported}"
        )

    temporary_output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    records: list[dict[str, Any]] = []

    for cap_meters in caps_m:
        cap_argument = format_cap_argument(cap_meters)
        label = cap_label(cap_meters)

        for verification_mode in verification_modes:
            extra_arguments = [
                distance_crs,
                cap_argument,
                verification_mode,
            ]

            for warmup_index in range(warmups):
                warmup_path = (
                    temporary_output_directory
                    / (
                        f"warmup_{warmup_index + 1}_"
                        f"{label}_{verification_mode}.csv"
                    )
                )

                run_cpp_algorithm(
                    executable_path=segment_bvh_executable,
                    properties_path=properties_path,
                    features_path=features_path,
                    vertices_path=vertices_path,
                    output_path=warmup_path,
                    algorithm="segment_bvh",
                    extra_arguments=extra_arguments,
                )

                warmup_path.unlink(missing_ok=True)

            for repetition in range(1, repetitions + 1):
                output_path = (
                    temporary_output_directory
                    / (
                        f"measured_{repetition}_"
                        f"{label}_{verification_mode}.csv"
                    )
                )

                retain_output_path = None

                if (
                    retained_output_directory is not None
                    and repetition == repetitions
                ):
                    retain_output_path = (
                        retained_output_directory
                        / (
                            "cpp_nearest_water_segment_bvh_"
                            f"{label}_{verification_mode}.csv"
                        )
                    )

                metrics = run_cpp_algorithm(
                    executable_path=segment_bvh_executable,
                    properties_path=properties_path,
                    features_path=features_path,
                    vertices_path=vertices_path,
                    output_path=output_path,
                    algorithm="segment_bvh",
                    extra_arguments=extra_arguments,
                    retain_output_path=retain_output_path,
                )

                metrics.update(
                    {
                        "repetition": repetition,
                        "execution_order": 1,
                        "cap_argument": cap_argument,
                        "cap_label": label,
                        "distance_crs": distance_crs,
                    }
                )

                records.append(metrics)

                output_path.unlink(missing_ok=True)

    runs = pd.DataFrame.from_records(records)

    summary = summarize_cap_sweep_runs(runs)

    summary.update(
        {
            "repetitions": repetitions,
            "warmups_per_configuration": warmups,
            "caps_m": [float(cap) for cap in caps_m],
            "verification_modes": list(verification_modes),
            "distance_crs": distance_crs,
        }
    )

    return runs, summary