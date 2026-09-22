"""
API Gateway management routes.

POST   /gateway/products              Create an API product
GET    /gateway/products              List all API products
GET    /gateway/products/{id}         Get one product
DELETE /gateway/products/{id}         Delete product
POST   /gateway/products/{id}/keys    Issue API key for a consumer
GET    /gateway/products/{id}/keys    List keys for product
DELETE /gateway/keys/{key_id}         Revoke an API key
GET    /gateway/products/{id}/analytics    Usage stats for product
GET    /gateway/analytics/summary          Global summary

POST   /gw/{product_id}/{path:path}   ─┐
GET    /gw/{product_id}/{path:path}   ─┤ Gateway proxy (all inbound API requests)
PUT    /gw/{product_id}/{path:path}   ─┤
PATCH  /gw/{product_id}/{path:path}   ─┤
DELETE /gw/{product_id}/{path:path}   ─┘

POST   /webhooks                      Register webhook subscription
GET    /webhooks                      List subscriptions
DELETE /webhooks/{sub_id}             Unsubscribe
GET    /webhooks/{sub_id}/deliveries  Delivery history
POST   /webhooks/deliveries/{id}/redeliver  Re-deliver

POST   /oas/import                    Import OAS spec → ApiProduct
GET    /oas/{product_id}/export       Export ApiProduct → OAS YAML
POST   /oas/{product_id}/generate-flow/{operation_id}  Generate flow skeleton
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ...gateway.analytics import get_analytics
from ...gateway.api_keys import ApiKeyManager, generate_api_key
from ...gateway.api_product import ApiProductDef, ApiPlanDef, ApiEndpointDef
from ...gateway.proxy import GatewayProxy
from ...gateway.rate_limiter import get_rate_limiter
from ...oas.spec import OasExporter, OasParser
from ...rbac.permissions import Permission, require_permission
from ...webhooks.manager import WebhookManager


router = APIRouter(tags=["gateway"])

_key_manager = ApiKeyManager()
_analytics = get_analytics()
_rate_limiter = get_rate_limiter()
_proxy = GatewayProxy(
    rate_limiter=_rate_limiter,
    key_manager=_key_manager,
    analytics=_analytics,
)
_webhook_manager = WebhookManager()
_oas_parser = OasParser()
_oas_exporter = OasExporter()


# ──────────────────────────────────────────────────────────────────────────────
# Product CRUD
# ──────────────────────────────────────────────────────────────────────────────

class CreateProductRequest(BaseModel):
    name: str
    version: str = "v1"
    base_path: str = ""
    description: str = ""
    endpoints: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    portal_enabled: bool = True


@router.post("/gateway/products", status_code=201)
async def create_product(
    body: CreateProductRequest,
    _user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
) -> dict[str, Any]:
    plans = [ApiPlanDef.from_dict(p) for p in body.plans] or [ApiPlanDef(name="default")]
    endpoints = [ApiEndpointDef.from_dict(e) for e in body.endpoints]
    product = ApiProductDef(
        product_id=body.name.lower().replace(" ", "_"),
        name=body.name,
        version=body.version,
        base_path=body.base_path or f"/gw/{body.name.lower().replace(' ', '-')}",
        description=body.description,
        endpoints=endpoints,
        plans=plans,
        portal_enabled=body.portal_enabled,
    )
    _proxy.register_product(product)
    return {"product_id": product.product_id, "name": product.name, "base_path": product.base_path}


@router.get("/gateway/products")
async def list_products(
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
) -> list[dict[str, Any]]:
    return [
        {
            "product_id": p.product_id,
            "name": p.name,
            "version": p.version,
            "base_path": p.base_path,
            "endpoint_count": len(p.endpoints),
            "plan_count": len(p.plans),
        }
        for p in _proxy.list_products()
    ]


@router.get("/gateway/products/{product_id}")
async def get_product(
    product_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
) -> dict[str, Any]:
    product = _proxy.get_product(product_id)
    if not product:
        raise HTTPException(404, f"Product '{product_id}' not found")
    return product.to_dict()


@router.delete("/gateway/products/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_DELETE)),
) -> None:
    product = _proxy.get_product(product_id)
    if not product:
        raise HTTPException(404, f"Product '{product_id}' not found")
    _proxy._products.pop(product_id, None)


# ──────────────────────────────────────────────────────────────────────────────
# API Key management
# ──────────────────────────────────────────────────────────────────────────────

class IssueKeyRequest(BaseModel):
    consumer_name: str
    consumer_email: str
    plan_name: str = "default"
    scopes: list[str] = []
    expires_at: datetime | None = None


@router.post("/gateway/products/{product_id}/keys", status_code=201)
async def issue_api_key(
    product_id: str,
    body: IssueKeyRequest,
    _user: dict = Depends(require_permission(Permission.CONNECTION_CREATE)),
) -> dict[str, Any]:
    product = _proxy.get_product(product_id)
    if not product:
        raise HTTPException(404, f"Product '{product_id}' not found")
    plaintext, record = _key_manager.create(
        consumer_name=body.consumer_name,
        consumer_email=body.consumer_email,
        product_id=product_id,
        plan_name=body.plan_name,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    return {
        "key_id": record.key_id,
        "api_key": plaintext,
        "consumer_name": record.consumer_name,
        "plan_name": record.plan_name,
        "_note": "Save this key — it will not be shown again.",
    }


@router.get("/gateway/products/{product_id}/keys")
async def list_keys(
    product_id: str,
    _user: dict = Depends(require_permission(Permission.CONNECTION_READ)),
) -> list[dict[str, Any]]:
    return [
        {
            "key_id": r.key_id,
            "consumer_name": r.consumer_name,
            "consumer_email": r.consumer_email,
            "plan_name": r.plan_name,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        }
        for r in _key_manager.list_by_product(product_id)
    ]


@router.delete("/gateway/keys/{key_id}", status_code=204)
async def revoke_key(
    key_id: str,
    _user: dict = Depends(require_permission(Permission.CONNECTION_DELETE)),
) -> None:
    if not _key_manager.revoke(key_id):
        raise HTTPException(404, f"Key '{key_id}' not found")


# ──────────────────────────────────────────────────────────────────────────────
# Gateway proxy routes (catch-all for inbound API traffic)
# ──────────────────────────────────────────────────────────────────────────────

@router.api_route("/gw/{product_id}/{endpoint_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def gateway_proxy(
    request: Request,
    product_id: str,
    endpoint_path: str,
) -> Any:
    return await _proxy.handle(request, product_id, endpoint_path)


# ──────────────────────────────────────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/gateway/products/{product_id}/analytics")
async def product_analytics(
    product_id: str,
    _user: dict = Depends(require_permission(Permission.EXECUTION_READ)),
) -> dict[str, Any]:
    product = _proxy.get_product(product_id)
    if not product:
        raise HTTPException(404, f"Product '{product_id}' not found")
    return {
        "product_id": product_id,
        "endpoints": _analytics.get_product_stats(product_id),
        "top_consumers": _analytics.get_top_consumers(product_id),
    }


@router.get("/gateway/analytics/summary")
async def analytics_summary(
    _user: dict = Depends(require_permission(Permission.EXECUTION_READ)),
) -> dict[str, Any]:
    return _analytics.summary()


# ──────────────────────────────────────────────────────────────────────────────
# Webhooks
# ──────────────────────────────────────────────────────────────────────────────

class WebhookSubscribeRequest(BaseModel):
    consumer_name: str
    url: str
    events: list[str] = ["*"]
    secret: str | None = None


@router.post("/webhooks", status_code=201)
async def create_webhook(
    body: WebhookSubscribeRequest,
    _user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
) -> dict[str, Any]:
    sub = _webhook_manager.subscribe(
        consumer_name=body.consumer_name,
        url=body.url,
        events=body.events,
        secret=body.secret,
    )
    return {
        "sub_id": sub.sub_id,
        "consumer_name": sub.consumer_name,
        "url": sub.url,
        "events": sub.events,
        "signing_secret": sub.secret,
        "_note": "Save the signing_secret — used to verify X-SangamMW-Signature on deliveries.",
    }


@router.get("/webhooks")
async def list_webhooks(
    consumer_name: str | None = None,
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
) -> list[dict[str, Any]]:
    subs = _webhook_manager.list_subscriptions(consumer_name)
    return [
        {
            "sub_id": s.sub_id,
            "consumer_name": s.consumer_name,
            "url": s.url,
            "events": s.events,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat(),
        }
        for s in subs
    ]


@router.delete("/webhooks/{sub_id}", status_code=204)
async def delete_webhook(
    sub_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_DELETE)),
) -> None:
    if not _webhook_manager.unsubscribe(sub_id):
        raise HTTPException(404, f"Subscription '{sub_id}' not found")


@router.get("/webhooks/{sub_id}/deliveries")
async def webhook_deliveries(
    sub_id: str,
    _user: dict = Depends(require_permission(Permission.EXECUTION_READ)),
) -> list[dict[str, Any]]:
    deliveries = _webhook_manager.get_delivery_history(sub_id)
    return [
        {
            "delivery_id": d.delivery_id,
            "event_type": d.event_type,
            "status": d.status,
            "attempts": d.attempts,
            "response_code": d.response_code,
            "last_attempt_at": d.last_attempt_at.isoformat() if d.last_attempt_at else None,
            "error": d.error,
        }
        for d in deliveries
    ]


@router.post("/webhooks/deliveries/{delivery_id}/redeliver", status_code=202)
async def redeliver_webhook(
    delivery_id: str,
    _user: dict = Depends(require_permission(Permission.EXECUTION_TRIGGER)),
) -> dict[str, Any]:
    delivery = await _webhook_manager.redeliver(delivery_id)
    if not delivery:
        raise HTTPException(404, f"Delivery '{delivery_id}' not found")
    return {
        "delivery_id": delivery.delivery_id,
        "status": delivery.status,
        "attempts": delivery.attempts,
    }


# ──────────────────────────────────────────────────────────────────────────────
# OAS import / export
# ──────────────────────────────────────────────────────────────────────────────

class OasImportRequest(BaseModel):
    spec: dict[str, Any]


@router.post("/oas/import", status_code=201)
async def import_oas(
    body: OasImportRequest,
    _user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
) -> dict[str, Any]:
    product = _oas_parser.parse(body.spec)
    _proxy.register_product(product)
    return {
        "product_id": product.product_id,
        "name": product.name,
        "endpoints_imported": len(product.endpoints),
    }


@router.get("/oas/{product_id}/export", response_class=PlainTextResponse)
async def export_oas(
    product_id: str,
    _user: dict = Depends(require_permission(Permission.FLOW_READ)),
) -> str:
    product = _proxy.get_product(product_id)
    if not product:
        raise HTTPException(404, f"Product '{product_id}' not found")
    return _oas_exporter.to_yaml(product)


@router.post("/oas/{product_id}/generate-flow/{operation_id}")
async def generate_flow_from_oas(
    product_id: str,
    operation_id: str,
    body: OasImportRequest,
    _user: dict = Depends(require_permission(Permission.FLOW_CREATE)),
) -> dict[str, Any]:
    flow_yaml = _oas_parser.generate_flow_skeleton(body.spec, operation_id)
    return {
        "product_id": product_id,
        "operation_id": operation_id,
        "flow_yaml": flow_yaml,
    }
