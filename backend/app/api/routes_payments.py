from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.dto import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentConfigResponse,
    WithdrawRequest,
    WithdrawResponse,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.db.models import User
from app.services.payments import PaymentError, PaymentService

router = APIRouter()


@router.get("/config", response_model=PaymentConfigResponse)
@limiter.limit("60/minute")
async def payment_config(request: Request) -> PaymentConfigResponse:
    return PaymentConfigResponse(
        stripe_enabled=settings.stripe_enabled,
        publishable_key=settings.stripe_publishable_key,
        currency=settings.payment_currency,
        chips_per_currency_unit=settings.chips_per_currency_unit,
        withdraw_min_chips=settings.withdraw_min_chips,
    )


@router.post("/checkout", response_model=CheckoutResponse)
@limiter.limit("20/minute")
async def create_checkout(
    request: Request,
    body: CheckoutRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutResponse:
    svc = PaymentService(db)
    try:
        result = await svc.create_checkout(user.id, body.chips)
    except PaymentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return CheckoutResponse(**result)


@router.post("/withdraw", response_model=WithdrawResponse)
@limiter.limit("20/minute")
async def withdraw(
    request: Request,
    body: WithdrawRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WithdrawResponse:
    svc = PaymentService(db)
    try:
        result = await svc.withdraw(user.id, body.chips, body.account_number)
    except PaymentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return WithdrawResponse(**result)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    svc = PaymentService(db)
    try:
        handled = await svc.fulfill_webhook(payload, sig)
    except PaymentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"handled": handled}
