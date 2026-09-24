"""
Flow scheduler management API.

GET    /api/v1/scheduler/jobs             — list all scheduled flows
POST   /api/v1/scheduler/jobs             — create or update a schedule
GET    /api/v1/scheduler/jobs/{flow_id}   — get one job
PATCH  /api/v1/scheduler/jobs/{flow_id}   — update (cron/interval/active)
DELETE /api/v1/scheduler/jobs/{flow_id}   — remove schedule
POST   /api/v1/scheduler/jobs/{flow_id}/trigger — run now (manual trigger)
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

try:
    from croniter import croniter as _croniter
    _HAS_CRONITER = True
except ImportError:
    _croniter = None  # type: ignore[assignment]
    _HAS_CRONITER = False
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.base import get_session
from ...db.tables import ScheduledFlowTable
from ...engine.flow_run_service import execute_flow_by_id
from ...engine.schedule_registry import apply_schedule_row, remove_schedule, touch_last_run
from ...rbac.permissions import Permission, require_permission

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    flow_id: str
    flow_name: str = ""
    cron_expr: str | None = None
    interval_seconds: int | None = None
    timezone: str = "UTC"
    is_active: bool = True

    @model_validator(mode="after")
    def _check_trigger(self) -> "JobCreate":
        if self.cron_expr is None and self.interval_seconds is None:
            raise ValueError("Provide either cron_expr or interval_seconds")
        if self.cron_expr is not None and self.interval_seconds is not None:
            raise ValueError("Provide only one of cron_expr or interval_seconds")
        if self.cron_expr is not None:
            from ...engine.cron_expr import validate_cron_expr

            try:
                validate_cron_expr(self.cron_expr)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            if _HAS_CRONITER:
                try:
                    _croniter(self.cron_expr)
                except (ValueError, KeyError) as exc:
                    raise ValueError(f"Invalid cron expression: {exc}") from exc
        return self


class JobUpdate(BaseModel):
    flow_name: str | None = None
    cron_expr: str | None = None
    interval_seconds: int | None = None
    timezone: str | None = None
    is_active: bool | None = None


def _row_to_dict(row: ScheduledFlowTable) -> dict[str, Any]:
    next_run: str | None = None
    if row.cron_expr and _HAS_CRONITER:
        try:
            cit = _croniter(row.cron_expr, datetime.now(UTC))
            next_run = cit.get_next(datetime).isoformat()
        except Exception:
            pass

    return {
        "flow_id": row.flow_id,
        "flow_name": row.flow_name,
        "cron_expr": row.cron_expr,
        "interval_seconds": row.interval_seconds,
        "timezone": row.timezone,
        "is_active": row.is_active,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "next_run_at": next_run,
        "trigger_type": "cron" if row.cron_expr else "interval",
        "trigger_label": _trigger_label(row),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _trigger_label(row: ScheduledFlowTable) -> str:
    if row.cron_expr:
        return _cron_human(row.cron_expr)
    if row.interval_seconds:
        secs = row.interval_seconds
        if secs >= 3600:
            return f"Every {secs // 3600}h"
        if secs >= 60:
            return f"Every {secs // 60}m"
        return f"Every {secs}s"
    return "—"


def _cron_human(expr: str) -> str:
    parts = expr.split()
    if len(parts) == 6:
        second, minute, hour, dom, month, dow = parts
        if dom == "*" and month == "*" and dow not in ("*", ""):
            days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            if re.match(r"^[0-6]$", dow):
                return f"Weekly on {days[int(dow)]} at {hour.zfill(2)}:{minute.zfill(2)}:{second.zfill(2)}"
        if dom == "*" and month == "*" and dow == "*":
            return f"Daily at {hour.zfill(2)}:{minute.zfill(2)}:{second.zfill(2)}"
        return f"cron({expr})"
    if len(parts) != 5:
        return expr
    minute, hour, dom, month, dow = parts
    if expr == "0 * * * *":
        return "Every hour"
    if expr == "*/5 * * * *":
        return "Every 5 minutes"
    if expr == "*/15 * * * *":
        return "Every 15 minutes"
    if expr == "*/30 * * * *":
        return "Every 30 minutes"
    if dom == "*" and month == "*" and dow == "*":
        if minute == "0" and re.match(r"^\d+$", hour):
            return f"Daily at {hour.zfill(2)}:00"
    if dom == "*" and month == "*" and re.match(r"^[0-6]$", dow):
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        return f"Weekly on {days[int(dow)]} at {hour.zfill(2)}:{minute.zfill(2)}"
    return f"cron({expr})"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(ScheduledFlowTable).order_by(ScheduledFlowTable.created_at.desc())
    )
    return [_row_to_dict(r) for r in result.scalars()]


@router.post("/jobs", status_code=201)
async def create_job(
    body: JobCreate,
    user: dict = Depends(require_permission(Permission.FLOW_UPDATE)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    existing = await session.execute(
        select(ScheduledFlowTable).where(ScheduledFlowTable.flow_id == body.flow_id)
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        row.flow_name = body.flow_name or row.flow_name
        row.cron_expr = body.cron_expr
        row.interval_seconds = body.interval_seconds
        row.timezone = body.timezone
        row.is_active = body.is_active
        row.updated_at = datetime.now(UTC)
    else:
        row = ScheduledFlowTable(
            flow_id=body.flow_id,
            flow_name=body.flow_name,
            cron_expr=body.cron_expr,
            interval_seconds=body.interval_seconds,
            timezone=body.timezone,
            is_active=body.is_active,
            created_by=user.get("sub", ""),
        )
        session.add(row)

    await session.commit()
    await session.refresh(row)
    apply_schedule_row(row, body.flow_id)
    return _row_to_dict(row)


@router.get("/jobs/{flow_id}")
async def get_job(
    flow_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return _row_to_dict(await _get_or_404(session, flow_id))


@router.patch("/jobs/{flow_id}")
async def update_job(
    flow_id: str,
    body: JobUpdate,
    _user: dict = Depends(require_permission(Permission.FLOW_UPDATE)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _get_or_404(session, flow_id)
    updates = body.model_dump(exclude_none=True)
    if "cron_expr" in updates and updates["cron_expr"]:
        from ...engine.cron_expr import validate_cron_expr

        try:
            validate_cron_expr(updates["cron_expr"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if _HAS_CRONITER:
            try:
                _croniter(updates["cron_expr"])
            except (ValueError, KeyError) as exc:
                raise HTTPException(status_code=422, detail=f"Invalid cron: {exc}") from exc
    for k, v in updates.items():
        setattr(row, k, v)
    row.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    apply_schedule_row(row, flow_id)
    return _row_to_dict(row)


@router.delete("/jobs/{flow_id}", status_code=204)
async def delete_job(
    flow_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_UPDATE)),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await _get_or_404(session, flow_id)
    await session.delete(row)
    await session.commit()
    remove_schedule(flow_id)


@router.post("/jobs/{flow_id}/trigger")
async def trigger_job(
    flow_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_DEPLOY)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _get_or_404(session, flow_id)
    run = await execute_flow_by_id(
        flow_id,
        trigger_type="schedule",
        triggered_by="scheduler-manual",
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"Flow {flow_id!r} not found")
    await touch_last_run(flow_id)
    return {
        "flow_id": flow_id,
        "run_id": run.run_id,
        "status": run.status,
        "triggered_at": datetime.now(UTC).isoformat(),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(session: AsyncSession, flow_id: str) -> ScheduledFlowTable:
    result = await session.execute(
        select(ScheduledFlowTable).where(ScheduledFlowTable.flow_id == flow_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No schedule for flow {flow_id!r}")
    return row
