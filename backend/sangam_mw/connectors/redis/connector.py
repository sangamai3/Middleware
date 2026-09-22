"""Redis connector — key-value read/write with pattern scan and hash support."""
from __future__ import annotations

import json
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
    import redis as redis_lib  # type: ignore[import]
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False


def _require_redis() -> None:
    if not _HAS_REDIS:
        raise ImportError("redis is required: pip install redis")


class RedisConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="redis",
            label="Redis",
            family="nosql",
            version="1.0.0",
            auth_type=AuthType.BASIC,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read/write Redis keys, hashes, lists and sorted sets.",
            connection_schema={
                "type": "object",
                "required": ["host"],
                "properties": {
                    "host": {"type": "string", "default": "localhost"},
                    "port": {"type": "integer", "default": 6379},
                    "password": {"type": "string", "secret": True},
                    "db": {"type": "integer", "default": 0},
                    "ssl": {"type": "boolean", "default": False},
                    "url": {
                        "type": "string",
                        "description": "Redis URL (overrides host/port/db)",
                    },
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Key pattern (e.g. 'user:*') or hash key",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["scan", "hash", "list", "zset", "get"],
                        "default": "scan",
                    },
                    "limit": {"type": "integer", "default": 1000},
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Key prefix or hash key",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["set", "hset", "lpush", "zadd"],
                        "default": "set",
                    },
                    "key_field": {
                        "type": "string",
                        "description": "Column to use as Redis key suffix",
                    },
                    "ttl_seconds": {"type": "integer", "description": "Optional TTL"},
                    "value_format": {
                        "type": "string",
                        "enum": ["json", "string"],
                        "default": "json",
                    },
                },
            },
        )

    def _client(self, handle: ConnectionHandle) -> "redis_lib.Redis":
        _require_redis()
        if isinstance(handle.raw_conn, redis_lib.Redis):
            return handle.raw_conn
        cfg = handle.config
        url = cfg.get("url")
        if url:
            client = redis_lib.from_url(str(url))
        else:
            client = redis_lib.Redis(
                host=str(cfg.get("host", "localhost")),
                port=int(cfg.get("port", 6379)),
                password=cfg.get("password") or None,
                db=int(cfg.get("db", 0)),
                ssl=bool(cfg.get("ssl", False)),
                decode_responses=True,
            )
        handle.raw_conn = client
        return client

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_redis()
        try:
            self._client(handle).ping()
            return True
        except Exception as exc:
            raise NetworkError(f"Redis connection failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        _require_redis()
        client = self._client(handle)
        prefixes: set[str] = set()
        for key in client.scan_iter("*", count=100):
            parts = str(key).split(":", 1)
            prefixes.add(parts[0] + ":*" if len(parts) > 1 else str(key))
            if len(prefixes) >= 50:
                break
        return [ObjectSchema(name=p, kind="key_pattern") for p in sorted(prefixes)]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        return [
            ColumnSchema(name="_key", data_type="string", nullable=False),
            ColumnSchema(name="_value", data_type="string", nullable=True),
            ColumnSchema(name="_type", data_type="string", nullable=True),
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        _require_redis()
        client = self._client(handle)
        mode = config.extra.get("mode", "scan")
        limit = config.limit or 1000
        pattern = config.object or "*"

        try:
            if mode == "hash":
                data = client.hgetall(pattern)
                rows = [{"_key": k, "_value": v} for k, v in data.items()]
            elif mode == "list":
                items = client.lrange(pattern, 0, limit - 1)
                rows = [{"_key": pattern, "_value": item, "_index": i} for i, item in enumerate(items)]
            elif mode == "zset":
                items = client.zrange(pattern, 0, limit - 1, withscores=True)
                rows = [{"_key": pattern, "_value": m, "_score": s} for m, s in items]
            elif mode == "get":
                val = client.get(pattern)
                rows = [{"_key": pattern, "_value": val}] if val is not None else []
            else:
                rows = []
                for key in client.scan_iter(pattern, count=200):
                    if len(rows) >= limit:
                        break
                    val = client.get(str(key))
                    k_type = client.type(str(key))
                    parsed: Any
                    if val:
                        try:
                            parsed = json.loads(str(val))
                        except Exception:
                            parsed = val
                    else:
                        parsed = None
                    rows.append({"_key": key, "_value": parsed, "_type": k_type})
        except Exception as exc:
            raise DataReadError(f"Redis read failed: {exc}") from exc

        if not rows:
            return pd.DataFrame(columns=["_key", "_value"])
        return pd.DataFrame(rows)

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        _require_redis()
        client = self._client(handle)
        mode = config.extra.get("mode", "set")
        key_prefix = config.object
        key_field = config.extra.get("key_field")
        ttl = config.extra.get("ttl_seconds")
        value_format = config.extra.get("value_format", "json")
        written = 0
        errors: list[dict[str, Any]] = []

        try:
            pipe = client.pipeline(transaction=False)
            for row in df.to_dict(orient="records"):
                if key_field and key_field in row:
                    key = f"{key_prefix}:{row[key_field]}" if key_prefix else str(row[key_field])
                elif "_key" in row:
                    key = str(row["_key"])
                else:
                    errors.append({"error": "no key field"})
                    continue

                if value_format == "json":
                    value = json.dumps(row)
                else:
                    value = str(row.get("_value", ""))

                if mode == "set":
                    pipe.set(key, value, ex=ttl)
                elif mode == "hset":
                    pipe.hset(key_prefix or key, key.split(":")[-1], value)
                elif mode == "lpush":
                    pipe.lpush(key_prefix or key, value)
                elif mode == "zadd":
                    score = float(row.get("_score", 0))
                    pipe.zadd(key_prefix or key, {value: score})
                written += 1

            pipe.execute()
        except Exception as exc:
            raise NetworkError(f"Redis write failed: {exc}") from exc

        return WriteResult(rows_written=written, rows_failed=len(errors), errors=errors)
