from __future__ import annotations

from typing import Any

import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import Point

from caprm.ingest import (
    add_canonical_fema_fields,
    build_nested_property_sample,
    fetch_property_points_with_metadata,
    prepare_property_cache,
    select_unique_identifier,
    validate_property_points,
)


def test_fema_fields_are_canonicalized() -> None:
    fema = gpd.GeoDataFrame(
        {
            "FLD_ZONE": ["AE", "X"],
            "SFHA_TF": ["T", "F"],
        },
        geometry=[
            Point(0, 0),
            Point(1, 1),
        ],
        crs="EPSG:4326",
    )

    result = add_canonical_fema_fields(
        fema,
        {
            "zone_field_candidates": ["FLD_ZONE"],
            "sfha_field_candidates": ["SFHA_TF"],
        },
    )

    assert result["fema_zone"].tolist() == ["AE", "X"]
    assert result["sfha_flag"].tolist() == ["T", "F"]


def test_unique_identifier_skips_nonunique_candidate() -> None:
    dataframe = pd.DataFrame(
        {
            "DFIRM_ID": ["36055C", "36055C"],
            "FLD_AR_ID": ["36055C_1", "36055C_2"],
        }
    )

    result = select_unique_identifier(
        dataframe,
        ["DFIRM_ID", "FLD_AR_ID"],
        "FEMA feature identifier",
    )

    assert result == "FLD_AR_ID"


def test_unique_identifier_rejects_all_invalid_candidates() -> None:
    dataframe = pd.DataFrame(
        {
            "A": ["same", "same"],
            "B": ["one", pd.NA],
        }
    )

    with pytest.raises(
        ValueError,
        match="No complete unique",
    ):
        select_unique_identifier(
            dataframe,
            ["A", "B"],
            "identifier",
        )


def test_property_points_are_sorted_by_sample_order() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P2", "P1"],
            "sample_order": [1, 0],
        },
        geometry=[
            Point(-77.6, 43.2),
            Point(-77.7, 43.1),
        ],
        crs="EPSG:4326",
    )

    result = validate_property_points(
        properties,
        expected_limit=2,
    )

    assert result["property_id"].tolist() == ["P1", "P2"]


def test_duplicate_property_ids_are_rejected() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1", "P1"],
        },
        geometry=[
            Point(-77.6, 43.2),
            Point(-77.7, 43.1),
        ],
        crs="EPSG:4326",
    )

    with pytest.raises(
        ValueError,
        match="duplicate IDs",
    ):
        validate_property_points(properties)


def test_prepare_property_cache_uses_minimal_schema() -> None:
    properties = gpd.GeoDataFrame(
        {
            "property_id": ["P1", "P2"],
            "sample_order": [0, 1],
            "cache_origin": ["test", "test"],
            "unused": [10, 20],
        },
        geometry=[
            Point(-77.7, 43.1),
            Point(-77.6, 43.2),
        ],
        crs="EPSG:4326",
    )

    result = prepare_property_cache(properties)

    assert result.columns.tolist() == [
        "sample_order",
        "property_id",
        "latitude",
        "longitude",
        "cache_origin",
        "geometry",
    ]
    assert result["latitude"].tolist() == [43.1, 43.2]
    assert result["longitude"].tolist() == [-77.7, -77.6]


