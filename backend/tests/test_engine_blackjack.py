import random

import pytest

from app.engine.blackjack import (
    BlackjackAction,
    BlackjackPhase,
    apply_action,
    hand_value,
    new_round_state,
    play_dealer,
    settle,
)


def test_hand_value_ace_soft():
    v, soft = hand_value(["AH", "6H"])
    assert v == 17
    assert soft is True


def test_hand_value_hard():
    v, _ = hand_value(["10H", "5D", "6C"])
    assert v == 21


def test_new_round_and_stand(monkeypatch):
    rng = random.Random(42)
    st = new_round_state(bet=10.0, rng=rng)
    if st.phase == BlackjackPhase.finished:
        pytest.skip("dealt instant terminal hand")
    apply_action(st, BlackjackAction.stand)
    assert st.phase == BlackjackPhase.dealer_turn
    play_dealer(st)
    assert st.phase == BlackjackPhase.finished
    key, credit = settle(st)
    assert key in ("win", "loss", "draw")
    assert credit >= 0


def test_hit_bust():
    rng = random.Random(0)
    for _ in range(200):
        st = new_round_state(bet=5.0, rng=rng)
        if st.phase != BlackjackPhase.player_turn:
            continue
        while st.phase == BlackjackPhase.player_turn:
            apply_action(st, BlackjackAction.hit)
        if st.message == "player_bust":
            key, credit = settle(st)
            assert key == "loss"
            assert credit == 0.0
            return
    pytest.skip("could not sample bust in bounded attempts")
