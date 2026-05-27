"""Blackjack RL environment wrapping the casino engine for Q-Learning training."""
from __future__ import annotations

import random
import sys
import os

# Allow importing from backend without installing it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.engine.blackjack import (
    BlackjackAction,
    BlackjackPhase,
    hand_value,
    new_round_state,
    apply_action,
    play_dealer,
    settle,
)


def _state_key(hand: list[str], dealer_upcard: str) -> tuple[int, int, bool]:
    """Return (player_value, dealer_upcard_value, is_soft) state representation."""
    player_val, soft = hand_value(hand)
    player_val = min(player_val, 21)

    # Dealer upcard value (Ace = 11)
    from app.engine.blackjack import _card_rank
    rank = _card_rank(dealer_upcard)
    if rank == "A":
        dealer_val = 11
    elif rank in ("J", "Q", "K"):
        dealer_val = 10
    else:
        dealer_val = int(rank)

    return (player_val, dealer_val, soft)


class BlackjackEnv:
    """Single-player blackjack environment for Q-Learning."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.state = None

    def reset(self, bet: float = 10.0):
        """Start a new round. Returns state key."""
        self.state = new_round_state(bet, self.rng)
        while self.state.phase == BlackjackPhase.finished:
            # Natural blackjack/push on deal — just restart
            self.state = new_round_state(bet, self.rng)
        dealer_upcard = self.state.dealer_hand[0]
        return _state_key(self.state.player_hand, dealer_upcard)

    def step(self, action: int) -> tuple[tuple, float, bool]:
        """
        Apply action (0=STAND, 1=HIT).
        Returns (next_state_key, reward, done).
        """
        bj_action = BlackjackAction.stand if action == 0 else BlackjackAction.hit
        self.state = apply_action(self.state, bj_action)

        if self.state.phase == BlackjackPhase.dealer_turn:
            self.state = play_dealer(self.state)

        if self.state.phase == BlackjackPhase.finished:
            result, payout = settle(self.state)
            if result == "win":
                reward = 1.0
            elif result == "draw":
                reward = 0.0
            else:
                reward = -1.0
            return None, reward, True

        dealer_upcard = self.state.dealer_hand[0]
        next_key = _state_key(self.state.player_hand, dealer_upcard)
        return next_key, 0.0, False
