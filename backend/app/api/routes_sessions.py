from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.dto import SessionCreateRequest, SessionResponse
from app.db.models import GameSession, GameType, User

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
