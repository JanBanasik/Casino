from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import GameSession, GameType, Round, RoundResult, TransactionType, User
from app.engine.roulette import (
    BetType,
    RouletteBet,
    evaluate_bets,
    spin,
    total_staked,
)
from app.services.wallet import WalletService

router = APIRouter()


class RouletteBetRequest(BaseModel):
    bet_type: str
    amount: float = Field(gt=0)
    number: int | None = None
    numbers: list[int] | None = None
    choice: str | None = None


class RouletteSpinRequest(BaseModel):
    session_id: UUID
    bets: list[RouletteBetRequest] = Field(min_length=1)


class RouletteSpinResponse(BaseModel):
    result: int
    color: str
    payouts: list[dict]
    total_payout: float
    net: float
    new_balance: float


@router.post("/spin", response_model=RouletteSpinResponse)
async def roulette_spin(
    body: RouletteSpinRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RouletteSpinResponse:
    # Validate session
    res = await db.execute(
        select(GameSession).where(
            GameSession.id == body.session_id,
            GameSession.user_id == user.id,
        )
    )
    gs = res.scalar_one_or_none()
    if gs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")
    if gs.game_type != GameType.roulette:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="wrong_game_type")

    # Parse bets
    try:
        bets = [
            RouletteBet(
                bet_type=BetType(b.bet_type),
                amount=b.amount,
                number=b.number,
                numbers=b.numbers,
                choice=b.choice,
            )
            for b in body.bets
        ]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    total_bet = total_staked(bets)

    wallet_svc = WalletService(db)
    wallet = await wallet_svc.get_wallet_for_user(user.id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_wallet")
    if wallet.balance < total_bet:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="insufficient_balance")

    # Deduct total stake
    await wallet_svc.apply_amount(wallet.id, -total_bet, TransactionType.bet)

    # Spin
    result_num = spin()
    from app.engine.roulette import number_color
    result_color = number_color(result_num)

    # Evaluate
    payouts = evaluate_bets(result_num, bets)
    payout_total = sum(p["payout"] for p in payouts)

    # Credit winnings
    if payout_total > 0:
        await wallet_svc.apply_amount(wallet.id, payout_total, TransactionType.win)

    net = payout_total - total_bet

    # Save round
    result_key = "win" if net > 0 else ("draw" if net == 0 else "loss")
    rr = RoundResult[result_key]
    db.add(Round(
        session_id=body.session_id,
        result=rr,
        payout_amount=payout_total,
        ai_actions={"game": "roulette", "result": result_num, "color": result_color},
    ))
    await db.commit()
    await db.refresh(wallet)

    return RouletteSpinResponse(
        result=result_num,
        color=result_color,
        payouts=payouts,
        total_payout=payout_total,
        net=net,
        new_balance=wallet.balance,
    )
