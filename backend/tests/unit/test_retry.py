"""Retry helper for RateLimitError / NetworkError."""

import pytest

from sangam_mw.connectors.base.errors import AuthenticationError, NetworkError, RateLimitError
from sangam_mw.connectors.base.retry import call_with_retry


def test_retries_network_error_then_succeeds() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise NetworkError("down")
        return "ok"

    slept: list[float] = []
    assert call_with_retry(fn, sleep=slept.append) == "ok"
    assert calls["n"] == 3
    assert slept == [30.0, 60.0]


def test_uses_retry_after_from_rate_limit() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitError("slow down", retry_after=7)
        return "ok"

    slept: list[float] = []
    assert call_with_retry(fn, sleep=slept.append) == "ok"
    assert slept == [7.0]


def test_gives_up_after_max_attempts() -> None:
    def fn() -> str:
        raise NetworkError("still down")

    slept: list[float] = []
    with pytest.raises(NetworkError, match="still down"):
        call_with_retry(fn, max_attempts=3, sleep=slept.append)
    assert len(slept) == 2


def test_does_not_retry_auth_error() -> None:
    def fn() -> str:
        raise AuthenticationError("bad creds")

    slept: list[float] = []
    with pytest.raises(AuthenticationError):
        call_with_retry(fn, sleep=slept.append)
    assert slept == []


def test_max_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        call_with_retry(lambda: None, max_attempts=0)
