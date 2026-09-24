"""Add step_label to step_executions for run timeline display."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "step_executions",
        sa.Column("step_label", sa.String(500), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("step_executions", "step_label")
