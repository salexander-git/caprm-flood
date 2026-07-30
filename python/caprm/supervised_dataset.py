"""Assemble and verify the PHASE C supervised dataset.

The dataset is the join of two frozen upstream products:

    outputs/index/property_exposure_index_countywide.csv   the v2 label
    outputs/cpp_input/water_properties_projected_countywide.csv   x, y EPSG:26918

Nothing here computes a label. Scoring is frozen at
``preliminary_exposure_index_v2`` and this module reads it; if a label cannot be
produced without changing ``scoring.py``, this module raises rather than
improvises.

Every property of the join that C1 is required to verify is verified here and
returned as a report, not assumed:

    row count on both sides, unique-ID count on both sides, key-set symmetry in
    BOTH directions, null counts, the scoring-policy string on every row, and
    the SHA-256 of the index CSV against the manifest that describes it.

The key column is text, not an integer. Property IDs carry leading zeros and at
least one countywide ID is alphanumeric (``1600100001003000WC``), so the column
is read with an explicit string dtype. Reading it as a number would silently
strip leading zeros from 267,361 rows and coerce one to NaN, and the join would
then fail in a way that looks like a data problem rather than a dtype problem.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

EXPECTED_ROW_COUNT = 267_362
EXPECTED_POLICY_VERSION = "preliminary_exposure_index_v2"
LABEL_COLUMN = "exposure_index_0_100"
KEY_COLUMN = "property_id"
X_COLUMN = "projected_x"
Y_COLUMN = "projected_y"
DISTANCE_CRS = "EPSG:26918"

_INDEX_REQUIRED_COLUMNS = (
    KEY_COLUMN,
    "fema_component_0_100",
    "water_component_0_100",
    "terrain_absolute_component_0_100",
    "terrain_relative_component_0_100",
    LABEL_COLUMN,
    "exposure_percentile",
    "scoring_policy_version",
)
_COORD_REQUIRED_COLUMNS = (KEY_COLUMN, X_COLUMN, Y_COLUMN)


class DatasetVerificationError(RuntimeError):
    """Raised when the assembled dataset fails a stated verification."""


@dataclass(frozen=True)
class DatasetReport:
    """Everything C1 must verify rather than assume, as measured values."""

    index_path: str
    index_sha256: str
    index_sha256_matches_manifest: bool | None
    coordinates_path: str
    coordinates_sha256: str
    index_rows: int
    index_unique_ids: int
    coordinate_rows: int
    coordinate_unique_ids: int
    joined_rows: int
    ids_only_in_index: int
    ids_only_in_coordinates: int
    null_counts: dict[str, int]
    scoring_policy_versions: list[str]
    distance_crs: str
    label_min: float
    label_max: float
    label_mean: float
    label_std: float
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    duplicate_coordinate_rows: int
    distinct_coordinate_pairs: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: str | Path, chunk_bytes: int = 1 << 20) -> str:
    """SHA-256 of a file, streamed so a 40 MB CSV does not enter memory twice."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_bytes)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_index_csv(path: str | Path) -> pd.DataFrame:
    """Read the frozen v2 exposure index with the key column as text."""
    frame = pd.read_csv(path, dtype={KEY_COLUMN: str}, float_precision="round_trip")
    missing = [c for c in _INDEX_REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise DatasetVerificationError(f"index CSV missing columns: {missing}")
    return frame


def read_coordinates_csv(path: str | Path) -> pd.DataFrame:
    """Read the projected property coordinates with the key column as text."""
    frame = pd.read_csv(path, dtype={KEY_COLUMN: str}, float_precision="round_trip")
    missing = [c for c in _COORD_REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise DatasetVerificationError(f"coordinate CSV missing columns: {missing}")
    return frame


def build_supervised_dataset(
    index_csv: str | Path,
    coordinates_csv: str | Path,
    index_manifest_json: str | Path | None = None,
    expected_rows: int = EXPECTED_ROW_COUNT,
    expected_policy_version: str = EXPECTED_POLICY_VERSION,
) -> tuple[pd.DataFrame, DatasetReport]:
    """Join label to coordinates and verify the join.

    Returns ``(frame, report)`` where ``frame`` carries exactly
    ``[property_id, x, y, exposure_index_0_100]`` sorted by ``property_id`` for
    a deterministic byte-level output, and ``report`` carries the measured
    verification values.

    Raises ``DatasetVerificationError`` on any failed check. In particular the
    key sets are compared in both directions and an asymmetry is an error, not
    something an inner join is allowed to absorb silently.
    """
    index_path, coord_path = Path(index_csv), Path(coordinates_csv)
    index = read_index_csv(index_path)
    coords = read_coordinates_csv(coord_path)

    index_sha = sha256_file(index_path)
    coord_sha = sha256_file(coord_path)

    manifest_match: bool | None = None
    if index_manifest_json is not None:
        manifest = json.loads(Path(index_manifest_json).read_text(encoding="utf-8"))
        declared = manifest.get("output_sha256")
        manifest_match = declared == index_sha
        if not manifest_match:
            raise DatasetVerificationError(
                "index CSV does not match its manifest: "
                f"manifest output_sha256={declared} measured={index_sha}"
            )
        declared_policy = manifest.get("schema_version")
        if declared_policy != expected_policy_version:
            raise DatasetVerificationError(
                f"manifest schema_version={declared_policy!r}, expected "
                f"{expected_policy_version!r}"
            )

    policies = sorted(index["scoring_policy_version"].unique().tolist())
    if policies != [expected_policy_version]:
        raise DatasetVerificationError(
            f"index carries scoring_policy_version {policies}, expected "
            f"exactly [{expected_policy_version!r}]"
        )

    for name, frame in (("index", index), ("coordinates", coords)):
        if len(frame) != expected_rows:
            raise DatasetVerificationError(
                f"{name} CSV has {len(frame)} rows, expected {expected_rows}"
            )
        if frame[KEY_COLUMN].nunique() != expected_rows:
            raise DatasetVerificationError(
                f"{name} CSV has {frame[KEY_COLUMN].nunique()} unique "
                f"{KEY_COLUMN} values, expected {expected_rows}"
            )

    index_ids = set(index[KEY_COLUMN])
    coord_ids = set(coords[KEY_COLUMN])
    only_index = len(index_ids - coord_ids)
    only_coords = len(coord_ids - index_ids)
    if only_index or only_coords:
        raise DatasetVerificationError(
            f"key sets are asymmetric: {only_index} IDs only in the index, "
            f"{only_coords} IDs only in the coordinates. This is reported "
            "rather than dropped by an inner join."
        )

    joined = index.merge(
        coords[[KEY_COLUMN, X_COLUMN, Y_COLUMN]],
        on=KEY_COLUMN,
        how="inner",
        validate="one_to_one",
    )
    if len(joined) != expected_rows:
        raise DatasetVerificationError(
            f"join produced {len(joined)} rows, expected {expected_rows}"
        )

    null_counts = {c: int(joined[c].isna().sum()) for c in joined.columns}
    offending = {c: n for c, n in null_counts.items() if n}
    if offending:
        raise DatasetVerificationError(f"nulls present after join: {offending}")

    dataset = (
        joined[[KEY_COLUMN, X_COLUMN, Y_COLUMN, LABEL_COLUMN]]
        .rename(columns={X_COLUMN: "x", Y_COLUMN: "y"})
        .sort_values(KEY_COLUMN, kind="mergesort")
        .reset_index(drop=True)
    )

    duplicate_mask = dataset.duplicated(subset=["x", "y"], keep=False)
    report = DatasetReport(
        index_path=str(index_path),
        index_sha256=index_sha,
        index_sha256_matches_manifest=manifest_match,
        coordinates_path=str(coord_path),
        coordinates_sha256=coord_sha,
        index_rows=len(index),
        index_unique_ids=int(index[KEY_COLUMN].nunique()),
        coordinate_rows=len(coords),
        coordinate_unique_ids=int(coords[KEY_COLUMN].nunique()),
        joined_rows=len(dataset),
        ids_only_in_index=only_index,
        ids_only_in_coordinates=only_coords,
        null_counts=null_counts,
        scoring_policy_versions=policies,
        distance_crs=DISTANCE_CRS,
        label_min=float(dataset[LABEL_COLUMN].min()),
        label_max=float(dataset[LABEL_COLUMN].max()),
        label_mean=float(dataset[LABEL_COLUMN].mean()),
        label_std=float(dataset[LABEL_COLUMN].std(ddof=1)),
        x_min=float(dataset["x"].min()),
        x_max=float(dataset["x"].max()),
        y_min=float(dataset["y"].min()),
        y_max=float(dataset["y"].max()),
        duplicate_coordinate_rows=int(duplicate_mask.sum()),
        distinct_coordinate_pairs=int(len(dataset.drop_duplicates(subset=["x", "y"]))),
    )
    return dataset, report


def write_dataset(frame: pd.DataFrame, path: str | Path) -> str:
    """Write the dataset deterministically and return its SHA-256."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # "%.17g" guarantees a float64 survives the text round trip. It is not
    # cosmetic: pandas' DEFAULT CSV float parser is not correctly rounded, and on
    # the countywide coordinate file it disagrees with float_precision=
    # "round_trip" on 34,221 eastings and 43,206 northings by up to 9.31e-10 m —
    # the same order as BOUNDARY_EPSILON_METERS. Reader and writer are pinned
    # together here so the dataset reproduces its source coordinates exactly.
    frame.to_csv(out, index=False, lineterminator="\n", float_format="%.17g")
    return sha256_file(out)


def write_manifest(
    path: str | Path,
    report: DatasetReport,
    output_path: str | Path,
    output_sha256: str,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Write the dataset manifest. A manifest must reproduce what it describes."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": "supervised_dataset_v2",
        "label_policy_version": EXPECTED_POLICY_VERSION,
        "label_column": LABEL_COLUMN,
        "input_crs": DISTANCE_CRS,
        "output": str(output_path),
        "output_sha256": output_sha256,
        "verification": report.to_dict(),
    }
    if extra:
        payload.update(dict(extra))
    out.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")