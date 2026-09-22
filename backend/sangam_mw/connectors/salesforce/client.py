"""Salesforce HTTP client — ported from AgentStudio ``db_salesforce.py.eta``.

instance_url comes from the OAuth token response (client credentials or JWT
bearer). A pre-issued access_token may be supplied for tests / static sessions.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..base.errors import AuthenticationError, ConnectorValidationError, DataReadError
from ..base.http import raise_for_status, request
from .security import (
    is_salesforce_my_domain_url,
    salesforce_api_version,
    validate_salesforce_url,
)

_CLIENT_CREDENTIALS = "salesforceClientCredentials"
_JWT_BEARER = "salesforceJwtBearer"


class SalesforceClient:
    def __init__(
        self,
        config: dict[str, Any],
        http: Any | None = None,
        *,
        verify_hosts: bool = True,
    ) -> None:
        self.config = config
        self._http = http
        self.verify_hosts = verify_hosts
        self._token: str | None = (
            str(config["access_token"]) if config.get("access_token") else None
        )
        instance = config.get("instance_url")
        self._instance_url: str | None = self._validate_url(str(instance)) if instance else None
        self._expires = 0.0 if self._token else 0.0
        if self._token:
            self._expires = time.time() + 1800.0

    @property
    def api_version(self) -> str:
        return salesforce_api_version(
            self.config.get("api_version") or self.config.get("apiVersion")
        )

    @property
    def instance_url(self) -> str:
        self._ensure_session()
        return self._instance_url or ""

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self._request("POST", path, json=body)

    def patch(self, path: str, body: dict[str, Any]) -> Any:
        return self._request("PATCH", path, json=body)

    def soql(self, query: str, max_records: int = 200, max_pages: int = 10) -> list[dict[str, Any]]:
        max_records = max(1, min(int(max_records or 200), 10000))
        max_pages = max(1, min(int(max_pages or 10), 20))
        resp = self.get(f"/services/data/{self.api_version}/query/", params={"q": query})
        raise_for_status(resp)
        body = resp.json()
        records = list(body.get("records", []))[:max_records]
        pages = 1
        next_url = body.get("nextRecordsUrl")
        while next_url and len(records) < max_records and pages < max_pages:
            if not isinstance(next_url, str) or not next_url.startswith("/services/data/"):
                raise DataReadError("Unsafe Salesforce nextRecordsUrl")
            resp = self.get(next_url)
            raise_for_status(resp)
            body = resp.json()
            records.extend(body.get("records", []))
            records = records[:max_records]
            next_url = body.get("nextRecordsUrl")
            pages += 1
        return records

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        self._ensure_session()
        url = self._url(path)
        http = self._http_client()
        resp = http.request(method, url, headers=self._headers(), **kwargs)
        if getattr(resp, "status_code", 0) == 401 and self._auth_type() != "access_token":
            self._ensure_session(force=True)
            resp = http.request(method, url, headers=self._headers(), **kwargs)
        raise_for_status(resp)
        return resp

    def _ensure_session(self, force: bool = False) -> None:
        if not force and self._token and time.time() < self._expires:
            return
        if self.config.get("access_token") and not force:
            self._token = str(self.config["access_token"])
            if self.config.get("instance_url"):
                self._instance_url = self._validate_url(str(self.config["instance_url"]))
            self._expires = time.time() + 1800.0
            return
        self._fetch_session()

    def _fetch_session(self) -> None:
        auth_type = self._auth_type()
        if auth_type == _JWT_BEARER:
            payload = self._fetch_token_jwt_bearer()
        elif auth_type == _CLIENT_CREDENTIALS:
            payload = self._fetch_token_client_credentials()
        else:
            raise AuthenticationError("Missing Salesforce access_token or OAuth auth_type")
        self._token = payload["access_token"]
        self._instance_url = self._validate_url(str(payload["instance_url"]))
        self._expires = time.time() + 1800.0

    def _fetch_token_client_credentials(self) -> dict[str, Any]:
        login_url = self._validate_url(
            str(self.config.get("login_url") or self.config.get("loginUrl") or "")
        )
        if not is_salesforce_my_domain_url(login_url):
            raise ConnectorValidationError(
                "Client Credentials must use the org My Domain URL, not login.salesforce.com"
            )
        client_id = self.config.get("client_id") or self.config.get("clientId")
        client_secret = self.config.get("client_secret") or self.config.get("clientSecret")
        if not client_id or not client_secret:
            raise AuthenticationError("Missing Salesforce client_id / client_secret")
        resp = request(
            self._http_client(),
            "POST",
            f"{login_url}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        return _token_payload(resp.json())

    def _fetch_token_jwt_bearer(self) -> dict[str, Any]:
        import jwt as pyjwt

        login_url = self._validate_url(
            str(
                self.config.get("login_url")
                or self.config.get("loginUrl")
                or "https://login.salesforce.com"
            )
        )
        client_id = self.config.get("client_id") or self.config.get("clientId")
        username = self.config.get("username")
        private_key = self.config.get("private_key") or self.config.get("privateKey")
        if not client_id or not username or not private_key:
            raise AuthenticationError("JWT bearer requires client_id, username, and private_key")
        now = int(time.time())
        assertion = pyjwt.encode(
            {"iss": client_id, "sub": username, "aud": login_url, "exp": now + 300},
            private_key,
            algorithm="RS256",
        )
        resp = request(
            self._http_client(),
            "POST",
            f"{login_url}/services/oauth2/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        return _token_payload(resp.json())

    def _auth_type(self) -> str:
        if self.config.get("access_token"):
            return "access_token"
        return str(
            self.config.get("auth_type") or self.config.get("authType") or _CLIENT_CREDENTIALS
        )

    def _validate_url(self, value: str) -> str:
        return validate_salesforce_url(value, check_dns=self.verify_hosts)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        root = (self._instance_url or "").rstrip("/")
        if path.startswith("http"):
            return path
        return f"{root}{path}" if path.startswith("/") else f"{root}/{path}"

    def _http_client(self) -> Any:
        if self._http is not None:
            return self._http
        self._http = httpx.Client(timeout=30.0)
        return self._http


def _token_payload(payload: Any) -> dict[str, Any]:
    if (
        not isinstance(payload, dict)
        or "access_token" not in payload
        or "instance_url" not in payload
    ):
        raise AuthenticationError("Salesforce token response missing access_token or instance_url")
    return payload
