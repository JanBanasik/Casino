import json
import uuid
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings

TICKET_PREFIX = "ws_ticket:"


@dataclass(frozen=True)
class WsTicketPayload:
    user_id: UUID
    session_id: UUID
    table_id: str


def _ticket_key(jti: str) -> str:
    return f"{TICKET_PREFIX}{jti}"


async def create_ws_ticket(
    redis: Redis,
    *,
    user_id: UUID,
    session_id: UUID,
    table_id: str,
) -> tuple[str, int]:
    jti = str(uuid.uuid4())
    payload = {
        "user_id": str(user_id),
        "session_id": str(session_id),
        "table_id": table_id,
    }
    ttl = settings.ws_ticket_ttl_seconds
    await redis.set(_ticket_key(jti), json.dumps(payload), ex=ttl)
    return jti, ttl


async def consume_ws_ticket(redis: Redis, jti: str) -> WsTicketPayload | None:
    raw = await redis.getdel(_ticket_key(jti))
    if raw is None:
        return None
    data = json.loads(raw)
    return WsTicketPayload(
        user_id=UUID(data["user_id"]),
        session_id=UUID(data["session_id"]),
        table_id=data["table_id"],
    )
