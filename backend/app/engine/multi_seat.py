"""Multi-seat blackjack: shared deck and dealer, human + bot seats."""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass, field

from app.engine.blackjack import (
    BlackjackAction,
    BlackjackPhase,
    _fresh_deck,
    hand_value,
    is_bust,
    play_dealer,
    settle,
)

BOT_PROFILES = [
    {"display_name": "Alex_K", "avatar_key": "a1"},
    {"display_name": "Marta99", "avatar_key": "m2"},
    {"display_name": "JanekW", "avatar_key": "j3"},
    {"display_name": "Ola_P", "avatar_key": "o4"},
    {"display_name": "Kris77", "avatar_key": "k5"},
    {"display_name": "Ewa_M", "avatar_key": "e6"},
]


class SeatStatus(str, enum.Enum):
    empty = "empty"
    waiting = "waiting"
    acting = "acting"
    stood = "stood"
    bust = "bust"
    finished = "finished"


@dataclass
class SeatState:
    seat_index: int
    display_name: str
    avatar_key: str
    is_human: bool
    occupant_id: str
    hand: list[str] = field(default_factory=list)
    bet: float = 10.0
    status: SeatStatus = SeatStatus.waiting
    result: str | None = None
    payout: float = 0.0


@dataclass
class MultiSeatBlackjackState:
    deck: list[str]
    dealer_hand: list[str]
    seats: list[SeatState]
    human_seat_index: int
    active_seat_index: int | None = None
    phase: BlackjackPhase = BlackjackPhase.player_turn
    message: str | None = None

    def human_seat(self) -> SeatState:
        return self.seats[self.human_seat_index]

    def to_public_dict(self, *, table_phase: str = "playing") -> dict:
        hide_dealer = self.phase == BlackjackPhase.player_turn
        dealer_visible = (
            list(self.dealer_hand)
            if not hide_dealer
            else ([self.dealer_hand[0]] if self.dealer_hand else [])
        )
        human = self.human_seat()
        return {
            "table_phase": table_phase,
            "phase": self.phase.value,
            "player_hand": list(human.hand),
            "dealer_hand": dealer_visible,
            "dealer_hidden_count": max(0, len(self.dealer_hand) - len(dealer_visible)),
            "bet": human.bet,
            "message": self.message,
            "active_seat_index": self.active_seat_index,
            "human_seat_index": self.human_seat_index,
            "seats": [
                {
                    "seat_index": s.seat_index,
                    "display_name": s.display_name,
                    "avatar_key": s.avatar_key,
                    "is_human": s.is_human,
                    "hand": list(s.hand),
                    "bet": s.bet,
                    "status": s.status.value,
                    "result": s.result,
                    "payout": s.payout,
                }
                for s in self.seats
                if s.status != SeatStatus.empty
            ],
        }


def _check_seat_blackjack(seat: SeatState, dealer_hand: list[str]) -> bool:
    pv, _ = hand_value(seat.hand)
    dv, _ = hand_value(dealer_hand)
    if pv == 21:
        seat.status = SeatStatus.finished
        if dv == 21:
            seat.result = "draw"
        else:
            seat.result = "win"
        return True
    if dv == 21:
        seat.status = SeatStatus.finished
        seat.result = "loss"
        return True
    return False


def _next_active_seat(state: MultiSeatBlackjackState, start: int) -> int | None:
    for i in range(start, len(state.seats)):
        s = state.seats[i]
        if s.status == SeatStatus.empty:
            continue
        if s.status in (SeatStatus.acting, SeatStatus.waiting):
            return i
    return None


