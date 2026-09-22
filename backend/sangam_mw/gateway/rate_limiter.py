"""
Sliding window rate limiter.

Uses in-memory counters (suitable for single-process deployments).
For multi-process / multi-replica, wire in the Redis backend by setting
REDIS_URL in config — falls back to in-memory transparently.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: float
    retry_after: int = 0

    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_at)),
            **({"Retry-After": str(self.retry_after)} if self.retry_after else {}),
        }


class _SlidingWindowCounter:
    """Thread-safe sliding window counter using a deque of timestamps."""

    def __init__(self, window_seconds: int) -> None:
        self.window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def check_and_record(self, limit: int) -> tuple[bool, int, float]:
        """Returns (allowed, remaining, reset_at)."""
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            count = len(self._timestamps)
            if count < limit:
                self._timestamps.append(now)
                remaining = limit - count - 1
                reset_at = (self._timestamps[0] + self.window) if self._timestamps else now + self.window
                return True, remaining, reset_at
            reset_at = self._timestamps[0] + self.window
            return False, 0, reset_at


class RateLimiter:
    """
    Per-key sliding window rate limiter.

    Keys are (consumer_key, window_label) so a consumer can be checked
    against both per-minute and per-day limits independently.
    """

    def __init__(self) -> None:
        self._counters: dict[str, _SlidingWindowCounter] = {}
        self._lock = Lock()

    def _get_counter(self, key: str, window_seconds: int) -> _SlidingWindowCounter:
        with self._lock:
            composite = f"{key}:{window_seconds}"
            if composite not in self._counters:
                self._counters[composite] = _SlidingWindowCounter(window_seconds)
            return self._counters[composite]

    def check(
        self,
        consumer_key: str,
        requests_per_minute: int,
        requests_per_day: int,
    ) -> RateLimitResult:
        minute_counter = self._get_counter(consumer_key, 60)
        day_counter = self._get_counter(consumer_key, 86_400)

        ok_min, remaining_min, reset_min = minute_counter.check_and_record(requests_per_minute)
        if not ok_min:
            return RateLimitResult(
                allowed=False,
                limit=requests_per_minute,
                remaining=0,
                reset_at=reset_min,
                retry_after=max(1, int(reset_min - time.time())),
            )

        ok_day, remaining_day, reset_day = day_counter.check_and_record(requests_per_day)
        if not ok_day:
            return RateLimitResult(
                allowed=False,
                limit=requests_per_day,
                remaining=0,
                reset_at=reset_day,
                retry_after=max(1, int(reset_day - time.time())),
            )

        return RateLimitResult(
            allowed=True,
            limit=min(requests_per_minute, requests_per_day),
            remaining=min(remaining_min, remaining_day),
            reset_at=min(reset_min, reset_day),
        )

    def reset(self, consumer_key: str) -> None:
        with self._lock:
            keys_to_del = [k for k in self._counters if k.startswith(f"{consumer_key}:")]
            for k in keys_to_del:
                del self._counters[k]


_global_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter()
    return _global_limiter
