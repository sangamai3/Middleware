"""Add scheduled_flows table for Flow Scheduler jobs."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_flows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flow_id", sa.String(255), nullable=False),
        sa.Column("flow_name", sa.String(255), server_default="", nullable=False),
        sa.Column("cron_expr", sa.String(100), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scheduled_flows_flow_id", "scheduled_flows", ["flow_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_scheduled_flows_flow_id", table_name="scheduled_flows")
    op.drop_table("scheduled_flows")
