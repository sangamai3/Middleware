"""
SparkEngine — PySpark stub for large-scale (≥ 500K row) transforms.

Falls back to pandas with a warning when PySpark is not configured.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_SPARK_AVAILABLE = False
try:
    from pyspark.sql import SparkSession  # type: ignore[import-untyped]
    _SPARK_AVAILABLE = True
except ImportError:
    pass


class SparkEngine:
    """
    Execute SQL transforms via PySpark.

    When PySpark is not installed or SPARK_MASTER is not configured, the engine
    falls back to DuckDB and logs a warning.  This allows flows to run in
    development without a Spark cluster while flagging scale for production.
    """

    def __init__(self, master: str = "local[*]", app_name: str = "SangamMW") -> None:
        self._master = master
        self._app_name = app_name
        self._session: object | None = None

    def _get_session(self) -> object:
        if not _SPARK_AVAILABLE:
            raise RuntimeError("PySpark is not installed")
        if self._session is None:
            self._session = (
                SparkSession.builder  # type: ignore[union-attr]
                .master(self._master)
                .appName(self._app_name)
                .getOrCreate()
            )
        return self._session

    def execute(self, sql: str, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        if not _SPARK_AVAILABLE:
            logger.warning(
                "PySpark not available — falling back to DuckDB for SQL transform. "
                "Install pyspark and configure SPARK_MASTER to use distributed execution."
            )
            from .duckdb_engine import DuckDBEngine
            return DuckDBEngine().execute(sql, frames)

        spark = self._get_session()
        registered: list[str] = []
        try:
            for name, df in frames.items():
                sdf = spark.createDataFrame(df)  # type: ignore[union-attr]
                sdf.createOrReplaceTempView(name)
                registered.append(name)
            result_sdf = spark.sql(sql)  # type: ignore[union-attr]
            return result_sdf.toPandas()
        finally:
            for name in registered:
                try:
                    spark.catalog.dropTempView(name)  # type: ignore[union-attr]
                except Exception:
                    pass

    def stop(self) -> None:
        if self._session is not None and _SPARK_AVAILABLE:
            self._session.stop()  # type: ignore[union-attr]
            self._session = None
