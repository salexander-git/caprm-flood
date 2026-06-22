from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(
    0,
    str(PYTHON_SOURCE_DIRECTORY),
)

from caprm.ingest import repository_path
from caprm.water_benchmark import (
    benchmark_water_algorithms,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()

    try:
        return resolved.relative_to(
            REPOSITORY_ROOT
        ).as_posix()
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repeatedly benchmark brute-force and BVH C++ "
            "nearest-water implementations."
        )
    )

    parser.add_argument(
        "--brute-force-executable",
        default=(
            "cpp/spatial_core/build/"
            "water_distance_bruteforce.exe"
        ),
    )

    parser.add_argument(
        "--indexed-executable",
        default=(
            "cpp/spatial_core/build/"
            "water_distance_indexed.exe"
        ),
    )

    parser.add_argument(
        "--properties",
        default=(
            "outputs/cpp_input/"
            "water_properties_projected.csv"
        ),
    )

    parser.add_argument(
        "--features",
        default=(
            "outputs/cpp_input/water_features.csv"
        ),
    )

    parser.add_argument(
        "--vertices",
        default=(
            "outputs/cpp_input/water_vertices.csv"
        ),
    )

    parser.add_argument(
        "--runs-output",
        default=(
            "outputs/benchmark/"
            "water_cpp_benchmark_runs.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        default=(
            "outputs/validation/"
            "water_cpp_benchmark_summary.json"
        ),
    )

    parser.add_argument(
        "--temporary-output-directory",
        default=(
            "outputs/benchmark/"
            "temporary_water_outputs"
        ),
    )

    parser.add_argument(
        "--repetitions",
        type=int,
        default=7,
    )

    parser.add_argument(
        "--warmups",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    brute_force_executable = repository_path(
        args.brute_force_executable
    )

    indexed_executable = repository_path(
        args.indexed_executable
    )

    properties_path = repository_path(
        args.properties
    )

    features_path = repository_path(
        args.features
    )

    vertices_path = repository_path(
        args.vertices
    )

    runs_output_path = repository_path(
        args.runs_output
    )

    summary_output_path = repository_path(
        args.summary_output
    )

    temporary_output_directory = repository_path(
        args.temporary_output_directory
    )

    runs, summary = benchmark_water_algorithms(
        brute_force_executable=(
            brute_force_executable
        ),
        indexed_executable=indexed_executable,
        properties_path=properties_path,
        features_path=features_path,
        vertices_path=vertices_path,
        temporary_output_directory=(
            temporary_output_directory
        ),
        repetitions=args.repetitions,
        warmups=args.warmups,
    )

    summary.update(
        {
            "created_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "brute_force_executable": display_path(
                brute_force_executable
            ),
            "brute_force_executable_sha256": sha256(
                brute_force_executable
            ),
            "indexed_executable": display_path(
                indexed_executable
            ),
            "indexed_executable_sha256": sha256(
                indexed_executable
            ),
            "properties_input": display_path(
                properties_path
            ),
            "features_input": display_path(
                features_path
            ),
            "vertices_input": display_path(
                vertices_path
            ),
        }
    )

    runs_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    runs.to_csv(
        runs_output_path,
        index=False,
        float_format="%.12f",
    )

    summary_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_output_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()