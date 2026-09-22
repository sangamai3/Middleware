"""
FlowValidator — pre-flight checks before deploying a flow.

Validates:
  - DAG integrity (cycles, unknown deps)
  - SQL syntax (DuckDB EXPLAIN)
  - Python code syntax (py_compile)
  - YAML field specs (known fn names, target present)
  - Step type is registered
"""

from __future__ import annotations

from ..connectors.base.errors import FlowValidationError
from ..models.flow import FlowDefinition, StepConfig
from .dag import DAGParser
from ..transforms import validate_sql, validate_python, validate_yaml_fields


_KNOWN_STEP_TYPES = {
    "connector_read",
    "connector_write",
    "transform_map",
    "transform_filter",
    "transform_sql",
    "transform_script",
    "router",
    "set_variable",
    "logger",
    "sub_flow",
    "approval",
    "notification",
    "iterator",
    "merge",
    "lookup_table",
    "sync_endpoint",
    "global_exception",
    "component_exception",
}


class FlowValidator:
    def __init__(self, flow: FlowDefinition) -> None:
        self._flow = flow

    def validate(self) -> list[str]:
        """
        Run all pre-flight checks.

        Returns a list of warning strings (non-fatal).
        Raises FlowValidationError for any fatal issue.
        """
        warnings: list[str] = []

        # 1. DAG integrity
        parser = DAGParser(self._flow.steps)
        parser.validate()

        # 2. Per-step validation
        for step in self._flow.steps:
            warnings.extend(self._validate_step(step))

        return warnings

    def _validate_step(self, step: StepConfig) -> list[str]:
        warnings: list[str] = []

        if step.type not in _KNOWN_STEP_TYPES:
            warnings.append(f"Step '{step.id}' uses unknown type '{step.type}'")

        if step.type == "transform_sql":
            sql = step.config.get("sql")
            if not sql:
                raise FlowValidationError(
                    f"Step '{step.id}' (transform_sql) is missing 'sql' in config"
                )
            try:
                validate_sql(sql, {})
            except Exception as exc:
                raise FlowValidationError(
                    f"Step '{step.id}' SQL validation failed: {exc}"
                ) from exc

        elif step.type == "transform_script":
            code = step.config.get("code")
            if not code:
                raise FlowValidationError(
                    f"Step '{step.id}' (transform_script) is missing 'code' in config"
                )
            try:
                validate_python(code)
            except Exception as exc:
                raise FlowValidationError(
                    f"Step '{step.id}' Python validation failed: {exc}"
                ) from exc

        elif step.type == "transform_map":
            fields = step.config.get("fields")
            if not fields:
                raise FlowValidationError(
                    f"Step '{step.id}' (transform_map) is missing 'fields' in config"
                )
            try:
                validate_yaml_fields(fields)
            except Exception as exc:
                raise FlowValidationError(
                    f"Step '{step.id}' field spec validation failed: {exc}"
                ) from exc

        return warnings
