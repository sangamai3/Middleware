"""
Prometheus metrics endpoint for SangamMW.

Exposes /metrics in the Prometheus text format.
Metrics:
  sangam_mw_runs_total{flow_id, status}
  sangam_mw_run_duration_seconds (histogram)
  sangam_mw_rows_processed_total{flow_id, step_id}
  sangam_mw_rows_failed_total{flow_id, step_id}
  sangam_mw_connector_duration_seconds (histogram)
  sangam_mw_active_connections (gauge)
"""
from __future__ import annotations

try:
    from prometheus_client import (  # type: ignore[import]
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False

REGISTRY = None
runs_total = None
run_duration = None
rows_processed = None
rows_failed = None
connector_duration = None
active_connections = None


def init_metrics() -> None:
    global REGISTRY, runs_total, run_duration, rows_processed, rows_failed
    global connector_duration, active_connections

    if not _HAS_PROMETHEUS or REGISTRY is not None:
        return

    REGISTRY = CollectorRegistry()

    runs_total = Counter(
        "sangam_mw_runs_total",
        "Total flow execution runs",
        ["flow_id", "status"],
        registry=REGISTRY,
    )
    run_duration = Histogram(
        "sangam_mw_run_duration_seconds",
        "Flow execution duration in seconds",
        ["flow_id"],
        buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, 300, 600],
        registry=REGISTRY,
    )
    rows_processed = Counter(
        "sangam_mw_rows_processed_total",
        "Total rows processed by step",
        ["flow_id", "step_id"],
        registry=REGISTRY,
    )
    rows_failed = Counter(
        "sangam_mw_rows_failed_total",
        "Total rows failed by step",
        ["flow_id", "step_id"],
        registry=REGISTRY,
    )
    connector_duration = Histogram(
        "sangam_mw_connector_duration_seconds",
        "Connector operation duration",
        ["connector_id", "operation"],
        buckets=[0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30],
        registry=REGISTRY,
    )
    active_connections = Gauge(
        "sangam_mw_active_connections",
        "Currently open connector connections",
        ["connector_id"],
        registry=REGISTRY,
    )


def record_run_complete(flow_id: str, status: str, duration_s: float) -> None:
    if not _HAS_PROMETHEUS or runs_total is None:
        return
    runs_total.labels(flow_id=flow_id, status=status).inc()
    run_duration.labels(flow_id=flow_id).observe(duration_s)


def record_step_rows(flow_id: str, step_id: str, processed: int, failed: int) -> None:
    if not _HAS_PROMETHEUS or rows_processed is None:
        return
    rows_processed.labels(flow_id=flow_id, step_id=step_id).inc(processed)
    rows_failed.labels(flow_id=flow_id, step_id=step_id).inc(failed)


def record_connector_op(connector_id: str, operation: str, duration_s: float) -> None:
    if not _HAS_PROMETHEUS or connector_duration is None:
        return
    connector_duration.labels(connector_id=connector_id, operation=operation).observe(duration_s)


def metrics_output() -> tuple[bytes, str]:
    if not _HAS_PROMETHEUS or REGISTRY is None:
        text = "# prometheus_client not installed — pip install prometheus-client\n"
        return text.encode(), "text/plain"
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
