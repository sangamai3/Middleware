"""
Data lineage tracker.

Records which connector/object each flow step reads from or writes to.
Enables:
  - Visual lineage graph in UI
  - Impact analysis: "which flows will break if I change connection X?"
  - Schema drift detection: alert when object schema changes vs recorded fields
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.tables import FlowLineageTable


async def record_lineage(
    session: AsyncSession,
    *,
    flow_id: str,
    flow_version: str,
    step_id: str,
    step_type: str,
    direction: str,
    connection_id: str | None = None,
    connector_id: str | None = None,
    object_name: str | None = None,
    fields: list[str] | None = None,
) -> None:
    row = FlowLineageTable(
        flow_id=flow_id,
        flow_version=flow_version,
        step_id=step_id,
        step_type=step_type,
        direction=direction,
        connection_id=connection_id,
        connector_id=connector_id,
        object_name=object_name,
        fields=fields or [],
    )
    session.add(row)
    await session.flush()


async def get_flow_lineage(
    session: AsyncSession,
    flow_id: str,
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(FlowLineageTable)
        .where(FlowLineageTable.flow_id == flow_id)
        .order_by(FlowLineageTable.step_id)
    )
    rows = result.scalars().all()
    return [
        {
            "flow_id": r.flow_id,
            "flow_version": r.flow_version,
            "step_id": r.step_id,
            "step_type": r.step_type,
            "direction": r.direction,
            "connection_id": r.connection_id,
            "connector_id": r.connector_id,
            "object_name": r.object_name,
            "fields": r.fields,
            "recorded_at": r.recorded_at.isoformat(),
        }
        for r in rows
    ]


async def impact_analysis(
    session: AsyncSession,
    *,
    connection_id: str | None = None,
    connector_id: str | None = None,
    object_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return all flows that read from or write to the given resource.
    Used when changing a connection/connector/table to know what will be affected.
    """
    filters = []
    if connection_id:
        filters.append(FlowLineageTable.connection_id == connection_id)
    if connector_id:
        filters.append(FlowLineageTable.connector_id == connector_id)
    if object_name:
        filters.append(FlowLineageTable.object_name == object_name)

    if not filters:
        return []

    result = await session.execute(
        select(FlowLineageTable)
        .where(or_(*filters))
        .order_by(FlowLineageTable.flow_id, FlowLineageTable.step_id)
    )
    rows = result.scalars().all()
    seen: set[tuple[str, str]] = set()
    affected: list[dict[str, Any]] = []
    for r in rows:
        key = (r.flow_id, r.step_id)
        if key not in seen:
            seen.add(key)
            affected.append({
                "flow_id": r.flow_id,
                "step_id": r.step_id,
                "direction": r.direction,
                "connector_id": r.connector_id,
                "object_name": r.object_name,
            })
    return affected
