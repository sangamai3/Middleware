"""Unit tests for connector auth handlers."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sangam_mw.connectors.base.auth import (
    APIKeyHandler,
    BasicAuthHandler,
    NoAuthHandler,
    OAuth2Handler,
    ServiceAccountHandler,
    get_auth_handler,
    parse_token_expiry,
)
from sangam_mw.connectors.base.errors import AuthenticationError
from sangam_mw.connectors.base.metadata import AuthType


class TestAPIKeyHandler:
    def test_bearer_header_default(self) -> None:
        applied = APIKeyHandler().apply({"api_key": "secret-key"})
        assert applied.headers["Authorization"] == "Bearer secret-key"

    def test_query_location(self) -> None:
        applied = APIKeyHandler().apply(
            {"api_key": "k", "api_key_in": "query", "api_key_param": "key"}
        )
        assert applied.query == {"key": "k"}
        assert applied.headers == {}

    def test_missing_key(self) -> None:
        with pytest.raises(AuthenticationError, match="api_key"):
            APIKeyHandler().apply({})


class TestBasicAuthHandler:
    def test_username_password(self) -> None:
        applied = BasicAuthHandler().apply({"username": "u", "password": "p"})
        assert applied.basic_auth == ("u", "p")

    def test_missing_username(self) -> None:
        with pytest.raises(AuthenticationError, match="username"):
            BasicAuthHandler().apply({"password": "p"})


class TestServiceAccountHandler:
    def test_json_key_dict(self) -> None:
        applied = ServiceAccountHandler().apply(
            {"json_key": {"type": "service_account", "project_id": "p"}}
        )
        assert applied.service_account is not None
        assert applied.service_account["project_id"] == "p"

    def test_json_key_path(self, tmp_path: Path) -> None:
        path = tmp_path / "sa.json"
        path.write_text('{"client_email": "svc@example.com"}', encoding="utf-8")
        applied = ServiceAccountHandler().apply({"json_key_path": str(path)})
        assert applied.service_account is not None
        assert applied.service_account["client_email"] == "svc@example.com"

    def test_missing(self) -> None:
        with pytest.raises(AuthenticationError, match="json_key"):
            ServiceAccountHandler().apply({})


class TestOAuth2Handler:
    def test_apply_bearer(self) -> None:
        applied = OAuth2Handler().apply({"access_token": "tok"})
        assert applied.headers["Authorization"] == "Bearer tok"

    def test_apply_missing_token(self) -> None:
        with pytest.raises(AuthenticationError, match="access_token"):
            OAuth2Handler().apply({})

    def test_pkce_challenge_is_s256(self) -> None:
        import base64
        import hashlib

        pair = OAuth2Handler().generate_pkce()
        digest = hashlib.sha256(pair.verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert pair.challenge == expected
        assert pair.method == "S256"

    def test_authorization_url_includes_pkce(self) -> None:
        handler = OAuth2Handler()
        pkce = handler.generate_pkce()
        url = handler.authorization_url(
            authorize_url="https://example.com/authorize",
            client_id="cid",
            redirect_uri="https://app/callback",
            scopes=["read", "write"],
            state="xyz",
            pkce=pkce,
        )
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "scope=read+write" in url or "scope=read%20write" in url

    def test_needs_refresh_within_buffer(self) -> None:
        handler = OAuth2Handler()
        now = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
        soon = now + timedelta(seconds=30)
        assert handler.needs_refresh(soon, now=now) is True
        later = now + timedelta(hours=1)
        assert handler.needs_refresh(later, now=now) is False
        assert handler.needs_refresh(None, now=now) is False

    @pytest.mark.asyncio
    async def test_refresh_updates_access_token(self) -> None:
        handler = OAuth2Handler()
        payload = {
            "access_token": "new-token",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value=payload)
        fake_client = MagicMock()
        fake_client.post = AsyncMock(return_value=response)
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=None)

        with patch("sangam_mw.connectors.base.auth.httpx.AsyncClient", return_value=fake_client):
            updated = await handler.refresh(
                {
                    "client_id": "cid",
                    "client_secret": "sec",
                    "refresh_token": "old-refresh",
                    "token_url": "https://example.com/token",
                    "access_token": "old",
                }
            )
        assert updated["access_token"] == "new-token"
        assert updated["refresh_token"] == "new-refresh"
        assert updated["token_expires_at"] is not None

    @pytest.mark.asyncio
    async def test_refresh_missing_fields(self) -> None:
        with pytest.raises(AuthenticationError, match="refresh_token"):
            await OAuth2Handler().refresh({"access_token": "x"})


class TestFactoryAndExpiry:
    def test_get_auth_handler_maps_types(self) -> None:
        assert isinstance(get_auth_handler(AuthType.NONE), NoAuthHandler)
        assert isinstance(get_auth_handler(AuthType.API_KEY), APIKeyHandler)
        assert isinstance(get_auth_handler(AuthType.BASIC), BasicAuthHandler)
        assert isinstance(get_auth_handler(AuthType.OAUTH2), OAuth2Handler)
        assert isinstance(get_auth_handler(AuthType.SERVICE_ACCOUNT), ServiceAccountHandler)

    def test_parse_token_expiry(self) -> None:
        dt = parse_token_expiry("2026-09-21T12:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert parse_token_expiry(None) is None
        from_int = parse_token_expiry(1_000_000_000)
        assert from_int is not None
