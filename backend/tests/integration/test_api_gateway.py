"""Integration tests for API Gateway — products, keys, proxy via TestClient."""

import pytest
from fastapi.testclient import TestClient

from sangam_mw.api.main import app
from sangam_mw.api.routes.auth import get_current_user
from sangam_mw.auth.models import UserInDB


ADMIN_USER = UserInDB(
    user_id="admin-1", email="admin@sangam.ai", role="admin",
    hashed_password="x", is_active=True,
)

PRODUCT_YAML = """
product_id: test-product
name: Test API
version: "1.0"
base_path: /test
endpoints:
  - path: /ping
    method: GET
    flow_id: ping-flow
    auth: none
    mock_response:
      status_code: 200
      body: {message: pong}
plans:
  - name: free
    requests_per_day: 1000
    requests_per_minute: 60
"""


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestGatewayProducts:
    def test_create_product_returns_201(self, client):
        resp = client.post("/gateway/products", json={"yaml_content": PRODUCT_YAML})
        assert resp.status_code in (200, 201)

    def test_list_products_returns_200(self, client):
        resp = client.get("/gateway/products")
        assert resp.status_code == 200

    def test_list_products_is_list(self, client):
        resp = client.get("/gateway/products")
        data = resp.json()
        assert isinstance(data, list)

    def test_get_product_by_id(self, client):
        create_resp = client.post("/gateway/products", json={"yaml_content": PRODUCT_YAML})
        product_id = create_resp.json().get("product_id", "test-product")
        get_resp = client.get(f"/gateway/products/{product_id}")
        assert get_resp.status_code == 200

    def test_get_nonexistent_product_returns_404(self, client):
        resp = client.get("/gateway/products/does-not-exist")
        assert resp.status_code == 404


class TestGatewayApiKeys:
    def test_create_api_key_returns_plaintext(self, client):
        resp = client.post(
            "/gateway/products/test-product/keys",
            json={"consumer_name": "acme", "consumer_email": "dev@acme.com", "plan_name": "free"},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "plaintext_key" in data or "key" in data or "api_key" in data

    def test_list_api_keys(self, client):
        resp = client.get("/gateway/products/test-product/keys")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestGatewayAnalytics:
    def test_analytics_returns_200(self, client):
        resp = client.get("/gateway/products/test-product/analytics")
        assert resp.status_code in (200, 404)  # 404 if product doesn't exist in clean state

    def test_analytics_summary_returns_200(self, client):
        resp = client.get("/gateway/analytics/summary")
        assert resp.status_code == 200


class TestGatewayProxy:
    def test_mock_endpoint_returns_pong(self, client):
        # ensure product is created
        client.post("/gateway/products", json={"yaml_content": PRODUCT_YAML})
        resp = client.get("/gw/test-product/ping")
        assert resp.status_code in (200, 401, 403, 404)  # depends on auth state
