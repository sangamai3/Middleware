"""
Flow management routes.

CRUD for FlowDefinition. Validates on deploy/activate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...connectors.base.errors import FlowValidationError
from ...db.base import get_session
from ...db.flow_store import (
    delete_flow_definition,
    get_flow_definition,
    insert_flow,
    list_flow_summaries,
    update_flow_definition,
)
from ...engine.executor import FlowExecutor
from ...engine.validator import FlowValidator
from ...models.flow import FlowDefinition, FlowStatus
from ..auth import get_current_user

router = APIRouter(prefix="/flows", tags=["flows"])


class FlowCreateRequest(BaseModel):
    definition: dict[str, Any]


class FlowUpdateRequest(BaseModel):
    definition: dict[str, Any]


class FlowPreviewRequest(BaseModel):
    definition: dict[str, Any]
    step_id: str
    limit: int = 25


@router.post("/preview", response_model=dict)
def preview_flow_step(
    req: FlowPreviewRequest,
    _user: dict = Depends(get_current_user),
) -> dict:
    """Run upstream steps through ``step_id`` and return sample rows (no writes)."""
    flow = FlowDefinition.model_validate(req.definition)
    if req.step_id not in {s.id for s in flow.steps}:
        raise HTTPException(status_code=400, detail=f"Unknown step_id '{req.step_id}'")
    limit = max(1, min(req.limit, 500))
    executor = FlowExecutor()
    return executor.preview(flow, req.step_id, limit=limit)


@router.post("/", response_model=dict)
async def create_flow(
    req: FlowCreateRequest,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    flow = FlowDefinition.model_validate(req.definition)
    now = datetime.now(timezone.utc)
    flow.created_at = flow.created_at or now
    flow.updated_at = now
    existing = await get_flow_definition(session, flow.flow_id)
    if existing:
        raise HTTPException(status_code=409, detail="Flow already exists")
    created_by = _user.get("sub") or _user.get("email") or ""
    await insert_flow(session, flow, created_by=created_by)
    return {"flow_id": flow.flow_id, "status": flow.status}


@router.get("/", response_model=list[dict])
async def list_flows(
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await list_flow_summaries(session)


@router.get("/{flow_id}", response_model=dict)
async def get_flow(
    flow_id: str,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    flow = await get_flow_definition(session, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow.model_dump()


@router.put("/{flow_id}", response_model=dict)
async def update_flow(
    flow_id: str,
    req: FlowUpdateRequest,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await get_flow_definition(session, flow_id):
        raise HTTPException(status_code=404, detail="Flow not found")
    flow = FlowDefinition.model_validate(req.definition)
    if flow.flow_id != flow_id:
        raise HTTPException(status_code=400, detail="flow_id in body must match URL")
    updated = await update_flow_definition(session, flow_id, flow)
    if not updated:
        raise HTTPException(status_code=404, detail="Flow not found")
    return {"flow_id": flow_id, "status": updated.status}


@router.delete("/{flow_id}", response_model=dict)
async def delete_flow(
    flow_id: str,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await delete_flow_definition(session, flow_id):
        raise HTTPException(status_code=404, detail="Flow not found")
    return {"deleted": flow_id}


@router.post("/{flow_id}/validate", response_model=dict)
async def validate_flow(
    flow_id: str,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    flow = await get_flow_definition(session, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        validator = FlowValidator(flow)
        warnings = validator.validate()
        return {"valid": True, "warnings": warnings}
    except FlowValidationError as exc:
        return {"valid": False, "error": str(exc)}


class DockerComposeRequest(BaseModel):
    """Generate docker-compose for a dedicated flow worker."""

    definition: dict[str, Any] | None = None
    memory_profile: str = "minimal"
    image_tag: str = "latest"
    control_plane_url: str = "http://host.docker.internal:8100"
    host_data_root: str | None = None


@router.post("/{flow_id}/docker-compose", response_model=dict)
async def generate_docker_compose(
    flow_id: str,
    body: DockerComposeRequest,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    from ...runtime.flow_compose import generate_flow_compose

    if body.definition:
        flow = FlowDefinition.model_validate({**body.definition, "flow_id": flow_id})
    else:
        flow = await get_flow_definition(session, flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")

    return generate_flow_compose(
        flow,
        memory_profile=body.memory_profile,
        image_tag=body.image_tag,
        control_plane_url=body.control_plane_url,
        host_data_root=body.host_data_root,
    )


@router.post("/{flow_id}/deploy", response_model=dict)
async def deploy_flow(
    flow_id: str,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    flow = await get_flow_definition(session, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        validator = FlowValidator(flow)
        validator.validate()
    except FlowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    flow.status = FlowStatus.DEPLOYED
    updated = await update_flow_definition(session, flow_id, flow)
    if not updated:
        raise HTTPException(status_code=404, detail="Flow not found")
    return {"flow_id": flow_id, "status": updated.status}
