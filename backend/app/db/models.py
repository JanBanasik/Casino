import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TransactionType(str, enum.Enum):
    deposit = "deposit"
    bet = "bet"
    win = "win"
    bonus = "bonus"
    purchase = "purchase"
    withdrawal = "withdrawal"


class WithdrawalStatus(str, enum.Enum):
    requested = "requested"
    paid = "paid"
    rejected = "rejected"


class GameType(str, enum.Enum):
    blackjack = "blackjack"
    poker = "poker"
    roulette = "roulette"


class RoundResult(str, enum.Enum):
    win = "win"
    loss = "loss"
    draw = "draw"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    wallet: Mapped["Wallet | None"] = relationship(back_populates="user", uselist=False)
    game_sessions: Mapped[list["GameSession"]] = relationship(back_populates="user")


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retention_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    welcome_bonus_claimed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    daily_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_daily_claim_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_rescue_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="wallet")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type_enum"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    wallet: Mapped["Wallet"] = relationship(back_populates="transactions")


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_type: Mapped[GameType] = mapped_column(
        Enum(GameType, name="game_type_enum"), nullable=False, default=GameType.blackjack
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="game_sessions")
    rounds: Mapped[list["Round"]] = relationship(back_populates="session")


class Notification(Base):
    """A bonus/system alert the player must explicitly acknowledge.

    Surfaced off-table (never mid-round) by a blocking modal on the web app.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )


class Withdrawal(Base):
    """A cash-out request: chips converted to fiat at the configured rate."""

    __tablename__ = "withdrawals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chips: Mapped[float] = mapped_column(Float, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)  # fiat in grosze
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="pln")
    payout_account: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus, name="withdrawal_status_enum"),
        nullable=False,
        default=WithdrawalStatus.requested,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    result: Mapped[RoundResult] = mapped_column(
        Enum(RoundResult, name="round_result_enum"), nullable=False
    )
    payout_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bet_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ai_actions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    session: Mapped["GameSession"] = relationship(back_populates="rounds")
