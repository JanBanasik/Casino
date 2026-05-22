from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LobbySeatOccupant(BaseModel):
    user_id: UUID
    session_id: UUID
    display_name: str
    avatar_key: str = "you"


class TableLobby(BaseModel):
    seats: list[LobbySeatOccupant | None] = Field(default_factory=lambda: [None] * 7)

    def redis_key(self, table_id: str) -> str:
        return f"table:{table_id}:lobby"

    @classmethod
    def empty(cls) -> TableLobby:
        return cls(seats=[None] * 7)

    def to_public(self) -> list[dict[str, Any] | None]:
        out: list[dict[str, Any] | None] = []
        for i, occ in enumerate(self.seats):
            if occ is None:
                out.append(None)
            else:
                out.append(
                    {
                        "seat_index": i,
                        "display_name": occ.display_name,
                        "avatar_key": occ.avatar_key,
                        "is_human": True,
                    }
                )
        return out


def lobby_key(table_id: str) -> str:
    return f"table:{table_id}:lobby"


async def load_table_lobby(redis, table_id: str) -> TableLobby:
    raw = await redis.get(lobby_key(table_id))
    if not raw:
        return TableLobby.empty()
    data = json.loads(raw)
    seats: list[LobbySeatOccupant | None] = []
    for item in data.get("seats", [None] * 7):
        if item is None:
            seats.append(None)
        else:
            seats.append(
                LobbySeatOccupant(
                    user_id=UUID(item["user_id"]),
                    session_id=UUID(item["session_id"]),
                    display_name=item["display_name"],
                    avatar_key=item.get("avatar_key", "you"),
                )
            )
    while len(seats) < 7:
        seats.append(None)
    return TableLobby(seats=seats[:7])


async def save_table_lobby(redis, table_id: str, lobby: TableLobby, ttl_seconds: int) -> None:
    payload = {
        "seats": [
            None
            if s is None
            else {
                "user_id": str(s.user_id),
                "session_id": str(s.session_id),
                "display_name": s.display_name,
                "avatar_key": s.avatar_key,
            }
            for s in lobby.seats
        ]
    }
    await redis.set(lobby_key(table_id), json.dumps(payload), ex=ttl_seconds)
