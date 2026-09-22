"""Map HTTP failures onto the connector error taxonomy."""

from __future__ import annotations

from typing import Any

import httpx

from .errors import AuthenticationError, DataReadError, NetworkError, RateLimitError


def raise_for_status(response: Any) -> None:
    code = response.status_code
    if code in (401, 403):
        raise AuthenticationError(f"HTTP {code}: {response.text[:300]}")
    if code == 429:
        retry_after = response.headers.get("Retry-After")
        delay = int(retry_after) if retry_after and retry_after.isdigit() else None
        raise RateLimitError(f"HTTP 429: {response.text[:300]}", retry_after=delay)
    if code >= 500:
        raise NetworkError(f"HTTP {code}: {response.text[:300]}")
    if code >= 400:
        raise DataReadError(f"HTTP {code}: {response.text[:300]}")


def request(client: Any, method: str, url: str, **kwargs: Any) -> Any:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.TransportError as exc:
        raise NetworkError(str(exc)) from exc
    raise_for_status(response)
    return response
