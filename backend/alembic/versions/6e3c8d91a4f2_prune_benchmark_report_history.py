"""prune benchmark report history to five runs per type

Revision ID: 6e3c8d91a4f2
Revises: b29c4a7e13f0
"""
from __future__ import annotations

from typing import Union

from alembic import op


revision: str = "6e3c8d91a4f2"
down_revision: Union[str, None] = "b29c4a7e13f0"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Benchmark evidence is reproducible and the product now deliberately keeps
    # only the five newest reports of each type. Child evidence rows are removed
    # by the existing ON DELETE CASCADE foreign key.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY benchmark_type
                    ORDER BY created_at DESC, id DESC
                ) AS position
            FROM benchmark_runs
        )
        DELETE FROM benchmark_runs AS run
        USING ranked
        WHERE run.id = ranked.id
          AND ranked.position > 5
        """
    )


def downgrade() -> None:
    # Deleted historical reports cannot be reconstructed during downgrade.
    pass
