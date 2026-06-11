"""Bonus economy + difficulty registry coverage."""
import uuid

import pytest

from app.engine.poker import SimplePokerBotPolicy
from app.ml_inference.poker_policies import LoosePokerBotPolicy
from app.ml_inference.policies import BasicStrategyPolicy, RandomLegalPolicy
from app.ml_inference.registry import (
    Difficulty,
    get_blackjack_policy,
    get_poker_policy,
    normalize_difficulty,
)


def _u(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ── Difficulty registry ───────────────────────────────────────────────────────
def test_normalize_difficulty_defaults_to_medium():
    assert normalize_difficulty(None) == Difficulty.medium
    assert normalize_difficulty("nonsense") == Difficulty.medium
    assert normalize_difficulty("HARD") == Difficulty.hard


def test_blackjack_easy_medium_mapping():
    assert isinstance(get_blackjack_policy("easy"), RandomLegalPolicy)
    assert isinstance(get_blackjack_policy("medium"), BasicStrategyPolicy)
    # hard is always usable (deep-RL or graceful fallback).
    assert hasattr(get_blackjack_policy("hard"), "choose_action")


def test_poker_easy_medium_mapping():
    assert isinstance(get_poker_policy("easy"), LoosePokerBotPolicy)
    assert isinstance(get_poker_policy("medium"), SimplePokerBotPolicy)
    assert hasattr(get_poker_policy("hard"), "choose_action")


def test_registry_caches_instances():
    assert get_blackjack_policy("easy") is get_blackjack_policy("easy")
    assert get_poker_policy("medium") is get_poker_policy("medium")


# ── Bonus economy via the API ─────────────────────────────────────────────────
def _register(client, username: str) -> str:
    # Unique source IP → own rate-limit bucket, so the suite's many sign-ups
    # don't trip the per-IP register cap.
    ip = ".".join(str(b) for b in uuid.uuid4().bytes[:4])
    headers = {"X-Forwarded-For": ip}
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@e.com", "password": "password123"},
        headers=headers,
    )
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
        headers=headers,
    )
    return res.json()["access_token"]


@pytest.mark.integration
def test_welcome_bonus_credited_on_register(client):
    token = _register(client, _u("welcome"))
    me = client.get("/api/wallet/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["balance"] > 0


@pytest.mark.integration
def test_daily_claim_then_cooldown(client):
    token = _register(client, _u("daily"))
    h = {"Authorization": f"Bearer {token}"}

    status = client.get("/api/wallet/daily", headers=h).json()
    assert status["available"] is True

    first = client.post("/api/wallet/daily/claim", headers=h).json()
    assert first["granted"] is True
    assert first["amount"] > 0
    assert first["streak"] == 1

    # Immediate re-claim is on cooldown.
    second = client.post("/api/wallet/daily/claim", headers=h).json()
    assert second["granted"] is False


@pytest.mark.integration
def test_rescue_unavailable_with_healthy_balance(client):
    token = _register(client, _u("rescue"))
    h = {"Authorization": f"Bearer {token}"}
    # Fresh wallet holds the welcome bonus, so rescue must decline.
    res = client.post("/api/wallet/rescue", headers=h).json()
    assert res["granted"] is False


@pytest.mark.integration
def test_history_endpoint_shape(client):
    token = _register(client, _u("hist"))
    h = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/sessions/history", headers=h)
    assert res.status_code == 200
    assert res.json()["rounds"] == []