def test_nested_property_sample_preserves_regression_first() -> None:
    regression = gpd.GeoDataFrame(
        {
            "property_id": ["R1", "R2"],
            "sample_order": [0, 1],
            "cache_origin": [
                "validated_milestone_1_baseline",
                "validated_milestone_1_baseline",
            ],
        },
        geometry=[
            Point(-77.7, 43.1),
            Point(-77.6, 43.2),
        ],
        crs="EPSG:4326",
    )
    remote = gpd.GeoDataFrame(
        {
            "property_id": ["R2", "N1", "N2", "N3"],
            "sample_order": [0, 1, 2, 3],
            "cache_origin": [
                "arcgis_object_id_ordered",
                "arcgis_object_id_ordered",
                "arcgis_object_id_ordered",
                "arcgis_object_id_ordered",
            ],
        },
        geometry=[
            Point(-77.6, 43.2),
            Point(-77.5, 43.3),
            Point(-77.4, 43.4),
            Point(-77.3, 43.5),
        ],
        crs="EPSG:4326",
    )

    result = build_nested_property_sample(
        regression,
        remote,
        target_count=4,
    )

    assert result["property_id"].tolist() == [
        "R1",
        "R2",
        "N1",
        "N2",
    ]
    assert result["sample_order"].tolist() == [0, 1, 2, 3]
    assert result["property_id"].nunique() == 4
    assert result.loc[0, "cache_origin"] == (
        "validated_milestone_1_baseline"
    )
    assert result.loc[2, "cache_origin"] == (
        "arcgis_object_id_ordered_extension"
    )


def test_nested_property_sample_rejects_insufficient_extension() -> None:
    regression = gpd.GeoDataFrame(
        {
            "property_id": ["R1", "R2"],
            "sample_order": [0, 1],
            "cache_origin": ["test", "test"],
        },
        geometry=[
            Point(-77.7, 43.1),
            Point(-77.6, 43.2),
        ],
        crs="EPSG:4326",
    )
    remote = gpd.GeoDataFrame(
        {
            "property_id": ["R1", "N1"],
            "sample_order": [0, 1],
            "cache_origin": ["remote", "remote"],
        },
        geometry=[
            Point(-77.7, 43.1),
            Point(-77.5, 43.3),
        ],
        crs="EPSG:4326",
    )

    with pytest.raises(
        ValueError,
        match="does not contain enough unique",
    ):
        build_nested_property_sample(
            regression,
            remote,
            target_count=4,
        )


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def make_feature(object_id: int) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "OBJECTID": object_id,
            "SBL": f"P{object_id}",
        },
        "geometry": {
            "type": "Point",
            "coordinates": [
                -77.8 + object_id / 100.0,
                43.0 + object_id / 100.0,
            ],
        },
    }


