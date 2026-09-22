"""Integration tests for health check endpoints via TestClient."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from sangam_mw.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_shape(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("ok", "healthy", "alive")

    def test_health_has_version(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "version" in data or "app" in data

    def test_health_response_is_fast(self, client):
        import time
        start = time.monotonic()
        client.get("/health")
        elapsed = time.monotonic() - start
        assert elapsed < 1.0


class TestHealthReadyEndpoint:
    def test_ready_returns_200_or_503(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code in (200, 503)

    def test_ready_response_has_checks(self, client):
        resp = client.get("/health/ready")
        data = resp.json()
        assert "checks" in data or "status" in data

    def test_ready_503_has_degraded_status(self, client):
        resp = client.get("/health/ready")
        if resp.status_code == 503:
            data = resp.json()
            assert data.get("status") in ("degraded", "unavailable", "error")


class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type_is_text(self, client):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_metrics_contains_process_metrics(self, client):
        resp = client.get("/metrics")
        # Prometheus always exposes these
        assert "python_info" in resp.text or "process_" in resp.text
