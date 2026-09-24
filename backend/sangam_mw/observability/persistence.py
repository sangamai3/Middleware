"""
Observability persistence helpers.

Called from FlowExecutor after a run completes:
  - persist_run()      — write ExecutionRun + StepExecution rows to DB
  - append_log()       — append one line to ExecutionLogTable + forward externally
  - upsert_metrics_bucket() — update MetricsBucketTable for the flow's minute bucket
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC, timedelta
from typing import Any

import structlog

from ..db.base import get_session_factory
from ..db.tables import (
    ExecutionLogTable,
    ExecutionRunTable,
    MetricsBucketTable,
    StepExecutionTable,
)
from ..models.execution import ExecutionRun, StepExecution, RunStatus
from .forwarder import get_forwarder

logger = structlog.get_logger(__name__)


async def persist_run(
    run: ExecutionRun,
    flow_name: str = "",
    correlation_id: str | None = None,
) -> None:
    """Write completed ExecutionRun + all StepExecution rows to Postgres."""
    try:
        duration_ms = None
        if run.started_at and run.ended_at:
            duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)

        async with get_session_factory()() as session:
            row = ExecutionRunTable(
                run_id=run.run_id,
                flow_id=run.flow_id,
                flow_name=flow_name,
                correlation_id=correlation_id,
                trigger_type=run.trigger_type,
                status=str(run.status.value if hasattr(run.status, "value") else run.status),
                started_at=run.started_at,
                ended_at=run.ended_at,
                duration_ms=duration_ms,
                rows_processed=run.rows_processed,
                rows_failed=run.rows_failed,
                rows_written=run.rows_written,
                error_message=run.error_message,
                triggered_by=run.triggered_by,
            )
            session.add(row)

            for step in run.steps:
                step_duration = None
                if step.started_at and step.ended_at:
                    s_at = step.started_at if isinstance(step.started_at, datetime) else datetime.fromtimestamp(step.started_at, tz=UTC)
                    e_at = step.ended_at if isinstance(step.ended_at, datetime) else datetime.fromtimestamp(step.ended_at, tz=UTC)
                    step_duration = int((e_at - s_at).total_seconds() * 1000)

                s_row = StepExecutionTable(
                    run_id=run.run_id,
                    step_id=step.step_id,
                    step_type=step.step_type,
                    step_label=step.step_label or "",
                    connector_id=step.connector_id,
                    status=str(step.status.value if hasattr(step.status, "value") else step.status),
                    started_at=step.started_at if isinstance(step.started_at, datetime) else (
                        datetime.fromtimestamp(step.started_at, tz=UTC) if step.started_at else None
                    ),
                    ended_at=step.ended_at if isinstance(step.ended_at, datetime) else (
                        datetime.fromtimestamp(step.ended_at, tz=UTC) if step.ended_at else None
                    ),
                    duration_ms=step.duration_ms or step_duration,
                    rows_in=step.rows_in or 0,
                    rows_out=step.rows_out or 0,
                    rows_failed=0,
                    error_type=step.error_type,
                    error_message=step.error_message,
                    retry_count=step.retry_count,
                )
                session.add(s_row)

            await session.commit()
    except Exception as exc:
        logger.warning("persist_run_failed", run_id=run.run_id, error=str(exc))


async def append_log(
    run_id: str,
    flow_id: str,
    message: str,
    level: str = "INFO",
    step_id: str | None = None,
    correlation_id: str | None = None,
    payload: Any = None,
) -> None:
    """Append one log line to ExecutionLogTable and enqueue for external forwarding."""
    payload_preview: str | None = None
    if payload is not None:
        try:
            import json
            raw = json.dumps(payload) if not isinstance(payload, str) else payload
            payload_preview = raw[:512]
        except Exception:
            pass

    try:
        async with get_session_factory()() as session:
            row = ExecutionLogTable(
                run_id=run_id,
                flow_id=flow_id,
                step_id=step_id,
                correlation_id=correlation_id,
                level=level.upper(),
                message=message,
                payload_preview=payload_preview,
                timestamp=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        logger.warning("append_log_failed", run_id=run_id, error=str(exc))

    # Fire-and-forget to external forwarder
    event_dict = {
        "run_id": run_id,
        "flow_id": flow_id,
        "step_id": step_id,
        "correlation_id": correlation_id,
        "level": level,
        "message": message,
        "payload_preview": payload_preview,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    asyncio.create_task(_forward(event_dict))


async def _forward(event: dict[str, Any]) -> None:
    try:
        await get_forwarder().enqueue(event)
    except Exception as exc:
        logger.warning("forwarder_enqueue_failed", error=str(exc))


async def _emit_business_event(
    flow_id: str,
    run_id: str,
    event_name: str,
    payload: dict[str, Any],
    step_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """Insert a custom domain event into BusinessEventTable."""
    try:
        from ..db.tables import BusinessEventTable

        async with get_session_factory()() as session:
            row = BusinessEventTable(
                flow_id=flow_id,
                run_id=run_id,
                step_id=step_id,
                correlation_id=correlation_id,
                event_name=event_name,
                payload=payload,
                occurred_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        logger.warning("emit_business_event_failed", flow_id=flow_id, event_name=event_name, error=str(exc))


async def upsert_metrics_bucket(
    flow_id: str,
    duration_ms: int,
    status: Any,
    rows: int,
) -> None:
    """
    Upsert the per-minute MetricsBucket for this flow.
    Uses a simple increment approach: fetch, update, commit.
    """
    try:
        from sqlalchemy import select

        now = datetime.now(UTC)
        bucket_ts = now.replace(second=0, microsecond=0)
        is_error = str(status).lower() in ("failed", "error", "timed_out")

        async with get_session_factory()() as session:
            stmt = select(MetricsBucketTable).where(
                MetricsBucketTable.flow_id == flow_id,
                MetricsBucketTable.bucket_ts == bucket_ts,
            )
            result = await session.execute(stmt)
            bucket = result.scalar_one_or_none()

            if bucket is None:
                bucket = MetricsBucketTable(
                    flow_id=flow_id,
                    bucket_ts=bucket_ts,
                    granularity="minute",
                    run_count=1,
                    error_count=1 if is_error else 0,
                    total_rows=rows,
                    total_duration_ms=duration_ms,
                    p50_ms=duration_ms,
                    p95_ms=duration_ms,
                    p99_ms=duration_ms,
                )
                session.add(bucket)
            else:
                bucket.run_count += 1
                if is_error:
                    bucket.error_count += 1
                bucket.total_rows += rows
                bucket.total_duration_ms += duration_ms
                # Simple running approximation for percentiles
                avg = bucket.total_duration_ms // bucket.run_count
                bucket.p50_ms = avg
                bucket.p95_ms = max(bucket.p95_ms or 0, duration_ms)
                bucket.p99_ms = max(bucket.p99_ms or 0, duration_ms)

            await session.commit()
    except Exception as exc:
        logger.warning("upsert_metrics_bucket_failed", flow_id=flow_id, error=str(exc))
