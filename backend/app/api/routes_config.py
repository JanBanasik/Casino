from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.limiter import limiter

router = APIRouter()


class GameConfigResponse(BaseModel):
    win_multiplier_easy: float
    win_multiplier_medium: float
    win_multiplier_hard: float
    poker_min_buyin: float


@router.get("/game", response_model=GameConfigResponse)
@limiter.limit("120/minute")
async def game_config(request: Request) -> GameConfigResponse:
    """Public display config so the UI never hard-codes payout multipliers."""
    return GameConfigResponse(
        win_multiplier_easy=settings.win_multiplier_easy,
        win_multiplier_medium=settings.win_multiplier_medium,
        win_multiplier_hard=settings.win_multiplier_hard,
        poker_min_buyin=settings.poker_min_buyin,
    )
