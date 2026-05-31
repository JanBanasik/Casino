from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dto import LoginRequest, RegisterRequest, TokenResponse
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, Wallet

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    exists = await db.execute(select(User.id).where(User.username == body.username))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")
    exists_email = await db.execute(select(User.id).where(User.email == str(body.email)))
    if exists_email.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_taken")

    user = User(
        username=body.username,
        email=str(body.email),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    wallet = Wallet(user_id=user.id, balance=0.0, retention_level=0)
    db.add(wallet)
    await db.commit()
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    res = await db.execute(select(User).where(User.username == body.username))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        logger.warning("Failed login attempt for username={}", body.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)
