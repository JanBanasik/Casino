"""Poker bot policies: deep-RL (PPO) with heuristic fallback.

``PokerRLPolicy`` loads the PPO model trained by
``rl_training/train_poker_ppo.py`` and exposes the same
``choose_action(seat, state, rng)`` interface as the engine's
``SimplePokerBotPolicy``, so it is a drop-in replacement consumed by
``advance_poker_bots``.

If stable-baselines3/torch is unavailable or the model file is missing,
construction raises and ``make_poker_policy`` falls back to the heuristic —
the app never hard-depends on torch.
"""
from __future__ import annotations

import os
import random

from app.engine.poker import (
    PokerAction,
    PokerSeat,
    PokerState,
    SimplePokerBotPolicy,
)
from app.ml_inference.poker_features import decode_poker_action, encode_poker_obs

_MODEL_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), "notebooks", "models", "ppo_poker_bot.zip"
    )
)


class PokerRLPolicy:
    """PPO-backed Texas Hold'em policy. Raises on construction if unavailable."""

    name = "ppo_poker"

    def __init__(self, model_path: str | None = None) -> None:
        path = model_path or _MODEL_PATH
        if not os.path.exists(path):
            raise RuntimeError(f"model_not_found:{path}")
        try:
            import numpy as np
            from stable_baselines3 import PPO
        except Exception as exc:  # pragma: no cover - only without ml deps
            raise RuntimeError(f"sb3_import_failed:{exc}") from exc
        try:
            self._model = PPO.load(path, device="cpu")
        except Exception as exc:
            raise RuntimeError(f"model_load_failed:{exc}") from exc
        self._np = np

    def choose_action(
        self,
        seat: PokerSeat,
        state: PokerState,
        rng: random.Random | None = None,
    ) -> tuple[PokerAction, float]:
        obs = self._np.array(encode_poker_obs(seat, state), dtype=self._np.float32)
        action, _ = self._model.predict(obs, deterministic=True)
        action_idx = int(self._np.asarray(action).reshape(-1)[0])
        return decode_poker_action(action_idx, seat, state)


class LoosePokerBotPolicy:
    """Weak "easy" bot: a calling station that rarely folds and never bluffs.

    Mirrors the ``choose_action`` interface so it drops into ``advance_poker_bots``.
    """

    name = "loose_poker"

    def choose_action(
        self,
        seat: PokerSeat,
        state: PokerState,
        rng: random.Random | None = None,
    ) -> tuple[PokerAction, float]:
        rng = rng or random.Random()
        call_amount = state.current_bet - seat.bet_phase
        if call_amount <= 0:
            return PokerAction.check, 0.0
        # Calls almost anything it can afford; folds only to very large bets.
        if call_amount <= seat.chips * 0.6:
            return PokerAction.call, 0.0
        return PokerAction.fold, 0.0


def make_poker_policy():
    """Best available poker policy.

    Controlled by ``POKER_BOT_POLICY`` (ppo|heuristic). Defaults to PPO, falling
    back to the heuristic when the model or ML runtime is unavailable.
    """
    preference = os.getenv("POKER_BOT_POLICY", "ppo").strip().lower()
    if preference == "heuristic":
        return SimplePokerBotPolicy()
    try:
        return PokerRLPolicy()
    except Exception:
        return SimplePokerBotPolicy()
