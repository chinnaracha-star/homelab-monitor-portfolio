"""Require photo_monitor_settings.watch_folders after backfill.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("photo_monitor_settings") as batch:
        batch.alter_column(
            "watch_folders",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("photo_monitor_settings") as batch:
        batch.alter_column(
            "watch_folders",
            existing_type=sa.JSON(),
            nullable=True,
        )
