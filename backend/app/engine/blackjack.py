"""Pure blackjack rules: single deck, no split/double in MVP."""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["C", "D", "H", "S"]


class BlackjackPhase(str, enum.Enum):
    player_turn = "player_turn"
    dealer_turn = "dealer_turn"
    finished = "finished"


class BlackjackAction(str, enum.Enum):
    hit = "HIT"
    stand = "STAND"


@dataclass(slots=True)
class BlackjackState:
    deck: list[str]
    player_hand: list[str]
    dealer_hand: list[str]
    phase: BlackjackPhase
    bet: float = 10.0
    message: str | None = None

    def to_public_dict(self) -> dict:
        """Dealer first card hidden during player_turn."""
        dealer_visible = (
            self.dealer_hand
            if self.phase != BlackjackPhase.player_turn
            else ([self.dealer_hand[0]] if self.dealer_hand else [])
        )
        return {
            "phase": self.phase.value,
            "player_hand": list(self.player_hand),
            "dealer_hand": list(dealer_visible),
            "dealer_hidden_count": max(0, len(self.dealer_hand) - len(dealer_visible)),
            "bet": self.bet,
            "message": self.message,
        }


def _card_rank(card: str) -> str:
    return card[:-1]


def hand_value(cards: list[str]) -> tuple[int, bool]:
    """Return (best_value, is_soft) where is_soft means soft ace used as 11."""
    total = 0
    aces = 0
    for c in cards:
        r = _card_rank(c)
        if r == "A":
            aces += 1
            total += 1
        elif r in ("J", "Q", "K"):
            total += 10
        else:
            total += int(r)
    soft = False
    while aces > 0 and total + 10 <= 21:
        total += 10
        aces -= 1
        soft = True
    while aces > 0:
        total += 1
        aces -= 1
    return total, soft


def is_bust(cards: list[str]) -> bool:
    return hand_value(cards)[0] > 21


def _fresh_deck(rng: random.Random) -> list[str]:
    deck = [f"{r}{s}" for s in SUITS for r in RANKS]
    rng.shuffle(deck)
    return deck


def new_round_state(bet: float, rng: random.Random | None = None) -> BlackjackState:
    rng = rng or random.Random()
    deck = _fresh_deck(rng)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    st = BlackjackState(
        deck=deck,
        player_hand=player,
        dealer_hand=dealer,
        phase=BlackjackPhase.player_turn,
        bet=bet,
    )
    if is_bust(st.player_hand):
        st.phase = BlackjackPhase.finished
        st.message = "player_bust_natural_impossible"
    pv, _ = hand_value(st.player_hand)
    dv, _ = hand_value(st.dealer_hand)
    if pv == 21 and dv == 21:
        st.phase = BlackjackPhase.finished
        st.message = "push_blackjack"
    elif pv == 21:
        st.phase = BlackjackPhase.finished
        st.message = "player_blackjack"
    elif dv == 21:
        st.phase = BlackjackPhase.finished
        st.message = "dealer_blackjack"
    return st


def apply_action(state: BlackjackState, action: BlackjackAction) -> BlackjackState:
    if state.phase != BlackjackPhase.player_turn:
        raise ValueError("not_player_turn")
    if action == BlackjackAction.hit:
        if not state.deck:
            raise ValueError("empty_deck")
        state.player_hand.append(state.deck.pop())
        if is_bust(state.player_hand):
            state.phase = BlackjackPhase.finished
            state.message = "player_bust"
        return state
    if action == BlackjackAction.stand:
        state.phase = BlackjackPhase.dealer_turn
        return state
    raise ValueError("unknown_action")


def play_dealer(state: BlackjackState) -> BlackjackState:
    if state.phase != BlackjackPhase.dealer_turn:
        return state
    while hand_value(state.dealer_hand)[0] < 17:
        if not state.deck:
            raise ValueError("empty_deck")
        state.dealer_hand.append(state.deck.pop())
    state.phase = BlackjackPhase.finished
    if is_bust(state.dealer_hand):
        state.message = "dealer_bust"
    return state


def settle(state: BlackjackState) -> tuple[str, float]:
    """
    Returns (result_key, payout_credit) for player after the bet was already deducted.
    payout_credit: amount added to wallet after the bet was deducted
    (0 on loss, stake on push, stake plus profit on win).
    """
    bet = state.bet
    if state.message == "player_bust":
        return "loss", 0.0
    if state.message == "dealer_blackjack" and hand_value(state.player_hand)[0] != 21:
        return "loss", 0.0
    if state.message == "player_blackjack":
        return "win", bet + bet * 1.5
    if state.message == "push_blackjack":
        return "draw", bet
    if state.message == "dealer_bust":
        return "win", bet * 2.0
    pv, _ = hand_value(state.player_hand)
    dv, _ = hand_value(state.dealer_hand)
    if pv > dv:
        return "win", bet * 2.0
    if pv < dv:
        return "loss", 0.0
    return "draw", bet
