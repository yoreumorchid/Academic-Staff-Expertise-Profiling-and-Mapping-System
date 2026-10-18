"""add reviewable peer benchmark evidence

Revision ID: f3a1c9d84e62
Revises: c9a712e684f1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3a1c9d84e62"
down_revision: Union[str, None] = "c9a712e684f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("benchmark_white_spaces", sa.Column("peer_filename", sa.String(255)))
    op.add_column("benchmark_white_spaces", sa.Column("detected_section", sa.String(255)))
    op.add_column("benchmark_white_spaces", sa.Column("source_excerpt", sa.Text()))
    op.add_column("benchmark_white_spaces", sa.Column("nearest_staff_id", sa.Uuid()))
    op.add_column("benchmark_white_spaces", sa.Column("nearest_staff_name", sa.String(255)))
    op.add_column("benchmark_white_spaces", sa.Column("nearest_cluster_label", sa.String(255)))
    op.add_column("benchmark_white_spaces", sa.Column("nearest_cluster_distance", sa.Float()))
    op.add_column("benchmark_white_spaces", sa.Column("coverage_classification", sa.String(32)))
    op.add_column("benchmark_white_spaces", sa.Column("review_status", sa.String(48)))
    op.create_foreign_key(
        "fk_benchmark_white_spaces_nearest_staff_id_users",
        "benchmark_white_spaces",
        "users",
        ["nearest_staff_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_benchmark_white_spaces_nearest_staff_id_users",
        "benchmark_white_spaces",
        type_="foreignkey",
    )
    for column in (
        "review_status",
        "coverage_classification",
        "nearest_cluster_distance",
        "nearest_cluster_label",
        "nearest_staff_name",
        "nearest_staff_id",
        "source_excerpt",
        "detected_section",
        "peer_filename",
    ):
        op.drop_column("benchmark_white_spaces", column)
