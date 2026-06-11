"""Authoritative blackjack table bet limits (mirrors the frontend lobby).

The client can be stale or tampered with, so min/max stakes are enforced
server-side at round start. Solo tables use a dynamic id (``solo-<uuid>``) and
therefore are not in this registry — they fall back to the default limits, and
the client additionally passes the intended minimum for its origin table.
"""
from __future__ import annotations

# table_id -> (min_bet, max_bet)
_BLACKJACK_TABLE_LIMITS: dict[str, tuple[float, float]] = {
    "table-classic": (5.0, 200.0),
    "table-emerald": (10.0, 500.0),
    "table-gold": (25.0, 2000.0),
    "table-vip": (100.0, 10000.0),
    "default": (10.0, 1000.0),
}

# Solo / unknown tables use the player's own chips, so allow a generous max
# (matches the frontend's solo default). The min still defaults to 10.
_DEFAULT_LIMITS: tuple[float, float] = (10.0, 10000.0)


def blackjack_bet_limits(table_id: str) -> tuple[float, float]:
    return _BLACKJACK_TABLE_LIMITS.get(table_id, _DEFAULT_LIMITS)


# ── Poker blinds (mirrors the frontend poker lobby) ───────────────────────────
# table_id -> (small_blind, big_blind)
_POKER_TABLE_BLINDS: dict[str, tuple[float, float]] = {
    "poker-table-1": (5.0, 10.0),
    "poker-table-2": (10.0, 20.0),
    "poker-vip": (50.0, 100.0),
}

_DEFAULT_BLINDS: tuple[float, float] = (10.0, 20.0)


def poker_table_blinds(table_id: str) -> tuple[float, float]:
    return _POKER_TABLE_BLINDS.get(table_id, _DEFAULT_BLINDS)


def validate_blackjack_bet(table_id: str, bet: float, client_min: float = 0.0) -> None:
    """Raise ValueError if ``bet`` violates the table's stake limits.

    The effective minimum is the larger of the server's table minimum and the
    client-declared minimum (so solo tables still enforce their origin table's
    floor even though the server can't identify them).
    """
    table_min, table_max = blackjack_bet_limits(table_id)
    effective_min = max(table_min, client_min or 0.0)
    if bet < effective_min:
        raise ValueError("bet_below_minimum")
    if bet > table_max:
        raise ValueError("bet_above_maximum")
