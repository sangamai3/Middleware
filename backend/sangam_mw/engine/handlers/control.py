"""
Control / utility step handlers: Router, SetVariable, Logger.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..context import ExecutionContext
from .base import StepHandler

logger = logging.getLogger(__name__)


class RouterHandler(StepHandler):
    """
    Routes the upstream DataFrame to one of several branches based on
    a pandas .query() expression.

    config:
      source_step: str
      routes:
        - expression: "amount > 1000"
          target_step: high_value
        - expression: "amount <= 1000"
          target_step: standard
      default_target: fallback_step   # optional

    Returns the upstream DataFrame unchanged (routing is handled by the executor).
    """

    @property
    def step_type(self) -> str:
        return "router"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame:
        source_step: str = config["source_step"]
        return context.get_output(source_step)


class SetVariableHandler(StepHandler):
    """
    Set one or more flow variables from literals or upstream column values.

    config:
      variables:
        - name: total_rows
          source_step: read_step
          expression: "len(df)"   # evaluated against upstream df
        - name: env
          value: "production"
    """

    @property
    def step_type(self) -> str:
        return "set_variable"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> None:
        for var_spec in config.get("variables", []):
            name: str = var_spec["name"]
            if "value" in var_spec:
                context.set_variable(name, var_spec["value"])
            elif "source_step" in var_spec and "expression" in var_spec:
                df = context.get_output(var_spec["source_step"])
                value = eval(var_spec["expression"], {"df": df})  # noqa: S307 — controlled expression
                context.set_variable(name, value)
        return None


class LoggerHandler(StepHandler):
    """
    Log a message with optional context values.

    config:
      message: "Processed {rows} rows"
      level: "info"   # debug, info, warning, error
      source_step: read_step   # optional — passes through df unchanged
    """

    @property
    def step_type(self) -> str:
        return "logger"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame | None:
        message: str = config.get("message", "")
        level: str = config.get("level", "info").lower()

        template_vars: dict[str, Any] = dict(context.variables)
        template_vars.update(context.row_counts())

        try:
            rendered = message.format(**template_vars)
        except KeyError:
            rendered = message

        log = getattr(logger, level, logger.info)
        log("[flow=%s run=%s] %s", context.flow_id, context.run_id, rendered)

        source_step: str | None = config.get("source_step")
        if source_step:
            return context.get_output(source_step)
        return None
