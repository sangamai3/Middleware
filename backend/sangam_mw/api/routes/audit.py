"""
Audit log API.

GET /api/v1/audit              list audit events (admin/developer)
GET /api/v1/audit/verify       verify hash-chain integrity (admin only)
GET /api/v1/audit/export       export as NDJSON for SIEM (admin only)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit.log import verify_chain
from ...db.base import get_session
from ...db.tables import AuditLogTable
from ...rbac.permissions import Permission, require_permission

router = APIRouter(prefix="/audit", tags=["audit"])


def _row_out(row: AuditLogTable) -> dict[str, Any]:
    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat(),
        "actor_id": row.actor_id,
        "actor_email": row.actor_email,
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "ip_address": row.ip_address,
        "entry_hash": row.entry_hash,
    }


@router.get("")
async def list_audit_events(
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    _user: dict = Depends(require_permission(Permission.AUDIT_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    filters = []
    if actor_id:
        filters.append(AuditLogTable.actor_id == actor_id)
    if action:
        filters.append(AuditLogTable.action == action)
    if resource_type:
        filters.append(AuditLogTable.resource_type == resource_type)
    if resource_id:
        filters.append(AuditLogTable.resource_id == resource_id)
    if since:
        filters.append(AuditLogTable.timestamp >= since)
    if until:
        filters.append(AuditLogTable.timestamp <= until)

    q = select(AuditLogTable).order_by(AuditLogTable.id.desc())
    if filters:
        q = q.where(and_(*filters))
    q = q.limit(limit).offset(offset)

    result = await session.execute(q)
    rows = result.scalars().all()
    return {"total": len(rows), "offset": offset, "events": [_row_out(r) for r in rows]}


@router.get("/verify")
async def verify_audit_chain(
    _user: dict = Depends(require_permission(Permission.SYSTEM_SETTINGS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    valid, count, broken_at = await verify_chain(session)
    return {
        "valid": valid,
        "rows_checked": count,
        "broken_at_entry": broken_at,
        "message": "Hash chain intact" if valid else f"Chain broken at entry {broken_at}",
    }


@router.get("/export")
async def export_audit_log(
    since: datetime | None = None,
    _user: dict = Depends(require_permission(Permission.SYSTEM_SETTINGS)),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    import json as _json

    q = select(AuditLogTable).order_by(AuditLogTable.id)
    if since:
        q = q.where(AuditLogTable.timestamp >= since)

    result = await session.execute(q)
    rows = result.scalars().all()

    def _generate():
        for row in rows:
            yield _json.dumps({
                **_row_out(row),
                "before_snapshot": row.before_snapshot,
                "after_snapshot": row.after_snapshot,
                "prev_hash": row.prev_hash,
                "user_agent": row.user_agent,
            }) + "\n"

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=audit-export.ndjson"},
    )
