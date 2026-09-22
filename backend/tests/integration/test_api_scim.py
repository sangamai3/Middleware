"""Integration tests for SCIM 2.0 endpoints via TestClient."""

import pytest
from fastapi.testclient import TestClient

from sangam_mw.api.main import app

SCIM_TOKEN = "test-scim-token"
SCIM_HEADERS = {"Authorization": f"Bearer {SCIM_TOKEN}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestScimServiceProviderConfig:
    def test_returns_200(self, client):
        resp = client.get("/scim/v2/ServiceProviderConfig", headers=SCIM_HEADERS)
        assert resp.status_code == 200

    def test_schemas_field_present(self, client):
        resp = client.get("/scim/v2/ServiceProviderConfig", headers=SCIM_HEADERS)
        data = resp.json()
        assert "schemas" in data or "documentationUri" in data


class TestScimSchemas:
    def test_returns_200(self, client):
        resp = client.get("/scim/v2/Schemas", headers=SCIM_HEADERS)
        assert resp.status_code == 200

    def test_user_schema_present(self, client):
        resp = client.get("/scim/v2/Schemas", headers=SCIM_HEADERS)
        data = resp.json()
        resources = data.get("Resources", []) or data.get("schemas", []) or []
        user_schemas = [r for r in resources if "User" in str(r)]
        assert len(user_schemas) >= 1


class TestScimUsers:
    USER_PAYLOAD = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": "jdoe@acme.com",
        "name": {"givenName": "John", "familyName": "Doe"},
        "emails": [{"value": "jdoe@acme.com", "primary": True}],
        "active": True,
    }

    def test_create_user_returns_201(self, client):
        payload = dict(self.USER_PAYLOAD, userName="newuser@acme.com",
                       emails=[{"value": "newuser@acme.com", "primary": True}])
        resp = client.post("/scim/v2/Users", json=payload, headers=SCIM_HEADERS)
        assert resp.status_code == 201

    def test_create_user_returns_id(self, client):
        payload = dict(self.USER_PAYLOAD, userName="idtest@acme.com",
                       emails=[{"value": "idtest@acme.com", "primary": True}])
        resp = client.post("/scim/v2/Users", json=payload, headers=SCIM_HEADERS)
        data = resp.json()
        assert "id" in data

    def test_duplicate_email_returns_409(self, client):
        payload = dict(self.USER_PAYLOAD, userName="dup@acme.com",
                       emails=[{"value": "dup@acme.com", "primary": True}])
        client.post("/scim/v2/Users", json=payload, headers=SCIM_HEADERS)
        resp = client.post("/scim/v2/Users", json=payload, headers=SCIM_HEADERS)
        assert resp.status_code == 409

    def test_list_users_returns_200(self, client):
        resp = client.get("/scim/v2/Users", headers=SCIM_HEADERS)
        assert resp.status_code == 200

    def test_list_users_totalResults_present(self, client):
        resp = client.get("/scim/v2/Users", headers=SCIM_HEADERS)
        data = resp.json()
        assert "totalResults" in data

    def test_get_user_by_id(self, client):
        payload = dict(self.USER_PAYLOAD, userName="gettest@acme.com",
                       emails=[{"value": "gettest@acme.com", "primary": True}])
        create_resp = client.post("/scim/v2/Users", json=payload, headers=SCIM_HEADERS)
        user_id = create_resp.json()["id"]
        get_resp = client.get(f"/scim/v2/Users/{user_id}", headers=SCIM_HEADERS)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == user_id

    def test_get_nonexistent_user_returns_404(self, client):
        resp = client.get("/scim/v2/Users/does-not-exist-xyz", headers=SCIM_HEADERS)
        assert resp.status_code == 404

    def test_delete_user_soft_deletes(self, client):
        payload = dict(self.USER_PAYLOAD, userName="deltest@acme.com",
                       emails=[{"value": "deltest@acme.com", "primary": True}])
        create_resp = client.post("/scim/v2/Users", json=payload, headers=SCIM_HEADERS)
        user_id = create_resp.json()["id"]
        del_resp = client.delete(f"/scim/v2/Users/{user_id}", headers=SCIM_HEADERS)
        assert del_resp.status_code == 204
        get_resp = client.get(f"/scim/v2/Users/{user_id}", headers=SCIM_HEADERS)
        user = get_resp.json()
        assert user.get("active") is False

    def test_missing_token_returns_401(self, client):
        resp = client.get("/scim/v2/Users")
        assert resp.status_code == 401
