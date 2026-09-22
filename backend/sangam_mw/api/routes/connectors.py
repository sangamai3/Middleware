from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...connectors.base.errors import ConnectorValidationError
from ...connectors.base.registry import registry
from ...connectors.base.schemas import ConnectionHandle
from ...connectors.base.validation import validate_config
from ..auth import get_current_user

router = APIRouter(prefix="/connectors", tags=["connectors"])


class TestConnectionRequest(BaseModel):
    config: dict


class IntrospectColumnsRequest(BaseModel):
    config: dict
    object_name: str


@router.get("/")
async def list_connectors(_: dict = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "connector_id": c.metadata.connector_id,
            "label": c.metadata.label,
            "family": c.metadata.family,
            "version": c.metadata.version,
            "auth_type": c.metadata.auth_type,
            "operations": [op.value for op in c.metadata.operations],
            "description": c.metadata.description,
            "tags": c.metadata.tags,
            "connection_schema": c.metadata.connection_schema,
            "read_schema": c.metadata.read_schema,
            "write_schema": c.metadata.write_schema,
        }
        for c in registry.all()
    ]


@router.get("/{connector_id}")
async def get_connector(connector_id: str, _: dict = Depends(get_current_user)) -> dict:
    try:
        connector = registry.get(connector_id)
    except KeyError:
        raise HTTPException(404, f"Connector '{connector_id}' not found")
    m = connector.metadata
    return {
        "connector_id": m.connector_id,
        "label": m.label,
        "family": m.family,
        "version": m.version,
        "auth_type": m.auth_type,
        "operations": [op.value for op in m.operations],
        "description": m.description,
        "connection_schema": m.connection_schema,
        "read_schema": m.read_schema,
        "write_schema": m.write_schema,
        "tags": m.tags,
    }


@router.post("/{connector_id}/test")
async def test_connection(
    connector_id: str,
    body: TestConnectionRequest,
    _: dict = Depends(get_current_user),
) -> dict:
    try:
        connector = registry.get(connector_id)
    except KeyError:
        raise HTTPException(404, f"Connector '{connector_id}' not found")
    try:
        validate_config(
            body.config, connector.metadata.connection_schema, label="connection config"
        )
    except ConnectorValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    handle = ConnectionHandle(
        connector_id=connector_id,
        connection_id="test",
        config=body.config,
        created_at=datetime.now(UTC),
    )
    try:
        ok = connector.test_connection(handle)
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    return {"success": ok}


@router.post("/{connector_id}/objects")
async def introspect_objects(
    connector_id: str,
    body: TestConnectionRequest,
    _: dict = Depends(get_current_user),
) -> list[dict]:
    try:
        connector = registry.get(connector_id)
    except KeyError:
        raise HTTPException(404, f"Connector '{connector_id}' not found")
    try:
        validate_config(
            body.config, connector.metadata.connection_schema, label="connection config"
        )
    except ConnectorValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    handle = ConnectionHandle(
        connector_id=connector_id,
        connection_id="introspect",
        config=body.config,
        created_at=datetime.now(UTC),
    )
    objects = connector.introspect_objects(handle)
    return [{"name": o.name, "kind": o.kind, "description": o.description} for o in objects]


@router.post("/{connector_id}/columns")
async def introspect_columns(
    connector_id: str,
    body: IntrospectColumnsRequest,
    _: dict = Depends(get_current_user),
) -> list[dict]:
    try:
        connector = registry.get(connector_id)
    except KeyError:
        raise HTTPException(404, f"Connector '{connector_id}' not found")
    try:
        validate_config(
            body.config, connector.metadata.connection_schema, label="connection config"
        )
    except ConnectorValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    handle = ConnectionHandle(
        connector_id=connector_id,
        connection_id="introspect",
        config=body.config,
        created_at=datetime.now(UTC),
    )
    cols = connector.introspect_columns(handle, body.object_name)
    return [
        {
            "name": c.name,
            "data_type": c.data_type,
            "nullable": c.nullable,
            "is_primary_key": c.is_primary_key,
            "description": c.description,
        }
        for c in cols
    ]


@router.get("/health")
async def connector_health(_: dict = Depends(get_current_user)) -> dict:
    """Return health summary for all registered connectors."""
    all_connectors = registry.ids()
    results = []
    for cid in all_connectors:
        try:
            connector = registry.get(cid)
            meta = connector.metadata
            results.append({
                "connector_id": cid,
                "label": meta.label,
                "family": meta.family,
                "status": "available",
                "operations": meta.operations,
            })
        except Exception as exc:
            results.append({
                "connector_id": cid,
                "label": cid,
                "family": "unknown",
                "status": "error",
                "error": str(exc),
                "operations": [],
            })
    return {
        "total": len(results),
        "available": sum(1 for r in results if r["status"] == "available"),
        "connectors": results,
        "checked_at": datetime.now(UTC).isoformat(),
    }
