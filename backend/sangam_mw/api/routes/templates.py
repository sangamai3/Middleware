"""
Integration template marketplace API.

GET  /api/v1/templates         — list all available templates
GET  /api/v1/templates/{id}    — get a single template by id
POST /api/v1/templates/{id}/instantiate — render template with parameters into a flow definition
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/templates", tags=["templates"])

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "sangam_mw" / "templates"
if not _TEMPLATES_DIR.exists():
    _TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _load_all() -> list[dict[str, Any]]:
    templates = []
    for path in sorted(_TEMPLATES_DIR.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
            templates.append(raw)
        except Exception:
            pass
    return templates


def _render(template_str: str, params: dict[str, Any]) -> str:
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        return str(params.get(key, match.group(0)))

    return re.sub(r"\{\{([^}]+)\}\}", replacer, template_str)


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    category: str
    tags: list[str]
    author: str
    version: str
    connections: list[dict[str, Any]]
    parameters: list[dict[str, Any]]


class InstantiateRequest(BaseModel):
    name: str
    parameters: dict[str, Any] = {}
    connection_ids: dict[str, str] = {}


class InstantiateResponse(BaseModel):
    flow_definition: dict[str, Any]


@router.get("", response_model=list[TemplateSummary])
async def list_templates(
    category: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    """List all integration templates, optionally filtered by category or tag."""
    templates = _load_all()
    if category:
        templates = [t for t in templates if t.get("category") == category]
    if tag:
        templates = [t for t in templates if tag in (t.get("tags") or [])]
    return [
        {
            "id": t.get("id", ""),
            "name": t.get("name", ""),
            "description": (t.get("description") or "").strip(),
            "category": t.get("category", ""),
            "tags": t.get("tags") or [],
            "author": t.get("author", ""),
            "version": t.get("version", "1.0.0"),
            "connections": t.get("connections") or [],
            "parameters": t.get("parameters") or [],
        }
        for t in templates
    ]


@router.get("/{template_id}")
async def get_template(template_id: str) -> dict[str, Any]:
    """Get a single template by ID."""
    for t in _load_all():
        if t.get("id") == template_id:
            return t
    raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")


@router.post("/{template_id}/instantiate", response_model=InstantiateResponse)
async def instantiate_template(
    template_id: str,
    body: InstantiateRequest,
) -> dict[str, Any]:
    """
    Render a template into a concrete flow definition.

    Parameters in `body.parameters` replace `{{parameter_name}}` placeholders.
    `body.connection_ids` maps connection placeholder IDs to real connection UUIDs.
    `body.name` sets the flow name.
    """
    tmpl: dict[str, Any] | None = None
    for t in _load_all():
        if t.get("id") == template_id:
            tmpl = t
            break
    if tmpl is None:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    defaults: dict[str, Any] = {}
    for param in (tmpl.get("parameters") or []):
        if "default" in param:
            defaults[param["name"]] = param["default"]

    render_ctx: dict[str, Any] = {**defaults, **body.parameters, "name": body.name}
    render_ctx.update(body.connection_ids)

    raw_definition = yaml.dump(tmpl.get("definition") or {})
    rendered_yaml = _render(raw_definition, render_ctx)

    try:
        flow_def: dict[str, Any] = yaml.safe_load(rendered_yaml)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Template rendering failed: {exc}") from exc

    flow_def["name"] = body.name

    return {"flow_definition": flow_def}
