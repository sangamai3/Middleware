"""REST API connector pagination tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from sangam_mw.connectors.base.metadata import AuthType
from sangam_mw.connectors.base.schemas import ConnectionHandle, ReadConfig, WriteConfig
from sangam_mw.connectors.rest_api.connector import RestApiConnector
from tests.connectors.fakes import FakeClient, FakeResponse


def _handle(client: FakeClient, extra: dict | None = None) -> ConnectionHandle:
    config = {
        "base_url": "https://api.example.com",
        "api_key": "secret",
        "objects": ["/customers"],
        **(extra or {}),
    }
    return ConnectionHandle(
        connector_id="rest-api",
        connection_id="rest",
        config=config,
        created_at=datetime.now(UTC),
        raw_conn=client,
    )


def test_rest_metadata() -> None:
    assert RestApiConnector().metadata.auth_type == AuthType.API_KEY
    assert RestApiConnector().metadata.connector_id == "rest-api"


def test_rest_offset_pagination() -> None:
    pages = {
        0: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}],
    }

    def handler(method: str, url: str, kwargs: dict) -> FakeResponse:
        params = kwargs.get("params") or {}
        offset = int(params.get("offset") or 0)
        return FakeResponse(json_data=pages.get(offset, []))

    client = FakeClient(handler)
    handle = _handle(client, {"pagination": "offset"})
    df = RestApiConnector().read(
        handle, ReadConfig(object="/customers", extra={"pagination": "offset"}, batch_size=2)
    )
    assert list(df["id"]) == [1, 2, 3]


def test_rest_cursor_pagination() -> None:
    def handler(method: str, url: str, kwargs: dict) -> FakeResponse:
        params = kwargs.get("params") or {}
        if not params.get("cursor"):
            return FakeResponse(json_data={"data": [{"id": 1}], "next_cursor": "abc"})
        return FakeResponse(json_data={"data": [{"id": 2}], "next_cursor": None})

    df = RestApiConnector().read(
        _handle(FakeClient(handler), {"items_path": "data"}),
        ReadConfig(object="/customers", extra={"pagination": "cursor"}),
    )
    assert list(df["id"]) == [1, 2]


def test_rest_link_header_pagination() -> None:
    def handler(method: str, url: str, kwargs: dict) -> FakeResponse:
        if url.endswith("/customers"):
            return FakeResponse(
                json_data=[{"id": 1}],
                headers={"Link": '<https://api.example.com/customers?page=2>; rel="next"'},
            )
        return FakeResponse(json_data=[{"id": 2}], headers={})

    df = RestApiConnector().read(
        _handle(FakeClient(handler)),
        ReadConfig(object="/customers", extra={"pagination": "link"}),
    )
    assert list(df["id"]) == [1, 2]


def test_rest_write_and_objects() -> None:
    posted: list = []

    def handler(method: str, url: str, kwargs: dict) -> FakeResponse:
        if method == "GET" and url.rstrip("/").endswith("example.com"):
            return FakeResponse(json_data={"ok": True})
        if method == "POST":
            posted.append(kwargs.get("json"))
            return FakeResponse(json_data={"ok": True})
        return FakeResponse(json_data=[{"id": 1, "name": "Ada"}])

    client = FakeClient(handler)
    handle = _handle(client)
    connector = RestApiConnector()
    assert connector.test_connection(handle) is True
    assert [o.name for o in connector.introspect_objects(handle)] == ["/customers"]
    result = connector.write(
        pd.DataFrame([{"name": "Ada"}]), handle, WriteConfig(object="/customers")
    )
    assert result.rows_written == 1
    assert posted
