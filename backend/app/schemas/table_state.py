from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.engine.blackjack import BlackjackPhase
from app.engine.multi_seat import MultiSeatBlackjackState, SeatState, SeatStatus


class SeatStateModel(BaseModel):
    seat_index: int
    display_name: str
    avatar_key: str
    is_human: bool
    occupant_id: str
    hand: list[str] = Field(default_factory=list)
    bet: float = 0.0
    status: SeatStatus = SeatStatus.waiting
    result: str | None = None
    payout: float = 0.0


class RedisTableState(BaseModel):
    session_id: UUID
    user_id: UUID
    table_id: str
    deck: list[str]
    dealer_hand: list[str]
    phase: BlackjackPhase
    seats: list[SeatStateModel]
    human_seat_index: int = 0
    active_seat_index: int | None = None
    bet: float = Field(default=10.0, ge=0)
    message: str | None = None
    bot_count: int = 0

    @classmethod
    def from_multi(
        cls,
        table_id: str,
        session_id: UUID,
        user_id: UUID,
        st: MultiSeatBlackjackState,
        bot_count: int = 0,
    ) -> RedisTableState:
        human = st.human_seat()
        return cls(
            session_id=session_id,
            user_id=user_id,
            table_id=table_id,
            deck=st.deck,
            dealer_hand=st.dealer_hand,
            phase=st.phase,
            seats=[
                SeatStateModel(
                    seat_index=s.seat_index,
                    display_name=s.display_name,
                    avatar_key=s.avatar_key,
                    is_human=s.is_human,
                    occupant_id=s.occupant_id,
                    hand=list(s.hand),
                    bet=s.bet,
                    status=s.status,
                    result=s.result,
                    payout=s.payout,
                )
                for s in st.seats
            ],
            human_seat_index=st.human_seat_index,
            active_seat_index=st.active_seat_index,
            bet=human.bet,
            message=st.message,
            bot_count=bot_count,
        )

    def to_multi(self) -> MultiSeatBlackjackState:
        seats = [
            SeatState(
                seat_index=s.seat_index,
                display_name=s.display_name,
                avatar_key=s.avatar_key,
                is_human=s.is_human,
                occupant_id=s.occupant_id,
                hand=list(s.hand),
                bet=s.bet,
                status=s.status,
                result=s.result,
                payout=s.payout,
            )
            for s in self.seats
        ]
        return MultiSeatBlackjackState(
            deck=list(self.deck),
            dealer_hand=list(self.dealer_hand),
            seats=seats,
            human_seat_index=self.human_seat_index,
            active_seat_index=self.active_seat_index,
            phase=self.phase,
            message=self.message,
        )

    def to_public_dict(self) -> dict:
        return self.to_multi().to_public_dict()

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
    if "seats" in data:
        for seat in data["seats"]:
            seat["status"] = SeatStatus(seat["status"])
    else:
        data["seats"] = [
            {
                "seat_index": 0,
                "display_name": "Gracz",
                "avatar_key": "you",
                "is_human": True,
                "occupant_id": str(data["user_id"]),
                "hand": data.pop("player_hand", []),
                "bet": data.get("bet", 10),
                "status": SeatStatus.acting.value,
                "result": None,
                "payout": 0.0,
            }
        ]
        data["human_seat_index"] = 0
        data["active_seat_index"] = 0 if data["phase"] == "player_turn" else None
        data["bot_count"] = 0
    return RedisTableState.model_validate(data)


async def save_table_state(redis, state: RedisTableState, ttl_seconds: int) -> None:
    payload = state.model_dump(mode="json")
    payload["session_id"] = str(state.session_id)
    payload["user_id"] = str(state.user_id)
    payload["phase"] = state.phase.value
    for seat in payload["seats"]:
        seat["status"] = seat["status"] if isinstance(seat["status"], str) else seat["status"]
    await redis.set(state.redis_key(), json.dumps(payload), ex=ttl_seconds)
