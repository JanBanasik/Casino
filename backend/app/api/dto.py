from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DepositRequest(BaseModel):
    amount: float = Field(gt=0, le=1_000_000)


class WalletResponse(BaseModel):
    balance: float
    retention_level: int


class DailyStatusResponse(BaseModel):
    available: bool
    streak: int
    next_amount: float
    next_available_at: str | None = None


class BonusGrantResponse(BaseModel):
    granted: bool
    amount: float
    balance: float
    message: str | None = None
    streak: int | None = None


class RoundHistoryItem(BaseModel):
    id: UUID
    game_type: str
    result: str
    bet_amount: float
    payout_amount: float
    net: float
    created_at: str


class RoundHistoryResponse(BaseModel):
    rounds: list[RoundHistoryItem]


class NotificationItem(BaseModel):
    id: UUID
    kind: str
    title: str
    body: str
    amount: float
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: list[NotificationItem]


# ── Payments ──────────────────────────────────────────────────────────────────
class PaymentConfigResponse(BaseModel):
    stripe_enabled: bool
    publishable_key: str
    currency: str
    chips_per_currency_unit: float
    withdraw_min_chips: float


class CheckoutRequest(BaseModel):
    chips: float = Field(gt=0, le=10_000_000)


class CheckoutResponse(BaseModel):
    # When Stripe is enabled, `url` redirects to hosted Checkout. In dev mode the
    # purchase is applied immediately and `simulated` is true.
    url: str | None = None
    simulated: bool = False
    balance: float | None = None
    amount_minor: int
    currency: str


class WithdrawRequest(BaseModel):
    chips: float = Field(gt=0, le=10_000_000)
    account_number: str = Field(min_length=10, max_length=40)


class WithdrawResponse(BaseModel):
    chips: float
    amount_minor: int
    currency: str
    status: str
    balance: float


class SessionCreateRequest(BaseModel):
    game_type: str = "blackjack"


class SessionResponse(BaseModel):
    id: UUID
    game_type: str
    started_at: str


class WsTicketRequest(BaseModel):
    table_id: str = Field(default="default", min_length=1, max_length=64)


class WsTicketResponse(BaseModel):
    ticket: str
    table_id: str
    expires_in: int
