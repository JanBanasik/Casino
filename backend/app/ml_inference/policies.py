"""Pluggable bot policies for blackjack bots.

Policy stack (best → simplest):
    SB3 PPO  →  SB3 DQN  →  Q-Learning table  →  Basic strategy  →  Random.

Deep-RL policies (PPO/DQN) need the optional ``ml`` dependency group
(stable-baselines3 + torch). When those imports fail — or the model file is
missing — construction raises and ``make_default_policy`` transparently falls
back to the next policy down the stack, so the app never hard-depends on torch.
"""
from __future__ import annotations

import os
import random
from typing import Protocol

from app.engine.blackjack import BlackjackAction, hand_value

_MODELS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "notebooks", "models")
)
_QLEARNING_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "rl_training", "saved_models", "qlearning_blackjack.pkl",
    )
)

# Hi-Lo card-counting weights (running count).
_HILO = {
    "2": 1, "3": 1, "4": 1, "5": 1, "6": 1,
    "7": 0, "8": 0, "9": 0,
    "10": -1, "J": -1, "Q": -1, "K": -1, "A": -1,
}


class PlayerBotPolicy(Protocol):
    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
        *,
        dealer_upcard: str | None = None,
        visible_cards: list[str] | None = None,
    ) -> BlackjackAction: ...


def _card_rank(card: str) -> str:
    return card[:-1]


def _dealer_card_value(dealer_upcard: str | None) -> int:
    """Dealer upcard as a model feature (Ace = 11, faces = 10)."""
    if not dealer_upcard:
        return 10
    rank = _card_rank(dealer_upcard)
    if rank == "A":
        return 11
    if rank in ("J", "Q", "K"):
        return 10
    try:
        return int(rank)
    except ValueError:
        return 10


def _true_count(visible_cards: list[str] | None, num_decks: int = 1) -> float:
    """Hi-Lo true count from the cards currently visible on the table."""
    if not visible_cards:
        return 0.0
    running = sum(_HILO.get(_card_rank(c), 0) for c in visible_cards)
    remaining_decks = max((num_decks * 52 - len(visible_cards)) / 52.0, 0.25)
    tc = running / remaining_decks
    return max(-20.0, min(20.0, tc))


class RandomLegalPolicy:
    name = "random_legal"

    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
        *,
        dealer_upcard: str | None = None,
        visible_cards: list[str] | None = None,
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
        *,
        dealer_upcard: str | None = None,
        visible_cards: list[str] | None = None,
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
        if os.path.exists(_QLEARNING_PATH):
            try:
                import pickle
                with open(_QLEARNING_PATH, "rb") as f:
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
        *,
        dealer_upcard: str | None = None,
        visible_cards: list[str] | None = None,
    ) -> BlackjackAction:
        if self._q_table is None:
            return BasicStrategyPolicy().choose_action(hand, rng)
        key = self._state_key(hand)
        q_vals = self._q_table.get(key, {0: 0.0, 1: 0.0})
        action_idx = max(q_vals, key=q_vals.get)
        return BlackjackAction.stand if action_idx == 0 else BlackjackAction.hit


class SB3BlackjackPolicy:
    """Deep-RL (PPO or DQN) blackjack policy backed by a stable-baselines3 model.

    Observation matches the training env (CountingBlackjackEnv):
        [player_score, dealer_card, usable_ace, true_count]
    Action space is Discrete(3): 0=STAND, 1=HIT, 2=DOUBLE. The live engine has
    no double, so DOUBLE is played as HIT (take one card).

    Raises RuntimeError on construction if stable-baselines3/torch is unavailable
    or the model file is missing — callers handle the fallback.
    """

    _ALGOS = {"ppo": "ppo_blackjack_bot.zip", "dqn": "dqn_blackjack_bot.zip"}

    def __init__(self, algo: str = "ppo") -> None:
        algo = algo.lower()
        if algo not in self._ALGOS:
            raise RuntimeError(f"unknown_sb3_algo:{algo}")
        self.name = f"sb3_{algo}"
        self._algo = algo
        model_path = os.path.join(_MODELS_DIR, self._ALGOS[algo])
        if not os.path.exists(model_path):
            raise RuntimeError(f"model_not_found:{model_path}")

        try:
            import numpy as np  # noqa: F401
            from stable_baselines3 import DQN, PPO
        except Exception as exc:  # pragma: no cover - exercised only without ml deps
            raise RuntimeError(f"sb3_import_failed:{exc}") from exc

        loader = PPO if algo == "ppo" else DQN
        try:
            self._model = loader.load(model_path, device="cpu")
        except Exception as exc:
            raise RuntimeError(f"model_load_failed:{exc}") from exc
        self._np = np

    def _encode(
        self,
        hand: list[str],
        dealer_upcard: str | None,
        visible_cards: list[str] | None,
    ):
        value, soft = hand_value(hand)
        return self._np.array(
            [
                float(min(max(value, 4), 31)),
                float(_dealer_card_value(dealer_upcard)),
                1.0 if soft else 0.0,
                _true_count(visible_cards),
            ],
            dtype=self._np.float32,
        )

    def choose_action(
        self,
        hand: list[str],
        rng: random.Random | None = None,
        *,
        dealer_upcard: str | None = None,
        visible_cards: list[str] | None = None,
    ) -> BlackjackAction:
        value, _ = hand_value(hand)
        if value >= 21:
            return BlackjackAction.stand
        obs = self._encode(hand, dealer_upcard, visible_cards)
        action, _ = self._model.predict(obs, deterministic=True)
        action_idx = int(self._np.asarray(action).reshape(-1)[0])
        # 0=STAND, 1=HIT, 2=DOUBLE. Double is only legal on the opening two
        # cards; after that the model's DOUBLE collapses to a plain HIT.
        if action_idx == 0:
            return BlackjackAction.stand
        if action_idx == 2 and len(hand) == 2:
            return BlackjackAction.double
        return BlackjackAction.hit


def make_default_policy() -> PlayerBotPolicy:
    """Build the best available policy.

    Order is configurable via ``BLACKJACK_BOT_POLICY`` (ppo|dqn|qlearning|basic|random).
    Unavailable choices fall through to the next viable policy.
    """
    preference = os.getenv("BLACKJACK_BOT_POLICY", "ppo").strip().lower()

    order = ["ppo", "dqn", "qlearning", "basic", "random"]
    if preference in order:
        order = order[order.index(preference):] + ["basic", "random"]

    for choice in order:
        try:
            if choice in ("ppo", "dqn"):
                return SB3BlackjackPolicy(choice)
            if choice == "qlearning":
                policy = QLearningPolicy()
                if policy._q_table is not None:
                    return policy
                continue
            if choice == "basic":
                return BasicStrategyPolicy()
            if choice == "random":
                return RandomLegalPolicy()
        except Exception:
            continue
    return BasicStrategyPolicy()
