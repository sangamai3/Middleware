"""
Flow management routes.

CRUD for FlowDefinition. Validates on deploy/activate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...connectors.base.errors import FlowValidationError
from ...engine.validator import FlowValidator
from ...models.flow import FlowDefinition, FlowStatus
from ..auth import get_current_user

router = APIRouter(prefix="/flows", tags=["flows"])


class FlowCreateRequest(BaseModel):
    definition: dict[str, Any]


class FlowUpdateRequest(BaseModel):
    definition: dict[str, Any]


# In-memory store for dev/test; replace with DB persistence in production.
_flows: dict[str, FlowDefinition] = {}


@router.post("/", response_model=dict)
def create_flow(
    req: FlowCreateRequest,
    _user: dict = Depends(get_current_user),
) -> dict:
    flow = FlowDefinition.model_validate(req.definition)
    now = datetime.now(timezone.utc)
    flow.created_at = flow.created_at or now
    flow.updated_at = now
    _flows[flow.flow_id] = flow
    return {"flow_id": flow.flow_id, "status": flow.status}


@router.get("/", response_model=list[dict])
def list_flows(_user: dict = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "flow_id": f.flow_id,
            "name": f.name,
            "status": f.status,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }
        for f in _flows.values()
    ]


@router.get("/{flow_id}", response_model=dict)
def get_flow(flow_id: str, _user: dict = Depends(get_current_user)) -> dict:
    flow = _flows.get(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow.model_dump()


@router.put("/{flow_id}", response_model=dict)
def update_flow(
    flow_id: str,
    req: FlowUpdateRequest,
    _user: dict = Depends(get_current_user),
) -> dict:
    if flow_id not in _flows:
        raise HTTPException(status_code=404, detail="Flow not found")
    existing = _flows[flow_id]
    flow = FlowDefinition.model_validate(req.definition)
    flow.created_at = existing.created_at
    flow.updated_at = datetime.now(timezone.utc)
    _flows[flow_id] = flow
    return {"flow_id": flow_id, "status": flow.status}


@router.delete("/{flow_id}", response_model=dict)
def delete_flow(flow_id: str, _user: dict = Depends(get_current_user)) -> dict:
    if flow_id not in _flows:
        raise HTTPException(status_code=404, detail="Flow not found")
    del _flows[flow_id]
    return {"deleted": flow_id}


@router.post("/{flow_id}/validate", response_model=dict)
def validate_flow(flow_id: str, _user: dict = Depends(get_current_user)) -> dict:
    flow = _flows.get(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        validator = FlowValidator(flow)
        warnings = validator.validate()
        return {"valid": True, "warnings": warnings}
    except FlowValidationError as exc:
        return {"valid": False, "error": str(exc)}


@router.post("/{flow_id}/deploy", response_model=dict)
def deploy_flow(flow_id: str, _user: dict = Depends(get_current_user)) -> dict:
    flow = _flows.get(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    try:
        validator = FlowValidator(flow)
        validator.validate()
    except FlowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    flow.status = FlowStatus.DEPLOYED
    return {"flow_id": flow_id, "status": flow.status}
