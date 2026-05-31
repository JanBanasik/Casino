"""Train a PPO Texas Hold'em bot against the heuristic opponents.

Usage:
    python rl_training/train_poker_ppo.py [--timesteps N] [--bots K] [--eval N]

The trained model is saved to the same ``models/`` directory the inference
layer reads from, so the live ``PokerRLPolicy`` picks it up automatically.
Requires the optional ``ml`` dependency group (stable-baselines3 + torch).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from poker_env import PokerEnv  # noqa: E402

_MODEL_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "backend", "app", "ml_inference", "notebooks", "models",
    )
)
_MODEL_PATH = os.path.join(_MODEL_DIR, "ppo_poker_bot")


def make_env(bots: int):
    def _factory():
        return PokerEnv(bot_count=bots)

    return _factory


def evaluate(model, bots: int, episodes: int, seed: int = 12345) -> float:
    """Average per-hand reward (big-blind units) under the greedy policy."""
    env = PokerEnv(bot_count=bots, seed=seed)
    total = 0.0
    for _ in range(episodes):
        obs, _ = env.reset()
        done = False
        ep = 0.0
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            ep += reward
        total += ep
    return total / episodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=400_000)
    parser.add_argument("--bots", type=int, default=2)
    parser.add_argument("--envs", type=int, default=8)
    parser.add_argument("--eval", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    vec_env = DummyVecEnv([make_env(args.bots) for _ in range(args.envs)])

    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=256,
        n_epochs=10,
        gamma=0.99,
        ent_coef=0.01,
        seed=args.seed,
        policy_kwargs=dict(net_arch=dict(pi=[128, 128], vf=[128, 128])),
        device="cpu",
    )

    print(f"Training PPO poker bot for {args.timesteps:,} timesteps "
          f"({args.bots} opponents, {args.envs} parallel envs)...")
    # progress_bar=True needs tqdm+rich (sb3[extra]); rely on verbose logging instead.
    model.learn(total_timesteps=args.timesteps)

    os.makedirs(_MODEL_DIR, exist_ok=True)
    model.save(_MODEL_PATH)
    print(f"Saved model → {_MODEL_PATH}.zip")

    if args.eval > 0:
        avg = evaluate(model, args.bots, args.eval, seed=args.seed + 1)
        print(f"\nGreedy eval over {args.eval:,} hands: "
              f"mean reward = {avg:+.3f} big blinds/hand")


if __name__ == "__main__":
    main()
