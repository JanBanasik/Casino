"""Pluggable bot policies."""

from __future__ import annotations

import random
from typing import Protocol

from app.engine.blackjack import BlackjackAction, BlackjackState, hand_value


class PlayerBotPolicy(Protocol):
    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
    ) -> BlackjackAction: ...


class DealerPolicy:
    name = "dealer_rules"


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
