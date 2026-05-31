"""Texas Hold'em RL environment: one PPO agent vs heuristic bots.

The learning agent sits at one seat of the existing casino poker engine and
plays full hands against ``SimplePokerBotPolicy`` opponents. Between the
agent's decisions the environment auto-plays every bot turn, so the agent only
ever observes states where it is on the action.

Reward is sparse: ``0`` while the hand is in progress, and the agent's net
chip change for the hand (normalised by the big blind) at terminal states.
"""
from __future__ import annotations

import os
import random
import sys

import gymnasium as gym
import numpy as np
from gymnasium import spaces

# Allow importing the backend package without installing it.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.engine.poker import (  # noqa: E402
    PokerPhase,
    SimplePokerBotPolicy,
    advance_poker_bots,
    apply_poker_action,
    new_poker_round,
)
from app.ml_inference.poker_features import (  # noqa: E402
    POKER_OBS_DIM,
    decode_poker_action,
    encode_poker_obs,
)


class PokerEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        bot_count: int = 2,
        buy_in: float = 1000.0,
        small_blind: float = 10.0,
        big_blind: float = 20.0,
        seed: int | None = None,
    ):
        super().__init__()
        self.bot_count = bot_count
        self.buy_in = buy_in
        self.small_blind = small_blind
        self.big_blind = big_blind

        self.action_space = spaces.Discrete(3)  # FOLD, CHECK/CALL, RAISE
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(POKER_OBS_DIM,), dtype=np.float32
        )

        self._rng = random.Random(seed)
        self._bot_policy = SimplePokerBotPolicy()
        self.state = None
        self.agent_seat_index = 0

    # ── gym API ────────────────────────────────────────────────────────────
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = random.Random(seed)

        # Deal hands until the agent actually has a decision to make (it may get
        # folded around to a showdown before ever acting on some deals).
        for _ in range(100):
            self.agent_seat_index = self._rng.randint(0, self.bot_count)
            self.state = new_poker_round(
                human_name="AGENT",
                human_id="agent",
                human_seat_index=self.agent_seat_index,
                bot_count=self.bot_count,
                buy_in=self.buy_in,
                small_blind=self.small_blind,
                big_blind=self.big_blind,
                rng=self._rng,
            )
            self._advance_to_agent()
            if not self._hand_over():
                break

        return self._obs(), {}

    def step(self, action):
        if self.state is None:
            raise RuntimeError("step before reset")

        seat = self.state.seats[self.agent_seat_index]
        poker_action, amount = decode_poker_action(int(action), seat, self.state)
        apply_poker_action(self.state, self.agent_seat_index, poker_action, amount)

        if not self._hand_over():
            advance_poker_bots(self.state, self._bot_policy, rng=self._rng)

        terminated = self._hand_over()
        reward = 0.0
        if terminated:
            seat = self.state.seats[self.agent_seat_index]
            # Net chip P/L for the whole hand, scaled by the big blind.
            reward = float((seat.chips - self.buy_in) / self.big_blind)

        return self._obs(), reward, terminated, False, {}

    # ── helpers ──────────────────────────────────────────────────────────────
    def _hand_over(self) -> bool:
        return self.state.phase in (PokerPhase.showdown, PokerPhase.finished)

    def _advance_to_agent(self) -> None:
        """Auto-play bots until it's the agent's turn or the hand ends."""
        if not self._hand_over() and self.state.active_seat_index != self.agent_seat_index:
            advance_poker_bots(self.state, self._bot_policy, rng=self._rng)

    def _obs(self) -> np.ndarray:
        seat = self.state.seats[self.agent_seat_index]
        return np.array(encode_poker_obs(seat, self.state), dtype=np.float32)
