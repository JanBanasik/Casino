from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.dto import DepositRequest, WalletResponse
from app.db.models import TransactionType, User
from app.services.wallet import WalletService

router = APIRouter()


@router.get("/me", response_model=WalletResponse)
async def wallet_me(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WalletResponse:
    svc = WalletService(db)
    wallet = await svc.get_wallet_for_user(user.id)
    if wallet is None:
        return WalletResponse(balance=0.0, retention_level=0)
    return WalletResponse(balance=wallet.balance, retention_level=wallet.retention_level)


@router.post("/deposit", response_model=WalletResponse)
async def deposit(
    body: DepositRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WalletResponse:
    svc = WalletService(db)
    wallet = await svc.get_wallet_for_user(user.id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_wallet")
    await svc.apply_amount(wallet.id, body.amount, TransactionType.deposit)
    await db.commit()
    wallet = await svc.get_wallet_for_user(user.id)
    assert wallet is not None
    return WalletResponse(balance=wallet.balance, retention_level=wallet.retention_level)
