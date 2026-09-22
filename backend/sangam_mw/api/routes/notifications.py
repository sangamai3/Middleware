"""
Notification alert rules API.

GET    /api/v1/notifications/rules
POST   /api/v1/notifications/rules
GET    /api/v1/notifications/rules/{rule_id}
PATCH  /api/v1/notifications/rules/{rule_id}
DELETE /api/v1/notifications/rules/{rule_id}
POST   /api/v1/notifications/rules/{rule_id}/test
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.base import get_session
from ...db.tables import AlertRuleTable
from ...notifications.dispatcher import get_dispatcher
from ...notifications.rules import AlertRule, AlertTrigger
from ...rbac.permissions import Permission, require_permission

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    name: str
    trigger: AlertTrigger
    flow_ids: list[str] | None = None
    conditions: dict[str, Any] = {}
    channels: list[dict[str, Any]] = []
    is_active: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    trigger: AlertTrigger | None = None
    flow_ids: list[str] | None = None
    conditions: dict[str, Any] | None = None
    channels: list[dict[str, Any]] | None = None
    is_active: bool | None = None


def _row_to_dict(row: AlertRuleTable) -> dict[str, Any]:
    return {
        "rule_id": row.rule_id,
        "name": row.name,
        "trigger": row.trigger,
        "flow_ids": row.flow_ids,
        "conditions": row.conditions,
        "channels": row.channels,
        "is_active": row.is_active,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/rules")
async def list_rules(
    user: dict = Depends(require_permission(Permission.FLOW_READ)),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    result = await session.execute(select(AlertRuleTable).order_by(AlertRuleTable.created_at.desc()))
    return [_row_to_dict(r) for r in result.scalars()]


@router.post("/rules", status_code=201)
async def create_rule(
    body: AlertRuleCreate,
    user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rule_id = uuid.uuid4().hex[:12]
    row = AlertRuleTable(
        rule_id=rule_id,
        name=body.name,
        trigger=body.trigger.value,
        flow_ids=body.flow_ids,
        conditions=body.conditions,
        channels=body.channels,
        is_active=body.is_active,
        created_by=user.get("sub", ""),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    _reload_dispatcher(session)
    return _row_to_dict(row)


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _get_or_404(session, rule_id)
    return _row_to_dict(row)


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: AlertRuleUpdate,
    _user: dict = Depends(require_permission(Permission.FLOW_UPDATE)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _get_or_404(session, rule_id)
    updates = body.model_dump(exclude_none=True)
    if "trigger" in updates:
        updates["trigger"] = updates["trigger"].value
    for k, v in updates.items():
        setattr(row, k, v)
    row.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    _reload_dispatcher(session)
    return _row_to_dict(row)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_DELETE)),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await _get_or_404(session, rule_id)
    await session.delete(row)
    await session.commit()
    get_dispatcher().remove_rule(rule_id)


@router.post("/rules/{rule_id}/test")
async def test_rule(
    rule_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _get_or_404(session, rule_id)
    rule = AlertRule(
        rule_id=row.rule_id,
        name=row.name,
        trigger=AlertTrigger(row.trigger),
        flow_ids=row.flow_ids,
        conditions=row.conditions or {},
        channels=row.channels or [],
        is_active=True,
    )
    test_ctx = {
        "flow_id": (row.flow_ids or ["test-flow"])[0],
        "run_id": "test-run",
        "status": "failed",
        "duration_ms": 99999,
        "error_message": "This is a test notification from SangamMW.",
        "rows_processed": 0,
        "error_rate": 1.0,
    }
    event_type_map = {
        "flow_failed": "run.failed",
        "flow_slow": "run.completed",
        "error_rate_high": "error_rate_high",
        "run_started": "run.started",
        "run_completed": "run.completed",
    }
    event = event_type_map.get(row.trigger, "run.failed")

    dispatcher = get_dispatcher()
    old_rules = list(dispatcher._rules)
    dispatcher._rules = [rule]
    fired = await dispatcher.dispatch(event, test_ctx)
    dispatcher._rules = old_rules

    return {"fired": bool(fired), "rule_id": rule_id, "channels_attempted": len(row.channels)}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(session: AsyncSession, rule_id: str) -> AlertRuleTable:
    result = await session.execute(
        select(AlertRuleTable).where(AlertRuleTable.rule_id == rule_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id!r} not found")
    return row


def _reload_dispatcher(session: AsyncSession) -> None:
    pass
