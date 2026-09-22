"""
OAS 3.0 parser and exporter.

OasParser:   Parse an OAS 3.0 spec dict/YAML → ApiProductDef + flow skeleton YAML
OasExporter: Export an ApiProductDef → minimal OAS 3.0 spec dict
FlowToOas:   Convert a flow definition YAML → OAS path + operation objects
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..gateway.api_product import ApiEndpointDef, ApiPlanDef, ApiProductDef


_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


@dataclass
class OasParser:
    @classmethod
    def from_file(cls, path: Path) -> "OasParser":
        return cls()

    def parse(self, oas: dict[str, Any]) -> ApiProductDef:
        info = oas.get("info", {})
        name = info.get("title", "Unnamed API")
        version = info.get("version", "v1")
        servers = oas.get("servers", [{}])
        base_path = servers[0].get("url", "/gw") if servers else "/gw"
        if base_path.startswith("http"):
            from urllib.parse import urlparse
            base_path = urlparse(base_path).path or "/gw"

        endpoints = []
        for path_str, path_item in oas.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() not in _HTTP_METHODS:
                    continue
                flow_id = operation.get("operationId", f"{method}_{path_str.replace('/', '_').strip('_')}")
                security = operation.get("security", oas.get("security", [{}]))
                auth = "api_key"
                if security:
                    first_scheme = list(security[0].keys())[0] if security[0] else "api_key"
                    if "bearer" in first_scheme.lower() or "jwt" in first_scheme.lower():
                        auth = "jwt"
                    elif first_scheme.lower() in ("", "none"):
                        auth = "none"
                endpoints.append(ApiEndpointDef(
                    path=path_str,
                    method=method.upper(),
                    flow_id=flow_id,
                    auth=auth,
                ))

        return ApiProductDef(
            product_id=name.lower().replace(" ", "_"),
            name=name,
            version=version,
            base_path=base_path,
            endpoints=endpoints,
            plans=[ApiPlanDef(name="default")],
        )

    def generate_flow_skeleton(self, oas: dict[str, Any], operation_id: str) -> str:
        """Generate a flow YAML skeleton for a given OAS operation."""
        for path_str, path_item in oas.get("paths", {}).items():
            for method, operation in path_item.items():
                if operation.get("operationId") == operation_id:
                    params = [p["name"] for p in operation.get("parameters", [])]
                    return yaml.dump({
                        "flow_id": operation_id,
                        "name": operation.get("summary", operation_id),
                        "description": f"Implements {method.upper()} {path_str}",
                        "trigger": {
                            "type": "api_gateway",
                            "product_id": "_replace_me_",
                            "path": path_str,
                            "method": method.upper(),
                        },
                        "steps": [
                            {
                                "step_id": "process_request",
                                "type": "transform_script",
                                "config": {
                                    "script": textwrap.dedent(f"""
                                        # Auto-generated from OAS operation: {operation_id}
                                        # Parameters: {', '.join(params) if params else 'none'}
                                        # TODO: implement business logic here
                                        import pandas as pd
                                        result = pd.DataFrame([{{"message": "not implemented"}}])
                                    """).strip(),
                                },
                            }
                        ],
                    }, default_flow_style=False, sort_keys=False)
        return f"# Operation '{operation_id}' not found in OAS spec\n"


class OasExporter:
    def export(self, product: ApiProductDef) -> dict[str, Any]:
        """Export an ApiProductDef to a minimal but valid OAS 3.0 spec."""
        paths: dict[str, Any] = {}
        for ep in product.endpoints:
            path_item = paths.setdefault(ep.path, {})
            op: dict[str, Any] = {
                "operationId": ep.flow_id,
                "summary": f"{ep.method} {ep.path}",
                "tags": [product.name],
                "responses": {
                    "200": {"description": "Success"},
                    "401": {"description": "Unauthorized"},
                    "429": {"description": "Rate limit exceeded"},
                },
            }
            if ep.auth == "api_key":
                op["security"] = [{"ApiKeyAuth": []}]
            elif ep.auth == "jwt":
                op["security"] = [{"BearerAuth": []}]
            path_item[ep.method.lower()] = op

        security_schemes: dict[str, Any] = {}
        auths = {ep.auth for ep in product.endpoints}
        if "api_key" in auths:
            security_schemes["ApiKeyAuth"] = {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            }
        if "jwt" in auths:
            security_schemes["BearerAuth"] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }

        return {
            "openapi": "3.0.3",
            "info": {
                "title": product.name,
                "version": product.version,
                "description": product.description,
            },
            "servers": [{"url": product.base_path}],
            "paths": paths,
            "components": {
                "securitySchemes": security_schemes,
            },
        }

    def to_yaml(self, product: ApiProductDef) -> str:
        return yaml.dump(
            self.export(product),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


class FlowToOas:
    """Derive OAS path+operation from a flow definition that has a trigger.type=api_gateway."""

    def extract_path(self, flow_def: dict[str, Any]) -> dict[str, Any] | None:
        trigger = flow_def.get("trigger", {})
        if trigger.get("type") != "api_gateway":
            return None
        path = trigger.get("path", "/")
        method = trigger.get("method", "GET").lower()
        return {
            path: {
                method: {
                    "operationId": flow_def.get("flow_id"),
                    "summary": flow_def.get("name", flow_def.get("flow_id")),
                    "description": flow_def.get("description", ""),
                    "responses": {"200": {"description": "Success"}},
                }
            }
        }
