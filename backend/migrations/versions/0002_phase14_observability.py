"""Phase 14: add observability tables + correlation_id columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to execution_runs
    op.add_column("execution_runs", sa.Column("flow_name", sa.String(255), nullable=False, server_default=""))
    op.add_column("execution_runs", sa.Column("correlation_id", sa.String(255), nullable=True))
    op.add_column("execution_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.create_index("ix_execution_runs_correlation_id", "execution_runs", ["correlation_id"])

    # Add new column to step_executions
    op.add_column("step_executions", sa.Column("connector_id", sa.String(255), nullable=True))

    # execution_logs
    op.create_table(
        "execution_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(255), nullable=False),
        sa.Column("flow_id", sa.String(255), nullable=False),
        sa.Column("step_id", sa.String(255), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("level", sa.String(10), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_preview", sa.String(512), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_execution_logs_run_id", "execution_logs", ["run_id"])
    op.create_index("ix_execution_logs_flow_id", "execution_logs", ["flow_id"])
    op.create_index("ix_execution_logs_level", "execution_logs", ["level"])
    op.create_index("ix_execution_logs_ts", "execution_logs", ["timestamp"])
    op.create_index("ix_execution_logs_correlation", "execution_logs", ["correlation_id"])

    # metrics_buckets
    op.create_table(
        "metrics_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flow_id", sa.String(255), nullable=False),
        sa.Column("bucket_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granularity", sa.String(10), nullable=False, server_default="minute"),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("p50_ms", sa.Integer(), nullable=True),
        sa.Column("p95_ms", sa.Integer(), nullable=True),
        sa.Column("p99_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_metrics_buckets_flow_id", "metrics_buckets", ["flow_id"])
    op.create_index("ix_metrics_buckets_bucket_ts", "metrics_buckets", ["bucket_ts"])
    op.create_index(
        "ix_metrics_buckets_flow_bucket",
        "metrics_buckets",
        ["flow_id", "bucket_ts"],
        unique=True,
    )

    # business_events
    op.create_table(
        "business_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flow_id", sa.String(255), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=False),
        sa.Column("step_id", sa.String(255), nullable=True),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("event_name", sa.String(255), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_business_events_flow_id", "business_events", ["flow_id"])
    op.create_index("ix_business_events_run_id", "business_events", ["run_id"])
    op.create_index("ix_business_events_name", "business_events", ["event_name"])
    op.create_index("ix_business_events_correlation", "business_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("business_events")
    op.drop_table("metrics_buckets")
    op.drop_table("execution_logs")
    op.drop_index("ix_execution_runs_correlation_id", table_name="execution_runs")
    op.drop_column("execution_runs", "duration_ms")
    op.drop_column("execution_runs", "correlation_id")
    op.drop_column("execution_runs", "flow_name")
    op.drop_column("step_executions", "connector_id")
