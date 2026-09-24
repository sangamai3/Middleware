"""Persist flow definitions in FlowTable."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .tables import FlowTable
from ..models.flow import FlowDefinition, FlowStatus


def _flow_from_row(row: FlowTable) -> FlowDefinition:
    data = dict(row.definition or {})
    data["flow_id"] = row.flow_id
    data["name"] = row.name
    data["description"] = row.description
    data["version"] = row.version
    data["status"] = row.status
    data["created_at"] = row.created_at
    data["updated_at"] = row.updated_at
    data["created_by"] = row.created_by
    return FlowDefinition.model_validate(data)


def _sync_row_from_flow(row: FlowTable, flow: FlowDefinition, created_by: str = "") -> None:
    row.name = flow.name
    row.description = flow.description
    row.version = flow.version
    row.status = flow.status.value if isinstance(flow.status, FlowStatus) else str(flow.status)
    row.definition = flow.model_dump(mode="json")
    row.updated_at = flow.updated_at or datetime.now(UTC)
    if created_by and not row.created_by:
        row.created_by = created_by


async def get_flow_definition(session: AsyncSession, flow_id: str) -> FlowDefinition | None:
    result = await session.execute(select(FlowTable).where(FlowTable.flow_id == flow_id))
    row = result.scalar_one_or_none()
    if not row:
        return None
    return _flow_from_row(row)


async def list_flow_summaries(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        select(FlowTable).order_by(FlowTable.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "flow_id": r.flow_id,
            "name": r.name,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


async def insert_flow(
    session: AsyncSession,
    flow: FlowDefinition,
    created_by: str = "",
) -> FlowDefinition:
    now = datetime.now(UTC)
    flow.created_at = flow.created_at or now
    flow.updated_at = now
    row = FlowTable(
        flow_id=flow.flow_id,
        name=flow.name,
        description=flow.description,
        version=flow.version,
        status=flow.status.value if isinstance(flow.status, FlowStatus) else str(flow.status),
        definition=flow.model_dump(mode="json"),
        created_at=flow.created_at,
        updated_at=flow.updated_at,
        created_by=created_by or flow.created_by,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _flow_from_row(row)


async def update_flow_definition(
    session: AsyncSession,
    flow_id: str,
    flow: FlowDefinition,
    created_by: str = "",
) -> FlowDefinition | None:
    result = await session.execute(select(FlowTable).where(FlowTable.flow_id == flow_id))
    row = result.scalar_one_or_none()
    if not row:
        return None
    flow.created_at = row.created_at
    flow.updated_at = datetime.now(UTC)
    _sync_row_from_flow(row, flow, created_by=created_by)
    await session.commit()
    await session.refresh(row)
    return _flow_from_row(row)


async def delete_flow_definition(session: AsyncSession, flow_id: str) -> bool:
    result = await session.execute(select(FlowTable).where(FlowTable.flow_id == flow_id))
    row = result.scalar_one_or_none()
    if not row:
        return False
    await session.delete(row)
    await session.commit()
    return True
