"""
Insights API — Phase 14 App Insights & Observability.

Routes:
  GET /insights/overview                 — summary tiles
  GET /insights/flows                    — per-flow health table
  GET /insights/flows/{flow_id}/runs     — paginated run history
  GET /insights/flows/{flow_id}/metrics  — time-series from MetricsBucketTable
  GET /insights/logs                     — full-text log search
  GET /insights/logs/{run_id}            — all logs for one run
  GET /insights/events                   — business event query
  GET /insights/runs/{run_id}            — full run detail
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text

from ...db.base import get_session
from ...db.tables import (
    BusinessEventTable,
    ExecutionLogTable,
    ExecutionRunTable,
    FlowTable,
    MetricsBucketTable,
    StepExecutionTable,
)
from ..auth import get_current_user

router = APIRouter(prefix="/insights", tags=["insights"])


def _dt(value: str | None, default: datetime) -> datetime:
    if value is None:
        return default
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# GET /insights/overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def get_overview(
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_flows = (await session.execute(select(func.count()).select_from(FlowTable))).scalar_one()

    runs_today = (
        await session.execute(
            select(func.count())
            .select_from(ExecutionRunTable)
            .where(ExecutionRunTable.started_at >= day_start)
        )
    ).scalar_one()

    errors_today = (
        await session.execute(
            select(func.count())
            .select_from(ExecutionRunTable)
            .where(
                ExecutionRunTable.started_at >= day_start,
                ExecutionRunTable.status.in_(["failed", "timed_out"]),
            )
        )
    ).scalar_one()

    avg_dur = (
        await session.execute(
            select(func.avg(ExecutionRunTable.duration_ms))
            .where(
                ExecutionRunTable.started_at >= day_start,
                ExecutionRunTable.duration_ms.isnot(None),
            )
        )
    ).scalar_one()

    error_rate = round((errors_today / runs_today * 100) if runs_today else 0, 1)

    return {
        "total_flows": total_flows,
        "runs_today": runs_today,
        "errors_today": errors_today,
        "error_rate": error_rate,
        "avg_duration_ms": int(avg_dur or 0),
    }


# ---------------------------------------------------------------------------
# GET /insights/flows
# ---------------------------------------------------------------------------

@router.get("/flows")
async def list_flow_insights(
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    since = _dt(from_dt, now - timedelta(days=1))
    until = _dt(to_dt, now)

    rows = (
        await session.execute(
            select(
                ExecutionRunTable.flow_id,
                ExecutionRunTable.flow_name,
                func.count().label("run_count"),
                func.sum(
                    (ExecutionRunTable.status.in_(["failed", "timed_out"])).cast(type_=None)
                ).label("error_count"),
                func.avg(ExecutionRunTable.duration_ms).label("avg_duration_ms"),
                func.max(ExecutionRunTable.started_at).label("last_run_at"),
            )
            .where(
                ExecutionRunTable.started_at >= since,
                ExecutionRunTable.started_at <= until,
            )
            .group_by(ExecutionRunTable.flow_id, ExecutionRunTable.flow_name)
            .order_by(func.max(ExecutionRunTable.started_at).desc())
        )
    ).all()

    # Get last status per flow separately (simpler than window func)
    last_status_rows = (
        await session.execute(
            select(ExecutionRunTable.flow_id, ExecutionRunTable.status, ExecutionRunTable.started_at)
            .where(ExecutionRunTable.started_at >= since)
            .order_by(ExecutionRunTable.started_at.desc())
        )
    ).all()
    last_status: dict[str, str] = {}
    for r in last_status_rows:
        if r.flow_id not in last_status:
            last_status[r.flow_id] = r.status

    result = []
    for r in rows:
        run_cnt = r.run_count or 0
        err_cnt = r.error_count or 0
        result.append({
            "flow_id": r.flow_id,
            "flow_name": r.flow_name or r.flow_id,
            "run_count": run_cnt,
            "error_count": err_cnt,
            "error_rate": round((err_cnt / run_cnt * 100) if run_cnt else 0, 1),
            "avg_duration_ms": int(r.avg_duration_ms or 0),
            "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            "last_status": last_status.get(r.flow_id, "unknown"),
        })
    return result


# ---------------------------------------------------------------------------
# GET /insights/flows/{flow_id}/runs
# ---------------------------------------------------------------------------

@router.get("/flows/{flow_id}/runs")
async def get_flow_runs(
    flow_id: str,
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
    status: str | None = Query(None),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
    triggered_by: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = _dt(from_dt, now - timedelta(days=7))
    until = _dt(to_dt, now)

    q = (
        select(ExecutionRunTable)
        .where(
            ExecutionRunTable.flow_id == flow_id,
            ExecutionRunTable.started_at >= since,
            ExecutionRunTable.started_at <= until,
        )
        .order_by(ExecutionRunTable.started_at.desc())
    )
    if status:
        q = q.where(ExecutionRunTable.status == status)
    if triggered_by:
        q = q.where(ExecutionRunTable.triggered_by == triggered_by)

    total_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(total_q)).scalar_one()

    runs = (await session.execute(q.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "runs": [
            {
                "run_id": r.run_id,
                "flow_id": r.flow_id,
                "flow_name": r.flow_name,
                "status": r.status,
                "trigger_type": r.trigger_type,
                "triggered_by": r.triggered_by,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "duration_ms": r.duration_ms,
                "rows_processed": r.rows_processed,
                "rows_failed": r.rows_failed,
                "correlation_id": r.correlation_id,
                "error_message": r.error_message,
            }
            for r in runs
        ],
    }


# ---------------------------------------------------------------------------
# GET /insights/flows/{flow_id}/metrics
# ---------------------------------------------------------------------------

@router.get("/flows/{flow_id}/metrics")
async def get_flow_metrics(
    flow_id: str,
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
    granularity: str = Query("minute"),
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    since = _dt(from_dt, now - timedelta(hours=24))
    until = _dt(to_dt, now)

    rows = (
        await session.execute(
            select(MetricsBucketTable)
            .where(
                MetricsBucketTable.flow_id == flow_id,
                MetricsBucketTable.bucket_ts >= since,
                MetricsBucketTable.bucket_ts <= until,
                MetricsBucketTable.granularity == granularity,
            )
            .order_by(MetricsBucketTable.bucket_ts.asc())
        )
    ).scalars().all()

    return [
        {
            "ts": r.bucket_ts.isoformat(),
            "run_count": r.run_count,
            "error_count": r.error_count,
            "total_rows": r.total_rows,
            "total_duration_ms": r.total_duration_ms,
            "p50_ms": r.p50_ms,
            "p95_ms": r.p95_ms,
            "p99_ms": r.p99_ms,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /insights/logs
# ---------------------------------------------------------------------------

@router.get("/logs")
async def search_logs(
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
    q: str | None = Query(None),
    flow_id: str | None = Query(None),
    run_id: str | None = Query(None),
    level: str | None = Query(None),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = _dt(from_dt, now - timedelta(hours=24))
    until = _dt(to_dt, now)

    stmt = (
        select(ExecutionLogTable)
        .where(
            ExecutionLogTable.timestamp >= since,
            ExecutionLogTable.timestamp <= until,
        )
        .order_by(ExecutionLogTable.timestamp.desc())
    )
    if q:
        stmt = stmt.where(ExecutionLogTable.message.ilike(f"%{q}%"))
    if flow_id:
        stmt = stmt.where(ExecutionLogTable.flow_id == flow_id)
    if run_id:
        stmt = stmt.where(ExecutionLogTable.run_id == run_id)
    if level:
        stmt = stmt.where(ExecutionLogTable.level == level.upper())

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "logs": [
            {
                "id": r.id,
                "run_id": r.run_id,
                "flow_id": r.flow_id,
                "step_id": r.step_id,
                "correlation_id": r.correlation_id,
                "level": r.level,
                "message": r.message,
                "payload_preview": r.payload_preview,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# GET /insights/logs/{run_id}
# ---------------------------------------------------------------------------

@router.get("/logs/{run_id}")
async def get_run_logs(
    run_id: str,
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(ExecutionLogTable)
            .where(ExecutionLogTable.run_id == run_id)
            .order_by(ExecutionLogTable.timestamp.asc())
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "step_id": r.step_id,
            "level": r.level,
            "message": r.message,
            "payload_preview": r.payload_preview,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /insights/events
# ---------------------------------------------------------------------------

@router.get("/events")
async def get_business_events(
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
    flow_id: str | None = Query(None),
    event_name: str | None = Query(None),
    correlation_id: str | None = Query(None),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = _dt(from_dt, now - timedelta(days=7))
    until = _dt(to_dt, now)

    stmt = (
        select(BusinessEventTable)
        .where(
            BusinessEventTable.occurred_at >= since,
            BusinessEventTable.occurred_at <= until,
        )
        .order_by(BusinessEventTable.occurred_at.desc())
    )
    if flow_id:
        stmt = stmt.where(BusinessEventTable.flow_id == flow_id)
    if event_name:
        stmt = stmt.where(BusinessEventTable.event_name == event_name)
    if correlation_id:
        stmt = stmt.where(BusinessEventTable.correlation_id == correlation_id)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "events": [
            {
                "id": r.id,
                "flow_id": r.flow_id,
                "run_id": r.run_id,
                "step_id": r.step_id,
                "correlation_id": r.correlation_id,
                "event_name": r.event_name,
                "payload": r.payload,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# GET /insights/runs/{run_id}
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}")
async def get_run_detail(
    run_id: str,
    _user: dict = Depends(get_current_user),
    session=Depends(get_session),
) -> dict[str, Any]:
    run = (
        await session.execute(
            select(ExecutionRunTable).where(ExecutionRunTable.run_id == run_id)
        )
    ).scalar_one_or_none()
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Run not found")

    steps = (
        await session.execute(
            select(StepExecutionTable)
            .where(StepExecutionTable.run_id == run_id)
            .order_by(StepExecutionTable.started_at.asc())
        )
    ).scalars().all()

    logs = (
        await session.execute(
            select(ExecutionLogTable)
            .where(ExecutionLogTable.run_id == run_id)
            .order_by(ExecutionLogTable.timestamp.asc())
        )
    ).scalars().all()

    events = (
        await session.execute(
            select(BusinessEventTable)
            .where(BusinessEventTable.run_id == run_id)
            .order_by(BusinessEventTable.occurred_at.asc())
        )
    ).scalars().all()

    return {
        "run_id": run.run_id,
        "flow_id": run.flow_id,
        "flow_name": run.flow_name,
        "correlation_id": run.correlation_id,
        "status": run.status,
        "trigger_type": run.trigger_type,
        "triggered_by": run.triggered_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "duration_ms": run.duration_ms,
        "rows_processed": run.rows_processed,
        "rows_failed": run.rows_failed,
        "error_message": run.error_message,
        "steps": [
            {
                "step_id": s.step_id,
                "step_type": s.step_type,
                "step_label": s.step_label or "",
                "connector_id": s.connector_id,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "rows_in": s.rows_in,
                "rows_out": s.rows_out,
                "error_type": s.error_type,
                "error_message": s.error_message,
                "retry_count": s.retry_count,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
            for s in steps
        ],
        "logs": [
            {
                "level": lg.level,
                "message": lg.message,
                "step_id": lg.step_id,
                "timestamp": lg.timestamp.isoformat() if lg.timestamp else None,
            }
            for lg in logs
        ],
        "business_events": [
            {
                "event_name": ev.event_name,
                "payload": ev.payload,
                "step_id": ev.step_id,
                "occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None,
            }
            for ev in events
        ],
    }
