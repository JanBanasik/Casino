"""add wallet bonus tracking columns

Revision ID: c2d3e4f5a6b7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallets",
        sa.Column(
            "welcome_bonus_claimed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "wallets",
        sa.Column("daily_streak", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "wallets",
        sa.Column("last_daily_claim_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "wallets",
        sa.Column("last_rescue_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "rounds",
        sa.Column("bet_amount", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("rounds", "bet_amount")
    op.drop_column("wallets", "last_rescue_at")
    op.drop_column("wallets", "last_daily_claim_at")
    op.drop_column("wallets", "daily_streak")
    op.drop_column("wallets", "welcome_bonus_claimed")
