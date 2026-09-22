"""Connector auth handlers — one class per AuthType.

Connectors call `get_auth_handler(metadata.auth_type).apply(handle.config)`
to obtain HTTP headers / basic auth / service-account JSON. The framework
owns PKCE, token refresh, and credential presence checks.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from .errors import AuthenticationError
from .metadata import AuthType

_OAUTH_REFRESH_BUFFER_SECONDS = 60


@dataclass(frozen=True)
class AppliedAuth:
    headers: dict[str, str]
    query: dict[str, str]
    basic_auth: tuple[str, str] | None
    service_account: dict[str, Any] | None


@dataclass(frozen=True)
class PKCEPair:
    verifier: str
    challenge: str
    method: str = "S256"


class AuthHandler:
    auth_type: AuthType = AuthType.NONE

    def apply(self, config: dict[str, Any]) -> AppliedAuth:
        return AppliedAuth(headers={}, query={}, basic_auth=None, service_account=None)


class NoAuthHandler(AuthHandler):
    auth_type = AuthType.NONE


class APIKeyHandler(AuthHandler):
    auth_type = AuthType.API_KEY

    def apply(self, config: dict[str, Any]) -> AppliedAuth:
        key = config.get("api_key") or config.get("token")
        if not key:
            raise AuthenticationError("Missing api_key")
        header = str(config.get("api_key_header") or "Authorization")
        prefix = str(config.get("api_key_prefix", "Bearer"))
        value = f"{prefix} {key}".strip() if prefix else str(key)
        location = str(config.get("api_key_in") or "header")
        if location == "query":
            param = str(config.get("api_key_param") or "api_key")
            return AppliedAuth(
                headers={}, query={param: str(key)}, basic_auth=None, service_account=None
            )
        return AppliedAuth(headers={header: value}, query={}, basic_auth=None, service_account=None)


class BasicAuthHandler(AuthHandler):
    auth_type = AuthType.BASIC

    def apply(self, config: dict[str, Any]) -> AppliedAuth:
        username = config.get("username")
        if not username:
            raise AuthenticationError("Missing username")
        password = str(config.get("password") or "")
        return AppliedAuth(
            headers={},
            query={},
            basic_auth=(str(username), password),
            service_account=None,
        )


class ServiceAccountHandler(AuthHandler):
    auth_type = AuthType.SERVICE_ACCOUNT

    def apply(self, config: dict[str, Any]) -> AppliedAuth:
        key_data = _load_service_account(config)
        return AppliedAuth(headers={}, query={}, basic_auth=None, service_account=key_data)


class OAuth2Handler(AuthHandler):
    auth_type = AuthType.OAUTH2

    def apply(self, config: dict[str, Any]) -> AppliedAuth:
        token = config.get("access_token")
        if not token:
            raise AuthenticationError("Missing access_token")
        token_type = str(config.get("token_type") or "Bearer")
        return AppliedAuth(
            headers={"Authorization": f"{token_type} {token}"},
            query={},
            basic_auth=None,
            service_account=None,
        )

    def generate_pkce(self) -> PKCEPair:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return PKCEPair(verifier=verifier, challenge=challenge)

    def authorization_url(
        self,
        *,
        authorize_url: str,
        client_id: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
        state: str = "",
        pkce: PKCEPair | None = None,
        extra: dict[str, str] | None = None,
    ) -> str:
        params: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
        }
        if scopes:
            params["scope"] = " ".join(scopes)
        if state:
            params["state"] = state
        if pkce:
            params["code_challenge"] = pkce.challenge
            params["code_challenge_method"] = pkce.method
        if extra:
            params.update(extra)
        return f"{authorize_url}?{urlencode(params)}"

    async def exchange_code(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        return await _token_request(token_url, data)

    async def refresh(self, config: dict[str, Any]) -> dict[str, Any]:
        refresh_token = config.get("refresh_token")
        token_url = config.get("token_url")
        client_id = config.get("client_id")
        if not refresh_token or not token_url or not client_id:
            raise AuthenticationError(
                "Cannot refresh OAuth2 token: missing refresh_token, token_url, or client_id"
            )
        data = {
            "grant_type": "refresh_token",
            "refresh_token": str(refresh_token),
            "client_id": str(client_id),
            "client_secret": str(config.get("client_secret") or ""),
        }
        tokens = await _token_request(str(token_url), data)
        updated = dict(config)
        updated["access_token"] = tokens["access_token"]
        if tokens.get("refresh_token"):
            updated["refresh_token"] = tokens["refresh_token"]
        if tokens.get("token_type"):
            updated["token_type"] = tokens["token_type"]
        expires_at = tokens.get("token_expires_at")
        if expires_at is not None:
            updated["token_expires_at"] = expires_at
        return updated

    def needs_refresh(
        self,
        expires_at: datetime | None,
        *,
        buffer_seconds: int = _OAUTH_REFRESH_BUFFER_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        if expires_at is None:
            return False
        current = now or datetime.now(UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        remaining = (expires_at - current).total_seconds()
        return remaining < buffer_seconds


_HANDLERS: dict[AuthType, type[AuthHandler]] = {
    AuthType.NONE: NoAuthHandler,
    AuthType.API_KEY: APIKeyHandler,
    AuthType.BASIC: BasicAuthHandler,
    AuthType.OAUTH2: OAuth2Handler,
    AuthType.SERVICE_ACCOUNT: ServiceAccountHandler,
}


def get_auth_handler(auth_type: AuthType) -> AuthHandler:
    cls = _HANDLERS.get(auth_type)
    if cls is None:
        raise AuthenticationError(f"Unsupported auth type: {auth_type}")
    return cls()


def parse_token_expiry(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    return None


def _load_service_account(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("json_key") or config.get("credentials")
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip().startswith("{"):
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise AuthenticationError("Service account json_key must be an object")
        return loaded
    path = config.get("json_key_path") or config.get("key_file")
    if path:
        text = Path(str(path)).read_text(encoding="utf-8")
        loaded = json.loads(text)
        if not isinstance(loaded, dict):
            raise AuthenticationError("Service account key file must contain a JSON object")
        return loaded
    raise AuthenticationError("Missing service account json_key or json_key_path")


async def _token_request(token_url: str, data: dict[str, str]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, data=data, timeout=30.0)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        raise AuthenticationError(f"OAuth2 token request failed: {exc}") from exc
    if "access_token" not in payload:
        raise AuthenticationError("OAuth2 token response missing access_token")
    expires_in = payload.get("expires_in")
    result: dict[str, Any] = dict(payload)
    if expires_in is not None:
        result["token_expires_at"] = datetime.now(UTC) + timedelta(seconds=int(expires_in))
    return result
