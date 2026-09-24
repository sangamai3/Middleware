from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(50), default="developer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConnectionTable(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    connector_id: Mapped[str] = mapped_column(String(100), index=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    environment: Mapped[str] = mapped_column(String(50), default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    created_by: Mapped[str] = mapped_column(String(255), default="")


class FlowTable(Base):
    __tablename__ = "flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(20), default="1")
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    definition: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    created_by: Mapped[str] = mapped_column(String(255), default="")

    runs: Mapped[list["ExecutionRunTable"]] = relationship(
        back_populates="flow", lazy="noload", cascade="all, delete-orphan"
    )


class ExecutionRunTable(Base):
    __tablename__ = "execution_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    flow_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("flows.flow_id", ondelete="CASCADE"), index=True
    )
    flow_name: Mapped[str] = mapped_column(String(255), default="")
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual")
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(255), default="")

    flow: Mapped["FlowTable"] = relationship(back_populates="runs", lazy="noload")
    steps: Mapped[list["StepExecutionTable"]] = relationship(
        back_populates="run", lazy="noload", cascade="all, delete-orphan"
    )


class StepExecutionTable(Base):
    __tablename__ = "step_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("execution_runs.run_id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[str] = mapped_column(String(255))
    step_type: Mapped[str] = mapped_column(String(100))
    step_label: Mapped[str] = mapped_column(String(500), default="")
    connector_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_in: Mapped[int] = mapped_column(Integer, default=0)
    rows_out: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    run: Mapped["ExecutionRunTable"] = relationship(back_populates="steps", lazy="noload")


class ExecutionEventTable(Base):
    """Append-only log of all execution events. Feeds Run History UI and SSE stream."""

    __tablename__ = "execution_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(255), index=True)
    flow_id: Mapped[str] = mapped_column(String(255), index=True)
    event: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AuditLogTable(Base):
    """
    Append-only, hash-chained audit log.
    Each row's entry_hash = SHA-256(prev_hash + actor + action + resource + timestamp).
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_actor_action", "actor_id", "action"),
        Index("ix_audit_log_resource", "resource_type", "resource_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), index=True)
    actor_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(100), index=True)
    resource_id: Mapped[str] = mapped_column(String(255))
    before_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    after_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class FlowLineageTable(Base):
    """
    Data lineage edge: records which connector/object was read or written per flow step.
    Enables impact analysis: "which flows read from connection X / table Y?"
    """

    __tablename__ = "flow_lineage"
    __table_args__ = (
        Index("ix_lineage_flow_step", "flow_id", "step_id"),
        Index("ix_lineage_source", "connection_id", "object_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(255), index=True)
    flow_version: Mapped[str] = mapped_column(String(20), default="")
    step_id: Mapped[str] = mapped_column(String(255))
    step_type: Mapped[str] = mapped_column(String(100))
    direction: Mapped[str] = mapped_column(String(10))  # "read" | "write"
    connection_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    connector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    object_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fields: Mapped[list] = mapped_column(JSONB, default=list)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 8 — API Gateway tables
# ──────────────────────────────────────────────────────────────────────────────

class ApiProductTable(Base):
    """Persisted API product definition (base_path, endpoint list, plans)."""

    __tablename__ = "api_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(50), default="v1")
    base_path: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    definition: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    portal_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ApiKeyTable(Base):
    """Consumer API key — only the SHA-256 hash is stored, never the plaintext."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_product_active", "product_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    consumer_name: Mapped[str] = mapped_column(String(255))
    consumer_email: Mapped[str] = mapped_column(String(255))
    product_id: Mapped[str] = mapped_column(String(255), index=True)
    plan_name: Mapped[str] = mapped_column(String(100), default="default")
    scopes: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiUsageTable(Base):
    """Bucketed usage counters — one row per (key_id, endpoint, hour)."""

    __tablename__ = "api_usage"
    __table_args__ = (
        Index("ix_api_usage_key_window", "key_id", "window_start"),
        Index("ix_api_usage_product_window", "product_id", "window_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_id: Mapped[str] = mapped_column(String(32), index=True)
    product_id: Mapped[str] = mapped_column(String(255), index=True)
    endpoint_path: Mapped[str] = mapped_column(String(500))
    method: Mapped[str] = mapped_column(String(10))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class WebhookSubscriptionTable(Base):
    """Consumer webhook subscription — URL + event filter."""

    __tablename__ = "webhook_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sub_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    consumer_name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2000))
    events: Mapped[list] = mapped_column(JSONB, default=list)
    secret_hash: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WebhookDeliveryTable(Base):
    """Webhook delivery attempt record."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_sub", "sub_id", "last_attempt_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    sub_id: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlertRuleTable(Base):
    """Notification alert rule — fires channels when trigger conditions match."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    trigger: Mapped[str] = mapped_column(String(50), index=True)
    flow_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict)
    channels: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ScheduledFlowTable(Base):
    """Persisted flow schedule — cron or interval trigger."""

    __tablename__ = "scheduled_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    flow_name: Mapped[str] = mapped_column(String(255), default="")
    cron_expr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 14 — App Insights & Observability tables
# ──────────────────────────────────────────────────────────────────────────────

class ExecutionLogTable(Base):
    """Append-only log of per-step messages. Full-text searchable via GIN index."""

    __tablename__ = "execution_logs"
    __table_args__ = (
        Index("ix_execution_logs_run_id", "run_id"),
        Index("ix_execution_logs_flow_id", "flow_id"),
        Index("ix_execution_logs_level", "level"),
        Index("ix_execution_logs_ts", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(255), index=True)
    flow_id: Mapped[str] = mapped_column(String(255), index=True)
    step_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(10), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    payload_preview: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class MetricsBucketTable(Base):
    """
    Pre-aggregated per-minute metrics per flow.
    Upserted on every run completion — O(1) dashboard queries.
    """

    __tablename__ = "metrics_buckets"
    __table_args__ = (
        Index("ix_metrics_buckets_flow_bucket", "flow_id", "bucket_ts", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(255), index=True)
    bucket_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    granularity: Mapped[str] = mapped_column(String(10), default="minute")
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    p50_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p95_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p99_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BusinessEventTable(Base):
    """Custom domain events emitted from within flow steps via execution_context.emit()."""

    __tablename__ = "business_events"
    __table_args__ = (
        Index("ix_business_events_flow_run", "flow_id", "run_id"),
        Index("ix_business_events_name", "event_name"),
        Index("ix_business_events_correlation", "correlation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(255), index=True)
    run_id: Mapped[str] = mapped_column(String(255), index=True)
    step_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
