import uuid

import pytest
from redis.asyncio import Redis

from app.core.ws_tickets import consume_ws_ticket, create_ws_ticket
from tests.conftest import _register_and_login


def _unique_user(prefix: str = "ws") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_ws_ticket_single_use():
    redis = Redis.from_url("redis://localhost:16379/1", decode_responses=True)
    await redis.flushdb()

    user_id = "00000000-0000-0000-0000-000000000001"
    session_id = "00000000-0000-0000-0000-000000000002"
    from uuid import UUID

    ticket, ttl = await create_ws_ticket(
        redis,
        user_id=UUID(user_id),
        session_id=UUID(session_id),
        table_id="default",
    )
    assert ttl == 120

    payload = await consume_ws_ticket(redis, ticket)
    assert payload is not None
    assert str(payload.user_id) == user_id
    assert str(payload.session_id) == session_id
    assert payload.table_id == "default"

    again = await consume_ws_ticket(redis, ticket)
    assert again is None

    await redis.aclose()


@pytest.mark.integration
def test_auth_wallet_session_and_ws_ticket(client):
    token = _register_and_login(client, _unique_user("ws1"))

    dep = client.post(
        "/api/wallet/deposit",
        json={"amount": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dep.status_code == 200
    assert dep.json()["balance"] == 100

    session = client.post(
        "/api/sessions",
        json={"game_type": "blackjack"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert session.status_code == 200
    session_id = session.json()["id"]

    ticket_res = client.post(
        f"/api/sessions/{session_id}/ws-ticket",
        json={"table_id": "default"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ticket_res.status_code == 200
    ticket_data = ticket_res.json()
    assert "ticket" in ticket_data
    assert ticket_data["table_id"] == "default"
    assert ticket_data["expires_in"] == 120


@pytest.mark.integration
def test_ws_auth_handshake_and_new_round(client):
    token = _register_and_login(client, _unique_user("ws2"))

    client.post(
        "/api/wallet/deposit",
        json={"amount": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = client.post(
        "/api/sessions",
        json={"game_type": "blackjack"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]

    ticket = client.post(
        f"/api/sessions/{session_id}/ws-ticket",
        json={"table_id": "table-1"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["ticket"]

    with client.websocket_connect("/ws/tables/table-1") as ws:
        ws.send_json({"type": "auth", "ticket": ticket})
        auth = ws.receive_json()
        assert auth["type"] == "auth_ok"

        # On connect the server pushes an initial table snapshot (idle table) — drain it.
        snapshot = ws.receive_json()
        assert snapshot["type"] == "state"

        # Multi-seat flow: the player must take a seat before starting a round.
        ws.send_json({"type": "sit", "session_id": session_id, "seat_index": 0})
        seated = ws.receive_json()
        assert seated["type"] == "state"
        assert seated["payload"]["my_seat_index"] == 0

        ws.send_json({"type": "new_round", "session_id": session_id, "bet": 10})
        state = ws.receive_json()
        assert state["type"] == "state"
        assert "player_hand" in state["payload"]
        assert state["payload"]["bet"] == 10


@pytest.mark.integration
def test_ws_rejects_without_auth(client):
    with client.websocket_connect("/ws/tables/default") as ws:
        ws.send_json({"type": "new_round", "session_id": "x", "bet": 10})
        msg = ws.receive_json()
        assert msg["type"] == "auth_error"
        assert msg["error"] == "auth_required"


@pytest.mark.integration
def test_ws_rejects_invalid_ticket(client):
    with client.websocket_connect("/ws/tables/default") as ws:
        ws.send_json({"type": "auth", "ticket": "not-a-real-ticket"})
        msg = ws.receive_json()
        assert msg["type"] == "auth_error"
        assert msg["error"] == "invalid_ticket"
