"""Difficulty-dependent payout boosting.

Harder tables reward the player with a higher multiplier on *net winnings*
(the profit above the original stake). The returned stake is never scaled, so a
loss still loses exactly the stake and a draw still breaks even — only the win
profit grows with difficulty.
"""
from __future__ import annotations

import math

from app.core.config import settings
from app.ml_inference.registry import Difficulty, normalize_difficulty


def difficulty_win_multiplier(difficulty: str | Difficulty | None) -> float:
    d = difficulty if isinstance(difficulty, Difficulty) else normalize_difficulty(difficulty)
    return {
        Difficulty.easy: settings.win_multiplier_easy,
        Difficulty.medium: settings.win_multiplier_medium,
        Difficulty.hard: settings.win_multiplier_hard,
    }[d]


def round_chips(amount: float) -> float:
    """Round to the nearest whole chip, halves going up (1.25 → 1, 1.5 → 2)."""
    return float(math.floor(amount + 0.5))


def boost_credit(credit: float, stake: float, difficulty: str | Difficulty | None) -> float:
    """Final amount credited for a settled hand.

    Scales only the winning *profit* (``credit - stake``) by the level's
    multiplier, then rounds the whole credit to the nearest whole chip so the
    account never holds a fractional żeton (e.g. 32.5 → 33, 32.4 → 32). Losses
    (credit 0) and draws (credit == stake) are returned unchanged.
    """
    net = credit - stake
    if net <= 0:
        return credit
    mult = difficulty_win_multiplier(difficulty)
    return round_chips(stake + net * mult)
