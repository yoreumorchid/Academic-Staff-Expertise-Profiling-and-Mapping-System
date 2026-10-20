"""allow descriptive peer evidence without a coverage distance

Revision ID: 91c7e4b2d5a0
Revises: 6e3c8d91a4f2
"""
from __future__ import annotations

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "91c7e4b2d5a0"
down_revision: Union[str, None] = "6e3c8d91a4f2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column(
        "benchmark_white_spaces",
        "displacement_score",
        existing_type=sa.Float(),
        nullable=True,
    )
    # Earlier peer reports treated arbitrary document chunks as staff-coverage
    # evidence. Keep their source excerpts, but remove those derived claims so
    # historical reports follow the same descriptive-only interpretation.
    op.execute(
        """
        UPDATE benchmark_white_spaces AS evidence
        SET displacement_score = NULL,
            nearest_staff_id = NULL,
            nearest_staff_name = NULL,
            nearest_cluster_label = NULL,
            nearest_cluster_distance = NULL,
            coverage_classification = NULL,
            recommendation = NULL,
            review_status = 'source_overview'
        FROM benchmark_runs AS run
        WHERE evidence.run_id = run.id
          AND run.benchmark_type = 'PEER'
        """
    )
    op.execute(
        """
        UPDATE benchmark_runs
        SET narrative = NULL,
            visualization_payload = NULL,
            source_payload = COALESCE(source_payload, '{}'::jsonb) || jsonb_build_object(
                'mode', 'descriptive_curriculum_overview',
                'staff_comparison_used', false,
                'gap_classification_used', false,
                'interpretation', 'Historical peer source excerpts are shown as a curriculum overview only; previous automated staff-gap claims were removed.'
            )
        WHERE benchmark_type = 'PEER'
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM benchmark_white_spaces WHERE displacement_score IS NULL"
    )
    op.alter_column(
        "benchmark_white_spaces",
        "displacement_score",
        existing_type=sa.Float(),
        nullable=False,
    )
