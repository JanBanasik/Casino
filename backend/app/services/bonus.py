"""Player-economy bonuses for the play-money casino.

All amounts are tunable via :class:`app.core.config.Settings` (env vars), never
hard-coded at the call sites. The service is deliberately game-agnostic so the
same loss-streak / rescue rules apply to blackjack, poker and roulette.

Bonuses:
    * welcome      — one-off grant when a wallet first comes to life.
    * daily        — escalating reward, claimable once per cooldown window.
    * loss refund  — every N consecutive losses, refund a fraction of those stakes.
    * rescue       — top the wallet up when it can no longer cover a min bet.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.db.models import GameSession, Round, RoundResult, TransactionType, Wallet
from app.services.notifications import NotificationService


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    """Postgres may hand back naive datetimes depending on the driver/config."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class BonusService:
    def __init__(self, session):
        self.session = session

    # ── Welcome ───────────────────────────────────────────────────────────────

    async def grant_welcome(self, wallet: Wallet, wallet_service) -> float:
        """Grant the one-off welcome bonus. Returns the amount (0 if already claimed)."""
        if wallet.welcome_bonus_claimed:
            return 0.0
        amount = settings.bonus_welcome
        await wallet_service.apply_amount(wallet.id, amount, TransactionType.bonus)
        wallet.welcome_bonus_claimed = True
        await self.session.flush()
        return amount

    # ── Daily ─────────────────────────────────────────────────────────────────

    def _daily_amount(self, streak: int) -> float:
        amount = settings.bonus_daily_base + settings.bonus_daily_step * max(0, streak - 1)
        return min(amount, settings.bonus_daily_max)

    async def daily_status(self, wallet: Wallet) -> dict:
        """Whether the daily reward is claimable and what it would be worth."""
        now = _utcnow()
        last = _aware(wallet.last_daily_claim_at)
        cooldown = timedelta(hours=settings.bonus_daily_cooldown_hours)
        available = last is None or now - last >= cooldown
        # A gap of >2 cooldown windows resets the streak.
        streak_continues = last is not None and now - last < cooldown * 2
        next_streak = (wallet.daily_streak + 1) if streak_continues else 1
        next_available_at = None if available else (last + cooldown)
        return {
            "available": available,
            "streak": wallet.daily_streak,
            "next_amount": self._daily_amount(next_streak if available else wallet.daily_streak),
            "next_available_at": next_available_at.isoformat() if next_available_at else None,
        }

    async def claim_daily(self, wallet: Wallet, wallet_service) -> tuple[bool, float, int]:
        """Claim the daily reward. Returns (granted, amount, new_streak)."""
        now = _utcnow()
        last = _aware(wallet.last_daily_claim_at)
        cooldown = timedelta(hours=settings.bonus_daily_cooldown_hours)
        if last is not None and now - last < cooldown:
            return False, 0.0, wallet.daily_streak
        streak_continues = last is not None and now - last < cooldown * 2
        new_streak = (wallet.daily_streak + 1) if streak_continues else 1
        amount = self._daily_amount(new_streak)
        await wallet_service.apply_amount(wallet.id, amount, TransactionType.bonus)
        wallet.daily_streak = new_streak
        wallet.last_daily_claim_at = now
        await self.session.flush()
        return True, amount, new_streak

    # ── Loss-streak refund ────────────────────────────────────────────────────

    async def _recent_loss_streak(self, user_id: UUID, max_scan: int = 60) -> list[float]:
        """Stakes of the current run of consecutive losses (most recent first)."""
        q = (
            select(Round.result, Round.bet_amount)
            .join(GameSession, Round.session_id == GameSession.id)
            .where(GameSession.user_id == user_id)
            .order_by(Round.created_at.desc())
            .limit(max_scan)
        )
        rows = (await self.session.execute(q)).all()
        stakes: list[float] = []
        for res, bet in rows:
            if res == RoundResult.loss:
                stakes.append(float(bet or 0.0))
            else:
                break
        return stakes

    async def maybe_loss_refund(self, user_id: UUID, wallet_service) -> tuple[bool, float]:
        """Every N consecutive losses, refund a fraction of those N stakes.

        Fires when the streak length is a positive multiple of N, using the
        stakes of the most recent N losses so the refund scales with how much
        the player actually risked (and can never exceed the loss).
        """
        n = settings.bonus_loss_streak_count
        stakes = await self._recent_loss_streak(user_id)
        if n <= 0 or len(stakes) == 0 or len(stakes) % n != 0:
            return False, 0.0
        window = stakes[:n]
        refund = round(min(sum(window) * settings.bonus_loss_refund_pct,
                           settings.bonus_loss_refund_cap), 2)
        if refund <= 0:
            return False, 0.0
        wallet = await wallet_service.get_wallet_for_user(user_id)
        if wallet is None:
            return False, 0.0
        await wallet_service.apply_amount(wallet.id, refund, TransactionType.bonus)
        wallet.retention_level += 1
        await self.session.flush()
        return True, refund

    # ── Rescue ────────────────────────────────────────────────────────────────

    async def maybe_rescue(self, user_id: UUID, wallet_service) -> tuple[bool, float]:
        """Top the wallet up to the rescue target when it can't cover a min bet."""
        wallet = await wallet_service.get_wallet_for_user(user_id)
        if wallet is None:
            return False, 0.0
        if wallet.balance >= settings.bonus_rescue_threshold:
            return False, 0.0
        now = _utcnow()
        last = _aware(wallet.last_rescue_at)
        cooldown = timedelta(minutes=settings.bonus_rescue_cooldown_minutes)
        if last is not None and now - last < cooldown:
            return False, 0.0
        topup = round(settings.bonus_rescue_target - wallet.balance, 2)
        if topup <= 0:
            return False, 0.0
        await wallet_service.apply_amount(wallet.id, topup, TransactionType.bonus)
        wallet.last_rescue_at = now
        await self.session.flush()
        return True, topup

    # ── Combined post-round hook ──────────────────────────────────────────────

    async def settle_post_round(
        self, user_id: UUID, wallet_service, *, was_loss: bool
    ) -> dict | None:
        """Run loss-refund (on a loss) then rescue. Returns a payload or None.

        Shared by every game's finalizer so the rules stay identical across
        blackjack, poker and roulette.
        """
        payload: dict = {}
        notifications = NotificationService(self.session)
        if was_loss:
            granted, amount = await self.maybe_loss_refund(user_id, wallet_service)
            if granted:
                payload["loss_refund"] = True
                payload["loss_refund_amount"] = amount
                await notifications.create(
                    user_id,
                    kind="loss_refund",
                    title="Zwrot za pechową serię",
                    body=(
                        f"Trafiła Ci się seria przegranych — oddajemy część stawek: "
                        f"+{round(amount)} żetonów."
                    ),
                    amount=amount,
                )
        rescued, topup = await self.maybe_rescue(user_id, wallet_service)
        if rescued:
            payload["rescue"] = True
            payload["rescue_amount"] = topup
            await notifications.create(
                user_id,
                kind="rescue",
                title="Koło ratunkowe",
                body=(
                    f"Twoje saldo było na zerze — doładowaliśmy konto o "
                    f"+{round(topup)} żetonów, żebyś mógł grać dalej."
                ),
                amount=topup,
            )
        return payload or None
