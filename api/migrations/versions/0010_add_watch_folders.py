"""Add watch_folders JSON for Photo Monitor multi-folder support.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "photo_monitor_settings",
        sa.Column("watch_folders", sa.JSON(), nullable=True),
    )
    settings = sa.table(
        "photo_monitor_settings",
        sa.column("id", sa.Integer),
        sa.column("watch_folder", sa.String),
        sa.column("watch_folders", sa.JSON),
    )
    connection = op.get_bind()
    rows = connection.execute(sa.select(settings.c.id, settings.c.watch_folder)).fetchall()
    for row_id, watch_folder in rows:
        folders = [watch_folder] if watch_folder else []
        connection.execute(
            settings.update().where(settings.c.id == row_id).values(watch_folders=folders)
        )


def downgrade() -> None:
    op.drop_column("photo_monitor_settings", "watch_folders")
