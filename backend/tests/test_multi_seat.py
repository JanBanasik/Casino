"""Tests for multi-seat blackjack engine."""

import random

from app.engine.blackjack import BlackjackAction, BlackjackPhase
from app.engine.multi_seat import (
    SeatStatus,
    advance_bot_turns,
    apply_seat_action,
    finish_dealer_and_settle,
    human_settle_result,
    new_multi_round,
)
from app.ml_inference.policies import BasicStrategyPolicy


def test_solo_round_human_can_act():
    st = new_multi_round(
        bet=10,
        human_name="Jan",
        human_id="u1",
        human_seat_index=3,
        bot_count=0,
        rng=random.Random(1),
    )
    assert st.seats[3].is_human
    assert st.active_seat_index == 3
    apply_seat_action(st, 3, BlackjackAction.stand)
    assert st.phase == BlackjackPhase.dealer_turn


def test_multi_seat_has_bots():
    st = new_multi_round(
        bet=10,
        human_name="Jan",
        human_id="u1",
        human_seat_index=3,
        bot_count=2,
        rng=random.Random(2),
    )
    playing = [s for s in st.seats if s.status.value != "empty"]
    assert len(playing) == 3
    bots = [s for s in st.seats if not s.is_human and s.status.value != "empty"]
    assert len(bots) == 2


def test_bots_play_before_human():
    st = new_multi_round(bet=10, human_name="Jan", human_id="u1", bot_count=2, rng=random.Random(3))
    policy = BasicStrategyPolicy()
    actions = advance_bot_turns(st, policy, stop_at_human=True)
    if st.active_seat_index is not None:
        assert st.seats[st.active_seat_index].is_human or st.phase != BlackjackPhase.player_turn
    assert isinstance(actions, list)


def test_hit_keeps_turn_until_stand_or_bust():
    st = None
    for seed in range(200):
        candidate = new_multi_round(
            bet=10,
            human_name="Jan",
            human_id="u1",
            human_seat_index=3,
            bot_count=0,
            rng=random.Random(seed),
        )
        idx = candidate.human_seat_index
        if (
            candidate.phase == BlackjackPhase.player_turn
            and candidate.seats[idx].status == SeatStatus.acting
        ):
            st = candidate
            break
    assert st is not None
    idx = st.human_seat_index
    hand_len = len(st.seats[idx].hand)
    apply_seat_action(st, idx, BlackjackAction.hit)
    if st.seats[idx].status == SeatStatus.bust:
        return
    assert st.phase == BlackjackPhase.player_turn
    assert st.active_seat_index == idx
    assert len(st.seats[idx].hand) == hand_len + 1


def test_finish_dealer_settles_human():
    st = new_multi_round(bet=10, human_name="Jan", human_id="u1", bot_count=0, rng=random.Random(4))
    apply_seat_action(st, st.human_seat_index, BlackjackAction.stand)
    finish_dealer_and_settle(st)
    result, payout = human_settle_result(st)
    assert result in ("win", "loss", "draw")
    assert payout >= 0
