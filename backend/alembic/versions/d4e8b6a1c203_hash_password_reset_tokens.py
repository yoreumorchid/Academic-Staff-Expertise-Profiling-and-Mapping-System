"""Store password reset token hashes instead of bearer tokens.

Revision ID: d4e8b6a1c203
Revises: 79b86c3f1a27
Create Date: 2026-10-06 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e8b6a1c203"
down_revision: Union[str, None] = "79b86c3f1a27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows contain plaintext bearer secrets and cannot be converted
    # without keeping those secrets usable. Expiring them is the safe migration.
    op.execute("DELETE FROM password_reset_tokens")
    op.drop_constraint(
        "uq_password_reset_token", "password_reset_tokens", type_="unique"
    )
    op.alter_column(
        "password_reset_tokens",
        "token",
        new_column_name="token_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.create_unique_constraint(
        "uq_password_reset_token_hash", "password_reset_tokens", ["token_hash"]
    )


def downgrade() -> None:
    # Hashes cannot be restored to their original bearer secrets. Expire them
    # rather than making the database digest usable as a reset token.
    op.execute("DELETE FROM password_reset_tokens")
    op.drop_constraint(
        "uq_password_reset_token_hash", "password_reset_tokens", type_="unique"
    )
    op.alter_column(
        "password_reset_tokens",
        "token_hash",
        new_column_name="token",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
    op.create_unique_constraint(
        "uq_password_reset_token", "password_reset_tokens", ["token"]
    )
