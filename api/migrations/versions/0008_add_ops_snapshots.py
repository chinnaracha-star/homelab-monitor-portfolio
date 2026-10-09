"""Store photo storage and backup snapshots for Phase 8.3 trends.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ops_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ops_snapshots_kind", "ops_snapshots", ["kind"])
    op.create_index("ix_ops_snapshots_observed_at", "ops_snapshots", ["observed_at"])


def downgrade() -> None:
    op.drop_index("ix_ops_snapshots_observed_at", table_name="ops_snapshots")
    op.drop_index("ix_ops_snapshots_kind", table_name="ops_snapshots")
    op.drop_table("ops_snapshots")
