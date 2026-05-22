from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.dto import SessionCreateRequest, SessionResponse, WsTicketRequest, WsTicketResponse
from app.core.ws_tickets import create_ws_ticket
from app.db.models import GameSession, GameType, User
from app.db.redis_client import get_redis

router = APIRouter()


@router.post("", response_model=SessionResponse)
async def create_session(
    body: SessionCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    if body.game_type != "blackjack":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_game_type")
    gs = GameSession(user_id=user.id, game_type=GameType.blackjack)
    db.add(gs)
    await db.commit()
    await db.refresh(gs)
    return SessionResponse(
        id=gs.id,
        game_type=gs.game_type.value,
        started_at=gs.started_at.isoformat(),
    )


@router.post("/{session_id}/ws-ticket", response_model=WsTicketResponse)
async def mint_ws_ticket(
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
