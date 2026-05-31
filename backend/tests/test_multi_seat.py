"""Tests for multi-seat blackjack engine."""

import random

import pytest

from app.engine.blackjack import BlackjackAction, BlackjackPhase, hand_value
from app.engine.multi_seat import (
    SeatStatus,
    advance_bot_turns,
    apply_seat_action,
    finish_dealer_and_settle,
    human_settle_result,
    new_multi_round,
)
from app.ml_inference.policies import BasicStrategyPolicy


def _playable_solo_state(max_seed: int = 300):
    """First solo round where the human has an actionable two-card hand."""
    for seed in range(max_seed):
        st = new_multi_round(
            bet=10, human_name="H", human_id="u",
            human_seat_index=0, bot_count=0, rng=random.Random(seed),
        )
        seat = st.seats[0]
        if (
            st.phase == BlackjackPhase.player_turn
            and seat.status == SeatStatus.acting
            and len(seat.hand) == 2
        ):
            return st
    raise AssertionError("no playable solo hand found")


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


# ── Double down ───────────────────────────────────────────────────────────────
def test_double_doubles_bet_takes_one_card_and_locks_seat():
    st = _playable_solo_state()
    seat = st.seats[0]
    bet_before = seat.bet
    apply_seat_action(st, 0, BlackjackAction.double)
    assert seat.bet == bet_before * 2
    assert len(seat.hand) == 3
    assert seat.status in (SeatStatus.stood, SeatStatus.bust)
    # Solo: locking the only seat hands play to the dealer.
    assert st.phase == BlackjackPhase.dealer_turn
    assert st.active_seat_index is None


def test_double_rejected_after_a_hit():
    st = _playable_solo_state()
    apply_seat_action(st, 0, BlackjackAction.hit)
    if st.seats[0].status != SeatStatus.acting:
        pytest.skip("hand busted/locked on the hit")
    assert len(st.seats[0].hand) >= 3
    with pytest.raises(ValueError, match="double_only_initial"):
        apply_seat_action(st, 0, BlackjackAction.double)


def test_double_winning_payout_scales_with_doubled_bet():
    saw_win = False
    for seed in range(400):
        st = new_multi_round(
            bet=10, human_name="H", human_id="u",
            human_seat_index=0, bot_count=0, rng=random.Random(seed),
        )
        seat = st.seats[0]
        if not (
            st.phase == BlackjackPhase.player_turn
            and seat.status == SeatStatus.acting
            and len(seat.hand) == 2
        ):
            continue
        apply_seat_action(st, 0, BlackjackAction.double)
        finish_dealer_and_settle(st)
        if seat.result == "win" and not (hand_value(seat.hand)[0] == 21 and len(seat.hand) == 2):
            # Non-blackjack win pays 2× the (already doubled) stake.
            assert seat.payout == seat.bet * 2.0
            assert seat.bet == 20  # original 10, doubled
            saw_win = True
            break
    assert saw_win, "expected at least one winning double in the seed sweep"


# ── Split ─────────────────────────────────────────────────────────────────────
def _pair_state(max_seed: int = 500):
    for seed in range(max_seed):
        st = new_multi_round(
            bet=10, human_name="H", human_id="u",
            human_seat_index=0, bot_count=0, rng=random.Random(seed),
        )
        seat = st.seats[0]
        if (
            st.phase == BlackjackPhase.player_turn
            and seat.status == SeatStatus.acting
            and len(seat.hand) == 2
            and seat.hand[0][:-1] == seat.hand[1][:-1]
        ):
            return st
    raise AssertionError("no pair hand found")


def test_split_creates_two_hands_and_plays_first():
    st = _pair_state()
    seat = st.seats[0]
    apply_seat_action(st, 0, BlackjackAction.split)
    assert seat.has_split
    assert len(seat.hands) == 2
    assert len(seat.hands[0]) == 2  # first hand got a card
    assert len(seat.hands[1]) == 1  # second waits
    assert seat.hand_bets == [10.0, 10.0]
    assert st.active_seat_index == 0
    assert st.phase == BlackjackPhase.player_turn


def test_split_rejected_when_not_pair():
    st = _playable_solo_state()
    if st.seats[0].hand[0][:-1] == st.seats[0].hand[1][:-1]:
        pytest.skip("got a pair in playable state")
    with pytest.raises(ValueError, match="split_not_allowed"):
        apply_seat_action(st, 0, BlackjackAction.split)


def test_split_both_hands_settle():
    st = _pair_state()
    apply_seat_action(st, 0, BlackjackAction.split)
    # Play both hands to stand
    for _ in range(20):
        if st.phase != BlackjackPhase.player_turn:
            break
        if st.active_seat_index != 0:
            break
        apply_seat_action(st, 0, BlackjackAction.stand)
    finish_dealer_and_settle(st)
    seat = st.seats[0]
    assert st.phase == BlackjackPhase.finished
    assert len(seat.hand_results) == 2
    assert seat.payout == sum(seat.hand_payouts)
    assert sum(seat.hand_bets) == 20.0
