import asyncio
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket
from loguru import logger
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
    logger.info("WS table auth_ok user={} table={}", payload.user_id, table_id)
    return payload.user_id


async def _heartbeat(websocket: WebSocket, interval: int = 25) -> None:
    """Sends ping every `interval` seconds; exits silently when connection dies."""
    while True:
        await asyncio.sleep(interval)
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            return


async def _emit_seat_actions(websocket: WebSocket, events: list[dict], public: dict) -> None:
    """Legacy helper — used only for human HIT results (no intermediate states needed)."""
    for ev in events:
        await websocket.send_json({"type": "seat_action", "payload": ev})
        await asyncio.sleep(0.08)
    await websocket.send_json({"type": "state", "payload": public})


async def _run_deal_sequence(
    websocket: WebSocket,
    svc,
    user_id,
    sid,
    table_id: str,
    bet: float,
    solo: bool,
    bot_count: int,
    difficulty: str,
    min_bet: float,
) -> None:
    """Full deal + bot-thinking sequence with incremental state updates."""
    # 1. Deal cards — send initial state (all cards fly in simultaneously-staggered)
    _, initial_public, _, total_players = await svc.begin_round(
        user_id, sid, table_id, bet, solo=solo, bot_count=bot_count,
        difficulty=difficulty, min_bet=min_bet,
    )
    await websocket.send_json({"type": "state", "payload": initial_public})

    # 2. Wait for deal animation to complete before bots start acting
    #    (~400ms per card * 2 cards per player * total_players + buffer)
    deal_wait = total_players * 2 * 0.40 + 1.0
    await asyncio.sleep(deal_wait)

    # 3. Process bots one by one with "thinking" delay
    while True:
        result = await svc.advance_next_bot_step(user_id, table_id)
        if result is None:
            break
        event, public, stop = result
        await websocket.send_json({"type": "seat_action", "payload": event})
        await asyncio.sleep(1.4)  # bot "thinks" before state reveals
        await websocket.send_json({"type": "state", "payload": public})
        if stop:
            return

    # 4. If we get here, it's the human's turn — nothing more to send


async def _resume_round(
    websocket: WebSocket,
    svc,
    user_id,
    table_id: str,
) -> None:
    """After a human action, auto-play any remaining bot seats then the dealer.

    Handles bots seated *after* the human (which would otherwise stall the
    round) and applies uniformly to hit/stand/double — a double simply ends the
    human's turn like a stand.
    """
    while True:
        result = await svc.advance_next_bot_step(user_id, table_id)
        if result is None:
            break  # human's turn again, or no longer player_turn
        event, public, _ = result
        await websocket.send_json({"type": "seat_action", "payload": event})
        await asyncio.sleep(1.4)
        await websocket.send_json({"type": "state", "payload": public})
        if not public.get("round_in_progress", True):
            return  # round already settled during bot play
    # Run the dealer if we've reached the dealer turn (no-op while still
    # the human's turn — dealer_step returns None unless phase == dealer_turn).
    await _run_dealer_sequence(websocket, svc, user_id, table_id)


async def _run_dealer_sequence(
    websocket: WebSocket,
    svc,
    user_id,
    table_id: str,
) -> None:
    """After all players act, dealer draws card by card with dramatic pauses."""
    await asyncio.sleep(0.6)
    while True:
        result = await svc.dealer_step(user_id, table_id)
        if result is None:
            break
        public, done = result
        await websocket.send_json({"type": "state", "payload": public})
        if done:
            break
        await asyncio.sleep(0.9)  # pause between dealer cards


@router.websocket("/ws/tables/{table_id}")
async def table_ws(websocket: WebSocket, table_id: str) -> None:
    await websocket.accept()
    user_id = await _authenticate_ws(websocket, table_id)
    if user_id is None:
        return

    redis = get_redis()

    if db_session.async_session_factory is not None:
        async with db_session.async_session_factory() as db:
            svc = GameRoundService(db, redis)
            snap = await svc.table_snapshot(user_id, table_id)
            await websocket.send_json({"type": "state", "payload": snap})

    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("WS table disconnect user={} table={}", user_id, table_id)
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
                        case "sit":
                            sid = UUID(str(msg["session_id"]))
                            seat_index = int(msg.get("seat_index", 0))
                            public = await svc.sit_at_table(user_id, sid, table_id, seat_index)
                            await websocket.send_json({"type": "state", "payload": public})
                        case "place_bet" | "new_round":
                            sid = UUID(str(msg["session_id"]))
                            bet = float(msg.get("bet", 10))
                            solo = bool(msg.get("solo", False))
                            bot_count = int(msg.get("bot_count", 0))
                            difficulty = str(msg.get("difficulty", "medium"))
                            min_bet = float(msg.get("min_bet", 0))
                            # Incremental: deal → animate → bots think → human's turn
                            await _run_deal_sequence(
                                websocket, svc, user_id, sid, table_id,
                                bet, solo, bot_count, difficulty, min_bet,
                            )
                        case "action":
                            raw_action = str(msg.get("action", "")).upper()
                            action = BlackjackAction(raw_action)
                            public, retention, seat_events = await svc.apply_player_action(
                                user_id, table_id, action
                            )
                            if retention:
                                public = dict(public)
                                public["retention"] = retention
                            # Send human's action result immediately
                            await _emit_seat_actions(websocket, seat_events, public)
                            # Then resume remaining bots and the dealer, unless
                            # apply_player_action already settled the round.
                            in_progress = public.get("round_in_progress", True)
                            if in_progress and public.get("phase") != "finished":
                                await _resume_round(websocket, svc, user_id, table_id)
                        case "pong":
                            pass  # heartbeat response — keep connection alive
                        case None:
                            await websocket.send_json({"error": "missing_type"})
                        case _:
                            await websocket.send_json({"error": "unknown_type"})
                except ValueError as e:
                    await websocket.send_json({"error": str(e)})
                except KeyError as e:
                    await websocket.send_json({"error": f"missing_field:{e.args[0]!s}"})
    finally:
        heartbeat_task.cancel()
