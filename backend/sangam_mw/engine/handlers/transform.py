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
    """Declarative field mapping with optional per-field transforms.

    Supports two config formats:

    Legacy (YAML fields list):
        config.fields = [{source, target, fn, ...}]

    UI format (mappings list):
        config.mappings     = [{source, target, fn, args: {}}]
        config.drop_unmapped = true  # only keep mapped columns (default true)
    """

    @property
    def step_type(self) -> str:
        return "transform_map"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame:
        depends_on: list[str] = config.get("_depends_on", [])
        source_step: str = config.get("source_step") or (depends_on[0] if depends_on else "")
        if not source_step:
            raise ValueError("transform_map has no upstream step — connect it to a source node")

        df = context.get_output(source_step)

        # UI format: config.mappings takes priority over legacy config.fields
        if "mappings" in config and config["mappings"]:
            return self._apply_mappings(df, config)

        # Legacy YAML fields format
        if "fields" in config and config["fields"]:
            mapper = FieldMapper.from_yaml(config["fields"])
            return mapper.apply(df)

        # No mapping rules defined — pass through unchanged
        return df

    @staticmethod
    def _apply_mappings(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
        """Convert UI mappings format to FieldSpec list and apply."""
        drop_unmapped: bool = config.get("drop_unmapped", True)
        mappings: list[dict] = config.get("mappings", [])

        # Build FieldSpec-compatible dicts from UI mappings
        specs: list[dict] = []
        for m in mappings:
            src = m.get("source") or ""
            tgt = m.get("target") or src
            if not src and not tgt:
                continue
            fn = m.get("fn") or m.get("transform") or None
            args: dict = m.get("args") or {}
            spec: dict = {"source": src, "target": tgt}
            if fn:
                spec["fn"] = fn
            spec.update(args)
            specs.append(spec)

        if not specs:
            return df

        mapper = FieldMapper.from_yaml(specs)

        if drop_unmapped:
            return mapper.apply(df)

        # Keep unmapped columns alongside the mapped ones
        mapped_targets = {s.get("target", s.get("source", "")) for s in specs}
        result = mapper.apply(df)
        for col in df.columns:
            if col not in mapped_targets and col not in result.columns:
                result[col] = df[col]
        return result


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
