"""Salesforce connector tests — AgentStudio client behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import unquote_plus

import pandas as pd
import pytest

from sangam_mw.connectors.base.errors import DataReadError, RateLimitError
from sangam_mw.connectors.base.http import raise_for_status
from sangam_mw.connectors.base.metadata import AuthType
from sangam_mw.connectors.base.schemas import ConnectionHandle, ReadConfig, WriteConfig
from sangam_mw.connectors.salesforce.client import SalesforceClient
from sangam_mw.connectors.salesforce.connector import SalesforceConnector
from sangam_mw.connectors.salesforce.security import validate_salesforce_url
from tests.connectors.fakes import FakeClient, FakeResponse


def _handle(client: FakeClient | None = None, **config: object) -> ConnectionHandle:
    base = {
        "instance_url": "https://example.my.salesforce.com",
        "access_token": "token",
        "api_version": "v61.0",
    }
    base.update(config)
    return ConnectionHandle(
        connector_id="salesforce",
        connection_id="sf",
        config=base,
        created_at=datetime.now(UTC),
        raw_conn=client,
    )


def _sf_handler(method: str, url: str, kwargs: dict) -> FakeResponse:
    if method == "POST" and url.endswith("/services/oauth2/token"):
        return FakeResponse(
            json_data={
                "access_token": "fresh-token",
                "instance_url": "https://example.my.salesforce.com",
            }
        )
    if method == "GET" and url.rstrip("/").endswith("/services/data/v61.0"):
        return FakeResponse(json_data={"identity": "/id"})
    if url.endswith("/sobjects"):
        return FakeResponse(
            json_data={
                "sobjects": [
                    {"name": "Account", "label": "Account", "queryable": True},
                    {"name": "SetupAuditTrail", "label": "Setup", "queryable": False},
                ]
            }
        )
    if url.endswith("/sobjects/Account/describe"):
        return FakeResponse(
            json_data={
                "fields": [
                    {"name": "Id", "type": "id", "nillable": False, "label": "Account ID"},
                    {"name": "Name", "type": "string", "nillable": True, "label": "Account Name"},
                ]
            }
        )
    if "/query/next" in url:
        return FakeResponse(
            json_data={"done": True, "records": [{"Id": "002", "Name": "Beta", "attributes": {}}]}
        )
    if "/query" in url:
        return FakeResponse(
            json_data={
                "done": False,
                "nextRecordsUrl": "/services/data/v61.0/query/next",
                "records": [
                    {
                        "attributes": {"type": "Account"},
                        "Id": "001",
                        "Name": "Alpha",
                        "Account": {"Name": "Acme", "attributes": {"type": "Account"}},
                    }
                ],
            }
        )
    if method == "POST" and "/sobjects/Account" in url:
        return FakeResponse(json_data={"id": "003", "success": True})
    if method == "PATCH":
        return FakeResponse(json_data={})
    return FakeResponse(status_code=404, text="not found")


@pytest.fixture
def connector() -> SalesforceConnector:
    return SalesforceConnector()


@pytest.fixture
def handle() -> ConnectionHandle:
    return _handle(FakeClient(_sf_handler))


class TestSalesforceConnector:
    def test_metadata(self, connector: SalesforceConnector) -> None:
        assert connector.metadata.connector_id == "salesforce"
        assert connector.metadata.auth_type == AuthType.OAUTH2

    def test_connection(self, connector: SalesforceConnector, handle: ConnectionHandle) -> None:
        assert connector.test_connection(handle) is True

    def test_introspect_skips_non_queryable(
        self, connector: SalesforceConnector, handle: ConnectionHandle
    ) -> None:
        names = [o.name for o in connector.introspect_objects(handle)]
        assert names == ["Account"]

    def test_introspect_columns(
        self, connector: SalesforceConnector, handle: ConnectionHandle
    ) -> None:
        cols = connector.introspect_columns(handle, "Account")
        assert [c.name for c in cols] == ["Id", "Name"]
        assert cols[0].is_primary_key is True

    def test_read_soql_paginates_and_flattens(
        self, connector: SalesforceConnector, handle: ConnectionHandle
    ) -> None:
        df = connector.read(
            handle,
            ReadConfig(object="Account", mode="soql", query="SELECT Id, Name FROM Account"),
        )
        assert list(df["Id"]) == ["001", "002"]
        assert "Account.Name" in df.columns
        assert df.loc[0, "Account.Name"] == "Acme"

    def test_read_object_mode_builds_soql(
        self, connector: SalesforceConnector, handle: ConnectionHandle
    ) -> None:
        client = handle.raw_conn
        connector.read(
            handle,
            ReadConfig(object="Account", fields=["Id", "Name"], filter="Name != null", limit=10),
        )
        queries = [
            unquote_plus(str((kwargs.get("params") or {}).get("q") or ""))
            for _, _url, kwargs in client.calls
        ]
        joined = " ".join(queries)
        assert "FROM Account" in joined
        assert "Name != null" in joined

    def test_write_append_and_upsert(
        self, connector: SalesforceConnector, handle: ConnectionHandle
    ) -> None:
        df = pd.DataFrame([{"Name": "New Co"}])
        result = connector.write(df, handle, WriteConfig(object="Account", mode="append"))
        assert result.rows_written == 1

        up = pd.DataFrame([{"ExtId__c": "ext-1", "Name": "Upserted"}])
        result = connector.write(
            up, handle, WriteConfig(object="Account", mode="upsert", upsert_key="ExtId__c")
        )
        assert result.rows_updated == 1
        client = handle.raw_conn
        assert any(method == "PATCH" for method, url, _ in client.calls)


def test_rejects_unsafe_next_records_url() -> None:
    def handler(method: str, url: str, kwargs: dict) -> FakeResponse:
        if "/query" in url:
            return FakeResponse(
                json_data={
                    "records": [{"Id": "001"}],
                    "nextRecordsUrl": "https://evil.example/steal",
                }
            )
        return FakeResponse(json_data={})

    client = SalesforceClient(
        {
            "access_token": "t",
            "instance_url": "https://example.my.salesforce.com",
            "api_version": "v61.0",
        },
        http=FakeClient(handler),
        verify_hosts=False,
    )
    with pytest.raises(DataReadError, match="Unsafe"):
        client.soql("SELECT Id FROM Account")


def test_client_credentials_fetches_instance_url() -> None:
    def handler(method: str, url: str, kwargs: dict) -> FakeResponse:
        if method == "POST" and url.endswith("/token"):
            return FakeResponse(
                json_data={
                    "access_token": "cc-token",
                    "instance_url": "https://acme.my.salesforce.com",
                }
            )
        return FakeResponse(json_data={"ok": True})

    client = SalesforceClient(
        {
            "auth_type": "salesforceClientCredentials",
            "login_url": "https://acme.my.salesforce.com",
            "client_id": "cid",
            "client_secret": "sec",
            "api_version": "v61.0",
        },
        http=FakeClient(handler),
        verify_hosts=False,
    )
    client.get("/services/data/v61.0/")
    assert client.instance_url == "https://acme.my.salesforce.com"


def test_https_host_validation() -> None:
    with pytest.raises(Exception, match="HTTPS"):
        validate_salesforce_url("http://acme.my.salesforce.com", check_dns=False)


def test_http_429_maps_to_rate_limit() -> None:
    with pytest.raises(RateLimitError) as exc:
        raise_for_status(FakeResponse(status_code=429, text="slow", headers={"Retry-After": "15"}))
    assert exc.value.retry_after == 15
