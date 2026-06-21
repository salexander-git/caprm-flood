from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# This file is stored at:
# <repository>/python/scripts/capture_environment.py
#
# parents[0] = python/scripts
# parents[1] = python
# parents[2] = repository root
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = (
    REPOSITORY_ROOT / "configs" / "monroe_fema_spike.yaml"
)
DEFAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "validation"
    / "milestone_1_environment.json"
)

PACKAGE_NAMES = [
    "certifi",
    "charset-normalizer",
    "geopandas",
    "idna",
    "numpy",
    "packaging",
    "pandas",
    "pyogrio",
    "pyproj",
    "python-dateutil",
    "PyYAML",
    "requests",
    "shapely",
    "six",
    "tzdata",
    "urllib3",
]


def resolve_repository_path(value: str | Path) -> Path:
    """
    Resolve a path relative to the repository root unless it is absolute.

    This makes the script independent of the terminal's current directory.
    """
    path = Path(value)

    if path.is_absolute():
        return path

    return REPOSITORY_ROOT / path


def display_path(path: Path) -> str:
    """
    Prefer a repository-relative path in generated metadata.

    Absolute paths are used only when the path lies outside the repository.
    """
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def run_command(command: list[str]) -> dict[str, Any]:
    """
    Run an external command from the repository root.

    Missing executables and nonzero exit codes are recorded rather than
    causing environment capture to fail.
    """
    executable_path = shutil.which(command[0])

    if executable_path is None:
        return {
            "available": False,
            "command": command,
            "executable_path": None,
            "return_code": None,
            "output": None,
            "error": f"Executable not found: {command[0]}",
        }

    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        return {
            "available": True,
            "command": command,
            "executable_path": executable_path,
            "return_code": None,
            "output": None,
            "error": str(exc),
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    combined_output = "\n".join(
        part for part in (stdout, stderr) if part
    )

    return {
        "available": True,
        "command": command,
        "executable_path": executable_path,
        "return_code": completed.returncode,
        "output": combined_output or None,
        "error": (
            None
            if completed.returncode == 0
            else combined_output or "Command returned a nonzero exit code."
        ),
    }


def get_package_version(package_name: str) -> str | None:
    """Return the installed package version in the active interpreter."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def calculate_sha256(path: Path) -> str:
    """Calculate a file checksum without loading the entire file at once."""
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def describe_file(path: Path) -> dict[str, Any]:
    """Describe the existence, size, and checksum of one file."""
    resolved_path = path.resolve()

    if not resolved_path.exists():
        return {
            "path": display_path(resolved_path),
            "resolved_path": str(resolved_path),
            "exists": False,
            "is_file": False,
        }

    if not resolved_path.is_file():
        return {
            "path": display_path(resolved_path),
            "resolved_path": str(resolved_path),
            "exists": True,
            "is_file": False,
        }

    return {
        "path": display_path(resolved_path),
        "resolved_path": str(resolved_path),
        "exists": True,
        "is_file": True,
        "size_bytes": resolved_path.stat().st_size,
        "sha256": calculate_sha256(resolved_path),
    }


def describe_shapefile_family(shapefile_path: Path) -> dict[str, Any]:
    """
    Describe a shapefile and all sidecar files sharing its filename stem.

    The .shp file alone does not fully identify a shapefile dataset because
    geometry, attributes, indexing, projection, and encoding may be stored
    across several files.
    """
    resolved_path = shapefile_path.resolve()
    parent = resolved_path.parent
    stem = resolved_path.stem

    family_files = sorted(
        candidate
        for candidate in parent.glob(f"{stem}.*")
        if candidate.is_file()
    )

    return {
        "requested_path": display_path(resolved_path),
        "resolved_requested_path": str(resolved_path),
        "requested_path_exists": resolved_path.exists(),
        "family_file_count": len(family_files),
        "files": [
            describe_file(family_file)
            for family_file in family_files
        ],
    }


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and require a mapping at its root."""
    with path.open("r", encoding="utf-8-sig") as input_file:
        loaded = yaml.safe_load(input_file)

    if not isinstance(loaded, dict):
        raise RuntimeError(
            f"Expected a YAML mapping at the root of {path}."
        )

    return loaded


def collect_git_information() -> dict[str, Any]:
    """Capture the current Git repository state."""
    return {
        "repository_root": run_command(
            ["git", "rev-parse", "--show-toplevel"]
        ),
        "branch": run_command(
            ["git", "branch", "--show-current"]
        ),
        "commit": run_command(
            ["git", "rev-parse", "HEAD"]
        ),
        "status_short": run_command(
            ["git", "status", "--short"]
        ),
        "latest_commit": run_command(
            [
                "git",
                "log",
                "-1",
                "--pretty=format:%H%n%an%n%ad%n%s",
            ]
        ),
    }


def collect_tool_information() -> dict[str, Any]:
    """Capture available compilers, Git, and CMake."""
    return {
        "git": run_command(["git", "--version"]),
        "msvc_cl": run_command(["cl"]),
        "g++": run_command(["g++", "--version"]),
        "clang++": run_command(["clang++", "--version"]),
        "cmake": run_command(["cmake", "--version"]),
    }


def collect_environment(config_path: Path) -> dict[str, Any]:
    """Build the complete Milestone 1 environment manifest."""
    package_versions = {
        package_name: get_package_version(package_name)
        for package_name in PACKAGE_NAMES
    }

    environment: dict[str, Any] = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(REPOSITORY_ROOT),
        "current_working_directory": str(Path.cwd()),
        "python": {
            "version": sys.version,
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
            "using_repository_virtual_environment": (
                REPOSITORY_ROOT / ".venv"
            ) in Path(sys.executable).parents,
            "version_info": {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro,
            },
        },
        "operating_system": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "platform": platform.platform(),
        },
        "packages": package_versions,
        "git": collect_git_information(),
        "tools": collect_tool_information(),
        "configuration_file": describe_file(config_path),
        "requirements_file": describe_file(
            REPOSITORY_ROOT / "requirements.txt"
        ),
    }

    if not config_path.exists():
        environment["configuration_error"] = (
            f"Configuration file does not exist: {config_path}"
        )
        return environment

    try:
        config = load_yaml(config_path)
    except Exception as exc:
        environment["configuration_error"] = str(exc)
        return environment

    environment["configuration_values"] = {
        "project": config.get("project"),
        "outputs": config.get("outputs"),
    }

    fema_config = config.get("fema_flood_polygons", {})

    if not isinstance(fema_config, dict):
        environment["fema_input"] = {
            "error": (
                "The fema_flood_polygons configuration section "
                "is not a YAML mapping."
            )
        }
        return environment

    fema_path_value = fema_config.get("manual_input_path")

    if not fema_path_value:
        environment["fema_input"] = {
            "exists": False,
            "error": (
                "No fema_flood_polygons.manual_input_path was found "
                "in the configuration."
            ),
        }
        return environment

    fema_path = resolve_repository_path(str(fema_path_value))

    if fema_path.suffix.lower() == ".shp":
        environment["fema_input"] = describe_shapefile_family(
            fema_path
        )
    else:
        environment["fema_input"] = describe_file(fema_path)

    return environment


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Capture the CAPRM-Flood Python environment, operating system, "
            "Git state, compiler availability, configuration, and FEMA "
            "input provenance."
        )
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=(
            "Configuration path. Relative paths are interpreted from "
            "the repository root."
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

    config_path = resolve_repository_path(args.config)
    output_path = resolve_repository_path(args.output)

    environment = collect_environment(config_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(environment, indent=2),
        encoding="utf-8",
    )

    print(f"Repository root: {REPOSITORY_ROOT}")
    print(f"Python executable: {sys.executable}")
    print(f"Wrote environment manifest to {output_path}")


if __name__ == "__main__":
    main()