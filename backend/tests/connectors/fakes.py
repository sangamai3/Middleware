"""Fake HTTP client used by Salesforce and REST connector tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        text: str = "",
        headers: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.text = text if text else ("" if json_data is None else str(json_data))
        self.headers = headers or {}

    def json(self) -> Any:
        return self._json


class FakeClient:
    def __init__(self, handler: Callable[[str, str, dict], FakeResponse]) -> None:
        self._handler = handler
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        record = (method.upper(), url, kwargs)
        self.calls.append(record)
        return self._handler(method.upper(), url, kwargs)

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> FakeResponse:
        return self.request("PATCH", url, **kwargs)
