"""Add photo_events and photo_monitor_settings for Photo Monitor.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("folder", sa.String(length=1000), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("telegram_sent", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("folder", "filename", name="uq_photo_events_folder_filename"),
    )
    op.create_index("ix_photo_events_folder", "photo_events", ["folder"])
    op.create_index("ix_photo_events_created_at", "photo_events", ["created_at"])
    op.create_index("ix_photo_events_telegram_sent", "photo_events", ["telegram_sent"])

    op.create_table(
        "photo_monitor_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("watch_folder", sa.String(length=1000), nullable=False),
        sa.Column("recursive", sa.Boolean(), nullable=False),
        sa.Column("scan_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("max_events", sa.Integer(), nullable=False),
        sa.Column("auto_delete_days", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("photo_monitor_settings")
    op.drop_index("ix_photo_events_telegram_sent", table_name="photo_events")
    op.drop_index("ix_photo_events_created_at", table_name="photo_events")
    op.drop_index("ix_photo_events_folder", table_name="photo_events")
    op.drop_table("photo_events")
