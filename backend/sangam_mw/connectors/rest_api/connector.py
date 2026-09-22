"""Generic REST API connector — API key / bearer auth and pluggable pagination."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import urljoin

import httpx
import pandas as pd

from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.errors import AuthenticationError, ConnectorValidationError, DataReadError
from ..base.http import request
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)


class RestApiConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="rest-api",
            label="REST API",
            family="rest",
            version="1.0.0",
            auth_type=AuthType.API_KEY,
            operations=[OperationType.READ, OperationType.WRITE],
            description=(
                "Generic HTTP connector matching AgentStudio REST auth: none, bearer, "
                "apiKeyHeader, apiKeyQuery, basic, customHeaders, oauth2ClientCredentials."
            ),
            connection_schema={
                "type": "object",
                "required": ["base_url"],
                "properties": {
                    "base_url": {"type": "string"},
                    "auth_type": {
                        "type": "string",
                        "enum": [
                            "none",
                            "bearer",
                            "apiKeyHeader",
                            "apiKeyQuery",
                            "basic",
                            "customHeaders",
                            "oauth2ClientCredentials",
                        ],
                    },
                    "api_key": {"type": "string", "secret": True},
                    "token": {
                        "type": "string",
                        "secret": True,
                        "description": "Bearer token alias",
                    },
                    "api_key_header": {"type": "string", "default": "Authorization"},
                    "api_key_prefix": {"type": "string", "default": "Bearer"},
                    "api_key_in": {
                        "type": "string",
                        "enum": ["header", "query"],
                        "default": "header",
                    },
                    "username": {"type": "string"},
                    "password": {"type": "string", "secret": True},
                    "custom_headers": {
                        "type": "string",
                        "description": "JSON array of {key,value} for customHeaders auth",
                    },
                    "token_url": {"type": "string"},
                    "client_id": {"type": "string"},
                    "client_secret": {"type": "string", "secret": True},
                    "scope": {"type": "string"},
                    "pagination": {
                        "type": "string",
                        "enum": ["none", "offset", "cursor", "link"],
                        "default": "none",
                    },
                    "items_path": {
                        "type": "string",
                        "description": "Dotted path to the list of records in the JSON body",
                    },
                    "objects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Known endpoint paths for the object browser",
                    },
                },
            },
            read_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string", "description": "Path relative to base_url"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                    "pagination": {"type": "string", "enum": ["none", "offset", "cursor", "link"]},
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string"},
                    "mode": {"type": "string", "enum": ["append"], "default": "append"},
                },
            },
        )

    def test_connection(self, handle: ConnectionHandle) -> bool:
        client = self._client(handle)
        request(client, "GET", self._url(handle, handle.config.get("health_path") or ""))
        return True

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        objects = handle.config.get("objects") or []
        return [ObjectSchema(name=str(name), kind="endpoint") for name in objects]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        df = self.sample(handle, object_name, limit=1)
        return [
            ColumnSchema(name=str(col), data_type=str(dtype)) for col, dtype in df.dtypes.items()
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        frames = list(self.read_batch(handle, config))
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
        if config.fields:
            df = df[config.fields]
        if config.limit is not None:
            df = df.head(config.limit)
        return df.reset_index(drop=True)

    def read_batch(self, handle: ConnectionHandle, config: ReadConfig) -> Iterator[pd.DataFrame]:
        pagination = str(
            config.extra.get("pagination")
            or handle.config.get("pagination")
            or config.mode
            or "none"
        )
        if pagination in ("object", "query"):
            pagination = "none"
        client = self._client(handle)
        if pagination == "none":
            yield self._fetch_page(client, handle, config, {})
            return
        if pagination == "offset":
            yield from self._paginate_offset(client, handle, config)
            return
        if pagination == "cursor":
            yield from self._paginate_cursor(client, handle, config)
            return
        if pagination in ("link", "link_header"):
            yield from self._paginate_link(client, handle, config)
            return
        raise ConnectorValidationError(f"Unknown pagination mode '{pagination}'")

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        if df.empty:
            return WriteResult(rows_written=0)
        client = self._client(handle)
        records = df.where(pd.notnull(df), None).to_dict(orient="records")
        request(client, "POST", self._url(handle, config.object), json=records)
        return WriteResult(rows_written=len(df))

    def _paginate_offset(
        self, client: httpx.Client, handle: ConnectionHandle, config: ReadConfig
    ) -> Iterator[pd.DataFrame]:
        offset_param = str(config.extra.get("offset_param") or "offset")
        limit_param = str(config.extra.get("limit_param") or "limit")
        offset = 0
        yielded = 0
        while True:
            params = {offset_param: offset, limit_param: config.batch_size}
            df = self._fetch_page(client, handle, config, params)
            if df.empty:
                return
            if config.limit is not None:
                df = df.head(config.limit - yielded)
            yielded += len(df)
            yield df
            if len(df) < config.batch_size or (
                config.limit is not None and yielded >= config.limit
            ):
                return
            offset += len(df)

    def _paginate_cursor(
        self, client: httpx.Client, handle: ConnectionHandle, config: ReadConfig
    ) -> Iterator[pd.DataFrame]:
        cursor_param = str(config.extra.get("cursor_param") or "cursor")
        cursor_field = str(config.extra.get("cursor_field") or "next_cursor")
        cursor: str | None = None
        yielded = 0
        while True:
            params: dict[str, Any] = {
                str(config.extra.get("limit_param") or "limit"): config.batch_size
            }
            if cursor:
                params[cursor_param] = cursor
            df, payload = self._fetch_page_with_payload(client, handle, config, params)
            if df.empty:
                return
            if config.limit is not None:
                df = df.head(config.limit - yielded)
            yielded += len(df)
            yield df
            cursor_val = _dig(payload, cursor_field)
            if not cursor_val or (config.limit is not None and yielded >= config.limit):
                return
            cursor = str(cursor_val)

    def _paginate_link(
        self, client: httpx.Client, handle: ConnectionHandle, config: ReadConfig
    ) -> Iterator[pd.DataFrame]:
        url: str | None = self._url(handle, config.object)
        yielded = 0
        while url:
            resp = request(client, "GET", url)
            records = _extract_items(resp.json(), handle.config.get("items_path"))
            df = pd.DataFrame(records)
            if df.empty:
                return
            if config.limit is not None:
                df = df.head(config.limit - yielded)
            yielded += len(df)
            yield df.reset_index(drop=True)
            url = _next_link(resp.headers.get("Link") or resp.headers.get("link"))
            if config.limit is not None and yielded >= config.limit:
                return

    def _fetch_page(
        self,
        client: httpx.Client,
        handle: ConnectionHandle,
        config: ReadConfig,
        params: dict[str, Any],
    ) -> pd.DataFrame:
        df, _payload = self._fetch_page_with_payload(client, handle, config, params)
        return df

    def _fetch_page_with_payload(
        self,
        client: httpx.Client,
        handle: ConnectionHandle,
        config: ReadConfig,
        params: dict[str, Any],
    ) -> tuple[pd.DataFrame, Any]:
        resp = request(client, "GET", self._url(handle, config.object), params=params or None)
        payload = resp.json()
        records = _extract_items(payload, handle.config.get("items_path"))
        return pd.DataFrame(records).reset_index(drop=True), payload

    def _client(self, handle: ConnectionHandle) -> Any:
        if handle.raw_conn is not None:
            return handle.raw_conn
        from .auth import auth_headers, auth_params, oauth_auth

        cfg = dict(handle.config)
        return httpx.Client(
            base_url=str(cfg.get("base_url") or ""),
            headers=auth_headers(cfg),
            params=auth_params(cfg),
            auth=oauth_auth(cfg),
            timeout=20.0,
        )

    def _url(self, handle: ConnectionHandle, path: str) -> str:
        base = str(handle.config.get("base_url") or "").rstrip("/") + "/"
        if not handle.config.get("base_url"):
            raise AuthenticationError("Missing base_url")
        return urljoin(base, str(path or "").lstrip("/"))


def _extract_items(payload: Any, items_path: object) -> list[dict]:
    if items_path:
        value: Any = payload
        for part in str(items_path).split("."):
            if not isinstance(value, dict):
                raise DataReadError(f"items_path '{items_path}' did not resolve to a list")
            value = value.get(part)
        payload = value
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item if isinstance(item, dict) else {"value": item} for item in payload]
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "records"):
            if isinstance(payload.get(key), list):
                return list(payload[key])
        return [payload]
    raise DataReadError("REST response is not a JSON object or array")


def _dig(payload: Any, path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _next_link(header: str | None) -> str | None:
    # RFC 5988: <url>; rel="next"
    if not header:
        return None
    for part in header.split(","):
        section = part.strip()
        if 'rel="next"' in section or "rel=next" in section:
            start = section.find("<")
            end = section.find(">")
            if start != -1 and end != -1:
                return section[start + 1 : end]
    return None
