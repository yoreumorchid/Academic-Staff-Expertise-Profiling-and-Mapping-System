"""Prevent more than one active synchronization job per user.

Revision ID: 7b7c21a9d1e4
Revises: eb95f33512f8
Create Date: 2026-10-05 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7b7c21a9d1e4"
down_revision: Union[str, None] = "eb95f33512f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_sync_jobs_one_active_per_user",
        "sync_jobs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_sync_jobs_one_active_per_user",
        table_name="sync_jobs",
    )
