"""Tests for multi-seat blackjack engine."""

import random

from app.engine.blackjack import BlackjackAction, BlackjackPhase
from app.engine.multi_seat import (
    advance_bot_turns,
    apply_seat_action,
    finish_dealer_and_settle,
    human_settle_result,
    new_multi_round,
)
from app.ml_inference.policies import BasicStrategyPolicy


def test_solo_round_human_can_act():
    st = new_multi_round(bet=10, human_name="Jan", human_id="u1", bot_count=0, rng=random.Random(1))
    assert len(st.seats) == 1
    assert st.seats[0].is_human
    assert st.active_seat_index == 0
    apply_seat_action(st, 0, BlackjackAction.stand)
    assert st.phase == BlackjackPhase.dealer_turn


def test_multi_seat_has_bots():
    st = new_multi_round(bet=10, human_name="Jan", human_id="u1", bot_count=2, rng=random.Random(2))
    assert len(st.seats) == 3
    bots = [s for s in st.seats if not s.is_human]
    assert len(bots) == 2


def test_bots_play_before_human():
    st = new_multi_round(bet=10, human_name="Jan", human_id="u1", bot_count=2, rng=random.Random(3))
    policy = BasicStrategyPolicy()
    actions = advance_bot_turns(st, policy, stop_at_human=True)
    if st.active_seat_index is not None:
        assert st.seats[st.active_seat_index].is_human or st.phase != BlackjackPhase.player_turn
    assert isinstance(actions, list)


def test_finish_dealer_settles_human():
    st = new_multi_round(bet=10, human_name="Jan", human_id="u1", bot_count=0, rng=random.Random(4))
    apply_seat_action(st, st.human_seat_index, BlackjackAction.stand)
    finish_dealer_and_settle(st)
    result, payout = human_settle_result(st)
    assert result in ("win", "loss", "draw")
    assert payout >= 0
