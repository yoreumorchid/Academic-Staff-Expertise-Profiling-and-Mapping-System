"""add reviewable OpenAlex global topic evidence

Revision ID: a61d72e5b904
Revises: f3a1c9d84e62
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a61d72e5b904"
down_revision: Union[str, None] = "f3a1c9d84e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "benchmark_white_spaces", sa.Column("external_source_id", sa.String(64))
    )
    op.add_column(
        "benchmark_white_spaces", sa.Column("external_subfield", sa.String(255))
    )
    op.add_column(
        "benchmark_white_spaces", sa.Column("external_works_count", sa.BigInteger())
    )
    op.add_column(
        "benchmark_white_spaces", sa.Column("external_updated_date", sa.String(64))
    )


def downgrade() -> None:
    for column in (
        "external_updated_date",
        "external_works_count",
        "external_subfield",
        "external_source_id",
    ):
        op.drop_column("benchmark_white_spaces", column)
