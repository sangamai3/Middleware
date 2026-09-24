"""
Flow entry trigger handlers — Scheduler, Webhook, Event, Streaming.

These steps mark how a flow is started; on manual/API runs they no-op successfully
so downstream steps can execute. Schedule/webhook wiring is handled outside the executor.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..context import ExecutionContext
from .base import StepHandler

logger = logging.getLogger(__name__)

_TRIGGER_TYPES = (
    "scheduler",
    "webhook_trigger",
    "event_trigger",
    "streaming_trigger",
)


class FlowTriggerHandler(StepHandler):
    """No-op trigger step — succeeds without producing a DataFrame."""

    def __init__(self, step_type: str) -> None:
        if step_type not in _TRIGGER_TYPES:
            raise ValueError(f"Not a trigger step type: {step_type!r}")
        self._step_type = step_type

    @property
    def step_type(self) -> str:
        return self._step_type

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame | None:
        if self._step_type == "scheduler":
            cron = config.get("cron") or config.get("cron_expr")
            interval = config.get("interval_seconds")
            summary = config.get("schedule_summary")
            logger.info(
                "[flow=%s run=%s] Scheduler trigger (cron=%s interval=%s summary=%s)",
                context.flow_id,
                context.run_id,
                cron,
                interval,
                summary,
            )
        else:
            logger.info(
                "[flow=%s run=%s] Trigger step %s",
                context.flow_id,
                context.run_id,
                self._step_type,
            )
        return None


def trigger_handlers() -> dict[str, StepHandler]:
    return {t: FlowTriggerHandler(t) for t in _TRIGGER_TYPES}
