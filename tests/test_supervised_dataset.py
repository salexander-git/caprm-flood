"""Tests for caprm.supervised_dataset.

Every check the module claims to perform is exercised against a synthetic
fixture whose defect is known in advance, because a verification that has never
been shown to fail is not a verification (Nucleus 18.25).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from caprm.supervised_dataset import (
    DatasetVerificationError,
    build_supervised_dataset,
    read_index_csv,
    sha256_file,
    write_dataset,
)

POLICY = "preliminary_exposure_index_v2"
IDS = ["00104000010011100000", "00104000010011200000", "1600100001003000WC"]


def _index_frame(ids=None, policy=POLICY):
    ids = list(IDS if ids is None else ids)
    n = len(ids)
    return pd.DataFrame(
        {
            "property_id": ids,
            "fema_component_0_100": [10.0] * n,
            "water_component_0_100": [20.0 + i for i in range(n)],
            "terrain_absolute_component_0_100": [30.0] * n,
            "terrain_relative_component_0_100": [40.0] * n,
            "exposure_index_0_100": [11.0 + i for i in range(n)],
            "exposure_percentile": [50.0] * n,
            "scoring_policy_version": [policy] * n,
        }
    )


def _coord_frame(ids=None):
    ids = list(IDS if ids is None else ids)
    return pd.DataFrame(
        {
            "sample_order": range(len(ids)),
            "property_id": ids,
            "projected_x": [280000.0 + 10 * i for i in range(len(ids))],
            "projected_y": [4770000.0 + 10 * i for i in range(len(ids))],
        }
    )


def _write(tmp_path: Path, index: pd.DataFrame, coords: pd.DataFrame):
    ip = tmp_path / "index.csv"
    cp = tmp_path / "coords.csv"
    index.to_csv(ip, index=False, lineterminator="\n")
    coords.to_csv(cp, index=False, lineterminator="\n")
    return ip, cp


def test_happy_path_reports_measured_values(tmp_path):
    ip, cp = _write(tmp_path, _index_frame(), _coord_frame())
    dataset, report = build_supervised_dataset(ip, cp, expected_rows=3)
    assert list(dataset.columns) == ["property_id", "x", "y", "exposure_index_0_100"]
    assert report.joined_rows == 3
    assert report.index_unique_ids == 3
    assert report.ids_only_in_index == 0
    assert report.ids_only_in_coordinates == 0
    assert report.scoring_policy_versions == [POLICY]
    assert report.distance_crs == "EPSG:26918"
    assert report.index_sha256 == sha256_file(ip)


def test_leading_zeros_and_alphanumeric_id_survive_the_read(tmp_path):
    """The one defect that would look like a data problem and is a dtype problem."""
    ip, _ = _write(tmp_path, _index_frame(), _coord_frame())
    frame = read_index_csv(ip)
    assert frame["property_id"].iloc[0].startswith("00104")
    assert frame["property_id"].iloc[2] == "1600100001003000WC"


def test_output_is_sorted_and_byte_deterministic(tmp_path):
    ip, cp = _write(tmp_path, _index_frame(), _coord_frame())
    dataset, _ = build_supervised_dataset(ip, cp, expected_rows=3)
    assert dataset["property_id"].is_monotonic_increasing
    a = write_dataset(dataset, tmp_path / "a.csv")
    b = write_dataset(dataset, tmp_path / "b.csv")
    assert a == b


def test_row_count_mismatch_raises(tmp_path):
    ip, cp = _write(tmp_path, _index_frame(), _coord_frame())
    with pytest.raises(DatasetVerificationError, match="rows, expected 4"):
        build_supervised_dataset(ip, cp, expected_rows=4)


def test_duplicate_property_id_raises(tmp_path):
    dup = IDS[:2] + [IDS[0]]
    ip, cp = _write(tmp_path, _index_frame(dup), _coord_frame(dup))
    with pytest.raises(DatasetVerificationError, match="unique"):
        build_supervised_dataset(ip, cp, expected_rows=3)


def test_key_asymmetry_is_reported_not_dropped(tmp_path):
    """An inner join would silently return 2 rows and look healthy."""
    other = IDS[:2] + ["99999999999999999999"]
    ip, cp = _write(tmp_path, _index_frame(), _coord_frame(other))
    with pytest.raises(DatasetVerificationError, match="asymmetric"):
        build_supervised_dataset(ip, cp, expected_rows=3)


def test_wrong_policy_version_raises(tmp_path):
    ip, cp = _write(tmp_path, _index_frame(policy="preliminary_exposure_index_v1"), _coord_frame())
    with pytest.raises(DatasetVerificationError, match="scoring_policy_version"):
        build_supervised_dataset(ip, cp, expected_rows=3)


def test_null_label_raises(tmp_path):
    index = _index_frame()
    index.loc[1, "exposure_index_0_100"] = None
    ip, cp = _write(tmp_path, index, _coord_frame())
    with pytest.raises(DatasetVerificationError, match="nulls present"):
        build_supervised_dataset(ip, cp, expected_rows=3)


def test_manifest_checksum_mismatch_raises(tmp_path):
    ip, cp = _write(tmp_path, _index_frame(), _coord_frame())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"output_sha256": "0" * 64, "schema_version": POLICY}), encoding="utf-8"
    )
    with pytest.raises(DatasetVerificationError, match="does not match its manifest"):
        build_supervised_dataset(ip, cp, index_manifest_json=manifest, expected_rows=3)


def test_manifest_checksum_match_passes(tmp_path):
    ip, cp = _write(tmp_path, _index_frame(), _coord_frame())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"output_sha256": sha256_file(ip), "schema_version": POLICY}),
        encoding="utf-8",
    )
    _, report = build_supervised_dataset(
        ip, cp, index_manifest_json=manifest, expected_rows=3
    )
    assert report.index_sha256_matches_manifest is True


def test_missing_column_raises(tmp_path):
    index = _index_frame().drop(columns=["exposure_index_0_100"])
    ip, cp = _write(tmp_path, index, _coord_frame())
    with pytest.raises(DatasetVerificationError, match="missing columns"):
        build_supervised_dataset(ip, cp, expected_rows=3)