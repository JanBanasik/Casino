"""Shared observation/action codec for the RL poker bot.

Both the training environment (``rl_training/poker_env.py``) and the live
inference policy import this module, so the agent always sees identical
features and the same action mapping in training and production.

Observation is a fixed-length float vector built purely from the acting seat
and public game state — no reference to the original buy-in — so it is
reproducible at inference time. Action space is ``Discrete(3)``:

    0 = FOLD   (remapped to CHECK when checking is free)
    1 = CHECK / CALL
    2 = RAISE  (pot-based sizing, clamped to the stack; falls back to
                check/call when a raise is not affordable)
"""
from __future__ import annotations

from app.engine.poker import (
    PokerAction,
    PokerPhase,
    PokerSeat,
    PokerState,
    SeatStatus,
    _hand_strength,
)

#: Reference stack used to normalise chip/pot features (matches the default buy-in).
STACK_REF = 1000.0

POKER_OBS_DIM = 14

_PHASE_ORDER = [
    PokerPhase.pre_flop,
    PokerPhase.flop,
    PokerPhase.turn,
    PokerPhase.river,
]


def _clip01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def encode_poker_obs(seat: PokerSeat, state: PokerState) -> list[float]:
    """Return a length-``POKER_OBS_DIM`` feature list for ``seat`` to act."""
    call_amount = max(state.current_bet - seat.bet_phase, 0.0)
    can_check = call_amount <= 0.0
    pot = state.pot
    strength = _hand_strength(seat.hole_cards, state.community_cards)
    pot_odds = call_amount / (pot + call_amount + 1e-6) if call_amount > 0 else 0.0
    active_opponents = sum(
        1
        for s in state.seats
        if s.seat_index != seat.seat_index and s.status == SeatStatus.active
    )

    phase_onehot = [1.0 if state.phase == p else 0.0 for p in _PHASE_ORDER]

    return [
        _clip01(strength),
        _clip01(pot / STACK_REF),
        _clip01(call_amount / STACK_REF),
        _clip01(seat.chips / (2.0 * STACK_REF)),
        _clip01(state.current_bet / STACK_REF),
        _clip01(seat.bet_phase / STACK_REF),
        _clip01(pot_odds),
        *phase_onehot,
        _clip01(active_opponents / 5.0),
        1.0 if can_check else 0.0,
        _clip01(len(state.community_cards) / 5.0),
    ]


def decode_poker_action(
    action_idx: int,
    seat: PokerSeat,
    state: PokerState,
) -> tuple[PokerAction, float]:
    """Map a discrete action to a legal (PokerAction, raise_target) pair."""
    call_amount = max(state.current_bet - seat.bet_phase, 0.0)
    can_check = call_amount <= 0.0

    if action_idx == 0:  # FOLD — but never fold when checking is free.
        if can_check:
            return PokerAction.check, 0.0
        return PokerAction.fold, 0.0

    if action_idx == 2:  # RAISE
        raise_size = max(state.big_blind * 2.0, state.pot * 0.5)
        target = state.current_bet + raise_size
        # Can we actually put more in than a call? If not, fall back.
        affordable_extra = seat.chips - call_amount
        if affordable_extra > 0:
            return PokerAction.raise_, target
        # Cannot raise → call (or check if free).
        return (PokerAction.check, 0.0) if can_check else (PokerAction.call, 0.0)

    # action_idx == 1 → CHECK / CALL
    return (PokerAction.check, 0.0) if can_check else (PokerAction.call, 0.0)
