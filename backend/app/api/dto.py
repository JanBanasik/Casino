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


class SessionCreateRequest(BaseModel):
    game_type: str = "blackjack"


class SessionResponse(BaseModel):
    id: UUID
    game_type: str
    started_at: str
