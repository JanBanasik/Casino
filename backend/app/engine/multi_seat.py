"""Multi-seat blackjack: shared deck and dealer, human + bot seats."""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass, field

from app.engine.blackjack import (
    BlackjackAction,
    BlackjackPhase,
    _card_rank,
    _fresh_deck,
    hand_value,
    is_bust,
    play_dealer,
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
    # Split state — populated after a SPLIT action (one split per seat, MVP).
    has_split: bool = False
    hands: list[list[str]] = field(default_factory=list)
    hand_bets: list[float] = field(default_factory=list)
    hand_statuses: list[SeatStatus] = field(default_factory=list)
    hand_results: list[str | None] = field(default_factory=list)
    hand_payouts: list[float] = field(default_factory=list)
    active_hand_index: int = 0


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
        seats_out = []
        for s in self.seats:
            if s.status == SeatStatus.empty:
                continue
            entry: dict = {
                "seat_index": s.seat_index,
                "display_name": s.display_name,
                "avatar_key": s.avatar_key,
                "is_human": s.is_human,
                "hand": list(_active_hand(s)),
                "bet": s.bet,
                "status": s.status.value,
                "result": s.result,
                "payout": s.payout,
            }
            if s.has_split:
                entry["has_split"] = True
                entry["hands"] = [list(h) for h in s.hands]
                entry["hand_bets"] = list(s.hand_bets)
                entry["active_hand_index"] = s.active_hand_index
                entry["hand_results"] = list(s.hand_results)
            seats_out.append(entry)
        return {
            "table_phase": table_phase,
            "phase": self.phase.value,
            "player_hand": list(_active_hand(human)),
            "player_hands": [list(h) for h in human.hands] if human.has_split else None,
            "active_hand_index": human.active_hand_index if human.has_split else None,
            "dealer_hand": dealer_visible,
            "dealer_hidden_count": max(0, len(self.dealer_hand) - len(dealer_visible)),
            "bet": human.bet,
            "message": self.message,
            "active_seat_index": self.active_seat_index,
            "human_seat_index": self.human_seat_index,
            "seats": seats_out,
        }


# ── Split helpers ─────────────────────────────────────────────────────────────


def _active_hand(seat: SeatState) -> list[str]:
    if seat.has_split and seat.hands:
        return seat.hands[seat.active_hand_index]
    return seat.hand


def _sync_active_hand(seat: SeatState) -> None:
    seat.hand = list(_active_hand(seat))


def _can_split(seat: SeatState) -> bool:
    if seat.has_split or seat.status != SeatStatus.acting:
        return False
    h = seat.hand
    if len(h) != 2:
        return False
    return _card_rank(h[0]) == _card_rank(h[1])


def _split_seat(seat: SeatState, state: MultiSeatBlackjackState) -> None:
    if not _can_split(seat):
        raise ValueError("split_not_allowed")
    if not state.deck:
        raise ValueError("empty_deck")
    c0, c1 = seat.hand[0], seat.hand[1]
    bet = seat.bet
    h0 = [c0, state.deck.pop()]
    h1 = [c1]
    seat.has_split = True
    seat.hands = [h0, h1]
    seat.hand_bets = [bet, bet]
    seat.hand_statuses = [SeatStatus.acting, SeatStatus.waiting]
    seat.hand_results = [None, None]
    seat.hand_payouts = [0.0, 0.0]
    seat.active_hand_index = 0
    _sync_active_hand(seat)
    if is_bust(h0):
        seat.hand_statuses[0] = SeatStatus.bust
        seat.hand_results[0] = "loss"


def _lock_current_split_hand(seat: SeatState, final_status: SeatStatus) -> None:
    idx = seat.active_hand_index
    seat.hand_statuses[idx] = final_status
    if final_status == SeatStatus.bust:
        seat.hand_results[idx] = "loss"
    elif final_status == SeatStatus.stood:
        seat.hand_results[idx] = None


def _advance_split_hand(seat: SeatState, state: MultiSeatBlackjackState) -> bool:
    """Deal to / activate the next split hand. Returns True if still on this seat."""
    if not seat.has_split:
        return False
    idx = seat.active_hand_index
    # Find next hand waiting for its second card / play.
    for j in range(idx + 1, len(seat.hands)):
        if seat.hand_statuses[j] == SeatStatus.waiting:
            if len(seat.hands[j]) == 1:
                seat.hands[j].append(state.deck.pop())
            seat.active_hand_index = j
            seat.hand_statuses[j] = SeatStatus.acting
            seat.status = SeatStatus.acting
            _sync_active_hand(seat)
            if is_bust(seat.hands[j]):
                seat.hand_statuses[j] = SeatStatus.bust
                seat.hand_results[j] = "loss"
                return _advance_split_hand(seat, state)
            return True
    # All split hands resolved for this seat.
    seat.status = SeatStatus.stood
    _sync_active_hand(seat)
    return False


def _seat_still_acting(seat: SeatState) -> bool:
    if not seat.has_split:
        return seat.status == SeatStatus.acting
    return any(s == SeatStatus.acting for s in seat.hand_statuses)


# ── Round helpers ─────────────────────────────────────────────────────────────


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


def _dealer_upcard(state: MultiSeatBlackjackState) -> str | None:
    return state.dealer_hand[0] if state.dealer_hand else None


def _visible_table_cards(state: MultiSeatBlackjackState) -> list[str]:
    cards: list[str] = []
    for s in state.seats:
        if s.status == SeatStatus.empty:
            continue
        if s.has_split:
            for h in s.hands:
                cards.extend(h)
        else:
            cards.extend(s.hand)
    up = _dealer_upcard(state)
    if up is not None:
        cards.append(up)
    return cards


def _next_active_seat(state: MultiSeatBlackjackState, start: int) -> int | None:
    for i in range(start, len(state.seats)):
        s = state.seats[i]
        if s.status == SeatStatus.empty:
            continue
        if _seat_still_acting(s):
            return i
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
    if not _seat_still_acting(seat):
        raise ValueError("seat_not_acting")

    active = _active_hand(seat)

    if action == BlackjackAction.split:
        _split_seat(seat, state)
        if seat.hand_statuses[0] == SeatStatus.bust:
            if _advance_split_hand(seat, state):
                state.active_seat_index = seat_index
                return state
        else:
            state.active_seat_index = seat_index
            return state

    elif action == BlackjackAction.hit:
        if not state.deck:
            raise ValueError("empty_deck")
        active.append(state.deck.pop())
        _sync_active_hand(seat)
        if is_bust(active):
            if seat.has_split:
                _lock_current_split_hand(seat, SeatStatus.bust)
                if _advance_split_hand(seat, state):
                    state.active_seat_index = seat_index
                    return state
            else:
                seat.status = SeatStatus.bust
                seat.result = "loss"
        else:
            state.active_seat_index = seat_index
            return state

    elif action == BlackjackAction.stand:
        if seat.has_split:
            _lock_current_split_hand(seat, SeatStatus.stood)
            if _advance_split_hand(seat, state):
                state.active_seat_index = seat_index
                return state
        else:
            seat.status = SeatStatus.stood

    elif action == BlackjackAction.double:
        if len(active) != 2:
            raise ValueError("double_only_initial")
        if not state.deck:
            raise ValueError("empty_deck")
        if seat.has_split:
            idx = seat.active_hand_index
            seat.hand_bets[idx] *= 2
            seat.bet = seat.hand_bets[idx]
        else:
            seat.bet *= 2
        active.append(state.deck.pop())
        _sync_active_hand(seat)
        if is_bust(active):
            final = SeatStatus.bust
            if seat.has_split:
                _lock_current_split_hand(seat, final)
                if _advance_split_hand(seat, state):
                    state.active_seat_index = seat_index
                    return state
            else:
                seat.status = final
                seat.result = "loss"
        elif seat.has_split:
            _lock_current_split_hand(seat, SeatStatus.stood)
            if _advance_split_hand(seat, state):
                state.active_seat_index = seat_index
                return state
        else:
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


def _settle_hand_vs_dealer(
    hand: list[str],
    dealer_hand: list[str],
    bet: float,
    *,
    pre_result: str | None = None,
) -> tuple[str, float]:
    if pre_result == "loss":
        return "loss", 0.0
    pv, _ = hand_value(hand)
    if pv == 21 and len(hand) == 2 and pre_result != "draw":
        dv, _ = hand_value(dealer_hand)
        if dv == 21 and len(dealer_hand) == 2:
            return "draw", bet
        return "win", bet + bet * 1.5
    if pre_result == "draw":
        return "draw", bet
    dv, _ = hand_value(dealer_hand)
    if is_bust(dealer_hand):
        return "win", bet * 2.0
    if pv > dv:
        return "win", bet * 2.0
    if pv < dv:
        return "loss", 0.0
    return "draw", bet


def _settle_seat_vs_dealer(seat: SeatState, dealer_hand: list[str]) -> None:
    if seat.has_split:
        total_payout = 0.0
        results: list[str] = []
        for i, hand in enumerate(seat.hands):
            if seat.hand_statuses[i] == SeatStatus.bust:
                res, pay = "loss", 0.0
            else:
                res, pay = _settle_hand_vs_dealer(
                    hand, dealer_hand, seat.hand_bets[i],
                    pre_result=seat.hand_results[i],
                )
            seat.hand_results[i] = res
            seat.hand_payouts[i] = pay
            total_payout += pay
            results.append(res)
        seat.payout = total_payout
        seat.bet = sum(seat.hand_bets)
        wins = sum(1 for r in results if r == "win")
        losses = sum(1 for r in results if r == "loss")
        if wins and not losses:
            seat.result = "win"
        elif losses and not wins:
            seat.result = "loss"
        elif all(r == "draw" for r in results):
            seat.result = "draw"
        else:
            seat.result = "win" if total_payout > seat.bet else "loss"
        return

    bet = seat.bet
    if seat.status == SeatStatus.bust:
        seat.result = "loss"
        seat.payout = 0.0
        return
    res, pay = _settle_hand_vs_dealer(
        seat.hand, dealer_hand, bet, pre_result=seat.result
    )
    seat.result = res
    seat.payout = pay


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
        if seat.status == SeatStatus.finished and seat.result and seat.payout > 0:
            continue
        _settle_seat_vs_dealer(seat, state.dealer_hand)

    human = state.human_seat()
    state.message = human.result or state.message
    return state


def advance_bot_turns(
    state: MultiSeatBlackjackState,
    policy,
    *,
    stop_at_human: bool = True,
) -> list[tuple[int, BlackjackAction]]:
    actions: list[tuple[int, BlackjackAction]] = []
    while state.phase == BlackjackPhase.player_turn and state.active_seat_index is not None:
        idx = state.active_seat_index
        seat = state.seats[idx]
        if seat.is_human:
            if stop_at_human:
                break
            break
        action = policy.choose_action(
            _active_hand(seat),
            dealer_upcard=_dealer_upcard(state),
            visible_cards=_visible_table_cards(state),
        )
        actions.append((idx, action))
        apply_seat_action(state, idx, action)
    return actions


def advance_one_bot(
    state: MultiSeatBlackjackState,
    policy,
) -> tuple[int, BlackjackAction] | None:
    if state.phase != BlackjackPhase.player_turn or state.active_seat_index is None:
        return None
    seat = state.seats[state.active_seat_index]
    if seat.is_human:
        return None
    action = policy.choose_action(
        _active_hand(seat),
        dealer_upcard=_dealer_upcard(state),
        visible_cards=_visible_table_cards(state),
    )
    idx = state.active_seat_index
    apply_seat_action(state, idx, action)
    return idx, action


def dealer_draw_one(state: MultiSeatBlackjackState) -> bool:
    from app.engine.blackjack import hand_value as hv
    if state.phase != BlackjackPhase.dealer_turn:
        return True
    if not state.deck:
        return True
    dv, soft = hv(state.dealer_hand)
    if dv < 17 or (soft and dv == 17):
        state.dealer_hand.append(state.deck.pop())
        dv2, _ = hv(state.dealer_hand)
        if dv2 >= 17 or is_bust(state.dealer_hand):
            return True
        return False
    return True


def human_settle_result(state: MultiSeatBlackjackState) -> tuple[str, float]:
    human = state.human_seat()
    if human.has_split:
        credit = sum(human.hand_payouts)
        total_bet = sum(human.hand_bets)
        if credit > total_bet:
            return "win", credit
        if credit < total_bet:
            return "loss", credit
        return "draw", credit
    if human.result == "win":
        return "win", human.payout
    if human.result == "draw":
        return "draw", human.payout
    return "loss", 0.0
