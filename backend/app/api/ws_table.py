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
from app.engine.blackjack import BlackjackAction
from app.services.game_round import GameRoundService

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


async def _emit_seat_actions(websocket: WebSocket, events: list[dict], public: dict) -> None:
    for ev in events:
        await websocket.send_json({"type": "seat_action", "payload": ev})
        await asyncio.sleep(0.35)
    await websocket.send_json({"type": "state", "payload": public})


@router.websocket("/ws/tables/{table_id}")
async def table_ws(websocket: WebSocket, table_id: str) -> None:
    await websocket.accept()
    user_id = await _authenticate_ws(websocket, table_id)
    if user_id is None:
        return

    redis = get_redis()

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
            svc = GameRoundService(db, redis)
            try:
                match mtype:
                    case "new_round":
                        sid = UUID(str(msg["session_id"]))
                        bet = float(msg.get("bet", 10))
                        solo = bool(msg.get("solo", False))
                        bot_count = int(msg.get("bot_count", 0))
                        _, public, seat_events = await svc.new_round(
                            user_id,
                            sid,
                            table_id,
                            bet,
                            solo=solo,
                            bot_count=bot_count,
                        )
                        await _emit_seat_actions(websocket, seat_events, public)
                    case "action":
                        raw_action = str(msg.get("action", "")).upper()
                        action = BlackjackAction(raw_action)
                        public, retention, seat_events = await svc.apply_player_action(
                            user_id, table_id, action
                        )
                        if retention:
                            public = dict(public)
                            public["retention"] = retention
                        await _emit_seat_actions(websocket, seat_events, public)
                    case None:
                        await websocket.send_json({"error": "missing_type"})
                    case _:
                        await websocket.send_json({"error": "unknown_type"})
            except ValueError as e:
                await websocket.send_json({"error": str(e)})
            except KeyError as e:
                await websocket.send_json({"error": f"missing_field:{e.args[0]!s}"})
