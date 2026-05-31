"""Tests for poker bot policies: feature codec, RL policy, and fallback."""

import importlib
import random

import pytest

from app.engine.poker import (
    PokerAction,
    PokerPhase,
    SeatStatus,
    SimplePokerBotPolicy,
    advance_poker_bots,
    apply_poker_action,
    new_poker_round,
)
from app.ml_inference.poker_features import (
    POKER_OBS_DIM,
    decode_poker_action,
    encode_poker_obs,
)
from app.ml_inference.poker_policies import PokerRLPolicy, make_poker_policy

_HAS_SB3 = importlib.util.find_spec("stable_baselines3") is not None
_requires_sb3 = pytest.mark.skipif(not _HAS_SB3, reason="stable-baselines3 not installed")


def _fresh_state(seed: int = 1):
    return new_poker_round(
        human_name="Me", human_id="u1", bot_count=2,
        small_blind=10, big_blind=20, rng=random.Random(seed),
    )


# ── Observation codec ──────────────────────────────────────────────────────────
def test_encode_obs_shape_and_bounds():
    st = _fresh_state()
    seat = st.seats[st.active_seat_index]
    obs = encode_poker_obs(seat, st)
    assert len(obs) == POKER_OBS_DIM
    assert all(0.0 <= x <= 1.0 for x in obs)


# ── Action decoder legality ────────────────────────────────────────────────────
def test_decode_fold_becomes_check_when_free():
    st = _fresh_state()
    seat = st.seats[st.active_seat_index]
    # Force a "no bet to call" situation.
    st.current_bet = seat.bet_phase
    action, _ = decode_poker_action(0, seat, st)
    assert action == PokerAction.check


def test_decode_fold_stays_fold_when_facing_bet():
    st = _fresh_state()
    seat = st.seats[st.active_seat_index]
    st.current_bet = seat.bet_phase + 50
    action, _ = decode_poker_action(0, seat, st)
    assert action == PokerAction.fold


def test_decode_raise_falls_back_when_unaffordable():
    st = _fresh_state()
    seat = st.seats[st.active_seat_index]
    # Facing a bet larger than the stack → cannot raise beyond a call.
    st.current_bet = seat.bet_phase + seat.chips + 100
    action, _ = decode_poker_action(2, seat, st)
    assert action in (PokerAction.call, PokerAction.check)


def test_decode_call_when_facing_bet():
    st = _fresh_state()
    seat = st.seats[st.active_seat_index]
    st.current_bet = seat.bet_phase + 20
    action, _ = decode_poker_action(1, seat, st)
    assert action == PokerAction.call


# ── Factory + fallback ─────────────────────────────────────────────────────────
def test_make_poker_policy_heuristic_override(monkeypatch):
    monkeypatch.setenv("POKER_BOT_POLICY", "heuristic")
    assert isinstance(make_poker_policy(), SimplePokerBotPolicy)


def test_make_poker_policy_always_usable(monkeypatch):
    monkeypatch.delenv("POKER_BOT_POLICY", raising=False)
    policy = make_poker_policy()
    assert hasattr(policy, "choose_action")


# ── RL policy end-to-end (needs ml deps + trained model) ───────────────────────
@_requires_sb3
def test_rl_policy_plays_full_hand_to_completion():
    try:
        policy = PokerRLPolicy()
    except RuntimeError as exc:
        pytest.skip(f"poker model unavailable: {exc}")

    buy_in = 1000.0
    for seed in range(15):
        rng = random.Random(seed)
        st = new_poker_round(
            human_name="Me", human_id="u1", bot_count=2, buy_in=buy_in,
            small_blind=10, big_blind=20, rng=rng,
        )
        occupied = [s for s in st.seats if s.status != SeatStatus.empty]
        for _ in range(400):
            if st.phase in (PokerPhase.showdown, PokerPhase.finished):
                break
            idx = st.active_seat_index
            if idx is None:
                break
            seat = st.seats[idx]
            action, amount = policy.choose_action(seat, st, rng)
            apply_poker_action(st, idx, action, amount)
        assert st.phase == PokerPhase.finished
        # Chips are conserved by the engine regardless of who is deciding.
        total = sum(s.chips for s in occupied)
        assert round(total, 6) == round(len(occupied) * buy_in, 6)


@_requires_sb3
def test_rl_policy_is_drop_in_for_advance_poker_bots():
    try:
        policy = PokerRLPolicy()
    except RuntimeError as exc:
        pytest.skip(f"poker model unavailable: {exc}")
    st = _fresh_state(seed=7)
    events = advance_poker_bots(st, policy, rng=random.Random(7))
    assert isinstance(events, list)
    for idx, action, amount in events:
        assert isinstance(action, PokerAction)
