"""Salesforce connector — AgentStudio REST client (SOQL, nextRecordsUrl, OAuth)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd

from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.errors import ConnectorValidationError
from ..base.http import raise_for_status
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)
from .client import SalesforceClient
from .security import validate_sobject_identifier
from .soql import sf_limit


class SalesforceConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="salesforce",
            label="Salesforce",
            family="saas",
            version="1.0.0",
            auth_type=AuthType.OAUTH2,
            operations=[OperationType.READ, OperationType.WRITE],
            description=(
                "Salesforce REST via AgentStudio client: client-credentials or JWT bearer; "
                "instance_url from the token; SOQL with safe nextRecordsUrl pagination."
            ),
            connection_schema={
                "type": "object",
                "properties": {
                    "auth_type": {
                        "type": "string",
                        "enum": [
                            "salesforceClientCredentials",
                            "salesforceJwtBearer",
                            "access_token",
                        ],
                        "default": "salesforceClientCredentials",
                    },
                    "login_url": {
                        "type": "string",
                        "description": "My Domain URL for client credentials; login/test for JWT",
                    },
                    "client_id": {"type": "string"},
                    "client_secret": {"type": "string", "secret": True},
                    "username": {"type": "string"},
                    "private_key": {"type": "string", "secret": True},
                    "access_token": {"type": "string", "secret": True},
                    "instance_url": {"type": "string"},
                    "api_version": {"type": "string", "default": "v61.0"},
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["object", "soql"], "default": "object"},
                    "object": {"type": "string"},
                    "query": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "filter": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string"},
                    "mode": {"type": "string", "enum": ["append", "upsert"], "default": "append"},
                    "upsert_key": {"type": "string"},
                },
            },
        )

    def test_connection(self, handle: ConnectionHandle) -> bool:
        client = self._sf(handle)
        resp = client.get(f"/services/data/{client.api_version}/")
        raise_for_status(resp)
        return True

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        client = self._sf(handle)
        resp = client.get(f"/services/data/{client.api_version}/sobjects")
        raise_for_status(resp)
        return [
            ObjectSchema(
                name=str(item["name"]),
                kind="table",
                description=str(item.get("label") or ""),
            )
            for item in resp.json().get("sobjects", [])
            if item.get("queryable")
        ]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        client = self._sf(handle)
        name = validate_sobject_identifier(object_name)
        resp = client.get(f"/services/data/{client.api_version}/sobjects/{name}/describe")
        raise_for_status(resp)
        return [
            ColumnSchema(
                name=str(field["name"]),
                data_type=str(field.get("type") or "string"),
                nullable=bool(field.get("nillable", True)),
                is_primary_key=str(field["name"]) == "Id",
                description=str(field.get("label") or ""),
            )
            for field in resp.json().get("fields", [])
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        frames = list(self.read_batch(handle, config))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def read_batch(self, handle: ConnectionHandle, config: ReadConfig) -> Iterator[pd.DataFrame]:
        client = self._sf(handle)
        cap = sf_limit(config.limit if config.limit is not None else 200)
        records = client.soql(self._soql(config), max_records=cap)
        df = pd.DataFrame([_flatten_record(r) for r in records])
        if not df.empty:
            yield df.reset_index(drop=True)

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        if df.empty:
            return WriteResult(rows_written=0)
        client = self._sf(handle)
        sobject = validate_sobject_identifier(config.object)
        written = 0
        updated = 0
        failed = 0
        errors: list[dict] = []
        version = client.api_version
        for row in df.where(pd.notnull(df), None).to_dict(orient="records"):
            body = {str(k): v for k, v in row.items() if k != "attributes"}
            try:
                if config.mode == "upsert":
                    key = config.upsert_key
                    if not key:
                        raise ConnectorValidationError(
                            "upsert_key is required for Salesforce upsert"
                        )
                    if key not in body:
                        raise ConnectorValidationError(f"upsert_key '{key}' missing from row")
                    value = body.pop(key)
                    resp = client.patch(
                        f"/services/data/{version}/sobjects/{sobject}/{key}/{value}",
                        body,
                    )
                    raise_for_status(resp)
                    updated += 1
                else:
                    resp = client.post(f"/services/data/{version}/sobjects/{sobject}/", body)
                    raise_for_status(resp)
                    written += 1
            except Exception as exc:
                failed += 1
                errors.append({"error": str(exc), "row": row})
        return WriteResult(
            rows_written=written + updated,
            rows_updated=updated,
            rows_failed=failed,
            errors=errors,
        )

    def _sf(self, handle: ConnectionHandle) -> SalesforceClient:
        if isinstance(handle.raw_conn, SalesforceClient):
            return handle.raw_conn
        return SalesforceClient(
            handle.config,
            http=handle.raw_conn,
            verify_hosts=handle.raw_conn is None,
        )

    def _soql(self, config: ReadConfig) -> str:
        if (config.mode or "object") == "soql":
            soql = config.query or config.extra.get("soql")
            if not soql:
                raise ConnectorValidationError("SOQL query is required when mode=soql")
            return str(soql)
        name = validate_sobject_identifier(config.object)
        fields = ", ".join(config.fields) if config.fields else "Id"
        soql = f"SELECT {fields} FROM {name}"
        if config.filter:
            soql += f" WHERE {config.filter}"
        soql += f" LIMIT {sf_limit(config.limit if config.limit is not None else 200)}"
        return soql


def _flatten_record(record: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in record.items():
        if key == "attributes":
            continue
        name = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(_flatten_record(value, name))
        else:
            flat[name if prefix else key] = value
    return flat
