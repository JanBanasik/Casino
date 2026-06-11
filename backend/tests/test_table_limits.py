"""Server-side blackjack stake validation."""
import pytest

from app.core.table_limits import blackjack_bet_limits, validate_blackjack_bet


def test_known_table_limits():
    assert blackjack_bet_limits("table-gold") == (25.0, 2000.0)
    assert blackjack_bet_limits("table-vip") == (100.0, 10000.0)


def test_unknown_table_falls_back_to_default():
    assert blackjack_bet_limits("solo-abc123") == (10.0, 10000.0)


def test_bet_below_table_minimum_rejected():
    # "table-gold" requires at least 25 — a 10 stake must be refused server-side.
    with pytest.raises(ValueError, match="bet_below_minimum"):
        validate_blackjack_bet("table-gold", 10)


def test_bet_above_table_maximum_rejected():
    with pytest.raises(ValueError, match="bet_above_maximum"):
        validate_blackjack_bet("table-gold", 5000)


def test_valid_bet_passes():
    validate_blackjack_bet("table-gold", 25)
    validate_blackjack_bet("table-gold", 2000)


def test_client_minimum_enforced_on_solo_tables():
    # A solo table is unknown server-side (default min 10), but the client passes
    # its origin table's minimum so the floor is still honoured.
    with pytest.raises(ValueError, match="bet_below_minimum"):
        validate_blackjack_bet("solo-xyz", 10, client_min=25)
    # Server registry always wins even if the client under-reports its minimum.
    with pytest.raises(ValueError, match="bet_below_minimum"):
        validate_blackjack_bet("table-gold", 10, client_min=5)
