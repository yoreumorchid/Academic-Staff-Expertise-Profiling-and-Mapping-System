"""add parent_label to expertise_tags and openalex_author_id to orcid_profiles

Revision ID: 247266f538ba
Revises: 40ba1d6c079f
Create Date: 2026-06-06 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "247266f538ba"
down_revision: Union[str, None] = "40ba1d6c079f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add intermediate umbrella label to expertise_tags for coarse mapping.
    op.add_column(
        "expertise_tags",
        sa.Column("parent_label", sa.String(length=255), nullable=True),
    )
    # Cache the OpenAlex author identifier resolved on first sync.
    op.add_column(
        "orcid_profiles",
        sa.Column("openalex_author_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orcid_profiles", "openalex_author_id")
    op.drop_column("expertise_tags", "parent_label")
