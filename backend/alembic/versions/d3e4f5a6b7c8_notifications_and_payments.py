"""notifications, withdrawals and payment transaction types

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-10 14:00:00.000000

Written as idempotent raw SQL: asyncpg's handling of ``ALTER TYPE ... ADD VALUE``
is non-transactional, so we cannot rely on rollback to undo partial DDL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'purchase'"))
    op.execute(sa.text("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'withdrawal'"))

    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "CREATE TYPE withdrawal_status_enum AS ENUM ('requested', 'paid', 'rejected'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $$;"
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind VARCHAR(32) NOT NULL,
                title VARCHAR(120) NOT NULL,
                body TEXT NOT NULL,
                amount DOUBLE PRECISION NOT NULL DEFAULT 0,
                acknowledged BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications(created_at)"
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS withdrawals (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                chips DOUBLE PRECISION NOT NULL,
                amount_minor INTEGER NOT NULL,
                currency VARCHAR(8) NOT NULL DEFAULT 'pln',
                status withdrawal_status_enum NOT NULL DEFAULT 'requested',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_withdrawals_user_id ON withdrawals(user_id)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS withdrawals"))
    op.execute(sa.text("DROP TABLE IF EXISTS notifications"))
    op.execute(sa.text("DROP TYPE IF EXISTS withdrawal_status_enum"))
