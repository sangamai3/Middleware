"""REST auth — ported from AgentStudio ``db_rest.py.eta``."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx

from ..base.errors import AuthenticationError


class OAuth2ClientCredentialsAuth(httpx.Auth):
    """Client-credentials token with early refresh (AgentStudio RestClient)."""

    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str = "") -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._token: str | None = None
        self._expires = 0.0

    def _fetch_token(self) -> None:
        form: dict[str, str] = {"grant_type": "client_credentials"}
        if self.scope:
            form["scope"] = self.scope
        resp = httpx.post(
            self.token_url,
            data=form,
            auth=(self.client_id, self.client_secret),
            timeout=20.0,
        )
        if resp.status_code in (400, 401):
            body = dict(form, client_id=self.client_id, client_secret=self.client_secret)
            resp = httpx.post(self.token_url, data=body, timeout=20.0)
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        try:
            ttl = float(payload.get("expires_in"))
        except (TypeError, ValueError):
            ttl = 300.0
        self._expires = time.time() + max(ttl - min(30.0, ttl * 0.2), 1.0)

    def auth_flow(self, request: httpx.Request):  # type: ignore[no-untyped-def]
        if not self._token or time.time() >= self._expires:
            self._fetch_token()
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


def rest_auth_type(config: dict[str, Any]) -> str:
    explicit = config.get("auth_type") or config.get("authType")
    if explicit:
        return str(explicit)
    if config.get("api_key") or config.get("token"):
        if str(config.get("api_key_in") or "header") == "query":
            return "apiKeyQuery"
        header = str(config.get("api_key_header") or "Authorization")
        if header != "Authorization":
            return "apiKeyHeader"
        return "bearer"
    return "none"


def auth_headers(config: dict[str, Any]) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    kind = rest_auth_type(config)
    if kind == "apiKeyHeader":
        name = str(config.get("api_key_header") or config.get("headerName") or "X-API-Key")
        value = str(config.get("api_key") or config.get("token") or "")
        if name:
            headers[name] = value
    elif kind == "bearer":
        token = str(
            config.get("token") or config.get("api_key") or config.get("bearer_token") or ""
        )
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif kind == "basic":
        user = str(config.get("username") or "")
        password = str(config.get("password") or "")
        raw = f"{user}:{password}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    elif kind == "customHeaders":
        raw_headers = config.get("custom_headers") or config.get("customHeaders") or "[]"
        rows = json.loads(raw_headers) if isinstance(raw_headers, str) else raw_headers
        for row in rows or []:
            key = str(row.get("key") or row.get("name") or "").strip()
            if key:
                headers[key] = str(row.get("value") or "")
    return headers


def auth_params(config: dict[str, Any]) -> dict[str, str]:
    if rest_auth_type(config) == "apiKeyQuery":
        name = str(config.get("api_key_param") or config.get("paramName") or "api_key")
        value = str(config.get("api_key") or config.get("token") or "")
        if name:
            return {name: value}
    return {}


def oauth_auth(config: dict[str, Any]) -> OAuth2ClientCredentialsAuth | None:
    if rest_auth_type(config) != "oauth2ClientCredentials":
        return None
    token_url = config.get("token_url") or config.get("tokenUrl")
    client_id = config.get("client_id") or config.get("clientId")
    client_secret = config.get("client_secret") or config.get("clientSecret")
    if not token_url or not client_id or not client_secret:
        raise AuthenticationError(
            "OAuth2 client credentials require token_url, client_id, client_secret"
        )
    return OAuth2ClientCredentialsAuth(
        str(token_url),
        str(client_id),
        str(client_secret),
        str(config.get("scope") or ""),
    )
