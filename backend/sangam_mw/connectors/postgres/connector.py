"""PostgreSQL connector — BASIC auth + SSL, schema introspect, INSERT / UPSERT / REPLACE."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from ..base.auth import BasicAuthHandler
from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.errors import AuthenticationError, ConnectorValidationError, DataReadError
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)


class PostgresConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="postgres",
            label="PostgreSQL",
            family="sql",
            version="1.0.0",
            auth_type=AuthType.BASIC,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read/write PostgreSQL tables with SSL, INSERT / UPSERT / REPLACE.",
            connection_schema={
                "type": "object",
                "required": ["host", "database", "username"],
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer", "default": 5432},
                    "database": {"type": "string"},
                    "username": {"type": "string"},
                    "password": {"type": "string", "secret": True},
                    "sslmode": {
                        "type": "string",
                        "enum": [
                            "disable",
                            "allow",
                            "prefer",
                            "require",
                            "verify-ca",
                            "verify-full",
                        ],
                        "default": "prefer",
                    },
                    "schema": {"type": "string", "default": "public"},
                    "pool_size": {"type": "integer", "default": 5},
                    "max_overflow": {"type": "integer", "default": 10},
                    "pool_timeout": {"type": "integer", "default": 30},
                    "url": {
                        "type": "string",
                        "description": "Optional full SQLAlchemy URL (overrides host/user fields)",
                    },
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["object", "sql"], "default": "object"},
                    "object": {"type": "string", "description": "Table name"},
                    "query": {"type": "string", "description": "SQL when mode=sql"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "filter": {"type": "string", "description": "SQL WHERE clause"},
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

    def test_connection(self, handle: ConnectionHandle) -> bool:
        engine = self._engine(handle)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        engine = self._engine(handle)
        schema = self._schema(handle)
        insp = inspect(engine)
        objects: list[ObjectSchema] = []
        for name in insp.get_table_names(schema=schema):
            objects.append(ObjectSchema(name=name, kind="table"))
        for name in insp.get_view_names(schema=schema):
            objects.append(ObjectSchema(name=name, kind="view"))
        return objects

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        engine = self._engine(handle)
        schema = self._schema(handle)
        insp = inspect(engine)
        pk = set(
            insp.get_pk_constraint(object_name, schema=schema).get("constrained_columns") or []
        )
        return [
            ColumnSchema(
                name=str(col["name"]),
                data_type=str(col.get("type") or "unknown"),
                nullable=bool(col.get("nullable", True)),
                is_primary_key=str(col["name"]) in pk,
            )
            for col in insp.get_columns(object_name, schema=schema)
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        engine = self._engine(handle)
        sql = self._select_sql(handle, config)
        try:
            with engine.connect() as conn:
                df = pd.read_sql_query(text(sql), conn)
        except Exception as exc:
            raise DataReadError(str(exc)) from exc
        if config.fields:
            df = df[config.fields]
        if config.limit is not None:
            df = df.head(config.limit)
        return df.reset_index(drop=True)

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        if df.empty:
            return WriteResult(rows_written=0)
        engine = self._engine(handle)
        table = config.object
        schema = self._schema(handle)
        if config.mode == "replace":
            self._replace_table(engine, schema, table, df)
            return WriteResult(rows_written=len(df))
        if config.mode == "upsert":
            if not config.upsert_key:
                raise ConnectorValidationError("upsert_key is required for postgres upsert")
            updated = self._upsert(engine, schema, table, df, config.upsert_key)
            return WriteResult(rows_written=len(df), rows_updated=updated)
        df.to_sql(table, engine, schema=schema, if_exists="append", index=False)
        return WriteResult(rows_written=len(df))

    def _select_sql(self, handle: ConnectionHandle, config: ReadConfig) -> str:
        if config.mode == "sql":
            if not config.query:
                raise ConnectorValidationError("SQL query is required when mode=sql")
            return str(config.query)
        schema = self._schema(handle)
        qualified = _qualify(schema, config.object)
        cols = ", ".join(_quote(c) for c in config.fields) if config.fields else "*"
        sql = f"SELECT {cols} FROM {qualified}"
        if config.filter:
            sql += f" WHERE {config.filter}"
        if config.limit is not None:
            sql += f" LIMIT {int(config.limit)}"
        return sql

    def _replace_table(
        self, engine: Engine, schema: str | None, table: str, df: pd.DataFrame
    ) -> None:
        qualified = _qualify(schema, table)
        with engine.begin() as conn:
            if engine.dialect.name == "sqlite":
                conn.execute(text(f"DELETE FROM {_quote(table)}"))
            else:
                conn.execute(text(f"TRUNCATE TABLE {qualified}"))
        df.to_sql(table, engine, schema=schema, if_exists="append", index=False)

    def _upsert(
        self, engine: Engine, schema: str | None, table: str, df: pd.DataFrame, key: str
    ) -> int:
        if key not in df.columns:
            raise ConnectorValidationError(f"upsert_key '{key}' is not a column")
        cols = list(df.columns)
        col_sql = ", ".join(_quote(c) for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)
        assignments = ", ".join(f"{_quote(c)}=excluded.{_quote(c)}" for c in cols if c != key)
        qualified = _qualify(schema, table)
        dialect = engine.dialect.name
        if dialect == "sqlite":
            sql = (
                f"INSERT INTO {_quote(table)} ({col_sql}) VALUES ({placeholders}) "
                f"ON CONFLICT({_quote(key)}) DO UPDATE SET {assignments}"
            )
        else:
            sql = (
                f"INSERT INTO {qualified} ({col_sql}) VALUES ({placeholders}) "
                f"ON CONFLICT ({_quote(key)}) DO UPDATE SET {assignments}"
            )
        rows: list[dict[str, Any]] = [
            {str(k): v for k, v in row.items()} for row in df.to_dict(orient="records")
        ]
        with engine.begin() as conn:
            conn.execute(text(sql), rows)
        return len(rows)

    def _schema(self, handle: ConnectionHandle) -> str | None:
        if isinstance(handle.raw_conn, Engine) and handle.raw_conn.dialect.name == "sqlite":
            return None
        if str(handle.config.get("url") or "").startswith("sqlite"):
            return None
        return str(handle.config.get("schema") or "public")

    def _engine(self, handle: ConnectionHandle) -> Engine:
        if isinstance(handle.raw_conn, Engine):
            return handle.raw_conn
        url = handle.config.get("url")
        if url:
            return create_engine(str(url))
        BasicAuthHandler().apply(handle.config)
        host = handle.config.get("host")
        database = handle.config.get("database")
        username = handle.config.get("username")
        if not host or not database or not username:
            raise AuthenticationError("Missing host, database, or username")
        password = quote_plus(str(handle.config.get("password") or ""))
        user = quote_plus(str(username))
        port = int(handle.config.get("port") or 5432)
        sslmode = handle.config.get("sslmode") or "prefer"
        pool_size = int(handle.config.get("pool_size") or 5)
        max_overflow = int(handle.config.get("max_overflow") or 10)
        pool_timeout = int(handle.config.get("pool_timeout") or 30)
        return create_engine(
            f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}",
            connect_args={"sslmode": sslmode},
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
        )


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _qualify(schema: str | None, table: str) -> str:
    if schema:
        return f"{_quote(schema)}.{_quote(table)}"
    return _quote(table)
