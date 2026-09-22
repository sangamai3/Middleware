"""Retry RateLimitError / NetworkError with exponential backoff (30s / 60s / 120s)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from .errors import NetworkError, RateLimitError

T = TypeVar("T")

DEFAULT_BACKOFF_SECONDS: tuple[float, ...] = (30.0, 60.0, 120.0)


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    backoff_seconds: tuple[float, ...] = DEFAULT_BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run `fn` and retry on retryable connector errors.

    Uses `RateLimitError.retry_after` when the connector supplies it; otherwise
    the next value from `backoff_seconds`.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    last_error: RateLimitError | NetworkError | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except (RateLimitError, NetworkError) as exc:
            last_error = exc
            if attempt >= max_attempts - 1:
                raise
            delay = _delay_for(exc, attempt, backoff_seconds)
            sleep(delay)
    assert last_error is not None
    raise last_error


def _delay_for(
    exc: RateLimitError | NetworkError,
    attempt: int,
    backoff_seconds: tuple[float, ...],
) -> float:
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        return float(exc.retry_after)
    if not backoff_seconds:
        return 0.0
    index = min(attempt, len(backoff_seconds) - 1)
    return backoff_seconds[index]
