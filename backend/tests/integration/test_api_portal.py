"""Integration tests for the developer portal (public) endpoints."""

import pytest
from fastapi.testclient import TestClient

from sangam_mw.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestPortalProducts:
    def test_list_public_returns_200(self, client):
        resp = client.get("/portal/products")
        assert resp.status_code == 200

    def test_list_public_is_list(self, client):
        resp = client.get("/portal/products")
        assert isinstance(resp.json(), list)

    def test_get_nonexistent_product_404(self, client):
        resp = client.get("/portal/products/no-such-product")
        assert resp.status_code == 404

    def test_get_product_spec_nonexistent_404(self, client):
        resp = client.get("/portal/products/no-such-product/spec")
        assert resp.status_code == 404

    def test_register_nonexistent_product_404(self, client):
        resp = client.post(
            "/portal/products/no-such-product/register",
            json={"consumer_name": "test", "consumer_email": "t@t.com"},
        )
        assert resp.status_code == 404

    def test_usage_requires_api_key(self, client):
        resp = client.get("/portal/products/no-such-product/usage")
        assert resp.status_code in (401, 403, 404)
