"""
Gateway analytics — per-endpoint and per-consumer usage aggregation.

Tracks: requests, errors, latency samples.
Computes: p50/p95/p99 latency, error rate, req/sec, top consumers.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class LatencyBucket:
    """Fixed-size sliding window of latency samples (last N requests)."""
    _samples: deque = field(default_factory=lambda: deque(maxlen=1000))
    _lock: Lock = field(default_factory=Lock)

    def record(self, latency_ms: float) -> None:
        with self._lock:
            self._samples.append(latency_ms)

    def percentile(self, p: float) -> float:
        with self._lock:
            if not self._samples:
                return 0.0
            sorted_samples = sorted(self._samples)
            idx = int(len(sorted_samples) * p / 100)
            return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def p50(self) -> float:
        return self.percentile(50)

    def p95(self) -> float:
        return self.percentile(95)

    def p99(self) -> float:
        return self.percentile(99)


@dataclass
class EndpointStats:
    endpoint_key: str
    total_requests: int = 0
    total_errors: int = 0
    latency: LatencyBucket = field(default_factory=LatencyBucket)
    _timestamps: deque = field(default_factory=lambda: deque(maxlen=3600))
    _lock: Lock = field(default_factory=Lock)

    def record(self, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self.total_requests += 1
            if status_code >= 400:
                self.total_errors += 1
            self._timestamps.append(time.time())
        self.latency.record(latency_ms)

    def requests_per_second(self, window_s: int = 60) -> float:
        cutoff = time.time() - window_s
        with self._lock:
            count = sum(1 for ts in self._timestamps if ts >= cutoff)
        return count / window_s

    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint_key,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": round(self.error_rate(), 4),
            "requests_per_second": round(self.requests_per_second(), 3),
            "latency_ms": {
                "p50": round(self.latency.p50(), 2),
                "p95": round(self.latency.p95(), 2),
                "p99": round(self.latency.p99(), 2),
            },
        }


class GatewayAnalytics:
    """Thread-safe in-process analytics store."""

    def __init__(self) -> None:
        self._endpoints: dict[str, EndpointStats] = {}
        self._consumers: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._lock = Lock()

    def _endpoint(self, key: str) -> EndpointStats:
        with self._lock:
            if key not in self._endpoints:
                self._endpoints[key] = EndpointStats(endpoint_key=key)
            return self._endpoints[key]

    def record(
        self,
        product_id: str,
        endpoint_path: str,
        method: str,
        consumer_key: str,
        status_code: int,
        latency_ms: float,
    ) -> None:
        key = f"{product_id}:{method}:{endpoint_path}"
        self._endpoint(key).record(status_code, latency_ms)
        with self._lock:
            self._consumers[consumer_key][key] += 1

    def get_product_stats(self, product_id: str) -> list[dict[str, Any]]:
        prefix = f"{product_id}:"
        with self._lock:
            keys = [k for k in self._endpoints if k.startswith(prefix)]
        return [self._endpoints[k].to_dict() for k in keys]

    def get_top_consumers(self, product_id: str, limit: int = 10) -> list[dict[str, Any]]:
        prefix = f"{product_id}:"
        result: dict[str, int] = defaultdict(int)
        with self._lock:
            for consumer, endpoints in self._consumers.items():
                for ep_key, count in endpoints.items():
                    if ep_key.startswith(prefix):
                        result[consumer] += count
        top = sorted(result.items(), key=lambda x: -x[1])[:limit]
        return [{"consumer_key": k, "total_requests": v} for k, v in top]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            endpoint_count = len(self._endpoints)
            consumer_count = len(self._consumers)
            total_requests = sum(s.total_requests for s in self._endpoints.values())
            total_errors = sum(s.total_errors for s in self._endpoints.values())
        return {
            "endpoints_tracked": endpoint_count,
            "consumers_tracked": consumer_count,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": round(total_errors / total_requests, 4) if total_requests else 0,
        }


_global_analytics: GatewayAnalytics | None = None


def get_analytics() -> GatewayAnalytics:
    global _global_analytics
    if _global_analytics is None:
        _global_analytics = GatewayAnalytics()
    return _global_analytics
