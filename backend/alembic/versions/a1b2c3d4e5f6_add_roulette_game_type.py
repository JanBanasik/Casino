"""add roulette game type

Revision ID: a1b2c3d4e5f6
Revises: bfaac1e87ebc
Create Date: 2026-05-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "bfaac1e87ebc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL allows adding values to an existing enum type
    op.execute(sa.text("ALTER TYPE game_type_enum ADD VALUE IF NOT EXISTS 'roulette'"))


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # In practice, just leave it — removing enum values is destructive.
    pass
