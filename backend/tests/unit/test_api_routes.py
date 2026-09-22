"""HTTP tests for platform auth and connector routes."""

from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sangam_mw.api.auth import create_access_token, get_current_user
from sangam_mw.api.main import app
from sangam_mw.config import get_settings
from sangam_mw.db.base import get_session


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_connectors_require_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/connectors/")
    assert resp.status_code == 401


def test_me_with_valid_jwt(client: TestClient) -> None:
    token = create_access_token({"sub": "user-1", "email": "dev@sangam.ai"})
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "dev@sangam.ai"


def test_google_login_requires_client_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    get_settings.cache_clear()
    resp = client.get(
        "/api/v1/auth/google/login",
        params={"redirect_uri": "http://localhost:5173/callback"},
    )
    assert resp.status_code == 500


def test_google_login_returns_url(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    get_settings.cache_clear()
    resp = client.get(
        "/api/v1/auth/google/login",
        params={"redirect_uri": "http://localhost:5173/callback", "state": "abc"},
    )
    assert resp.status_code == 200
    url = resp.json()["authorization_url"]
    assert "accounts.google.com" in url
    assert "cid.apps.googleusercontent.com" in url


def test_google_callback_issues_jwt(client: TestClient) -> None:
    class FakeUser:
        user_id = "gid"
        email = "dev@sangam.ai"
        name = "Dev"
        role = "developer"
        picture = None

    async def fake_exchange(code: str, redirect_uri: str) -> dict:
        return {"id": "gid", "email": "dev@sangam.ai", "name": "Dev"}

    async def fake_upsert(session: object, info: dict) -> FakeUser:
        return FakeUser()

    async def fake_session() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    app.dependency_overrides[get_session] = fake_session
    with (
        patch("sangam_mw.api.routes.auth.exchange_google_code", fake_exchange),
        patch("sangam_mw.api.routes.auth.upsert_google_user", fake_upsert),
    ):
        resp = client.post(
            "/api/v1/auth/google/callback",
            json={"code": "ok", "redirect_uri": "http://localhost:5173/callback"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "dev@sangam.ai"
    assert body["access_token"]


def test_list_connectors_authenticated(client: TestClient) -> None:
    async def fake_user() -> dict:
        return {"sub": "u1", "email": "dev@sangam.ai"}

    app.dependency_overrides[get_current_user] = fake_user
    resp = client.get("/api/v1/connectors/")
    assert resp.status_code == 200
    ids = [c["connector_id"] for c in resp.json()]
    assert "file" in ids


def test_file_connector_test_validates_schema(client: TestClient, tmp_path: Path) -> None:
    async def fake_user() -> dict:
        return {"sub": "u1"}

    app.dependency_overrides[get_current_user] = fake_user
    missing = client.post("/api/v1/connectors/file/test", json={"config": {}})
    assert missing.status_code == 422

    ok = client.post(
        "/api/v1/connectors/file/test",
        json={"config": {"base_path": str(tmp_path)}},
    )
    assert ok.status_code == 200
    assert ok.json()["success"] is True


def test_unknown_connector(client: TestClient) -> None:
    async def fake_user() -> dict:
        return {"sub": "u1"}

    app.dependency_overrides[get_current_user] = fake_user
    resp = client.get("/api/v1/connectors/not-a-connector")
    assert resp.status_code == 404
