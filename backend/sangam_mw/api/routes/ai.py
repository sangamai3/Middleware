"""
AI-assisted flow generation and field mapping API.

POST /api/v1/ai/generate-flow      → YAML flow definition from description
POST /api/v1/ai/suggest-mapping    → field mapping suggestions for source+target schema
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...ai.flow_gen import FieldMappingSuggester, FlowGenerator, MappingSuggestion
from ...config import get_settings
from ...connectors.base.schemas import ColumnSchema
from ...rbac.permissions import Permission, require_permission

router = APIRouter(prefix="/ai", tags=["ai"])


class GenerateFlowRequest(BaseModel):
    description: str
    available_connectors: list[str] = []
    available_connections: list[dict[str, Any]] = []
    provider: str = "anthropic"
    model: str = ""


class GenerateFlowResponse(BaseModel):
    flow_yaml: str
    provider: str
    model: str


class SuggestMappingRequest(BaseModel):
    source_schema: list[dict[str, Any]]
    target_schema: list[dict[str, Any]]
    provider: str = "anthropic"
    model: str = ""


@router.post("/generate-flow", response_model=GenerateFlowResponse)
async def generate_flow(
    body: GenerateFlowRequest,
    _user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
) -> dict[str, Any]:
    settings = get_settings()
    api_key = (
        getattr(settings, "anthropic_api_key", None)
        if body.provider == "anthropic"
        else getattr(settings, "openai_api_key", None)
    )
    if not api_key:
        raise HTTPException(
            status_code=422,
            detail=f"{body.provider.upper()}_API_KEY not configured in server settings",
        )
    try:
        gen = FlowGenerator(api_key=str(api_key), provider=body.provider, model=body.model)
        yaml_str = gen.generate(
            description=body.description,
            available_connectors=body.available_connectors,
            available_connections=body.available_connections,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Flow generation failed: {exc}") from exc

    return {
        "flow_yaml": yaml_str,
        "provider": body.provider,
        "model": gen._resolve_model(),
    }


@router.post("/suggest-mapping")
async def suggest_mapping(
    body: SuggestMappingRequest,
    _user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
) -> dict[str, Any]:
    settings = get_settings()
    api_key = (
        getattr(settings, "anthropic_api_key", None)
        if body.provider == "anthropic"
        else getattr(settings, "openai_api_key", None)
    )
    if not api_key:
        raise HTTPException(
            status_code=422,
            detail=f"{body.provider.upper()}_API_KEY not configured in server settings",
        )
    source = [ColumnSchema(name=f["name"], data_type=f.get("data_type", "string")) for f in body.source_schema]
    target = [ColumnSchema(name=f["name"], data_type=f.get("data_type", "string")) for f in body.target_schema]
    try:
        suggester = FieldMappingSuggester(api_key=str(api_key), provider=body.provider, model=body.model)
        suggestions: list[MappingSuggestion] = suggester.suggest(source, target)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mapping suggestion failed: {exc}") from exc

    return {
        "suggestions": [
            {
                "source_field": s.source_field,
                "target_field": s.target_field,
                "confidence": round(s.confidence, 2),
                "transform": s.transform,
                "reason": s.reason,
            }
            for s in sorted(suggestions, key=lambda x: -x.confidence)
        ],
        "count": len(suggestions),
    }