def build_seats(
    *,
    human_name: str,
    human_id: str,
    human_seat_index: int,
    bot_count: int,
    bet: float,
) -> list[SeatState]:
    """Seven table slots; human at chosen index, bots fill other slots up to bot_count."""
    human_seat_index = max(0, min(6, human_seat_index))
    bot_count = max(0, min(bot_count, 6))
    seats: list[SeatState] = []
    bot_idx = 0
    bots_left = bot_count
    for i in range(7):
        if i == human_seat_index:
            seats.append(
                SeatState(
                    seat_index=i,
                    display_name=human_name,
                    avatar_key="you",
                    is_human=True,
                    occupant_id=human_id,
                    bet=bet,
                    status=SeatStatus.waiting,
                )
            )
        elif bots_left > 0:
            profile = BOT_PROFILES[bot_idx % len(BOT_PROFILES)]
            bot_idx += 1
            bots_left -= 1
            seats.append(
                SeatState(
                    seat_index=i,
                    display_name=profile["display_name"],
                    avatar_key=profile["avatar_key"],
                    is_human=False,
                    occupant_id=f"bot_{profile['avatar_key']}",
                    bet=bet,
                    status=SeatStatus.waiting,
                )
            )
        else:
            seats.append(
                SeatState(
                    seat_index=i,
                    display_name="",
                    avatar_key="",
                    is_human=False,
                    occupant_id="",
                    bet=0.0,
                    status=SeatStatus.empty,
                )
            )
    return seats


def new_multi_round(
    *,
    bet: float,
    human_name: str,
    human_id: str,
    human_seat_index: int = 3,
    bot_count: int = 0,
    rng: random.Random | None = None,
) -> MultiSeatBlackjackState:
    rng = rng or random.Random()
    bot_count = max(0, min(bot_count, len(BOT_PROFILES)))
    seats = build_seats(
        human_name=human_name,
        human_id=human_id,
        human_seat_index=human_seat_index,
        bot_count=bot_count,
        bet=bet,
    )
    human_index = human_seat_index

    deck = _fresh_deck(rng)
    dealer = [deck.pop(), deck.pop()]

    for seat in seats:
        if seat.status == SeatStatus.empty:
            continue
        seat.hand = [deck.pop(), deck.pop()]
        seat.status = SeatStatus.acting
        if is_bust(seat.hand):
            seat.status = SeatStatus.bust
            seat.result = "loss"
        elif _check_seat_blackjack(seat, dealer):
            pass
        else:
            seat.status = SeatStatus.acting

    state = MultiSeatBlackjackState(
        deck=deck,
        dealer_hand=dealer,
        seats=seats,
        human_seat_index=human_index,
    )

    playing = [s for s in seats if s.status != SeatStatus.empty]
    if all(s.status in (SeatStatus.finished, SeatStatus.bust) for s in playing):
        state.phase = BlackjackPhase.finished
        state.message = "all_natural"
        return state

    state.active_seat_index = _next_active_seat(state, 0)
    return state


def apply_seat_action(
    state: MultiSeatBlackjackState,
    seat_index: int,
    action: BlackjackAction,
) -> MultiSeatBlackjackState:
    if state.phase != BlackjackPhase.player_turn:
        raise ValueError("not_player_turn")
    if state.active_seat_index != seat_index:
        raise ValueError("not_active_seat")

    seat = state.seats[seat_index]
    if seat.status != SeatStatus.acting:
        raise ValueError("seat_not_acting")

    if action == BlackjackAction.hit:
        if not state.deck:
            raise ValueError("empty_deck")
        seat.hand.append(state.deck.pop())
        if is_bust(seat.hand):
            seat.status = SeatStatus.bust
            seat.result = "loss"
        else:
            state.active_seat_index = seat_index
            return state
    elif action == BlackjackAction.stand:
        seat.status = SeatStatus.stood
    else:
        raise ValueError("unknown_action")

    next_idx = _next_active_seat(state, seat_index + 1)
    if next_idx is None:
        state.phase = BlackjackPhase.dealer_turn
        state.active_seat_index = None
    else:
        state.active_seat_index = next_idx
    return state


