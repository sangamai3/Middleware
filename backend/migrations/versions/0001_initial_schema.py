"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("picture", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("role", sa.String(50), nullable=False, server_default="developer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_user_id", "users", ["user_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("connector_id", sa.String(100), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("environment", sa.String(50), nullable=False, server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
    )
    op.create_index("ix_connections_connection_id", "connections", ["connection_id"])
    op.create_index("ix_connections_connector_id", "connections", ["connector_id"])

    op.create_table(
        "flows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flow_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.String(20), nullable=False, server_default="1"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_id"),
    )
    op.create_index("ix_flows_flow_id", "flows", ["flow_id"])
    op.create_index("ix_flows_status", "flows", ["status"])

    op.create_table(
        "execution_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=False),
        sa.Column("flow_id", sa.String(255), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(255), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["flow_id"], ["flows.flow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_execution_runs_run_id", "execution_runs", ["run_id"])
    op.create_index("ix_execution_runs_flow_id", "execution_runs", ["flow_id"])
    op.create_index("ix_execution_runs_status", "execution_runs", ["status"])

    op.create_table(
        "step_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=False),
        sa.Column("step_id", sa.String(255), nullable=False),
        sa.Column("step_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("rows_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["run_id"], ["execution_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_step_executions_run_id", "step_executions", ["run_id"])

    op.create_table(
        "execution_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=False),
        sa.Column("flow_id", sa.String(255), nullable=False),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_events_run_id", "execution_events", ["run_id"])
    op.create_index("ix_execution_events_flow_id", "execution_events", ["flow_id"])
    op.create_index("ix_execution_events_event", "execution_events", ["event"])
    op.create_index("ix_execution_events_created_at", "execution_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("execution_events")
    op.drop_table("step_executions")
    op.drop_table("execution_runs")
    op.drop_table("flows")
    op.drop_table("connections")
    op.drop_table("users")
