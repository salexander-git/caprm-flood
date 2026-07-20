from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "validation"
    / "repository_inventory.json"
)

IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
}

LARGE_FILE_THRESHOLD_BYTES = 5 * 1024 * 1024

EXPECTED_PATHS = [
    "README.md",
    "requirements.txt",
    ".gitignore",
    "configs/monroe_fema_spike.yaml",
    "configs/monroe_fema_spike_countywide.yaml",
    # Library
    "python/caprm/__init__.py",
    "python/caprm/ingest.py",
    "python/caprm/crs.py",
    "python/caprm/baseline.py",
    "python/caprm/validate.py",
    "python/caprm/evidence.py",
    "python/caprm/hydrography.py",
    "python/caprm/study_area.py",
    "python/caprm/water_distance.py",
    "python/caprm/terrain.py",
    "python/caprm/scoring.py",
    "python/caprm/sensitivity.py",
    "python/caprm/audit.py",
    # Milestone 1 and 2 entry points
    "python/scripts/run_fema_baseline.py",
    "python/scripts/run_water_baseline.py",
    "python/scripts/export_cpp_inputs.py",
    "python/scripts/compare_python_cpp_fema.py",
    "python/scripts/compare_python_cpp_water.py",
    "python/scripts/create_cpp_dev_fixture.py",
    "python/scripts/cache_hydrography.py",
    "python/scripts/build_property_evidence.py",
    # Milestone 3 entry points
    "python/scripts/prepare_terrain_raster.py",
    "python/scripts/build_terrain_evidence.py",
    "python/scripts/build_exposure_index.py",
    "python/scripts/analyze_scoring_sensitivity.py",
    "python/scripts/audit_milestone3_products.py",
    "python/scripts/summarize_milestone3_results.py",
    # C++
    "cpp/spatial_core/src/fema_pip_dev.cpp",
    "cpp/spatial_core/src/water_distance_bruteforce.cpp",
    "cpp/spatial_core/src/water_distance_indexed.cpp",
    # Documentation
    "docs/crs_policy.md",
    "docs/data_sources.md",
    "docs/validation.md",
    "docs/scoring_methodology.md",
    "docs/milestone_3.md",
    "tests",
]


def resolve_path(value: str | Path) -> Path:
    """
    Resolve a path relative to the repository root unless it is absolute.
    """
    path = Path(value)

    if path.is_absolute():
        return path

    return REPOSITORY_ROOT / path


