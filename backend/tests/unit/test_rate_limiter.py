"""Unit tests for the sliding window rate limiter."""

import time

import pytest

from sangam_mw.gateway.rate_limiter import RateLimiter, RateLimitResult, _SlidingWindowCounter


class TestSlidingWindowCounter:
    def test_allows_within_limit(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        for _ in range(5):
            allowed, remaining, reset_at = counter.check_and_record(limit=10)
            assert allowed

    def test_blocks_over_limit(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        for _ in range(10):
            counter.check_and_record(limit=10)
        allowed, remaining, reset_at = counter.check_and_record(limit=10)
        assert not allowed
        assert remaining == 0

    def test_remaining_decrements(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        _, r1, _ = counter.check_and_record(limit=5)
        _, r2, _ = counter.check_and_record(limit=5)
        assert r2 == r1 - 1

    def test_reset_at_is_future(self):
        counter = _SlidingWindowCounter(window_seconds=60)
        _, _, reset_at = counter.check_and_record(limit=100)
        assert reset_at > time.time()


class TestRateLimiter:
    def test_allows_under_limits(self):
        limiter = RateLimiter()
        result = limiter.check("consumer1", requests_per_minute=100, requests_per_day=10_000)
        assert result.allowed
        assert result.remaining >= 0

    def test_blocks_when_minute_limit_reached(self):
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check("burst_user", requests_per_minute=3, requests_per_day=1_000)
        result = limiter.check("burst_user", requests_per_minute=3, requests_per_day=1_000)
        assert not result.allowed
        assert result.retry_after > 0

    def test_different_consumers_independent(self):
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check("user_a", requests_per_minute=3, requests_per_day=1_000)
        result_b = limiter.check("user_b", requests_per_minute=3, requests_per_day=1_000)
        assert result_b.allowed

    def test_reset_clears_counter(self):
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check("user_reset", requests_per_minute=3, requests_per_day=1_000)
        result = limiter.check("user_reset", requests_per_minute=3, requests_per_day=1_000)
        assert not result.allowed
        limiter.reset("user_reset")
        result_after = limiter.check("user_reset", requests_per_minute=3, requests_per_day=1_000)
        assert result_after.allowed

    def test_headers_present_on_blocked(self):
        limiter = RateLimiter()
        for _ in range(2):
            limiter.check("h_user", requests_per_minute=2, requests_per_day=1_000)
        result = limiter.check("h_user", requests_per_minute=2, requests_per_day=1_000)
        headers = result.headers()
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "Retry-After" in headers

    def test_result_dataclass_fields(self):
        r = RateLimitResult(allowed=True, limit=100, remaining=99, reset_at=time.time() + 60)
        assert r.allowed
        assert r.retry_after == 0
