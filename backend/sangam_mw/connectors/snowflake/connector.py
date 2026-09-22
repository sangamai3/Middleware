"""Snowflake connector — account/user/password auth, SQL and object mode."""
from __future__ import annotations

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
    import snowflake.connector  # type: ignore[import]
    from snowflake.connector import DictCursor  # type: ignore[import]
    _HAS_SF = True
except ImportError:
    _HAS_SF = False


def _require_sf() -> None:
    if not _HAS_SF:
        raise ImportError(
            "snowflake-connector-python is required: pip install snowflake-connector-python"
        )


class SnowflakeConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="snowflake",
            label="Snowflake",
            family="analytics",
            version="1.0.0",
            auth_type=AuthType.BASIC,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read/write Snowflake tables with SQL and object mode.",
            connection_schema={
                "type": "object",
                "required": ["account", "user"],
                "properties": {
                    "account": {"type": "string", "description": "e.g. xy12345.us-east-1"},
                    "user": {"type": "string"},
                    "password": {"type": "string", "secret": True},
                    "private_key_pem": {
                        "type": "string",
                        "secret": True,
                        "description": "PEM key for key-pair auth (alternative to password)",
                    },
                    "database": {"type": "string"},
                    "schema": {"type": "string", "default": "PUBLIC"},
                    "warehouse": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "object": {"type": "string", "description": "Table or view name"},
                    "mode": {
                        "type": "string",
                        "enum": ["object", "sql"],
                        "default": "object",
                    },
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
                    "mode": {
                        "type": "string",
                        "enum": ["append", "upsert", "replace"],
                        "default": "append",
                    },
                    "upsert_key": {"type": "string"},
                },
            },
        )

    def _conn(self, handle: ConnectionHandle) -> "snowflake.connector.SnowflakeConnection":
        _require_sf()
        if handle.raw_conn is not None:
            return handle.raw_conn
        cfg = handle.config
        kwargs: dict = {
            "account": cfg["account"],
            "user": cfg["user"],
        }
        if cfg.get("private_key_pem"):
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key, Encoding, PrivateFormat, NoEncryption,
            )
            key = load_pem_private_key(cfg["private_key_pem"].encode(), password=None)
            kwargs["private_key"] = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        else:
            kwargs["password"] = cfg.get("password", "")
        for k in ("database", "schema", "warehouse", "role"):
            if cfg.get(k):
                kwargs[k] = cfg[k]
        conn = snowflake.connector.connect(**kwargs)
        handle.raw_conn = conn
        return conn

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_sf()
        try:
            with self._conn(handle).cursor() as cur:
                cur.execute("SELECT CURRENT_VERSION()")
            return True
        except Exception as exc:
            raise NetworkError(f"Snowflake connection failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        _require_sf()
        cfg = handle.config
        schema = cfg.get("schema", "PUBLIC")
        database = cfg.get("database", "")
        sql = "SHOW TABLES"
        if database:
            sql += f" IN DATABASE {database}"
        with self._conn(handle).cursor(DictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return [ObjectSchema(name=r["name"], kind="table") for r in (rows or [])]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        _require_sf()
        with self._conn(handle).cursor(DictCursor) as cur:
            cur.execute(f"DESCRIBE TABLE {object_name}")
            rows = cur.fetchall() or []
        return [
            ColumnSchema(
                name=r["name"],
                data_type=str(r.get("type", "string")).lower(),
                nullable=r.get("null?", "Y") == "Y",
            )
            for r in rows
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        _require_sf()
        if config.mode == "sql":
            sql = config.query
            if not sql:
                raise ConnectorValidationError("query is required when mode=sql")
        else:
            cols = ", ".join(f'"{c}"' for c in config.fields) if config.fields else "*"
            sql = f'SELECT {cols} FROM {config.object}'
            if config.filter:
                sql += f" WHERE {config.filter}"
            if config.limit:
                sql += f" LIMIT {int(config.limit)}"
        try:
            with self._conn(handle).cursor(DictCursor) as cur:
                cur.execute(str(sql))
                rows = cur.fetchall() or []
            return pd.DataFrame(rows).reset_index(drop=True)
        except Exception as exc:
            raise DataReadError(f"Snowflake read failed: {exc}") from exc

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        _require_sf()
        if df.empty:
            return WriteResult(rows_written=0)
        from snowflake.connector.pandas_tools import write_pandas  # type: ignore[import]
        try:
            conn = self._conn(handle)
            cfg = handle.config
            if config.mode == "replace":
                with conn.cursor() as cur:
                    cur.execute(f"TRUNCATE TABLE IF EXISTS {config.object}")
            success, _, nrows, _ = write_pandas(
                conn,
                df,
                config.object,
                database=cfg.get("database"),
                schema=cfg.get("schema", "PUBLIC"),
                auto_create_table=True,
                overwrite=(config.mode == "replace"),
            )
            return WriteResult(rows_written=int(nrows) if success else 0)
        except Exception as exc:
            raise NetworkError(f"Snowflake write failed: {exc}") from exc
