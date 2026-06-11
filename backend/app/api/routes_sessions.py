from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.dto import (
    RoundHistoryItem,
    RoundHistoryResponse,
    SessionCreateRequest,
    SessionResponse,
    WsTicketRequest,
    WsTicketResponse,
)
from app.core.limiter import limiter
from app.core.ws_tickets import create_ws_ticket
from app.db.models import GameSession, GameType, Round, User
from app.db.redis_client import get_redis

router = APIRouter()


@router.get("/history", response_model=RoundHistoryResponse)
@limiter.limit("60/minute")
async def round_history(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 25,
) -> RoundHistoryResponse:
    limit = max(1, min(limit, 100))
    q = (
        select(Round, GameSession.game_type)
        .join(GameSession, Round.session_id == GameSession.id)
        .where(GameSession.user_id == user.id)
        .order_by(Round.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    items = [
        RoundHistoryItem(
            id=rnd.id,
            game_type=game_type.value,
            result=rnd.result.value,
            bet_amount=rnd.bet_amount,
            payout_amount=rnd.payout_amount,
            net=rnd.payout_amount - rnd.bet_amount,
            created_at=rnd.created_at.isoformat(),
        )
        for rnd, game_type in rows
    ]
    return RoundHistoryResponse(rounds=items)


@router.post("", response_model=SessionResponse)
@limiter.limit("30/minute")
async def create_session(
    request: Request,
    body: SessionCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    _game_type_map = {
        "blackjack": GameType.blackjack,
        "poker": GameType.poker,
        "roulette": GameType.roulette,
    }
    if body.game_type not in _game_type_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_game_type")
    gs = GameSession(user_id=user.id, game_type=_game_type_map[body.game_type])
    db.add(gs)
    await db.commit()
    await db.refresh(gs)
    return SessionResponse(
        id=gs.id,
        game_type=gs.game_type.value,
        started_at=gs.started_at.isoformat(),
    )


@router.post("/{session_id}/ws-ticket", response_model=WsTicketResponse)
@limiter.limit("60/minute")
async def mint_ws_ticket(
    request: Request,
    session_id: UUID,
    body: WsTicketRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WsTicketResponse:
    res = await db.execute(
        select(GameSession).where(
            GameSession.id == session_id,
            GameSession.user_id == user.id,
        )
    )
    session = res.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found")
    if session.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_ended")

    ticket, expires_in = await create_ws_ticket(
        get_redis(),
        user_id=user.id,
        session_id=session_id,
        table_id=body.table_id,
    )
    return WsTicketResponse(ticket=ticket, table_id=body.table_id, expires_in=expires_in)
