"""
Lineage & impact analysis API.

GET /api/v1/lineage/{flow_id}        flow's full lineage graph
GET /api/v1/lineage/impact           affected flows for a given resource
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.base import get_session
from ...lineage.tracker import get_flow_lineage, impact_analysis
from ...rbac.permissions import Permission, require_permission

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get("/{flow_id}")
async def flow_lineage(
    flow_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    edges = await get_flow_lineage(session, flow_id)
    sources = [e for e in edges if e["direction"] == "read"]
    sinks = [e for e in edges if e["direction"] == "write"]
    return {
        "flow_id": flow_id,
        "sources": sources,
        "sinks": sinks,
        "total_edges": len(edges),
    }


@router.get("/impact")
async def impact(
    connection_id: str | None = Query(None),
    connector_id: str | None = Query(None),
    object_name: str | None = Query(None),
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    affected = await impact_analysis(
        session,
        connection_id=connection_id,
        connector_id=connector_id,
        object_name=object_name,
    )
    return {
        "query": {
            "connection_id": connection_id,
            "connector_id": connector_id,
            "object_name": object_name,
        },
        "affected_flows": affected,
        "count": len(affected),
    }