def run_git_command(arguments: list[str]) -> dict[str, Any]:
    """
    Run a Git command from the repository root.
    """
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        return {
            "success": False,
            "return_code": None,
            "output": None,
            "error": str(exc),
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    return {
        "success": completed.returncode == 0,
        "return_code": completed.returncode,
        "output": stdout or None,
        "error": stderr or None,
    }


def get_git_output(arguments: list[str]) -> str | None:
    """
    Return stdout from a successful Git command.
    """
    result = run_git_command(arguments)

    if not result["success"]:
        return None

    return result["output"]


def parse_git_path_output(arguments: list[str]) -> set[str]:
    """
    Run a Git command that returns one repository-relative path per line.
    """
    output = get_git_output(arguments)

    if not output:
        return set()

    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def get_tracked_files() -> set[str]:
    """
    Return files already tracked by Git.
    """
    return parse_git_path_output(["ls-files"])


def get_untracked_files() -> set[str]:
    """
    Return files that are untracked and are not ignored.

    These are the files Git normally shows with ?? in git status.
    """
    return parse_git_path_output(
        [
            "ls-files",
            "--others",
            "--exclude-standard",
        ]
    )


def get_ignored_files() -> set[str]:
    """
    Return files excluded by .gitignore or other standard Git ignore rules.
    """
    return parse_git_path_output(
        [
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
        ]
    )


def should_skip(path: Path, repository_root: Path) -> bool:
    """
    Return True when a path lies inside a directory that should not be
    inventoried, such as .git or .venv.
    """
    relative_parts = path.relative_to(repository_root).parts

    return any(
        part in IGNORED_DIRECTORY_NAMES
        for part in relative_parts
    )


def determine_git_state(
    relative_path: str,
    tracked_files: set[str],
    untracked_files: set[str],
    ignored_files: set[str],
) -> str:
    """
    Classify one file according to Git's view of the repository.
    """
    if relative_path in tracked_files:
        return "tracked"

    if relative_path in untracked_files:
        return "untracked"

    if relative_path in ignored_files:
        return "ignored"

    return "other"


def describe_file(
    path: Path,
    repository_root: Path,
    tracked_files: set[str],
    untracked_files: set[str],
    ignored_files: set[str],
) -> dict[str, Any]:
    """
    Describe one repository file.
    """
    relative_path = path.relative_to(repository_root).as_posix()
    size_bytes = path.stat().st_size

    git_state = determine_git_state(
        relative_path=relative_path,
        tracked_files=tracked_files,
        untracked_files=untracked_files,
        ignored_files=ignored_files,
    )

    return {
        "path": relative_path,
        "suffix": path.suffix.lower(),
        "size_bytes": size_bytes,
        "is_empty": size_bytes == 0,
        "is_large": size_bytes >= LARGE_FILE_THRESHOLD_BYTES,
        "git_state": git_state,
    }


def describe_expected_path(
    repository_root: Path,
    relative_path: str,
) -> dict[str, Any]:
    """
    Report whether an expected repository path exists.
    """
    path = repository_root / relative_path

    return {
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_directory": path.is_dir(),
        "size_bytes": (
            path.stat().st_size
            if path.exists() and path.is_file()
            else None
        ),
    }


def build_inventory(repository_root: Path) -> dict[str, Any]:
    """
    Build a complete repository inventory.
    """
    tracked_files = get_tracked_files()
    untracked_files = get_untracked_files()
    ignored_files = get_ignored_files()

    file_records: list[dict[str, Any]] = []

    for path in sorted(repository_root.rglob("*")):
        if should_skip(path, repository_root):
            continue

        if not path.is_file():
            continue

        file_records.append(
            describe_file(
                path=path,
                repository_root=repository_root,
                tracked_files=tracked_files,
                untracked_files=untracked_files,
                ignored_files=ignored_files,
            )
        )

    empty_files = [
        file_record["path"]
        for file_record in file_records
        if file_record["is_empty"]
    ]

    large_files = [
        {
            "path": file_record["path"],
            "size_bytes": file_record["size_bytes"],
            "git_state": file_record["git_state"],
        }
        for file_record in file_records
        if file_record["is_large"]
    ]

    tracked_file_records = [
        file_record["path"]
        for file_record in file_records
        if file_record["git_state"] == "tracked"
    ]

    untracked_file_records = [
        file_record["path"]
        for file_record in file_records
        if file_record["git_state"] == "untracked"
    ]

    ignored_file_records = [
        file_record["path"]
        for file_record in file_records
        if file_record["git_state"] == "ignored"
    ]

    other_file_records = [
        file_record["path"]
        for file_record in file_records
        if file_record["git_state"] == "other"
    ]

    expected_path_status = {
        relative_path: describe_expected_path(
            repository_root,
            relative_path,
        )
        for relative_path in EXPECTED_PATHS
    }

    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(repository_root),
        "current_working_directory": str(Path.cwd()),
        "git": {
            "branch": get_git_output(
                ["branch", "--show-current"]
            ),
            "commit": get_git_output(
                ["rev-parse", "HEAD"]
            ),
            "status_short": get_git_output(
                ["status", "--short"]
            ),
        },
        "summary": {
            "file_count": len(file_records),
            "tracked_file_count": len(tracked_file_records),
            "untracked_file_count": len(untracked_file_records),
            "ignored_file_count": len(ignored_file_records),
            "other_file_count": len(other_file_records),
            "empty_file_count": len(empty_files),
            "large_file_count": len(large_files),
        },
        "empty_files": empty_files,
        "large_files": large_files,
        "tracked_files": tracked_file_records,
        "untracked_files": untracked_file_records,
        "ignored_files": ignored_file_records,
        "other_files": other_file_records,
        "expected_paths": expected_path_status,
        "files": file_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a machine-readable inventory of the CAPRM-Flood "
            "repository, including tracked, untracked, ignored, empty, "
            "and large files."
        )
    )
    parser.add_argument(
        "--repository-root",
        default=str(REPOSITORY_ROOT),
        help=(
            "Repository root. The root inferred from this script is used "
            "by default."
        ),
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=(
            "Output JSON path. Relative paths are interpreted from "
            "the repository root."
        ),
    )

    args = parser.parse_args()

    repository_root = resolve_path(args.repository_root).resolve()
    output_path = resolve_path(args.output).resolve()

    if not repository_root.exists():
        raise RuntimeError(
            f"Repository root does not exist: {repository_root}"
        )

    if not (repository_root / ".git").exists():
        raise RuntimeError(
            f"{repository_root} does not appear to be a Git repository."
        )

    inventory = build_inventory(repository_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(inventory, indent=2),
        encoding="utf-8",
    )

    summary = inventory["summary"]

    print(f"Repository root: {repository_root}")
    print(f"Wrote repository inventory to {output_path}")
    print(f"Files inventoried: {summary['file_count']}")
    print(f"Tracked files: {summary['tracked_file_count']}")
    print(f"Untracked files: {summary['untracked_file_count']}")
    print(f"Ignored files: {summary['ignored_file_count']}")
    print(f"Other files: {summary['other_file_count']}")
    print(f"Empty files: {summary['empty_file_count']}")
    print(f"Large files: {summary['large_file_count']}")

    if inventory["untracked_files"]:
        print("\nUntracked files:")
        for path in inventory["untracked_files"]:
            print(f"  {path}")

    if inventory["empty_files"]:
        print("\nEmpty files:")
        for path in inventory["empty_files"]:
            print(f"  {path}")

    if inventory["large_files"]:
        print("\nLarge files:")
        for file_record in inventory["large_files"]:
            print(
                f"  {file_record['path']} "
                f"({file_record['size_bytes']} bytes, "
                f"{file_record['git_state']})"
            )


if __name__ == "__main__":
    main()