"""
HTTP Sidecar connector — polyglot connector protocol.

Any language (Java, Go, Node.js, Rust, etc.) can implement a connector by
exposing 6 HTTP endpoints. The framework calls them identically to native
Python connectors. Register in connector config:

  connector_id: my-java-connector
  runtime:
    type: http_sidecar
    url: http://localhost:9001
    command: ["java", "-jar", "connectors/my.jar"]  # optional auto-start
"""
from __future__ import annotations

import json
import subprocess
import time
from typing import Any

import pandas as pd

from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.errors import ConnectorValidationError, DataReadError, NetworkError
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)

try:
    import httpx  # type: ignore[import]
    _HAS_HTTPX = True
except ImportError:
    try:
        import requests as _requests  # type: ignore[import]
        _HAS_HTTPX = False
        _HAS_REQUESTS = True
    except ImportError:
        _HAS_HTTPX = False
        _HAS_REQUESTS = False


def _post(url: str, payload: dict, timeout: float = 30.0) -> dict:
    if _HAS_HTTPX:
        resp = httpx.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    elif _HAS_REQUESTS:
        resp = _requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    else:
        import urllib.request
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())


class HttpSidecarConnector(BaseConnector, SourceMixin, SinkMixin):
    """
    Polyglot HTTP sidecar connector. Wraps any sidecar that implements
    the 6-endpoint protocol at a given base_url.
    """

    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="http_sidecar",
            label="HTTP Sidecar (Polyglot)",
            family="polyglot",
            version="1.0.0",
            auth_type=AuthType.NONE,
            operations=[OperationType.READ, OperationType.WRITE],
            description=(
                "Wrap any Java/Go/Node.js connector that exposes the 6-endpoint "
                "SangamMW sidecar protocol."
            ),
            connection_schema={
                "type": "object",
                "required": ["base_url"],
                "properties": {
                    "base_url": {
                        "type": "string",
                        "description": "Sidecar base URL e.g. http://localhost:9001",
                    },
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command to auto-start sidecar if not running",
                    },
                    "startup_wait_seconds": {
                        "type": "number",
                        "default": 3.0,
                        "description": "Seconds to wait after launching command",
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "default": 30.0,
                        "description": "HTTP call timeout",
                    },
                    "connection_config": {
                        "type": "object",
                        "description": "Sidecar-specific connection settings (passed as-is)",
                    },
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "object": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "filter": {"type": "string"},
                    "limit": {"type": "integer"},
                    "query": {"type": "string"},
                    "extra": {"type": "object"},
                },
            },
            write_schema={
                "type": "object",
                "properties": {
                    "object": {"type": "string"},
                    "mode": {"type": "string", "default": "append"},
                    "upsert_key": {"type": "string"},
                    "extra": {"type": "object"},
                },
            },
        )

    def _base_url(self, handle: ConnectionHandle) -> str:
        url = str(handle.config.get("base_url") or "")
        if not url:
            raise ConnectorValidationError("http_sidecar requires base_url")
        return url.rstrip("/")

    def _connection_payload(self, handle: ConnectionHandle) -> dict[str, Any]:
        return dict(handle.config.get("connection_config") or {})

    def _timeout(self, handle: ConnectionHandle) -> float:
        return float(handle.config.get("timeout_seconds") or 30.0)

    def _ensure_started(self, handle: ConnectionHandle) -> None:
        cmd = handle.config.get("command")
        if not cmd or handle.raw_conn is not None:
            return
        try:
            _post(f"{self._base_url(handle)}/test", {"connection": {}}, timeout=2.0)
            return
        except Exception:
            pass
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        handle.raw_conn = proc
        time.sleep(float(handle.config.get("startup_wait_seconds") or 3.0))

    def test_connection(self, handle: ConnectionHandle) -> bool:
        self._ensure_started(handle)
        try:
            resp = _post(
                f"{self._base_url(handle)}/test",
                {"connection": self._connection_payload(handle)},
                timeout=self._timeout(handle),
            )
            return bool(resp.get("ok", False))
        except Exception as exc:
            raise NetworkError(f"Sidecar test failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        self._ensure_started(handle)
        try:
            resp = _post(
                f"{self._base_url(handle)}/objects",
                {"connection": self._connection_payload(handle)},
                timeout=self._timeout(handle),
            )
            return [
                ObjectSchema(name=obj["name"], kind=obj.get("kind", "object"))
                for obj in (resp if isinstance(resp, list) else resp.get("objects", []))
            ]
        except Exception as exc:
            raise NetworkError(f"Sidecar objects failed: {exc}") from exc

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        self._ensure_started(handle)
        try:
            resp = _post(
                f"{self._base_url(handle)}/columns",
                {
                    "connection": self._connection_payload(handle),
                    "object": object_name,
                },
                timeout=self._timeout(handle),
            )
            cols = resp if isinstance(resp, list) else resp.get("columns", [])
            return [ColumnSchema(name=c["name"], data_type=c.get("type", "string")) for c in cols]
        except Exception as exc:
            raise NetworkError(f"Sidecar columns failed: {exc}") from exc

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        self._ensure_started(handle)
        payload: dict[str, Any] = {
            "connection": self._connection_payload(handle),
            "object": config.object,
        }
        if config.fields:
            payload["fields"] = config.fields
        if config.filter:
            payload["filter"] = config.filter
        if config.limit:
            payload["limit"] = config.limit
        if config.query:
            payload["query"] = config.query
        if config.extra:
            payload["extra"] = config.extra
        try:
            resp = _post(
                f"{self._base_url(handle)}/read",
                payload,
                timeout=self._timeout(handle),
            )
            rows = resp if isinstance(resp, list) else resp.get("rows", [])
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(rows).reset_index(drop=True)
        except Exception as exc:
            raise DataReadError(f"Sidecar read failed: {exc}") from exc

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        self._ensure_started(handle)
        if df.empty:
            return WriteResult(rows_written=0)
        payload: dict[str, Any] = {
            "connection": self._connection_payload(handle),
            "object": config.object,
            "mode": config.mode,
            "rows": df.to_dict(orient="records"),
        }
        if config.upsert_key:
            payload["upsert_key"] = config.upsert_key
        if config.extra:
            payload["extra"] = config.extra
        try:
            resp = _post(
                f"{self._base_url(handle)}/write",
                payload,
                timeout=self._timeout(handle),
            )
            return WriteResult(rows_written=int(resp.get("rows_written", len(df))))
        except Exception as exc:
            raise NetworkError(f"Sidecar write failed: {exc}") from exc
