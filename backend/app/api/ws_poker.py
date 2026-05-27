import asyncio
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.core.ws_tickets import consume_ws_ticket
from app.db import session as db_session
from app.db.redis_client import get_redis
from app.engine.poker import PokerAction
from app.services.poker_round import PokerRoundService

router = APIRouter()


async def _authenticate_ws(websocket: WebSocket, table_id: str) -> UUID | None:
    try:
        raw = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=settings.ws_auth_timeout_seconds,
        )
    except TimeoutError:
        await websocket.send_json({"type": "auth_error", "error": "auth_timeout"})
        await websocket.close(code=4401)
        return None

    try:
        msg: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.send_json({"type": "auth_error", "error": "invalid_json"})
        await websocket.close(code=4401)
        return None

    if msg.get("type") != "auth":
        await websocket.send_json({"type": "auth_error", "error": "auth_required"})
        await websocket.close(code=4401)
        return None

    ticket = msg.get("ticket")
    if not ticket or not isinstance(ticket, str):
        await websocket.send_json({"type": "auth_error", "error": "missing_ticket"})
        await websocket.close(code=4401)
        return None

    redis = get_redis()
    payload = await consume_ws_ticket(redis, ticket)
    if payload is None:
        await websocket.send_json({"type": "auth_error", "error": "invalid_ticket"})
        await websocket.close(code=4401)
        return None

    if payload.table_id != table_id:
        await websocket.send_json({"type": "auth_error", "error": "table_mismatch"})
        await websocket.close(code=4401)
        return None

    await websocket.send_json({"type": "auth_ok"})
    return payload.user_id


async def _emit_seat_actions(
    websocket: WebSocket,
    events: list[dict],
    public: dict,
) -> None:
    for ev in events:
        await websocket.send_json({"type": "seat_action", "payload": ev})
        await asyncio.sleep(0.35)
    await websocket.send_json({"type": "state", "payload": public})


@router.websocket("/ws/poker/{table_id}")
async def poker_ws(websocket: WebSocket, table_id: str) -> None:
    await websocket.accept()
    user_id = await _authenticate_ws(websocket, table_id)
    if user_id is None:
        return

    redis = get_redis()

    if db_session.async_session_factory is not None:
        async with db_session.async_session_factory() as db:
            svc = PokerRoundService(db, redis)
            snap = await svc.table_snapshot(user_id, table_id)
            await websocket.send_json({"type": "state", "payload": snap})

    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return
        try:
            msg: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"error": "invalid_json"})
            continue

        mtype = msg.get("type")
        if db_session.async_session_factory is None:
            await websocket.send_json({"error": "server_misconfigured"})
            continue

        async with db_session.async_session_factory() as db:
            svc = PokerRoundService(db, redis)
            try:
                match mtype:
                    case "sit":
                        sid = UUID(str(msg["session_id"]))
                        seat_index = int(msg.get("seat_index", 0))
                        public = await svc.sit_at_table(user_id, sid, table_id, seat_index)
                        await websocket.send_json({"type": "state", "payload": public})

                    case "start_hand":
                        sid = UUID(str(msg["session_id"]))
                        buy_in = float(msg.get("buy_in", 500))
                        bot_count = int(msg.get("bot_count", 2))
                        _, public, seat_events = await svc.start_hand(
                            user_id, sid, table_id, buy_in, bot_count
                        )
                        await _emit_seat_actions(websocket, seat_events, public)

                    case "action":
                        raw_action = str(msg.get("action", "")).upper()
                        # PokerAction uses "RAISE" but enum value is "RAISE"
                        action_map = {
                            "FOLD": PokerAction.fold,
                            "CHECK": PokerAction.check,
                            "CALL": PokerAction.call,
                            "RAISE": PokerAction.raise_,
                        }
                        action = action_map.get(raw_action)
                        if action is None:
                            await websocket.send_json({"error": "unknown_action"})
                            continue
                        raise_amount = float(msg.get("amount", 0))
                        public, seat_events = await svc.apply_action(
                            user_id, table_id, action, raise_amount
                        )
                        await _emit_seat_actions(websocket, seat_events, public)

                    case None:
                        await websocket.send_json({"error": "missing_type"})
                    case _:
                        await websocket.send_json({"error": "unknown_type"})
            except ValueError as e:
                await websocket.send_json({"error": str(e)})
            except KeyError as e:
                await websocket.send_json({"error": f"missing_field:{e.args[0]!s}"})
