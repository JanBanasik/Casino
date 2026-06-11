"""Difficulty-aware bot policy registry.

A single process-wide cache holds one policy instance per (game, difficulty),
so the SB3 models load at most once and are shared across every table. Bot
advancement reloads game state from Redis on each step, so the *difficulty* —
not the policy object — is what gets persisted; the policy is re-resolved here.

Difficulty → policy mapping
    Blackjack: easy=random · medium=basic strategy · hard=PPO/DQN/Q-learning
    Poker:     easy=loose caller · medium=heuristic · hard=PPO
"""
from __future__ import annotations

import enum
from threading import Lock


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


def normalize_difficulty(value: str | None) -> Difficulty:
    if not value:
        return Difficulty.medium
    try:
        return Difficulty(str(value).strip().lower())
    except ValueError:
        return Difficulty.medium


_lock = Lock()
_blackjack_cache: dict[Difficulty, object] = {}
_poker_cache: dict[Difficulty, object] = {}


def _build_blackjack(difficulty: Difficulty):
    from app.ml_inference.policies import (
        BasicStrategyPolicy,
        QLearningPolicy,
        RandomLegalPolicy,
        SB3BlackjackPolicy,
    )

    if difficulty == Difficulty.easy:
        return RandomLegalPolicy()
    if difficulty == Difficulty.medium:
        return BasicStrategyPolicy()
    # hard: best available deep-RL, degrading gracefully without ml deps.
    for choice in ("ppo", "dqn"):
        try:
            return SB3BlackjackPolicy(choice)
        except Exception:
            continue
    try:
        ql = QLearningPolicy()
        if ql._q_table is not None:
            return ql
    except Exception:
        pass
    return BasicStrategyPolicy()


def _build_poker(difficulty: Difficulty):
    from app.engine.poker import SimplePokerBotPolicy
    from app.ml_inference.poker_policies import LoosePokerBotPolicy, PokerRLPolicy

    if difficulty == Difficulty.easy:
        return LoosePokerBotPolicy()
    if difficulty == Difficulty.medium:
        return SimplePokerBotPolicy()
    try:
        return PokerRLPolicy()
    except Exception:
        return SimplePokerBotPolicy()


def get_blackjack_policy(difficulty: Difficulty | str | None):
    diff = difficulty if isinstance(difficulty, Difficulty) else normalize_difficulty(difficulty)
    with _lock:
        if diff not in _blackjack_cache:
            _blackjack_cache[diff] = _build_blackjack(diff)
        return _blackjack_cache[diff]


def get_poker_policy(difficulty: Difficulty | str | None):
    diff = difficulty if isinstance(difficulty, Difficulty) else normalize_difficulty(difficulty)
    with _lock:
        if diff not in _poker_cache:
            _poker_cache[diff] = _build_poker(diff)
        return _poker_cache[diff]
