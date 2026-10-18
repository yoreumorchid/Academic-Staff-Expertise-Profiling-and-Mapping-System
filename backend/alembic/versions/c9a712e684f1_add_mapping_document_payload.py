"""add mapping document representation provenance

Revision ID: c9a712e684f1
Revises: d4e8b6a1c203
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c9a712e684f1"
down_revision: Union[str, None] = "d4e8b6a1c203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "course_grant_specs",
        sa.Column("document_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("course_grant_specs", "document_payload")
