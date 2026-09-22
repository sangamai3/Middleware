"""
Core API Gateway proxy.

Handles inbound HTTP requests routed to /gw/{product_id}/{path}:
  1. Look up ApiProduct definition
  2. Match endpoint by method + path
  3. Validate API key (or JWT)
  4. Check rate limit
  5. Apply request transform
  6. Invoke flow (sync) or return mock
  7. Apply response transform
  8. Record analytics
  9. Return HTTP response
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .analytics import GatewayAnalytics
from .api_keys import ApiKeyManager, ApiKeyRecord
from .api_product import ApiEndpointDef, ApiProductDef
from .rate_limiter import RateLimiter


class GatewayProxy:
    def __init__(
        self,
        rate_limiter: RateLimiter,
        key_manager: ApiKeyManager,
        analytics: GatewayAnalytics,
    ) -> None:
        self.rate_limiter = rate_limiter
        self.key_manager = key_manager
        self.analytics = analytics
        self._products: dict[str, ApiProductDef] = {}

    def register_product(self, product: ApiProductDef) -> None:
        self._products[product.product_id] = product

    def get_product(self, product_id: str) -> ApiProductDef | None:
        return self._products.get(product_id)

    def list_products(self) -> list[ApiProductDef]:
        return list(self._products.values())

    async def handle(self, request: Request, product_id: str, endpoint_path: str) -> JSONResponse:
        start_ms = time.monotonic() * 1000
        product = self._products.get(product_id)
        if not product:
            raise HTTPException(404, f"API product '{product_id}' not found")

        full_path = f"/{endpoint_path}" if not endpoint_path.startswith("/") else endpoint_path
        endpoint = product.match_endpoint(request.method, full_path)
        if not endpoint:
            raise HTTPException(404, f"No endpoint {request.method} {full_path} in product '{product_id}'")

        consumer_key, key_record = await self._authenticate(request, endpoint, product)
        plan = product.get_plan(key_record.plan_name if key_record else endpoint.rate_limit_plan)

        rl_result = self.rate_limiter.check(
            consumer_key=consumer_key,
            requests_per_minute=plan.requests_per_minute,
            requests_per_day=plan.requests_per_day,
        )
        if not rl_result.allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "retry_after": rl_result.retry_after,
                    "limit": rl_result.limit,
                },
                headers=rl_result.headers(),
            )

        if endpoint.mock_response is not None:
            response_data = endpoint.mock_response
        else:
            response_data = await self._invoke_flow(request, endpoint)

        response_data = self._apply_transform(response_data, endpoint.response_transform)

        latency_ms = time.monotonic() * 1000 - start_ms
        self.analytics.record(
            product_id=product_id,
            endpoint_path=full_path,
            method=request.method,
            consumer_key=consumer_key,
            status_code=200,
            latency_ms=latency_ms,
        )

        headers = rl_result.headers()
        headers["X-Response-Time"] = f"{latency_ms:.1f}ms"
        return JSONResponse(content=response_data, headers=headers)

    async def _authenticate(
        self, request: Request, endpoint: ApiEndpointDef, product: ApiProductDef
    ) -> tuple[str, ApiKeyRecord | None]:
        if endpoint.auth == "none":
            return "anonymous", None

        if endpoint.auth in ("api_key", "apikey"):
            key = (
                request.headers.get("X-API-Key")
                or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                or request.query_params.get("api_key", "")
            )
            if not key:
                raise HTTPException(401, "API key required. Pass X-API-Key header or ?api_key=")
            record = self.key_manager.validate(key)
            if not record:
                raise HTTPException(403, "Invalid or expired API key")
            if record.product_id != product.product_id:
                raise HTTPException(403, "API key not authorized for this product")
            if endpoint.ip_allowlist:
                client_ip = request.client.host if request.client else ""
                if client_ip not in endpoint.ip_allowlist:
                    raise HTTPException(403, f"IP {client_ip} not in allowlist")
            return record.key_id, record

        if endpoint.auth == "jwt":
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise HTTPException(401, "JWT bearer token required")
            return f"jwt:{auth[7:20]}", None

        return "open", None

    async def _invoke_flow(self, request: Request, endpoint: ApiEndpointDef) -> Any:
        """
        Invoke the flow engine synchronously.
        Passes query params + body as flow parameters.
        """
        params: dict[str, Any] = dict(request.query_params)
        params.update(dict(request.path_params))
        try:
            body_bytes = await request.body()
            if body_bytes:
                params["_body"] = json.loads(body_bytes)
        except Exception:
            pass

        req_params = self._apply_transform(params, endpoint.request_transform)

        return {
            "flow_id": endpoint.flow_id,
            "status": "invoked",
            "parameters": req_params,
            "_note": "flow engine integration: POST /api/v1/executions with these parameters",
        }

    def _apply_transform(self, data: Any, transform: dict[str, Any]) -> Any:
        """
        Apply a declarative field rename/filter transform.
        Supports: rename_fields, include_fields, exclude_fields, wrap_key.
        """
        if not transform or not isinstance(data, dict):
            return data

        result = dict(data)

        if renames := transform.get("rename_fields", {}):
            for old_name, new_name in renames.items():
                if old_name in result:
                    result[new_name] = result.pop(old_name)

        if include := transform.get("include_fields"):
            result = {k: v for k, v in result.items() if k in include}

        if exclude := transform.get("exclude_fields", []):
            for key in exclude:
                result.pop(key, None)

        if wrap_key := transform.get("wrap_key"):
            result = {wrap_key: result}

        return result
