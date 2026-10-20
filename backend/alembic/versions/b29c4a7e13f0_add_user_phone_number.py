"""add optional user phone number

Revision ID: b29c4a7e13f0
Revises: a61d72e5b904
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "b29c4a7e13f0"
down_revision: Union[str, None] = "a61d72e5b904"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Nullable preserves existing and restored accounts; new academic
    # registrations enforce the requirement at the API boundary.
    op.add_column("users", sa.Column("phone_number", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone_number")
