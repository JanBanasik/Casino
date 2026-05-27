from __future__ import annotations

import json
from uuid import UUID

from pydantic import BaseModel, Field

from app.engine.poker import PokerPhase, PokerSeat, PokerState, SeatStatus


class PokerSeatModel(BaseModel):
    seat_index: int
    display_name: str
    avatar_key: str
    is_human: bool
    occupant_id: str
    hole_cards: list[str] = Field(default_factory=list)
    chips: float = 1000.0
    bet_total: float = 0.0
    bet_phase: float = 0.0
    status: SeatStatus = SeatStatus.active
    result: str | None = None
    payout: float = 0.0
    has_acted: bool = False


class RedisPokerState(BaseModel):
    session_id: UUID
    user_id: UUID
    table_id: str
    deck: list[str]
    community_cards: list[str] = Field(default_factory=list)
    seats: list[PokerSeatModel]
    phase: PokerPhase
    pot: float = 0.0
    current_bet: float = 0.0
    min_raise: float = 20.0
    active_seat_index: int | None = None
    dealer_seat_index: int = 0
    human_seat_index: int = 0
    small_blind: float = 10.0
    big_blind: float = 20.0
    bot_count: int = 2
    message: str | None = None

    @classmethod
    def from_poker(
        cls,
        table_id: str,
        session_id: UUID,
        user_id: UUID,
        st: PokerState,
        bot_count: int = 2,
    ) -> RedisPokerState:
        return cls(
            session_id=session_id,
            user_id=user_id,
            table_id=table_id,
            deck=st.deck,
            community_cards=st.community_cards,
            seats=[
                PokerSeatModel(
                    seat_index=s.seat_index,
                    display_name=s.display_name,
                    avatar_key=s.avatar_key,
                    is_human=s.is_human,
                    occupant_id=s.occupant_id,
                    hole_cards=list(s.hole_cards),
                    chips=s.chips,
                    bet_total=s.bet_total,
                    bet_phase=s.bet_phase,
                    status=s.status,
                    result=s.result,
                    payout=s.payout,
                    has_acted=s.has_acted,
                )
                for s in st.seats
            ],
            phase=st.phase,
            pot=st.pot,
            current_bet=st.current_bet,
            min_raise=st.min_raise,
            active_seat_index=st.active_seat_index,
            dealer_seat_index=st.dealer_seat_index,
            human_seat_index=st.human_seat_index,
            small_blind=st.small_blind,
            big_blind=st.big_blind,
            bot_count=bot_count,
            message=st.message,
        )

    def to_poker(self) -> PokerState:
        seats = [
            PokerSeat(
                seat_index=s.seat_index,
                display_name=s.display_name,
                avatar_key=s.avatar_key,
                is_human=s.is_human,
                occupant_id=s.occupant_id,
                hole_cards=list(s.hole_cards),
                chips=s.chips,
                bet_total=s.bet_total,
                bet_phase=s.bet_phase,
                status=s.status,
                result=s.result,
                payout=s.payout,
                has_acted=s.has_acted,
            )
            for s in self.seats
        ]
        return PokerState(
            deck=list(self.deck),
            community_cards=list(self.community_cards),
            seats=seats,
            phase=self.phase,
            pot=self.pot,
            current_bet=self.current_bet,
            min_raise=self.min_raise,
            active_seat_index=self.active_seat_index,
            dealer_seat_index=self.dealer_seat_index,
            human_seat_index=self.human_seat_index,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            message=self.message,
        )

    def redis_key(self) -> str:
        return f"poker:{self.table_id}:state"


def poker_state_key(table_id: str) -> str:
    return f"poker:{table_id}:state"


async def load_poker_state(redis, table_id: str) -> RedisPokerState | None:
    raw = await redis.get(poker_state_key(table_id))
    if not raw:
        return None
    data = json.loads(raw)
    data["session_id"] = UUID(data["session_id"])
    data["user_id"] = UUID(data["user_id"])
    data["phase"] = PokerPhase(data["phase"])
    for seat in data.get("seats", []):
        seat["status"] = SeatStatus(seat["status"])
    return RedisPokerState.model_validate(data)


async def save_poker_state(redis, state: RedisPokerState, ttl_seconds: int) -> None:
    payload = state.model_dump(mode="json")
    payload["session_id"] = str(state.session_id)
    payload["user_id"] = str(state.user_id)
    payload["phase"] = state.phase.value
    for seat in payload["seats"]:
        if not isinstance(seat["status"], str):
            seat["status"] = seat["status"].value
    await redis.set(state.redis_key(), json.dumps(payload), ex=ttl_seconds)
