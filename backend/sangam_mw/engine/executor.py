"""
FlowExecutor — orchestrates step execution for a FlowDefinition.

Responsibilities:
  - Calls DAGParser for execution order
  - Routes each step to its handler
  - Emits structured FlowEvents to the EventBus
  - Handles per-step retry logic (calls call_with_retry)
  - Populates ExecutionRun + StepExecution models
  - Respects step.on_row_error and step.optional
  - Phase 14: auto-instruments every run with correlation_id, DB persistence,
    log indexing, and metrics bucket upserts
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from ..connectors.base.errors import SangamMWException
from ..connectors.base.retry import call_with_retry
from ..models.execution import ExecutionRun, RunStatus, StepExecution, StepStatus
from ..models.flow import FlowDefinition, StepConfig
from .context import ExecutionContext
from .dag import DAGParser
from .events import EventBus, EventType, FlowEvent, event_bus as default_bus
from .handlers import (
    ConnectorReadHandler,
    ConnectorWriteHandler,
    LoggerHandler,
    RouterHandler,
    SetVariableHandler,
    TransformFilterHandler,
    TransformMapHandler,
    TransformScriptHandler,
    TransformSQLHandler,
)
from .handlers.base import StepHandler

logger = structlog.get_logger(__name__)

_HANDLER_MAP: dict[str, StepHandler] = {
    "connector_read": ConnectorReadHandler(),
    "connector_write": ConnectorWriteHandler(),
    "transform_map": TransformMapHandler(),
    "transform_filter": TransformFilterHandler(),
    "transform_sql": TransformSQLHandler(),
    "transform_script": TransformScriptHandler(),
    "router": RouterHandler(),
    "set_variable": SetVariableHandler(),
    "logger": LoggerHandler(),
}


class FlowExecutor:
    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or default_bus

    def execute(
        self,
        flow: FlowDefinition,
        trigger_type: str = "manual",
        triggered_by: str | None = None,
        variables: dict[str, Any] | None = None,
    ) -> ExecutionRun:
        run_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        started_at = time.time()

        context = ExecutionContext(
            run_id=run_id,
            flow_id=flow.flow_id,
            correlation_id=correlation_id,
            variables=variables or {},
        )

        step_executions: list[StepExecution] = []
        run_status = RunStatus.RUNNING
        error_message: str | None = None

        self._bus.emit(FlowEvent(
            type=EventType.RUN_STARTED,
            run_id=run_id,
            flow_id=flow.flow_id,
            payload={
                "trigger_type": trigger_type,
                "triggered_by": triggered_by,
                "correlation_id": correlation_id,
            },
        ))
        self._fire_log(run_id, flow.flow_id, f"Run started (trigger={trigger_type})", "INFO", correlation_id=correlation_id)

        try:
            parser = DAGParser(flow.steps)
            ordered_ids = parser.topological_order()

            step_map = {s.id: s for s in flow.steps}
            for step_id in ordered_ids:
                step = step_map[step_id]
                self._fire_log(run_id, flow.flow_id, f"Step started: {step_id}", "INFO", step_id=step_id, correlation_id=correlation_id)
                step_exec = self._run_step(step, context)
                step_executions.append(step_exec)
                if step_exec.status == StepStatus.FAILED:
                    self._fire_log(run_id, flow.flow_id, f"Step failed: {step_id} — {step_exec.error_message}", "ERROR", step_id=step_id, correlation_id=correlation_id)
                    if not step.optional:
                        run_status = RunStatus.FAILED
                        error_message = step_exec.error_message
                        break
                else:
                    self._fire_log(run_id, flow.flow_id, f"Step completed: {step_id} (rows_out={step_exec.rows_out})", "INFO", step_id=step_id, correlation_id=correlation_id)

            if run_status == RunStatus.RUNNING:
                run_status = RunStatus.SUCCESS

        except Exception as exc:
            run_status = RunStatus.FAILED
            error_message = str(exc)
            logger.error("flow_execution_failed", flow_id=flow.flow_id, run_id=run_id, error=str(exc))
            self._fire_log(run_id, flow.flow_id, f"Flow execution error: {exc}", "ERROR", correlation_id=correlation_id)

        ended_at = time.time()
        total_rows = sum(
            se.rows_out or 0 for se in step_executions if se.rows_out is not None
        )
        duration_ms = int((ended_at - started_at) * 1000)

        self._bus.emit(FlowEvent(
            type=EventType.RUN_COMPLETED if run_status == RunStatus.SUCCESS else EventType.RUN_FAILED,
            run_id=run_id,
            flow_id=flow.flow_id,
            payload={"status": run_status, "error": error_message, "correlation_id": correlation_id},
        ))
        self._bus.close_run(run_id)

        level = "INFO" if run_status == RunStatus.SUCCESS else "ERROR"
        self._fire_log(run_id, flow.flow_id, f"Run {run_status} in {duration_ms}ms, rows={total_rows}", level, correlation_id=correlation_id)

        def _ts(t: float) -> datetime:
            return datetime.fromtimestamp(t, tz=timezone.utc)

        run = ExecutionRun(
            run_id=run_id,
            flow_id=flow.flow_id,
            trigger_type=trigger_type,
            status=run_status,
            started_at=_ts(started_at),
            ended_at=_ts(ended_at),
            rows_processed=total_rows,
            rows_failed=0,
            rows_written=0,
            steps=step_executions,
            error_message=error_message,
            triggered_by=triggered_by or "",
        )

        # Persist to DB and update metrics bucket (fire-and-forget)
        self._fire_persist(run, flow_name=getattr(flow, "name", ""), correlation_id=correlation_id, duration_ms=duration_ms, total_rows=total_rows)

        return run

    def _fire_log(
        self,
        run_id: str,
        flow_id: str,
        message: str,
        level: str = "INFO",
        step_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Schedule a log append without blocking the sync executor."""
        try:
            from ..observability.persistence import append_log
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(append_log(run_id, flow_id, message, level, step_id, correlation_id))
        except Exception:
            pass

    def _fire_persist(
        self,
        run: ExecutionRun,
        flow_name: str,
        correlation_id: str | None,
        duration_ms: int,
        total_rows: int,
    ) -> None:
        try:
            from ..observability.persistence import persist_run, upsert_metrics_bucket
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(persist_run(run, flow_name=flow_name, correlation_id=correlation_id))
                asyncio.ensure_future(upsert_metrics_bucket(run.flow_id, duration_ms, run.status, total_rows))
        except Exception:
            pass

    def _run_step(self, step: StepConfig, context: ExecutionContext) -> StepExecution:
        started_at = time.time()
        retry_count = 0
        status = StepStatus.RUNNING
        error_type: str | None = None
        error_message: str | None = None
        rows_in: int | None = None
        rows_out: int | None = None

        self._bus.emit(FlowEvent(
            type=EventType.STEP_STARTED,
            run_id=context.run_id,
            flow_id=context.flow_id,
            step_id=step.id,
        ))

        handler = _HANDLER_MAP.get(step.type)
        if handler is None:
            error_message = f"Unknown step type: {step.type!r}"
            status = StepStatus.FAILED
            self._bus.emit(FlowEvent(
                type=EventType.STEP_FAILED,
                run_id=context.run_id,
                flow_id=context.flow_id,
                step_id=step.id,
                payload={"error": error_message},
            ))
            ended_at = time.time()
            return StepExecution(
                step_id=step.id,
                step_type=step.type,
                status=status,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=int((ended_at - started_at) * 1000),
                error_message=error_message,
                retry_count=retry_count,
            )

        try:
            def _do_execute() -> Any:
                merged_config = {**step.config, "_depends_on": step.depends_on, "_step_id": step.id}
                return handler.execute(merged_config, context)

            result = call_with_retry(
                _do_execute,
                max_attempts=max(1, step.retries + 1),
            )

            if result is not None:
                context.set_output(step.id, result)
                rows_out = len(result)

            status = StepStatus.SUCCESS
            self._bus.emit(FlowEvent(
                type=EventType.STEP_COMPLETED,
                run_id=context.run_id,
                flow_id=context.flow_id,
                step_id=step.id,
                payload={"rows_out": rows_out},
            ))

        except SangamMWException as exc:
            status = StepStatus.FAILED
            error_type = type(exc).__name__
            error_message = str(exc)
            self._bus.emit(FlowEvent(
                type=EventType.STEP_FAILED,
                run_id=context.run_id,
                flow_id=context.flow_id,
                step_id=step.id,
                payload={"error": error_message, "error_type": error_type},
            ))
        except Exception as exc:
            status = StepStatus.FAILED
            error_type = type(exc).__name__
            error_message = str(exc)
            self._bus.emit(FlowEvent(
                type=EventType.STEP_FAILED,
                run_id=context.run_id,
                flow_id=context.flow_id,
                step_id=step.id,
                payload={"error": error_message, "error_type": error_type},
            ))

        ended_at = time.time()
        return StepExecution(
            step_id=step.id,
            step_type=step.type,
            status=status,
            started_at=datetime.fromtimestamp(started_at, tz=timezone.utc),
            ended_at=datetime.fromtimestamp(ended_at, tz=timezone.utc),
            duration_ms=int((ended_at - started_at) * 1000),
            rows_in=rows_in or 0,
            rows_out=rows_out or 0,
            error_type=error_type,
            error_message=error_message,
            retry_count=retry_count,
        )
