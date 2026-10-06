"""Add observable progress stage to synchronization jobs.

Revision ID: 79b86c3f1a27
Revises: 7b7c21a9d1e4
Create Date: 2026-10-05 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "79b86c3f1a27"
down_revision: Union[str, None] = "7b7c21a9d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sync_jobs",
        sa.Column(
            "progress_stage",
            sa.String(length=64),
            nullable=False,
            server_default="queued",
        ),
    )
    op.alter_column("sync_jobs", "progress_stage", server_default=None)


def downgrade() -> None:
    op.drop_column("sync_jobs", "progress_stage")
