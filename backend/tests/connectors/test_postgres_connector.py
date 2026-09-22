"""Postgres connector tests using an in-memory SQLite engine."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import create_engine, text

from sangam_mw.connectors.base.metadata import AuthType
from sangam_mw.connectors.base.schemas import ConnectionHandle, ReadConfig, WriteConfig
from sangam_mw.connectors.postgres.connector import PostgresConnector


def _engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, amount REAL)")
        )
        conn.execute(text("INSERT INTO customers (id, name, amount) VALUES (1, 'Ada', 10.5)"))
    return engine


def _handle(engine) -> ConnectionHandle:
    return ConnectionHandle(
        connector_id="postgres",
        connection_id="pg",
        config={"url": "sqlite:///:memory:", "username": "sangam", "password": "x"},
        created_at=datetime.now(UTC),
        raw_conn=engine,
    )


def test_postgres_metadata() -> None:
    assert PostgresConnector().metadata.auth_type == AuthType.BASIC
    assert PostgresConnector().metadata.connector_id == "postgres"


def test_postgres_introspect_and_read() -> None:
    engine = _engine()
    handle = _handle(engine)
    connector = PostgresConnector()
    assert connector.test_connection(handle) is True
    objects = connector.introspect_objects(handle)
    assert any(o.name == "customers" and o.kind == "table" for o in objects)
    cols = connector.introspect_columns(handle, "customers")
    names = [c.name for c in cols]
    assert "id" in names
    df = connector.read(handle, ReadConfig(object="customers", filter="amount > 1"))
    assert len(df) == 1
    assert df.loc[0, "name"] == "Ada"


def test_postgres_sql_mode() -> None:
    handle = _handle(_engine())
    df = PostgresConnector().read(
        handle, ReadConfig(object="customers", mode="sql", query="SELECT name FROM customers")
    )
    assert list(df.columns) == ["name"]


def test_postgres_append_upsert_replace() -> None:
    engine = _engine()
    handle = _handle(engine)
    connector = PostgresConnector()
    connector.write(
        pd.DataFrame({"id": [2], "name": ["Bob"], "amount": [3.0]}),
        handle,
        WriteConfig(object="customers", mode="append"),
    )
    connector.write(
        pd.DataFrame({"id": [2], "name": ["Robert"], "amount": [4.0]}),
        handle,
        WriteConfig(object="customers", mode="upsert", upsert_key="id"),
    )
    df = connector.read(handle, ReadConfig(object="customers"))
    assert set(df["name"]) == {"Ada", "Robert"}
    connector.write(
        pd.DataFrame({"id": [9], "name": ["Only"], "amount": [1.0]}),
        handle,
        WriteConfig(object="customers", mode="replace"),
    )
    df = connector.read(handle, ReadConfig(object="customers"))
    assert list(df["name"]) == ["Only"]
