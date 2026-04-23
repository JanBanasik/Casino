"""Pluggable bot policies; MVP uses rules / random — swap for RL later."""

from __future__ import annotations

import random
from typing import Protocol

from app.engine.blackjack import BlackjackAction, BlackjackState, hand_value


class PlayerBotPolicy(Protocol):
    def choose_action(
        self,
        state: BlackjackState,
        rng: random.Random | None = None,
    ) -> BlackjackAction: ...


class DealerPolicy:
    """Dealer rule: hit until value >= 17 (handled in engine.play_dealer)."""

    name = "dealer_rules_mvp"


class RandomLegalPolicy:
    """Random legal player action (stub for future RL agent)."""

    name = "random_legal"

    def choose_action(
        self,
        state: BlackjackState,
        rng: random.Random | None = None,
    ) -> BlackjackAction:
        rng = rng or random.Random()
        v, _ = hand_value(state.player_hand)
        if v >= 21:
            return BlackjackAction.stand
        return rng.choice([BlackjackAction.hit, BlackjackAction.stand])
