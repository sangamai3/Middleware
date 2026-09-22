"""
EngineRouter — auto-selects the right SQL engine based on row count.

< 500K rows  → DuckDB (in-process, fast)
≥ 500K rows  → SparkEngine (distributed; falls back to DuckDB if Spark not configured)
"""

from __future__ import annotations

import pandas as pd

_SPARK_THRESHOLD = 500_000


class EngineRouter:
    """
    Route SQL transforms to the appropriate engine.

    Usage:
        router = EngineRouter()
        result = router.execute(sql, frames={"step1": df})
    """

    def __init__(self, spark_threshold: int = _SPARK_THRESHOLD) -> None:
        self._threshold = spark_threshold

    def execute(self, sql: str, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        total_rows = sum(len(df) for df in frames.values())
        if total_rows >= self._threshold:
            from .spark_engine import SparkEngine
            return SparkEngine().execute(sql, frames)

        from .duckdb_engine import DuckDBEngine
        return DuckDBEngine().execute(sql, frames)

    def validate_sql(self, sql: str, frames: dict[str, pd.DataFrame]) -> None:
        from .duckdb_engine import validate_sql
        validate_sql(sql, frames)
