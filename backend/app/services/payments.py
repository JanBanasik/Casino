"""Chip purchases (Stripe) and cash-outs, with a fiat⇄chip exchange rate.

Rate: ``settings.chips_per_currency_unit`` chips == 1 unit of fiat. With the
default of 5, a chip is worth 0.20 zł (one fiat unit equals the smallest stake
available in any game), so chips are deliberately worth less than a złoty.

When ``STRIPE_SECRET_KEY`` is unset the service runs in *dev simulation* mode:
purchases are credited immediately with no real charge, so the app is fully
usable without Stripe keys. With a key set, real Stripe Checkout is used and
chips are credited from the webhook on ``checkout.session.completed``.
"""
from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import TransactionType, Withdrawal, WithdrawalStatus
from app.services.wallet import WalletService


def chips_to_minor(chips: float) -> int:
    """Chips → fiat minor units (grosze)."""
    fiat = chips / settings.chips_per_currency_unit
    return int(round(fiat * 100))


def minor_to_chips(amount_minor: int) -> float:
    """Fiat minor units → chips."""
    fiat = amount_minor / 100.0
    return round(fiat * settings.chips_per_currency_unit, 2)


def _normalize_account(raw: str) -> str | None:
    """Validate and normalize a bank account number / IBAN.

    Accepts a Polish NRB (26 digits) or an IBAN (country prefix + digits),
    tolerating spaces. Returns the normalized string, or None if invalid.
    """
    s = re.sub(r"\s+", "", raw or "").upper()
    if not (15 <= len(s) <= 34) or not s.isalnum():
        return None
    if sum(c.isdigit() for c in s) < 15:
        return None
    return s


class PaymentError(Exception):
    pass


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Purchase ──────────────────────────────────────────────────────────────

    async def create_checkout(self, user_id: UUID, chips: float) -> dict:
        """Start a chip purchase. Returns a dict describing how to proceed."""
        amount_minor = chips_to_minor(chips)
        if amount_minor <= 0:
            raise PaymentError("amount_too_small")

        if not settings.stripe_enabled:
            # Dev mode: credit immediately, no real charge.
            balance = await self._credit_purchase(user_id, chips, amount_minor)
            return {
                "simulated": True,
                "url": None,
                "balance": balance,
                "amount_minor": amount_minor,
                "currency": settings.payment_currency,
            }

        try:
            import stripe
        except Exception as exc:  # pragma: no cover - only without the package
            raise PaymentError(f"stripe_unavailable:{exc}") from exc

        stripe.api_key = settings.stripe_secret_key
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": settings.payment_currency,
                        "product_data": {"name": f"{round(chips)} żetonów"},
                        "unit_amount": amount_minor,
                    },
                    "quantity": 1,
                }
            ],
            success_url=settings.payment_success_url,
            cancel_url=settings.payment_cancel_url,
            metadata={"user_id": str(user_id), "chips": str(chips)},
        )
        return {
            "simulated": False,
            "url": session.url,
            "balance": None,
            "amount_minor": amount_minor,
            "currency": settings.payment_currency,
        }

    async def _credit_purchase(
        self, user_id: UUID, chips: float, amount_minor: int
    ) -> float:
        wallet_svc = WalletService(self.session)
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            raise PaymentError("no_wallet")
        await wallet_svc.apply_amount(wallet.id, chips, TransactionType.purchase)
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        return wallet.balance if wallet else 0.0

    async def fulfill_webhook(self, payload: bytes, sig_header: str | None) -> bool:
        """Verify a Stripe webhook and credit chips on a completed checkout."""
        if not settings.stripe_enabled:
            return False
        try:
            import stripe
        except Exception as exc:  # pragma: no cover
            raise PaymentError(f"stripe_unavailable:{exc}") from exc

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except Exception as exc:
            raise PaymentError(f"invalid_signature:{exc}") from exc

        if event["type"] != "checkout.session.completed":
            return False
        session = event["data"]["object"]
        meta = session.get("metadata") or {}
        user_id = meta.get("user_id")
        chips = meta.get("chips")
        if not user_id or not chips:
            return False
        amount_minor = session.get("amount_total") or chips_to_minor(float(chips))
        await self._credit_purchase(UUID(user_id), float(chips), int(amount_minor))
        await self.session.commit()
        return True

    # ── Withdrawal ────────────────────────────────────────────────────────────

    async def withdraw(self, user_id: UUID, chips: float, account_number: str) -> dict:
        account = _normalize_account(account_number)
        if account is None:
            raise PaymentError("invalid_account_number")
        if chips < settings.withdraw_min_chips:
            raise PaymentError("below_min_withdrawal")
        wallet_svc = WalletService(self.session)
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        if wallet is None:
            raise PaymentError("no_wallet")
        if wallet.balance < chips:
            raise PaymentError("insufficient_balance")

        amount_minor = chips_to_minor(chips)
        await wallet_svc.apply_amount(wallet.id, -chips, TransactionType.withdrawal)
        withdrawal = Withdrawal(
            user_id=user_id,
            chips=chips,
            amount_minor=amount_minor,
            currency=settings.payment_currency,
            status=WithdrawalStatus.requested,
            payout_account=account,
        )
        self.session.add(withdrawal)
        await self.session.flush()
        wallet = await wallet_svc.get_wallet_for_user(user_id)
        return {
            "chips": chips,
            "amount_minor": amount_minor,
            "currency": settings.payment_currency,
            "status": WithdrawalStatus.requested.value,
            "balance": wallet.balance if wallet else 0.0,
        }
