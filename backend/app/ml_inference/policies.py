"""Pluggable bot policies for blackjack bots."""
from __future__ import annotations

import os
import random
from typing import Protocol

from app.engine.blackjack import BlackjackAction, hand_value


class PlayerBotPolicy(Protocol):
    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
    ) -> BlackjackAction: ...


class RandomLegalPolicy:
    name = "random_legal"

    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
    ) -> BlackjackAction:
        rng = rng or random.Random()
        v, _ = hand_value(hand)
        if v >= 21:
            return BlackjackAction.stand
        return rng.choice([BlackjackAction.hit, BlackjackAction.stand])


class BasicStrategyPolicy:
    name = "basic_strategy"

    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
    ) -> BlackjackAction:
        value, soft = hand_value(hand)
        if value >= 17:
            return BlackjackAction.stand
        if soft and value >= 18:
            return BlackjackAction.stand
        if value <= 11:
            return BlackjackAction.hit
        return BlackjackAction.stand


class QLearningPolicy:
    """Q-Learning trained blackjack policy. Falls back to BasicStrategy if model not found."""

    name = "q_learning"

    def __init__(self) -> None:
        self._q_table: dict | None = None
        self._load_model()

    def _load_model(self) -> None:
        model_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "rl_training", "saved_models", "qlearning_blackjack.pkl",
        )
        model_path = os.path.normpath(model_path)
        if os.path.exists(model_path):
            try:
                import pickle
                with open(model_path, "rb") as f:
                    self._q_table = pickle.load(f)
            except Exception:
                self._q_table = None

    def _state_key(self, hand: list[str]) -> tuple[int, int, bool]:
        """Simplified state: (player_value, assumed_dealer_6, is_soft)."""
        value, soft = hand_value(hand)
        return (min(value, 21), 6, soft)

    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
    ) -> BlackjackAction:
        if self._q_table is None:
            return BasicStrategyPolicy().choose_action(hand, rng)
        key = self._state_key(hand)
        q_vals = self._q_table.get(key, {0: 0.0, 1: 0.0})
        action_idx = max(q_vals, key=q_vals.get)
        return BlackjackAction.stand if action_idx == 0 else BlackjackAction.hit


def make_default_policy() -> PlayerBotPolicy:
    """Create the best available policy (Q-Learning if model exists, else basic strategy)."""
    policy = QLearningPolicy()
    if policy._q_table is not None:
        return policy
    return BasicStrategyPolicy()
