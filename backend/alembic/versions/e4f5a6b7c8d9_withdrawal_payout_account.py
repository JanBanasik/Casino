"""add payout account (IBAN) to withdrawals

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "withdrawals",
        sa.Column("payout_account", sa.String(40), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("withdrawals", "payout_account")
