"""
Enhanced health check with dependency status.

GET /health          — quick liveness (no DB check; used by load balancer)
GET /health/ready    — readiness: checks DB, connectors, optional services
GET /health/deps     — deep dependency status (admin only)
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ...connectors.base.registry import registry
from ...rbac.permissions import Permission, require_permission

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.1.0",
        "connectors": len(registry.ids()),
    }


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    checks: dict[str, Any] = {}
    overall = "ok"

    # Database check
    db_ok = await _check_database()
    checks["database"] = db_ok
    if db_ok["status"] != "ok":
        overall = "degraded"

    # Connectors check
    conn_count = len(registry.ids())
    checks["connectors"] = {"status": "ok", "count": conn_count}
    if conn_count == 0:
        checks["connectors"]["status"] = "warn"
        overall = "degraded"

    # Secrets provider check
    checks["secrets"] = _check_secrets()
    if checks["secrets"]["status"] != "ok":
        overall = "degraded"

    status_code = 200 if overall == "ok" else 503
    return JSONResponse(
        content={"status": overall, "checks": checks, "timestamp": time.time()},
        status_code=status_code,
    )


@router.get("/health/deps")
async def dependency_status(
    _user: dict = Depends(require_permission(Permission.SYSTEM_SETTINGS)),
) -> dict[str, Any]:
    """Full dependency report — admin only."""
    return {
        "database": await _check_database(),
        "connectors": _check_connectors(),
        "secrets": _check_secrets(),
        "vault": _check_vault(),
        "prometheus": _check_prometheus(),
    }


async def _check_database() -> dict[str, Any]:
    try:
        from ...db.base import get_async_session
        async with get_async_session() as session:
            await session.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        return {"status": "ok", "latency_ms": 0}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _check_connectors() -> dict[str, Any]:
    ids = registry.ids()
    return {
        "status": "ok",
        "count": len(ids),
        "connectors": ids,
    }


def _check_secrets() -> dict[str, Any]:
    try:
        from ...vault.provider import get_secrets_provider, FernetSecretsProvider, VaultSecretsProvider
        provider = get_secrets_provider()
        kind = "fernet" if isinstance(provider, FernetSecretsProvider) else "vault"
        test = provider.encrypt("test")
        assert provider.decrypt(test) == "test"
        return {"status": "ok", "backend": kind}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _check_vault() -> dict[str, Any]:
    import os
    if os.environ.get("SECRETS_BACKEND", "fernet").lower() != "vault":
        return {"status": "not_configured", "backend": "fernet"}
    try:
        from ...vault.provider import VaultSecretsProvider
        provider = VaultSecretsProvider()
        return provider.health()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _check_prometheus() -> dict[str, Any]:
    try:
        from ...metrics import REGISTRY, _HAS_PROMETHEUS
        if not _HAS_PROMETHEUS:
            return {"status": "not_installed"}
        return {"status": "ok", "registry": "active" if REGISTRY else "not_initialized"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
