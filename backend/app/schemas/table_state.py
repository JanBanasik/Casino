from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.engine.blackjack import BlackjackPhase, BlackjackState


class RedisTableState(BaseModel):
    """Hot game state stored in Redis (Blackjack MVP)."""

    session_id: UUID
    user_id: UUID
    table_id: str
    deck: list[str]
    player_hand: list[str]
    dealer_hand: list[str]
    phase: BlackjackPhase
    bet: float = Field(ge=0)
    message: str | None = None

    @classmethod
    def from_blackjack(
        cls, table_id: str, session_id: UUID, user_id: UUID, st: BlackjackState
    ) -> RedisTableState:
        return cls(
            session_id=session_id,
            user_id=user_id,
            table_id=table_id,
            deck=st.deck,
            player_hand=st.player_hand,
            dealer_hand=st.dealer_hand,
            phase=st.phase,
            bet=st.bet,
            message=st.message,
        )

    def to_blackjack(self) -> BlackjackState:
        return BlackjackState(
            deck=list(self.deck),
            player_hand=list(self.player_hand),
            dealer_hand=list(self.dealer_hand),
            phase=self.phase,
            bet=self.bet,
            message=self.message,
        )

    def redis_key(self) -> str:
        return f"table:{self.table_id}:state"


def table_state_key(table_id: str) -> str:
    return f"table:{table_id}:state"


async def load_table_state(redis, table_id: str) -> RedisTableState | None:
    raw = await redis.get(table_state_key(table_id))
    if not raw:
        return None
    data: dict[str, Any] = json.loads(raw)
    data["session_id"] = UUID(data["session_id"])
    data["user_id"] = UUID(data["user_id"])
    data["phase"] = BlackjackPhase(data["phase"])
    return RedisTableState.model_validate(data)


async def save_table_state(redis, state: RedisTableState, ttl_seconds: int) -> None:
    payload = state.model_dump(mode="json")
    payload["session_id"] = str(state.session_id)
    payload["user_id"] = str(state.user_id)
    payload["phase"] = state.phase.value
    await redis.set(state.redis_key(), json.dumps(payload), ex=ttl_seconds)