def test_fetch_property_points_uses_sorted_object_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_batches: list[str] = []

    def fake_get(
        url: str,
        params: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        assert timeout == 30

        if not url.endswith("/query"):
            return FakeResponse(
                {
                    "objectIdField": "OBJECTID",
                    "maxRecordCount": 2,
                    "currentVersion": 11.3,
                    "editingInfo": {
                        "lastEditDate": 1234567890,
                    },
                }
            )

        assert params.get("returnIdsOnly") == "true"
        assert params["where"] == "COUNTY_NAME = 'Monroe'"
        return FakeResponse(
            {
                "objectIdFieldName": "OBJECTID",
                "objectIds": [3, 1, 2],
            }
        )

    def fake_post(
        url: str,
        data: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        assert timeout == 30
        assert url.endswith("/query")

        object_ids = str(data["objectIds"])
        feature_batches.append(object_ids)
        ids = [int(value) for value in object_ids.split(",")]

        return FakeResponse(
            {
                "type": "FeatureCollection",
                "features": [
                    make_feature(value)
                    for value in reversed(ids)
                ],
            }
        )

    monkeypatch.setattr(
        "caprm.ingest.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "caprm.ingest.requests.post",
        fake_post,
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
            "id_field_candidates": ["SBL", "OBJECTID"],
            "sample_limit": 3,
            "object_id_batch_size": 2,
        }
    }

    properties, metadata = fetch_property_points_with_metadata(
        config,
        timeout_seconds=30,
    )

    assert feature_batches == ["1,2", "3"]
    assert properties["property_id"].tolist() == [
        "P1",
        "P2",
        "P3",
    ]
    assert properties["sample_order"].tolist() == [0, 1, 2]
    assert metadata["selection_method"] == (
        "sorted_arcgis_object_ids"
    )
    assert metadata["source_object_id_field"] == "OBJECTID"
    assert metadata["property_id_field"] == "SBL"
    assert metadata["feature_request_method"] == "POST"
    assert metadata["selected_first_object_id"] == 1
    assert metadata["selected_last_object_id"] == 3


def test_fetch_property_points_skips_duplicate_and_missing_canonical_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_batches: list[str] = []
    sbl_by_object_id: dict[int, str | None] = {
        1: "P1",
        2: "P2",
        3: "P2",
        4: "P4",
        5: None,
        6: "P6",
    }

    def fake_get(
        url: str,
        params: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        assert timeout == 30

        if not url.endswith("/query"):
            return FakeResponse(
                {
                    "objectIdField": "OBJECTID",
                    "maxRecordCount": 2,
                    "currentVersion": 11.3,
                }
            )

        return FakeResponse(
            {
                "objectIdFieldName": "OBJECTID",
                "objectIds": [6, 4, 2, 5, 3, 1],
            }
        )

    def fake_post(
        url: str,
        data: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        assert timeout == 30
        assert url.endswith("/query")

        object_ids = str(data["objectIds"])
        feature_batches.append(object_ids)
        ids = [int(value) for value in object_ids.split(",")]

        features: list[dict[str, Any]] = []

        for object_id in reversed(ids):
            feature = make_feature(object_id)
            feature["properties"]["SBL"] = sbl_by_object_id[
                object_id
            ]
            features.append(feature)

        return FakeResponse(
            {
                "type": "FeatureCollection",
                "features": features,
            }
        )

    monkeypatch.setattr(
        "caprm.ingest.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "caprm.ingest.requests.post",
        fake_post,
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
            "id_field_candidates": ["SBL", "OBJECTID"],
            "sample_limit": 4,
            "object_id_batch_size": 2,
        }
    }

    properties, metadata = fetch_property_points_with_metadata(
        config,
        timeout_seconds=30,
    )

    assert feature_batches == ["1,2", "3,4", "5,6"]
    assert properties["property_id"].tolist() == [
        "P1",
        "P2",
        "P4",
        "P6",
    ]
    assert properties["sample_order"].tolist() == [0, 1, 2, 3]
    assert metadata["source_object_ids_requested_count"] == 6
    assert metadata["candidate_rows_examined_count"] == 6
    assert metadata["selected_object_id_count"] == 4
    assert metadata["selected_first_object_id"] == 1
    assert metadata["selected_last_object_id"] == 6
    assert metadata["excluded_duplicate_property_id_count"] == 1
    assert metadata["excluded_missing_property_id_count"] == 1
    assert metadata["feature_request_count"] == 3



def test_fetch_property_points_retries_transient_id_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    id_request_attempts = 0

    def fake_get(
        url: str,
        params: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        nonlocal id_request_attempts

        assert timeout == 30

        if not url.endswith("/query"):
            return FakeResponse(
                {
                    "objectIdField": "OBJECTID",
                    "maxRecordCount": 2,
                    "currentVersion": 11.3,
                }
            )

        id_request_attempts += 1

        if id_request_attempts == 1:
            raise requests.ReadTimeout(
                "temporary object-ID timeout"
            )

        return FakeResponse(
            {
                "objectIdFieldName": "OBJECTID",
                "objectIds": [2, 1],
            }
        )

    def fake_post(
        url: str,
        data: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        assert timeout == 30
        assert url.endswith("/query")

        ids = [
            int(value)
            for value in str(data["objectIds"]).split(",")
        ]

        return FakeResponse(
            {
                "type": "FeatureCollection",
                "features": [
                    make_feature(value)
                    for value in ids
                ],
            }
        )

    monkeypatch.setattr(
        "caprm.ingest.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "caprm.ingest.requests.post",
        fake_post,
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
            "id_field_candidates": ["SBL", "OBJECTID"],
            "sample_limit": 2,
            "object_id_batch_size": 2,
            "request_max_attempts": 2,
            "request_retry_backoff_seconds": 0,
        }
    }

    properties, metadata = fetch_property_points_with_metadata(
        config,
        timeout_seconds=30,
    )

    assert id_request_attempts == 2
    assert properties["property_id"].tolist() == ["P1", "P2"]
    assert metadata["request_max_attempts"] == 2
    assert metadata["request_retry_backoff_seconds"] == 0
