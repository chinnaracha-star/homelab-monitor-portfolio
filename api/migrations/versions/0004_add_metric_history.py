"""Create metric_history for dashboard time-series charts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("disk_percent", sa.Float(), nullable=True),
        sa.Column("temperature_celsius", sa.Float(), nullable=True),
        sa.Column("network_rx_bytes", sa.Float(), nullable=True),
        sa.Column("network_tx_bytes", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metric_history_agent_id", "metric_history", ["agent_id"])
    op.create_index("ix_metric_history_timestamp", "metric_history", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_metric_history_timestamp", table_name="metric_history")
    op.drop_index("ix_metric_history_agent_id", table_name="metric_history")
    op.drop_table("metric_history")
