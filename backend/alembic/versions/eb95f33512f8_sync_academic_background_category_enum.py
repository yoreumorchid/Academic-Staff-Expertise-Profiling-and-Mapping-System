"""sync_academic_background_category_enum

Revision ID: eb95f33512f8
Revises: 3c3176afb43c
Create Date: 2026-06-14 12:59:30.070160
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = 'eb95f33512f8'
down_revision: Union[str, None] = '3c3176afb43c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE academic_background_category RENAME TO academic_background_category_old")
    op.execute("CREATE TYPE academic_background_category AS ENUM ('education', 'appointment', 'award', 'service')")
    op.execute(
        "ALTER TABLE academic_background ALTER COLUMN category "
        "TYPE academic_background_category USING category::text::academic_background_category"
    )
    op.execute("DROP TYPE academic_background_category_old")


def downgrade() -> None:
    op.execute("ALTER TYPE academic_background_category RENAME TO academic_background_category_new")
    op.execute("CREATE TYPE academic_background_category AS ENUM ('administrative_role', 'award', 'education')")
    op.execute(
        "ALTER TABLE academic_background ALTER COLUMN category "
        "TYPE academic_background_category USING category::text::academic_background_category"
    )
    op.execute("DROP TYPE academic_background_category_new")