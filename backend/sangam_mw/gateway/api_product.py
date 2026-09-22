"""
API Product model — YAML-defined API products with endpoints, plans, and auth config.

api_product:
  name: Customer Data API
  version: v1
  base_path: /gw/customer-api
  endpoints:
    - path: /customers
      method: GET
      flow_id: salesforce-customer-query
      auth: api_key
      rate_limit_plan: pro
      cache_ttl_seconds: 60
  plans:
    - name: free
      requests_per_day: 1000
      requests_per_minute: 10
    - name: pro
      requests_per_day: 50000
      requests_per_minute: 500
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ApiPlanDef:
    name: str
    requests_per_day: int = 10_000
    requests_per_minute: int = 100

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ApiPlanDef":
        return cls(
            name=d["name"],
            requests_per_day=int(d.get("requests_per_day", 10_000)),
            requests_per_minute=int(d.get("requests_per_minute", 100)),
        )


@dataclass
class ApiEndpointDef:
    path: str
    method: str
    flow_id: str
    auth: str = "api_key"
    rate_limit_plan: str = "default"
    cache_ttl_seconds: int = 0
    request_transform: dict[str, Any] = field(default_factory=dict)
    response_transform: dict[str, Any] = field(default_factory=dict)
    ip_allowlist: list[str] = field(default_factory=list)
    mock_response: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ApiEndpointDef":
        return cls(
            path=d["path"],
            method=d.get("method", "GET").upper(),
            flow_id=d.get("flow_id", ""),
            auth=d.get("auth", "api_key"),
            rate_limit_plan=d.get("rate_limit_plan", "default"),
            cache_ttl_seconds=int(d.get("cache_ttl_seconds", 0)),
            request_transform=d.get("request_transform", {}),
            response_transform=d.get("response_transform", {}),
            ip_allowlist=d.get("ip_allowlist", []),
            mock_response=d.get("mock_response"),
        )

    @property
    def route_key(self) -> str:
        return f"{self.method}:{self.path}"


@dataclass
class ApiProductDef:
    product_id: str
    name: str
    version: str
    base_path: str
    description: str = ""
    endpoints: list[ApiEndpointDef] = field(default_factory=list)
    plans: list[ApiPlanDef] = field(default_factory=list)
    portal_enabled: bool = True
    oas_spec_path: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ApiProductDef":
        raw = d.get("api_product", d)
        plans = [ApiPlanDef.from_dict(p) for p in raw.get("plans", [])]
        if not plans:
            plans = [ApiPlanDef(name="default")]
        endpoints = [ApiEndpointDef.from_dict(e) for e in raw.get("endpoints", [])]
        name = raw["name"]
        return cls(
            product_id=raw.get("product_id", name.lower().replace(" ", "_")),
            name=name,
            version=raw.get("version", "v1"),
            base_path=raw.get("base_path", f"/gw/{name.lower().replace(' ', '-')}"),
            description=raw.get("description", ""),
            endpoints=endpoints,
            plans=plans,
            portal_enabled=raw.get("portal", {}).get("enabled", True),
            oas_spec_path=raw.get("portal", {}).get("oas_spec", ""),
        )

    def get_plan(self, plan_name: str) -> ApiPlanDef:
        for p in self.plans:
            if p.name == plan_name:
                return p
        return self.plans[0] if self.plans else ApiPlanDef(name="default")

    def match_endpoint(self, method: str, path: str) -> ApiEndpointDef | None:
        key = f"{method.upper()}:{path}"
        for ep in self.endpoints:
            if ep.route_key == key:
                return ep
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_product": {
                "product_id": self.product_id,
                "name": self.name,
                "version": self.version,
                "base_path": self.base_path,
                "description": self.description,
                "endpoints": [
                    {
                        "path": ep.path,
                        "method": ep.method,
                        "flow_id": ep.flow_id,
                        "auth": ep.auth,
                        "rate_limit_plan": ep.rate_limit_plan,
                        "cache_ttl_seconds": ep.cache_ttl_seconds,
                    }
                    for ep in self.endpoints
                ],
                "plans": [
                    {
                        "name": p.name,
                        "requests_per_day": p.requests_per_day,
                        "requests_per_minute": p.requests_per_minute,
                    }
                    for p in self.plans
                ],
                "portal": {
                    "enabled": self.portal_enabled,
                    "oas_spec": self.oas_spec_path,
                },
            }
        }


def load_product_yaml(path: Path) -> ApiProductDef:
    raw = yaml.safe_load(path.read_text())
    return ApiProductDef.from_dict(raw)
