from __future__ import annotations

import hashlib
import json
import random
import uuid as uuid_module
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

_AMBIENT_PROFILES = [
    ("Alex_K", "a1"),
    ("Marta99", "m2"),
    ("JanekW", "j3"),
    ("Ola_P", "o4"),
    ("Kris77", "k5"),
    ("Ewa_M", "e6"),
    ("TomekB", "t7"),
]


class LobbySeatOccupant(BaseModel):
    user_id: UUID
    session_id: UUID
    display_name: str
    avatar_key: str = "you"
    is_bot: bool = False


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
                        "is_human": not occ.is_bot,
                    }
                )
        return out

    def with_ambient_bots(self, table_id: str, count: int = 4) -> TableLobby:
        """Return a new TableLobby where empty seats are filled with deterministic ambient bots."""
        ambient = _get_ambient_bots(table_id, count)
        merged: list[LobbySeatOccupant | None] = []
        for i, real in enumerate(self.seats):
            if real is not None:
                merged.append(real)
            else:
                merged.append(ambient[i])
        return TableLobby(seats=merged)


def _get_ambient_bots(table_id: str, count: int = 4) -> list[LobbySeatOccupant | None]:
    """Returns a 7-slot list with deterministic bot occupants based on table_id hash."""
    h = int(hashlib.md5(table_id.encode()).hexdigest(), 16)
    rng = random.Random(h)

    slots = list(range(7))
    rng.shuffle(slots)
    bot_slots = set(slots[:count])

    result: list[LobbySeatOccupant | None] = [None] * 7
    for idx, slot in enumerate(slots[:count]):
        profile_idx = (h + idx) % len(_AMBIENT_PROFILES)
        name, key = _AMBIENT_PROFILES[profile_idx]
        fake_int = (h ^ (idx << 64)) & ((1 << 128) - 1)
        fake_uuid = uuid_module.UUID(int=fake_int)
        result[slot] = LobbySeatOccupant(
            user_id=fake_uuid,
            session_id=fake_uuid,
            display_name=name,
            avatar_key=key,
            is_bot=True,
        )
    return result


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
                    is_bot=item.get("is_bot", False),
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
                "is_bot": s.is_bot,
            }
            for s in lobby.seats
        ]
    }
    await redis.set(lobby_key(table_id), json.dumps(payload), ex=ttl_seconds)
