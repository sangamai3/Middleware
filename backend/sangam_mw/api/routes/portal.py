"""
Developer portal — public-facing API for consumers to discover and access APIs.

GET  /portal/products              List published API products (no auth required)
GET  /portal/products/{id}         Get product overview + endpoints
GET  /portal/products/{id}/spec    Download OAS 3.0 spec (YAML)
POST /portal/products/{id}/register   Self-register for access (issues a free-tier key)
GET  /portal/products/{id}/usage      Consumer's own usage (requires their API key)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .gateway import _proxy, _key_manager, _analytics, _oas_exporter, _webhook_manager


router = APIRouter(prefix="/portal", tags=["developer-portal"])


@router.get("/products")
async def portal_list_products() -> list[dict[str, Any]]:
    """Public listing of all available API products."""
    return [
        {
            "product_id": p.product_id,
            "name": p.name,
            "version": p.version,
            "description": p.description,
            "endpoint_count": len(p.endpoints),
            "plans": [
                {
                    "name": plan.name,
                    "requests_per_day": plan.requests_per_day,
                }
                for plan in p.plans
            ],
        }
        for p in _proxy.list_products()
        if p.portal_enabled
    ]


@router.get("/products/{product_id}")
async def portal_get_product(product_id: str) -> dict[str, Any]:
    """Get product details including endpoint docs."""
    product = _proxy.get_product(product_id)
    if not product or not product.portal_enabled:
        raise HTTPException(404, "Product not found")
    return {
        "product_id": product.product_id,
        "name": product.name,
        "version": product.version,
        "description": product.description,
        "base_path": product.base_path,
        "endpoints": [
            {
                "method": ep.method,
                "path": ep.path,
                "auth": ep.auth,
                "cache_ttl_seconds": ep.cache_ttl_seconds,
                "is_mock": ep.mock_response is not None,
            }
            for ep in product.endpoints
        ],
        "plans": [
            {
                "name": p.name,
                "requests_per_day": p.requests_per_day,
                "requests_per_minute": p.requests_per_minute,
            }
            for p in product.plans
        ],
    }


@router.get("/products/{product_id}/spec", response_class=PlainTextResponse)
async def portal_get_spec(product_id: str) -> str:
    """Download the OAS 3.0 spec for this product."""
    product = _proxy.get_product(product_id)
    if not product or not product.portal_enabled:
        raise HTTPException(404, "Product not found")
    return _oas_exporter.to_yaml(product)


class SelfRegisterRequest(BaseModel):
    name: str
    email: str
    plan_name: str = "free"
    use_case: str = ""


@router.post("/products/{product_id}/register", status_code=201)
async def portal_register(
    product_id: str,
    body: SelfRegisterRequest,
) -> dict[str, Any]:
    """
    Consumer self-registers for a product.
    Defaults to the first/free plan.
    Returns an API key that can be used immediately.
    """
    product = _proxy.get_product(product_id)
    if not product or not product.portal_enabled:
        raise HTTPException(404, "Product not found")

    plan_names = {p.name for p in product.plans}
    plan_name = body.plan_name if body.plan_name in plan_names else product.plans[0].name

    plaintext, record = _key_manager.create(
        consumer_name=body.name,
        consumer_email=body.email,
        product_id=product_id,
        plan_name=plan_name,
    )
    return {
        "api_key": plaintext,
        "key_id": record.key_id,
        "plan": plan_name,
        "product": product.name,
        "_note": "Save this key — it will not be shown again. Pass it as X-API-Key header.",
    }


@router.get("/products/{product_id}/usage")
async def portal_consumer_usage(
    product_id: str,
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> dict[str, Any]:
    """Consumer checks their own usage stats using their API key."""
    record = _key_manager.validate(x_api_key)
    if not record or record.product_id != product_id:
        raise HTTPException(403, "Invalid API key for this product")

    product = _proxy.get_product(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    plan = product.get_plan(record.plan_name)
    top = _analytics.get_top_consumers(product_id)
    my_requests = next(
        (item["total_requests"] for item in top if item["consumer_key"] == record.key_id), 0
    )

    return {
        "consumer": record.consumer_name,
        "plan": record.plan_name,
        "key_id": record.key_id,
        "limits": {
            "requests_per_day": plan.requests_per_day,
            "requests_per_minute": plan.requests_per_minute,
        },
        "usage": {
            "total_requests": my_requests,
        },
    }
