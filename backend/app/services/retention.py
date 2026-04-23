from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameSession, Round, RoundResult, TransactionType


class RetentionService:
    """MVP: three losses in a row -> bonus credit."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def consecutive_loss_streak(self, user_id: UUID, max_scan: int = 50) -> int:
        q = (
            select(Round.result)
            .join(GameSession, Round.session_id == GameSession.id)
            .where(GameSession.user_id == user_id)
            .order_by(Round.created_at.desc())
            .limit(max_scan)
        )
        rows = (await self.session.execute(q)).all()
        streak = 0
        for (res,) in rows:
            if res == RoundResult.loss:
                streak += 1
            else:
                break
        return streak

    async def maybe_bad_beat_bonus(self, user_id: UUID, wallet_service) -> tuple[bool, float]:
        """
        After a loss, grant bonus exactly when the player reaches 3 consecutive losses.
        Returns (granted, bonus_amount).
        """
        losses = await self.consecutive_loss_streak(user_id)
        if losses != 3:
            return False, 0.0
        bonus = 500.0
        wallet = await wallet_service.get_wallet_for_user(user_id)
        if wallet is None:
            return False, 0.0
        await wallet_service.apply_amount(
            wallet.id,
            bonus,
            TransactionType.bonus,
        )
        wallet.retention_level += 1
        await self.session.flush()
        return True, bonus
