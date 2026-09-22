"""
Transform step handlers — Map, Filter, SQL, Script.

Each handler reads the upstream DataFrame from context, applies
the transform, and returns the result DataFrame.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..context import ExecutionContext
from .base import StepHandler
from ...transforms import FieldMapper, DuckDBEngine, PythonSandbox


class TransformMapHandler(StepHandler):
    """YAML declarative field mapping."""

    @property
    def step_type(self) -> str:
        return "transform_map"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame:
        source_step: str = config["source_step"]
        df = context.get_output(source_step)
        mapper = FieldMapper.from_yaml(config["fields"])
        return mapper.apply(df)


class TransformFilterHandler(StepHandler):
    """pandas .query() filter applied to upstream output."""

    @property
    def step_type(self) -> str:
        return "transform_filter"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame:
        source_step: str = config["source_step"]
        df = context.get_output(source_step)
        expression: str = config["expression"]
        return df.query(expression).reset_index(drop=True)


class TransformSQLHandler(StepHandler):
    """DuckDB SQL transform over named upstream frames."""

    def __init__(self) -> None:
        self._engine = DuckDBEngine()

    @property
    def step_type(self) -> str:
        return "transform_sql"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame:
        sql: str = config["sql"]
        # source_steps maps table alias → step_id
        source_steps: dict[str, str] = config.get("source_steps", {})
        # If single source_step provided, default alias is the step_id
        if not source_steps and "source_step" in config:
            sid = config["source_step"]
            source_steps = {sid: sid}

        frames = {alias: context.get_output(step_id) for alias, step_id in source_steps.items()}
        return self._engine.execute(sql, frames)


class TransformScriptHandler(StepHandler):
    """Sandboxed Python script transform."""

    def __init__(self) -> None:
        self._sandbox = PythonSandbox()

    @property
    def step_type(self) -> str:
        return "transform_script"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame:
        source_step: str = config["source_step"]
        code: str = config["code"]
        df = context.get_output(source_step)
        return self._sandbox.execute(code, df)
