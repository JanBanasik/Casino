import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket

from app.core.security import decode_access_token
from app.db.redis_client import get_redis
from app.db.session import async_session_factory
from app.engine.blackjack import BlackjackAction
from app.services.game_round import GameRoundService

router = APIRouter()


@router.websocket("/ws/tables/{table_id}")
async def table_ws(
    websocket: WebSocket,
    table_id: str,
    token: str | None = Query(default=None),
) -> None:
    await websocket.accept()
    if not token:
        await websocket.send_json({"error": "missing_token"})
        await websocket.close(code=4401)
        return
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        await websocket.send_json({"error": "invalid_token"})
        await websocket.close(code=4401)
        return
    try:
        user_id = UUID(payload["sub"])
    except ValueError:
        await websocket.send_json({"error": "invalid_subject"})
        await websocket.close(code=4401)
        return

    redis = get_redis()

    while True:
        raw = await websocket.receive_text()
        try:
            msg: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"error": "invalid_json"})
            continue

        mtype = msg.get("type")
        if async_session_factory is None:
            await websocket.send_json({"error": "server_misconfigured"})
            continue

        async with async_session_factory() as db:
            svc = GameRoundService(db, redis)
            try:
                if mtype == "new_round":
                    sid = UUID(str(msg["session_id"]))
                    bet = float(msg.get("bet", 10))
                    _, public = await svc.new_round(user_id, sid, table_id, bet)
                    await websocket.send_json({"type": "state", "payload": public})
                elif mtype == "action":
                    raw_action = str(msg.get("action", "")).upper()
                    action = BlackjackAction(raw_action)
                    out = await svc.apply_player_action(user_id, table_id, action)
                    payload = dict(out["public"])
                    if out.get("retention"):
                        payload["retention"] = out["retention"]
                    await websocket.send_json({"type": "state", "payload": payload})
                else:
                    await websocket.send_json({"error": "unknown_type"})
            except ValueError as e:
                await websocket.send_json({"error": str(e)})
            except KeyError as e:
                await websocket.send_json({"error": f"missing_field:{e.args[0]!s}"})
