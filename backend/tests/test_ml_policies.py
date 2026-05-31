"""Tests for pluggable blackjack bot policies and SB3 PPO/DQN integration."""

import importlib
import random

import pytest

from app.engine.blackjack import BlackjackAction
from app.ml_inference.policies import (
    BasicStrategyPolicy,
    QLearningPolicy,
    RandomLegalPolicy,
    SB3BlackjackPolicy,
    _dealer_card_value,
    _true_count,
    make_default_policy,
)

_HAS_SB3 = importlib.util.find_spec("stable_baselines3") is not None
_requires_sb3 = pytest.mark.skipif(not _HAS_SB3, reason="stable-baselines3 not installed")


# ── Feature encoders ──────────────────────────────────────────────────────────
def test_dealer_card_value_mapping():
    assert _dealer_card_value("AS") == 11
    assert _dealer_card_value("KD") == 10
    assert _dealer_card_value("10H") == 10
    assert _dealer_card_value("7C") == 7
    assert _dealer_card_value(None) == 10


def test_true_count_sign_and_clamp():
    assert _true_count([]) == 0.0
    # Low cards seen → positive count (good for the player).
    assert _true_count(["2C", "3D", "4H", "5S", "6C"]) > 0
    # High cards seen → negative count.
    assert _true_count(["KC", "QD", "JH", "10S", "AC"]) < 0
    # Always clamped to the training observation range.
    assert -20.0 <= _true_count(["2C"] * 40) <= 20.0


# ── Simple policies always produce a legal action ──────────────────────────────
@pytest.mark.parametrize("policy", [RandomLegalPolicy(), BasicStrategyPolicy()])
def test_simple_policies_accept_extended_kwargs(policy):
    action = policy.choose_action(
        ["10H", "6S"],
        random.Random(0),
        dealer_upcard="9D",
        visible_cards=["10H", "6S", "9D"],
    )
    assert action in (BlackjackAction.hit, BlackjackAction.stand)


def test_basic_strategy_stands_on_hard_17_plus():
    assert (
        BasicStrategyPolicy().choose_action(["10H", "7S"]) == BlackjackAction.stand
    )
    assert BasicStrategyPolicy().choose_action(["5H", "6S"]) == BlackjackAction.hit


def test_qlearning_policy_returns_legal_action():
    action = QLearningPolicy().choose_action(["9H", "7S"], dealer_upcard="6D")
    assert action in (BlackjackAction.hit, BlackjackAction.stand)


# ── make_default_policy: explicit fallbacks ────────────────────────────────────
def test_make_default_policy_basic_override(monkeypatch):
    monkeypatch.setenv("BLACKJACK_BOT_POLICY", "basic")
    assert isinstance(make_default_policy(), BasicStrategyPolicy)


def test_make_default_policy_random_override(monkeypatch):
    monkeypatch.setenv("BLACKJACK_BOT_POLICY", "random")
    assert isinstance(make_default_policy(), RandomLegalPolicy)


def test_make_default_policy_unknown_pref_falls_back(monkeypatch):
    monkeypatch.setenv("BLACKJACK_BOT_POLICY", "does_not_exist")
    policy = make_default_policy()
    # Never crashes; returns some usable policy.
    assert hasattr(policy, "choose_action")


def test_sb3_unknown_algo_raises():
    with pytest.raises(RuntimeError):
        SB3BlackjackPolicy("not_an_algo")


# ── Deep-RL policies (only when ml deps + model files are present) ──────────────
@_requires_sb3
@pytest.mark.parametrize("algo", ["ppo", "dqn"])
def test_sb3_policy_decisions_are_legal(algo):
    try:
        policy = SB3BlackjackPolicy(algo)
    except RuntimeError as exc:  # model file missing in this checkout
        pytest.skip(f"{algo} model unavailable: {exc}")
    legal = (BlackjackAction.hit, BlackjackAction.stand, BlackjackAction.double)
    for hand, up in [(["10H", "6S"], "AS"), (["10H", "9S"], "6D"), (["AS", "6H"], "5C")]:
        action = policy.choose_action(
            hand, dealer_upcard=up, visible_cards=hand + [up]
        )
        assert action in legal
    # Always stands on a pat 21+ hand regardless of model output.
    assert policy.choose_action(["10H", "KS"], dealer_upcard="9D") == BlackjackAction.stand


@_requires_sb3
def test_sb3_double_only_on_initial_two_cards():
    try:
        policy = SB3BlackjackPolicy("ppo")
    except RuntimeError as exc:
        pytest.skip(f"ppo model unavailable: {exc}")

    # DOUBLE must never be returned once the hand has more than two cards.
    for hand in (["5H", "3S", "4D"], ["2H", "4S", "5D"], ["6H", "2S", "3D"]):
        assert policy.choose_action(hand, dealer_upcard="6D") != BlackjackAction.double

    # Across a sweep of strong two-card totals vs a weak dealer, the PPO bot
    # should choose to double at least once (its trained strategy doubles 9-11).
    saw_double = False
    two_card_hands = [
        ["5H", "6S"], ["6H", "5S"], ["5H", "5D"], ["4H", "5S"],
        ["6H", "4S"], ["3H", "6S"], ["2H", "7S"], ["4H", "6S"],
    ]
    for hand in two_card_hands:
        for up in ("4D", "5D", "6D", "3D"):
            action = policy.choose_action(hand, dealer_upcard=up, visible_cards=hand + [up])
            assert action in (
                BlackjackAction.hit,
                BlackjackAction.stand,
                BlackjackAction.double,
            )
            if action == BlackjackAction.double:
                saw_double = True
    assert saw_double, "PPO bot never doubled on any strong two-card hand"


@_requires_sb3
def test_default_policy_prefers_ppo_when_available(monkeypatch):
    monkeypatch.setenv("BLACKJACK_BOT_POLICY", "ppo")
    policy = make_default_policy()
    # Either the PPO model loaded, or it fell back cleanly — but it must be usable.
    assert hasattr(policy, "choose_action")
    if isinstance(policy, SB3BlackjackPolicy):
        assert policy.name == "sb3_ppo"
