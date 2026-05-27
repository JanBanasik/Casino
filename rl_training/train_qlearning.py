"""
Q-Learning trainer for Blackjack.

Usage:
    cd rl_training
    python train_qlearning.py

Saves trained Q-table to saved_models/qlearning_blackjack.pkl
"""
from __future__ import annotations

import pickle
import random
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from blackjack_env import BlackjackEnv, _state_key  # noqa: E402


# ── Hyperparameters ───────────────────────────────────────────────────────────
EPISODES = 200_000
ALPHA = 0.1          # learning rate
GAMMA = 0.99         # discount factor
EPSILON_START = 1.0
EPSILON_END = 0.05
EPSILON_DECAY = 0.9999_5   # per episode

ACTIONS = [0, 1]  # 0=STAND, 1=HIT


def train(seed: int = 42) -> dict:
    rng = random.Random(seed)
    env = BlackjackEnv(rng)

    # Q[state][action] = float
    Q: dict[tuple, dict[int, float]] = defaultdict(lambda: {0: 0.0, 1: 0.0})
    epsilon = EPSILON_START

    wins = losses = draws = 0

    for ep in range(1, EPISODES + 1):
        state = env.reset()
        done = False

        while not done:
            # ε-greedy action selection
            if rng.random() < epsilon:
                action = rng.choice(ACTIONS)
            else:
                q_vals = Q[state]
                action = max(q_vals, key=q_vals.get)

            next_state, reward, done = env.step(action)

            # Q-Learning update
            if done:
                target = reward
            else:
                target = reward + GAMMA * max(Q[next_state].values())

            Q[state][action] += ALPHA * (target - Q[state][action])
            state = next_state

        # Track stats
        if reward > 0:
            wins += 1
        elif reward < 0:
            losses += 1
        else:
            draws += 1

        epsilon = max(EPSILON_END, epsilon * EPSILON_DECAY)

        if ep % 20_000 == 0:
            total = wins + losses + draws
            win_rate = wins / total if total > 0 else 0
            print(f"Episode {ep:>7} | ε={epsilon:.4f} | WR={win_rate:.1%} | W={wins} L={losses} D={draws}")
            wins = losses = draws = 0

    return dict(Q)  # Convert to regular dict for pickling


def main():
    print("Training Q-Learning agent for Blackjack...")
    print(f"Episodes: {EPISODES:,} | α={ALPHA} | γ={GAMMA}")
    print("-" * 60)

    q_table = train()

    out_dir = os.path.join(os.path.dirname(__file__), "saved_models")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "qlearning_blackjack.pkl")

    with open(out_path, "wb") as f:
        pickle.dump(q_table, f)

    print(f"\n✓ Q-table saved to {out_path}")
    print(f"  States learned: {len(q_table)}")

    # Quick sanity check
    print("\nSample Q-values (player_val, dealer_upcard, soft):")
    for key in [(16, 7, False), (11, 10, False), (18, 6, True), (20, 5, False)]:
        qv = q_table.get(key, {0: 0.0, 1: 0.0})
        best = "STAND" if qv.get(0, 0) >= qv.get(1, 0) else "HIT"
        print(f"  {str(key):30s} → {best}  (Q={qv})")


if __name__ == "__main__":
    main()
