"""Unit tests for the GatewayProxy — auth transforms and rate limiting."""

from unittest.mock import MagicMock

import pytest

from sangam_mw.gateway.api_keys import ApiKeyManager
from sangam_mw.gateway.api_product import ApiEndpointDef, ApiPlanDef, ApiProductDef
from sangam_mw.gateway.analytics import GatewayAnalytics
from sangam_mw.gateway.proxy import GatewayProxy
from sangam_mw.gateway.rate_limiter import RateLimiter, RateLimitResult


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_endpoint(**kwargs) -> ApiEndpointDef:
    defaults = dict(
        path="/data",
        method="GET",
        flow_id="flow-1",
        auth="none",
        rate_limit_plan="default",
        cache_ttl_seconds=0,
        request_transform={},
        response_transform={},
        ip_allowlist=[],
        mock_response=None,
    )
    defaults.update(kwargs)
    return ApiEndpointDef(**defaults)


def _make_proxy() -> GatewayProxy:
    return GatewayProxy(RateLimiter(), ApiKeyManager(), GatewayAnalytics())


# ── _apply_transform ──────────────────────────────────────────────────────────

class TestApplyTransform:
    def test_rename_fields(self):
        proxy = _make_proxy()
        data = {"old_name": "value", "other": "x"}
        result = proxy._apply_transform(data, {"rename_fields": {"old_name": "new_name"}})
        assert "new_name" in result
        assert "old_name" not in result
        assert result["other"] == "x"

    def test_include_fields(self):
        proxy = _make_proxy()
        data = {"a": 1, "b": 2, "c": 3}
        result = proxy._apply_transform(data, {"include_fields": ["a", "c"]})
        assert set(result.keys()) == {"a", "c"}

    def test_exclude_fields(self):
        proxy = _make_proxy()
        data = {"a": 1, "b": 2, "secret": "hidden"}
        result = proxy._apply_transform(data, {"exclude_fields": ["secret"]})
        assert "secret" not in result
        assert "a" in result

    def test_wrap_key(self):
        proxy = _make_proxy()
        data = {"items": [1, 2, 3]}
        result = proxy._apply_transform(data, {"wrap_key": "response"})
        assert "response" in result
        assert result["response"]["items"] == [1, 2, 3]

    def test_empty_transform_is_identity(self):
        proxy = _make_proxy()
        data = {"x": 42}
        assert proxy._apply_transform(data, {}) == data

    def test_non_dict_data_returns_as_is(self):
        proxy = _make_proxy()
        # Non-dict data passes through unchanged even with transforms
        result = proxy._apply_transform([1, 2, 3], {"rename_fields": {"a": "b"}})
        assert result == [1, 2, 3]

    def test_rename_then_include(self):
        proxy = _make_proxy()
        data = {"a": 1, "b": 2}
        result = proxy._apply_transform(data, {
            "rename_fields": {"a": "alpha"},
            "include_fields": ["alpha"],
        })
        assert set(result.keys()) == {"alpha"}
        assert result["alpha"] == 1


# ── register_product / get_product ───────────────────────────────────────────

class TestProductRegistry:
    def test_register_and_retrieve(self):
        proxy = _make_proxy()
        product = ApiProductDef(
            product_id="p1", name="Test", version="1.0", base_path="/t",
            endpoints=[], plans=[],
        )
        proxy.register_product(product)
        assert proxy.get_product("p1") is product

    def test_get_missing_returns_none(self):
        proxy = _make_proxy()
        assert proxy.get_product("no-such") is None

    def test_list_products(self):
        proxy = _make_proxy()
        p1 = ApiProductDef("p1", "A", "1", "/a", [], [])
        p2 = ApiProductDef("p2", "B", "1", "/b", [], [])
        proxy.register_product(p1)
        proxy.register_product(p2)
        assert len(proxy.list_products()) == 2
