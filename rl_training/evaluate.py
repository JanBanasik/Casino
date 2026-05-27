"""Evaluate Q-Learning agent vs Basic Strategy."""
from __future__ import annotations

import os
import pickle
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from blackjack_env import BlackjackEnv  # noqa: E402


def load_q_table(path: str) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def evaluate_q_learning(q_table: dict, episodes: int = 10_000, seed: int = 99) -> dict:
    rng = random.Random(seed)
    env = BlackjackEnv(rng)
    wins = losses = draws = 0

    for _ in range(episodes):
        state = env.reset()
        done = False
        while not done:
            q_vals = q_table.get(state, {0: 0.0, 1: 0.0})
            action = max(q_vals, key=q_vals.get)
            state, reward, done = env.step(action)
        if reward > 0:
            wins += 1
        elif reward < 0:
            losses += 1
        else:
            draws += 1

    return {"wins": wins, "losses": losses, "draws": draws, "win_rate": wins / episodes}


def evaluate_basic_strategy(episodes: int = 10_000, seed: int = 99) -> dict:
    from app.engine.blackjack import hand_value
    rng = random.Random(seed)
    env = BlackjackEnv(rng)
    wins = losses = draws = 0

    for _ in range(episodes):
        state = env.reset()
        done = False
        while not done:
            # Basic strategy: hit if < 17
            val, soft = hand_value(env.state.player_hand)
            action = 1 if val < 17 else 0  # 1=hit, 0=stand
            state, reward, done = env.step(action)
        if reward > 0:
            wins += 1
        elif reward < 0:
            losses += 1
        else:
            draws += 1

    return {"wins": wins, "losses": losses, "draws": draws, "win_rate": wins / episodes}


if __name__ == "__main__":
    model_path = os.path.join(os.path.dirname(__file__), "saved_models", "qlearning_blackjack.pkl")

    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}")
        print("Run train_qlearning.py first.")
        sys.exit(1)

    q_table = load_q_table(model_path)
    EPISODES = 50_000

    print(f"Evaluating over {EPISODES:,} games each...\n")

    q_stats = evaluate_q_learning(q_table, EPISODES)
    bs_stats = evaluate_basic_strategy(EPISODES)

    print(f"Q-Learning:     WR={q_stats['win_rate']:.1%}  W={q_stats['wins']} L={q_stats['losses']} D={q_stats['draws']}")
    print(f"Basic Strategy: WR={bs_stats['win_rate']:.1%}  W={bs_stats['wins']} L={bs_stats['losses']} D={bs_stats['draws']}")
