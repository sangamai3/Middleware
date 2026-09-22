"""
DuckDBEngine — in-process SQL transforms via DuckDB.

Registers each upstream DataFrame as a virtual table named by step_id,
executes the user SQL, and returns the result as a DataFrame.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import duckdb
import pandas as pd

from ..connectors.base.errors import TransformSyntaxError, TransformMemoryError

if TYPE_CHECKING:
    pass

# DuckDB connections are not thread-safe for concurrent writes; use one per thread.
_local = threading.local()


def _conn() -> duckdb.DuckDBPyConnection:
    if not hasattr(_local, "conn"):
        _local.conn = duckdb.connect(database=":memory:")
    return _local.conn


class DuckDBEngine:
    """
    Execute arbitrary SQL against a dict of named DataFrames.

    Tables are registered as read-only DuckDB views for the duration of the
    query, then deregistered so memory is not held between steps.

    Usage:
        engine = DuckDBEngine()
        result = engine.execute(
            "SELECT id, amount * 1.1 AS adjusted FROM source_step",
            frames={"source_step": df}
        )
    """

    def execute(self, sql: str, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        conn = _conn()
        registered: list[str] = []
        try:
            for name, df in frames.items():
                conn.register(name, df)
                registered.append(name)
            try:
                result: pd.DataFrame = conn.execute(sql).df()
            except duckdb.OutOfMemoryException as exc:
                raise TransformMemoryError(
                    f"DuckDB ran out of memory executing SQL: {exc}"
                ) from exc
            except duckdb.Error as exc:
                raise TransformSyntaxError(
                    f"DuckDB SQL error: {exc}"
                ) from exc
        finally:
            for name in registered:
                try:
                    conn.unregister(name)
                except Exception:
                    pass
        return result


def validate_sql(sql: str, frames: dict[str, pd.DataFrame]) -> None:
    """
    Deploy-time validation: run EXPLAIN on the query to catch syntax errors
    without actually executing it.  Raises TransformSyntaxError on failure.
    """
    conn = _conn()
    registered: list[str] = []
    try:
        for name, df in frames.items():
            empty = df.head(0)
            conn.register(name, empty)
            registered.append(name)
        try:
            conn.execute(f"EXPLAIN {sql}")
        except duckdb.Error as exc:
            raise TransformSyntaxError(
                f"SQL validation failed: {exc}"
            ) from exc
    finally:
        for name in registered:
            try:
                conn.unregister(name)
            except Exception:
                pass