def _settle_seat_vs_dealer(seat: SeatState, dealer_hand: list[str], bet: float) -> None:
    tmp = type(
        "Tmp",
        (),
        {
            "player_hand": seat.hand,
            "dealer_hand": dealer_hand,
            "bet": bet,
            "message": None,
            "phase": BlackjackPhase.finished,
        },
    )()
    if seat.status == SeatStatus.bust:
        seat.result = "loss"
        seat.payout = 0.0
        return
    if seat.result == "win" and hand_value(seat.hand)[0] == 21 and len(seat.hand) == 2:
        seat.payout = bet + bet * 1.5
        return
    if seat.result == "draw":
        seat.payout = bet
        return
    if seat.result == "loss":
        seat.payout = 0.0
        return

    pv, _ = hand_value(seat.hand)
    dv, _ = hand_value(dealer_hand)
    if is_bust(dealer_hand):
        seat.result = "win"
        seat.payout = bet * 2.0
    elif pv > dv:
        seat.result = "win"
        seat.payout = bet * 2.0
    elif pv < dv:
        seat.result = "loss"
        seat.payout = 0.0
    else:
        seat.result = "draw"
        seat.payout = bet


def finish_dealer_and_settle(state: MultiSeatBlackjackState) -> MultiSeatBlackjackState:
    if state.phase == BlackjackPhase.dealer_turn:
        from app.engine.blackjack import BlackjackState

        st = BlackjackState(
            deck=list(state.deck),
            player_hand=["2C"],
            dealer_hand=list(state.dealer_hand),
            phase=BlackjackPhase.dealer_turn,
            bet=0.0,
        )
        play_dealer(st)
        state.deck = st.deck
        state.dealer_hand = st.dealer_hand
        state.phase = BlackjackPhase.finished
        if is_bust(state.dealer_hand):
            state.message = "dealer_bust"

    for seat in state.seats:
        if seat.status == SeatStatus.empty:
            continue
        if seat.status == SeatStatus.bust:
            seat.result = seat.result or "loss"
            seat.payout = 0.0
            continue
        if seat.status == SeatStatus.finished and seat.result and seat.payout > 0:
            continue
        _settle_seat_vs_dealer(seat, state.dealer_hand, seat.bet)

    human = state.human_seat()
    state.message = human.result or state.message
    return state


def advance_bot_turns(
    state: MultiSeatBlackjackState,
    policy,
    *,
    stop_at_human: bool = True,
) -> list[tuple[int, BlackjackAction]]:
    """Auto-play bot seats; returns list of (seat_index, action) for WS events."""
    actions: list[tuple[int, BlackjackAction]] = []
    while state.phase == BlackjackPhase.player_turn and state.active_seat_index is not None:
        idx = state.active_seat_index
        seat = state.seats[idx]
        if seat.is_human:
            if stop_at_human:
                break
            break
        action = policy.choose_action(seat.hand)
        actions.append((idx, action))
        apply_seat_action(state, idx, action)
    return actions


def advance_one_bot(
    state: MultiSeatBlackjackState,
    policy,
) -> tuple[int, BlackjackAction] | None:
    """Advance exactly ONE bot seat. Returns (seat_idx, action) or None if it's human's turn / done."""
    if state.phase != BlackjackPhase.player_turn or state.active_seat_index is None:
        return None
    seat = state.seats[state.active_seat_index]
    if seat.is_human:
        return None
    action = policy.choose_action(seat.hand)
    idx = state.active_seat_index
    apply_seat_action(state, idx, action)
    return idx, action


def dealer_draw_one(state: MultiSeatBlackjackState) -> bool:
    """Draw one card for the dealer (during dealer_turn). Returns True when dealer is done."""
    from app.engine.blackjack import hand_value as hv
    if state.phase != BlackjackPhase.dealer_turn:
        return True
    if not state.deck:
        return True
    dv, soft = hv(state.dealer_hand)
    # Dealer hits on soft 17 or less, stands on 17+ (hard or soft)
    if dv < 17 or (soft and dv == 17):
        state.dealer_hand.append(state.deck.pop())
        dv2, _ = hv(state.dealer_hand)
        if dv2 >= 17 or is_bust(state.dealer_hand):
            return True  # dealer done after this card
        return False
    return True  # dealer stands


def human_settle_result(state: MultiSeatBlackjackState) -> tuple[str, float]:
    human = state.human_seat()
    if human.result == "win":
        return "win", human.payout
    if human.result == "draw":
        return "draw", human.payout
    return "loss", 0.0
