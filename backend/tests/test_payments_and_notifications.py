"""Payments (purchase/withdraw + exchange rate) and must-accept notifications."""
import uuid

import pytest

from app.core.config import settings
from app.services.payments import chips_to_minor, minor_to_chips


def _u(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _auth(client, prefix: str) -> dict:
    """Register a fresh user from a unique IP (own rate-limit bucket) and return
    request headers carrying both the bearer token and that IP."""
    username = _u(prefix)
    ip = ".".join(str(b) for b in uuid.uuid4().bytes[:4])
    ip_header = {"X-Forwarded-For": ip}
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@e.com", "password": "password123"},
        headers=ip_header,
    )
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
        headers=ip_header,
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}", **ip_header}


# ── Exchange rate ──────────────────────────────────────────────────────────────
def test_chip_fiat_conversion_roundtrip():
    rate = settings.chips_per_currency_unit
    # 1 fiat unit buys `rate` chips, so `rate` chips == 100 minor units.
    assert chips_to_minor(rate) == 100
    assert minor_to_chips(100) == rate
    # A single chip is worth less than one fiat unit.
    assert chips_to_minor(1) < 100


@pytest.mark.integration
def test_payment_config_exposes_rate(client):
    h = _auth(client, "cfg")
    res = client.get("/api/payments/config", headers=h)
    assert res.status_code == 200
    body = res.json()
    assert body["chips_per_currency_unit"] == settings.chips_per_currency_unit
    assert "withdraw_min_chips" in body


# ── Purchase (dev simulation when Stripe disabled) ─────────────────────────────
@pytest.mark.integration
@pytest.mark.skipif(
    settings.stripe_enabled,
    reason="Stripe configured — checkout returns a hosted URL instead of crediting directly",
)
def test_dev_purchase_credits_chips(client):
    h = _auth(client, "buy")
    before = client.get("/api/wallet/me", headers=h).json()["balance"]
    res = client.post("/api/payments/checkout", json={"chips": 500}, headers=h)
    assert res.status_code == 200
    body = res.json()
    assert body["simulated"] is True
    assert body["balance"] == before + 500


# ── Withdrawal ─────────────────────────────────────────────────────────────────
_TEST_IBAN = "PL61109010140000071219812874"


@pytest.mark.integration
def test_withdraw_below_minimum_rejected(client):
    h = _auth(client, "wd_min")
    res = client.post(
        "/api/payments/withdraw",
        json={"chips": 1, "account_number": _TEST_IBAN},
        headers=h,
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "below_min_withdrawal"


@pytest.mark.integration
def test_withdraw_rejects_bad_account(client):
    h = _auth(client, "wd_bad")
    res = client.post(
        "/api/payments/withdraw",
        json={"chips": 250, "account_number": "123"},
        headers=h,
    )
    # Too short to satisfy the DTO min_length.
    assert res.status_code in (400, 422)


@pytest.mark.integration
def test_withdraw_success_deducts_balance(client):
    # The welcome bonus already funds the wallet above the withdrawal minimum.
    h = _auth(client, "wd_ok")
    before = client.get("/api/wallet/me", headers=h).json()["balance"]
    res = client.post(
        "/api/payments/withdraw",
        json={"chips": 250, "account_number": _TEST_IBAN},
        headers=h,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "requested"
    assert body["balance"] == before - 250
    assert body["amount_minor"] == chips_to_minor(250)


# ── Notifications ──────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_welcome_notification_then_ack(client):
    h = _auth(client, "notif")
    listing = client.get("/api/notifications", headers=h).json()["notifications"]
    welcome = [n for n in listing if n["kind"] == "welcome"]
    assert welcome, "welcome notification should be created on register"

    nid = welcome[0]["id"]
    ack = client.post(f"/api/notifications/{nid}/ack", headers=h)
    assert ack.status_code == 200 and ack.json()["acknowledged"] is True

    after = client.get("/api/notifications", headers=h).json()["notifications"]
    assert all(n["id"] != nid for n in after)
