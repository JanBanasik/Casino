from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Transaction, TransactionType, Wallet
from app.db.resilience import db_resilient


class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_wallet_for_user(self, user_id: UUID) -> Wallet | None:
        result = await self.session.execute(
            select(Wallet).where(Wallet.user_id == user_id).options(selectinload(Wallet.user))
        )
        return result.scalar_one_or_none()

    @db_resilient
    async def apply_amount(
        self,
        wallet_id: UUID,
        amount: float,
        tx_type: TransactionType,
    ) -> Wallet:
        result = await self.session.execute(
            select(Wallet).where(Wallet.id == wallet_id).with_for_update()
        )
        wallet = result.scalar_one()
        wallet.balance += amount
        self.session.add(
            Transaction(
                wallet_id=wallet.id,
                amount=amount,
                transaction_type=tx_type,
            )
        )
        await self.session.flush()
        return wallet
