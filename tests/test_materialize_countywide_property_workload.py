from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import geopandas as gpd
import pytest
from shapely.geometry import Point


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "python"
    / "scripts"
    / "materialize_countywide_property_workload.py"
)

SPEC = importlib.util.spec_from_file_location(
    "materialize_countywide_property_workload",
    SCRIPT_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(
        f"Could not load countywide materializer: {SCRIPT_PATH}"
    )

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeResponsePayload:
    pass


def make_feature(
    object_id: int,
    property_id: str | None,
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "OBJECTID": object_id,
            "SBL": property_id,
        },
        "geometry": {
            "type": "Point",
            "coordinates": [
                -77.8 + object_id / 100.0,
                43.0 + object_id / 100.0,
            ],
        },
    }


def make_cache(
    property_ids: list[str],
    origins: list[str],
) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "property_id": property_ids,
            "sample_order": range(
                len(property_ids)
            ),
            "cache_origin": origins,
        },
        geometry=[
            Point(
                -77.8 + index / 100.0,
                43.0 + index / 100.0,
            )
            for index in range(len(property_ids))
        ],
        crs="EPSG:4326",
    )


def test_fetch_all_unique_properties_scans_every_sorted_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    post_batches: list[str] = []

    def fake_request(
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if method == "GET" and not url.endswith(
            "/query"
        ):
            return {
                "objectIdField": "OBJECTID",
                "maxRecordCount": 2,
                "currentVersion": 11.3,
            }

        if method == "GET":
            return {
                "objectIds": [5, 3, 1, 4, 2],
            }

        object_ids = str(
            kwargs["data"]["objectIds"]
        )
        post_batches.append(object_ids)

        ids = [
            int(value)
            for value in object_ids.split(",")
        ]
        property_ids = {
            1: "P1",
            2: "P2",
            3: "P2",
            4: None,
            5: "P5",
        }

        return {
            "type": "FeatureCollection",
            "features": [
                make_feature(
                    object_id,
                    property_ids[object_id],
                )
                for object_id in reversed(ids)
            ],
        }

    monkeypatch.setattr(
        MODULE,
        "request_json_with_retries",
        fake_request,
    )

    config = {
        "property_points": {
            "source_name": "Test parcels",
            "source_url": (
                "https://example.test/FeatureServer/0/query"
            ),
            "county_field": "COUNTY_NAME",
            "county_value": "Monroe",
            "canonical_id_field": "SBL",
            "object_id_batch_size": 2,
        }
    }

    properties, metadata = (
        MODULE.fetch_all_unique_property_points(
            config=config,
            timeout_seconds=30,
        )
    )

    assert post_batches == [
        "1,2",
        "3,4",
        "5",
    ]
    assert properties[
        "property_id"
    ].tolist() == [
        "P1",
        "P2",
        "P5",
    ]
    assert properties[
        "sample_order"
    ].tolist() == [0, 1, 2]
    assert metadata[
        "source_matching_object_id_count"
    ] == 5
    assert metadata[
        "candidate_rows_examined_count"
    ] == 5
    assert metadata[
        "excluded_duplicate_property_id_count"
    ] == 1
    assert metadata[
        "excluded_missing_property_id_count"
    ] == 1
    assert metadata[
        "feature_request_count"
    ] == 3


def test_countywide_cache_preserves_validated_prefix() -> None:
    prefix = make_cache(
        ["P1", "P2"],
        ["prefix", "prefix"],
    )
    remote = make_cache(
        ["P1", "P2", "P3", "P4"],
        ["remote"] * 4,
    )

    combined, contract, comparison = (
        MODULE.build_countywide_nested_cache(
            prefix=prefix,
            remote=remote,
            coordinate_tolerance_degrees=1e-9,
            allow_prefix_source_drift=False,
        )
    )

    assert combined[
        "property_id"
    ].tolist() == [
        "P1",
        "P2",
        "P3",
        "P4",
    ]
    assert combined[
        "sample_order"
    ].tolist() == [0, 1, 2, 3]
    assert combined.loc[
        0,
        "cache_origin",
    ] == "prefix"
    assert combined.loc[
        2,
        "cache_origin",
    ] == (
        "arcgis_countywide_object_id_ordered_extension"
    )
    assert contract[
        "validated_prefix_preserved_exactly"
    ] is True
    assert contract[
        "cache_matches_current_source_id_set"
    ] is True
    assert comparison[
        "coordinate_mismatches"
    ] == 0


def test_countywide_cache_rejects_missing_prefix_id() -> None:
    prefix = make_cache(
        ["P1", "P2"],
        ["prefix", "prefix"],
    )
    remote = make_cache(
        ["P1", "P3"],
        ["remote", "remote"],
    )

    with pytest.raises(
        RuntimeError,
        match="no longer exactly contains",
    ):
        MODULE.build_countywide_nested_cache(
            prefix=prefix,
            remote=remote,
            coordinate_tolerance_degrees=1e-9,
            allow_prefix_source_drift=False,
        )


def test_countywide_cache_rejects_coordinate_drift() -> None:
    prefix = make_cache(
        ["P1", "P2"],
        ["prefix", "prefix"],
    )
    remote = make_cache(
        ["P1", "P2", "P3"],
        ["remote"] * 3,
    )
    remote.loc[
        remote["property_id"] == "P2",
        "geometry",
    ] = Point(-77.0, 42.0)

    with pytest.raises(
        RuntimeError,
        match="coordinate mismatches",
    ):
        MODULE.build_countywide_nested_cache(
            prefix=prefix,
            remote=remote,
            coordinate_tolerance_degrees=1e-9,
            allow_prefix_source_drift=False,
        )
