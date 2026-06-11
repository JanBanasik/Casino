"""Texas Hold'em Poker Engine — 1 human + up to 5 bots."""
from __future__ import annotations

import enum
import itertools
import random
from dataclasses import dataclass, field

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["C", "D", "H", "S"]
RANK_VALUE: dict[str, int] = {r: i for i, r in enumerate(RANKS)}  # 2=0 … A=12

BOT_PROFILES = [
    ("Alex_K", "a1"),
    ("Marta99", "m2"),
    ("JanekW", "j3"),
    ("Ola_P", "o4"),
    ("Kris77", "k5"),
]


# ── Enums ────────────────────────────────────────────────────────────────────

class PokerPhase(str, enum.Enum):
    waiting = "waiting"
    pre_flop = "pre_flop"
    flop = "flop"
    turn = "turn"
    river = "river"
    showdown = "showdown"
    finished = "finished"


class PokerAction(str, enum.Enum):
    fold = "FOLD"
    check = "CHECK"
    call = "CALL"
    raise_ = "RAISE"


class SeatStatus(str, enum.Enum):
    empty = "empty"
    active = "active"
    folded = "folded"
    all_in = "all_in"
    finished = "finished"


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class PokerSeat:
    seat_index: int
    display_name: str
    avatar_key: str
    is_human: bool
    occupant_id: str
    hole_cards: list[str] = field(default_factory=list)
    chips: float = 1000.0
    bet_total: float = 0.0   # total committed to pot in this hand
    bet_phase: float = 0.0   # committed in current betting round
    status: SeatStatus = SeatStatus.active
    result: str | None = None
    payout: float = 0.0
    has_acted: bool = False  # whether seat has acted in the current betting round


@dataclass
class PokerState:
    deck: list[str]
    community_cards: list[str]
    seats: list[PokerSeat]
    phase: PokerPhase
    pot: float
    current_bet: float     # highest bet to match in this round
    min_raise: float
    active_seat_index: int | None
    dealer_seat_index: int
    human_seat_index: int
    small_blind: float
    big_blind: float
    message: str | None

    def human_seat(self) -> PokerSeat:
        return self.seats[self.human_seat_index]

    def to_public_dict(self, *, table_phase: str = "playing") -> dict:
        hide_phase = self.phase not in (PokerPhase.showdown, PokerPhase.finished)
        seats_out = []
        for s in self.seats:
            if s.status == SeatStatus.empty:
                continue
            show_cards = s.is_human or not hide_phase
            seats_out.append({
                "seat_index": s.seat_index,
                "display_name": s.display_name,
                "avatar_key": s.avatar_key,
                "is_human": s.is_human,
                "hole_cards": list(s.hole_cards)
                if show_cards
                else (["??", "??"] if s.hole_cards else []),
                "chips": s.chips,
                "bet_phase": s.bet_phase,
                "bet_total": s.bet_total,
                "status": s.status.value,
                "result": s.result,
                "payout": s.payout,
            })
        human = self.human_seat()
        return {
            "table_phase": table_phase,
            "phase": self.phase.value,
            "community_cards": list(self.community_cards),
            "hole_cards": list(human.hole_cards),
            "pot": self.pot,
            "current_bet": self.current_bet,
            "min_raise": self.min_raise,
            "active_seat_index": self.active_seat_index,
            "dealer_seat_index": self.dealer_seat_index,
            "human_seat_index": self.human_seat_index,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "message": self.message,
            "seats": seats_out,
        }


# ── Deck ──────────────────────────────────────────────────────────────────────

def _fresh_deck(rng: random.Random) -> list[str]:
    deck = [f"{r}{s}" for s in SUITS for r in RANKS]
    rng.shuffle(deck)
    return deck


def _card_rank(card: str) -> str:
    return card[:-1]


def _card_suit(card: str) -> str:
    return card[-1]


# ── Hand evaluation ───────────────────────────────────────────────────────────

def _rank_val(card: str) -> int:
    return RANK_VALUE[_card_rank(card)]


def hand_rank(cards: list[str]) -> tuple:
    """Return a comparable tuple for a 5-card hand. Higher = better."""
    assert len(cards) == 5
    from collections import Counter

    vals = sorted([_rank_val(c) for c in cards], reverse=True)
    suits = [_card_suit(c) for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight = (vals[0] - vals[4] == 4 and len(set(vals)) == 5)
    # Wheel: A-2-3-4-5
    wheel = vals == [12, 3, 2, 1, 0]
    if wheel:
        is_straight = True
        vals = [3, 2, 1, 0, -1]  # 5-high straight

    counts = Counter(vals)
    count_pattern = sorted(counts.values(), reverse=True)
    # Tie-break order: cards that form the bigger group first (pairs/trips/quads),
    # then by rank — so a pair of Kings always beats a pair of 2s regardless of
    # kickers, and kickers are compared in descending order.
    ordered = sorted(vals, key=lambda v: (counts[v], v), reverse=True)

    if is_straight and is_flush:
        return (8, ordered)       # Straight flush
    if count_pattern[0] == 4:
        return (7, ordered)       # Four of a kind
    if count_pattern[:2] == [3, 2]:
        return (6, ordered)       # Full house
    if is_flush:
        return (5, ordered)       # Flush
    if is_straight:
        return (4, ordered)       # Straight
    if count_pattern[0] == 3:
        return (3, ordered)       # Three of a kind
    if count_pattern[:2] == [2, 2]:
        return (2, ordered)       # Two pair
    if count_pattern[0] == 2:
        return (1, ordered)       # One pair
    return (0, ordered)           # High card


HAND_NAMES = {
    8: "Poker",
    7: "Kareta",
    6: "Full",
    5: "Kolor",
    4: "Strit",
    3: "Trójka",
    2: "Dwie pary",
    1: "Para",
    0: "Wysoka karta",
}


def best_five_from_seven(hole: list[str], community: list[str]) -> tuple[tuple, list[str]]:
    """Return (hand_rank_tuple, best_5_cards) from up to 7 cards."""
    all_cards = hole + community
    best: tuple | None = None
    best_hand: list[str] = []
    for combo in itertools.combinations(all_cards, min(5, len(all_cards))):
        r = hand_rank(list(combo))
        if best is None or r > best:
            best = r
            best_hand = list(combo)
    return best or (0, []), best_hand


# ── Seat helpers ──────────────────────────────────────────────────────────────

def _build_seats(
    *,
    human_name: str,
    human_id: str,
    human_seat_index: int,
    bot_count: int,
    buy_in: float,
) -> list[PokerSeat]:
    human_seat_index = max(0, min(5, human_seat_index))
    bot_count = max(0, min(bot_count, len(BOT_PROFILES)))
    seats: list[PokerSeat] = []
    bot_idx = 0
    bots_left = bot_count
    for i in range(6):
        if i == human_seat_index:
            seats.append(PokerSeat(
                seat_index=i,
                display_name=human_name,
                avatar_key="you",
                is_human=True,
                occupant_id=human_id,
                chips=buy_in,
                status=SeatStatus.active,
            ))
        elif bots_left > 0:
            name, key = BOT_PROFILES[bot_idx % len(BOT_PROFILES)]
            bot_idx += 1
            bots_left -= 1
            seats.append(PokerSeat(
                seat_index=i,
                display_name=name,
                avatar_key=key,
                is_human=False,
                occupant_id=f"bot_{key}",
                chips=buy_in,
                status=SeatStatus.active,
            ))
        else:
            seats.append(PokerSeat(
                seat_index=i,
                display_name="",
                avatar_key="",
                is_human=False,
                occupant_id="",
                status=SeatStatus.empty,
            ))
    return seats


def _active_seats(state: PokerState) -> list[PokerSeat]:
    return [s for s in state.seats if s.status in (SeatStatus.active, SeatStatus.all_in)]


def _next_active_after(state: PokerState, start: int) -> int | None:
    n = len(state.seats)
    for offset in range(1, n + 1):
        i = (start + offset) % n
        if state.seats[i].status == SeatStatus.active:
            return i
    return None


# ── Round init ────────────────────────────────────────────────────────────────

def new_poker_round(
    *,
    human_name: str,
    human_id: str,
    human_seat_index: int = 0,
    bot_count: int = 2,
    buy_in: float = 1000.0,
    small_blind: float = 10.0,
    big_blind: float = 20.0,
    dealer_seat_index: int | None = None,
    rng: random.Random | None = None,
) -> PokerState:
    rng = rng or random.Random()
    bot_count = max(1, min(bot_count, len(BOT_PROFILES)))  # at least 1 bot
    seats = _build_seats(
        human_name=human_name,
        human_id=human_id,
        human_seat_index=human_seat_index,
        bot_count=bot_count,
        buy_in=buy_in,
    )
    active = [s for s in seats if s.status != SeatStatus.empty]
    if len(active) < 2:
        raise ValueError("need_at_least_2_players")

    # Dealer position (rotate each hand — caller tracks this)
    if dealer_seat_index is None:
        non_empty = [s.seat_index for s in seats if s.status != SeatStatus.empty]
        dealer_seat_index = rng.choice(non_empty)

    deck = _fresh_deck(rng)

    # Deal hole cards
    for seat in seats:
        if seat.status != SeatStatus.empty:
            seat.hole_cards = [deck.pop(), deck.pop()]

    # Post blinds
    active_indices = [s.seat_index for s in seats if s.status != SeatStatus.empty]
    d_pos = active_indices.index(dealer_seat_index) if dealer_seat_index in active_indices else 0
    sb_idx = active_indices[(d_pos + 1) % len(active_indices)]
    bb_idx = active_indices[(d_pos + 2) % len(active_indices)]
    first_to_act_idx = active_indices[(d_pos + 3) % len(active_indices)]

    sb_seat = seats[sb_idx]
    bb_seat = seats[bb_idx]

    sb_amount = min(small_blind, sb_seat.chips)
    bb_amount = min(big_blind, bb_seat.chips)

    sb_seat.chips -= sb_amount
    sb_seat.bet_phase = sb_amount
    sb_seat.bet_total = sb_amount
    if sb_seat.chips == 0:
        sb_seat.status = SeatStatus.all_in

    bb_seat.chips -= bb_amount
    bb_seat.bet_phase = bb_amount
    bb_seat.bet_total = bb_amount
    if bb_seat.chips == 0:
        bb_seat.status = SeatStatus.all_in

    pot = sb_amount + bb_amount

    state = PokerState(
        deck=deck,
        community_cards=[],
        seats=seats,
        phase=PokerPhase.pre_flop,
        pot=pot,
        current_bet=bb_amount,
        min_raise=bb_amount,
        active_seat_index=first_to_act_idx,
        dealer_seat_index=dealer_seat_index,
        human_seat_index=human_seat_index,
        small_blind=small_blind,
        big_blind=big_blind,
        message=None,
    )
    return state


# ── Action application ────────────────────────────────────────────────────────

def _reset_phase_bets(state: PokerState) -> None:
    for s in state.seats:
        s.bet_phase = 0.0
        s.has_acted = False


def _is_betting_complete(state: PokerState) -> bool:
    """True when all active (non-all-in) players have acted and bets are equal."""
    active = [s for s in state.seats if s.status == SeatStatus.active]
    if not active:
        return True
    acted = all(s.has_acted for s in active)
    bets_equal = len(set(s.bet_phase for s in active)) <= 1
    return acted and bets_equal


def _advance_phase(state: PokerState) -> None:
    """Move to next community card phase or showdown."""
    _reset_phase_bets(state)
    # If only 1 player left (others folded) → skip to showdown
    if len([s for s in state.seats if s.status == SeatStatus.active]) <= 1:
        # run out the board if needed
        while len(state.community_cards) < 5:
            state.community_cards.append(state.deck.pop())
        state.phase = PokerPhase.showdown
        _settle(state)
        return

    if state.phase == PokerPhase.pre_flop:
        state.community_cards += [state.deck.pop(), state.deck.pop(), state.deck.pop()]
        state.phase = PokerPhase.flop
    elif state.phase == PokerPhase.flop:
        state.community_cards.append(state.deck.pop())
        state.phase = PokerPhase.turn
    elif state.phase == PokerPhase.turn:
        state.community_cards.append(state.deck.pop())
        state.phase = PokerPhase.river
    elif state.phase == PokerPhase.river:
        state.phase = PokerPhase.showdown
        _settle(state)
        return

    state.current_bet = 0.0
    state.min_raise = state.big_blind
    # First to act post-flop: first active seat after dealer
    nxt = _next_active_after(state, state.dealer_seat_index)
    state.active_seat_index = nxt


def apply_poker_action(
    state: PokerState,
    seat_index: int,
    action: PokerAction,
    raise_amount: float = 0.0,
) -> PokerState:
    if state.phase in (PokerPhase.showdown, PokerPhase.finished):
        raise ValueError("hand_already_over")
    if state.active_seat_index != seat_index:
        raise ValueError("not_your_turn")

    seat = state.seats[seat_index]
    if seat.status != SeatStatus.active:
        raise ValueError("seat_not_active")

    if action == PokerAction.fold:
        seat.status = SeatStatus.folded
        seat.has_acted = True

    elif action == PokerAction.check:
        if seat.bet_phase < state.current_bet:
            raise ValueError("cannot_check_must_call")
        seat.has_acted = True

    elif action == PokerAction.call:
        call_amount = min(state.current_bet - seat.bet_phase, seat.chips)
        seat.chips -= call_amount
        seat.bet_phase += call_amount
        seat.bet_total += call_amount
        state.pot += call_amount
        if seat.chips == 0:
            seat.status = SeatStatus.all_in
        seat.has_acted = True

    elif action == PokerAction.raise_:
        total_raise = max(raise_amount, state.current_bet + state.min_raise)
        to_add = min(total_raise - seat.bet_phase, seat.chips)
        actual_total = seat.bet_phase + to_add
        old_bet = state.current_bet
        state.current_bet = actual_total
        state.min_raise = max(state.min_raise, actual_total - old_bet)
        seat.chips -= to_add
        seat.bet_phase = actual_total
        seat.bet_total += to_add
        state.pot += to_add
        if seat.chips == 0:
            seat.status = SeatStatus.all_in
        seat.has_acted = True
        # Others need to act again
        for s in state.seats:
            if s.seat_index != seat_index and s.status == SeatStatus.active:
                s.has_acted = False

    else:
        raise ValueError("unknown_action")

    # Check if betting round is complete
    if _is_betting_complete(state):
        _advance_phase(state)
    else:
        nxt = _next_active_after(state, seat_index)
        state.active_seat_index = nxt

    return state


# ── Settlement ────────────────────────────────────────────────────────────────

def _settle(state: PokerState) -> None:
    state.phase = PokerPhase.showdown
    contenders = [s for s in state.seats if s.status in (SeatStatus.active, SeatStatus.all_in)]

    if len(contenders) == 1:
        winner = contenders[0]
        winner.result = "win"
        winner.payout = state.pot
        winner.chips += state.pot
        for s in state.seats:
            if s != winner and s.status not in (SeatStatus.empty,):
                s.result = s.result or "loss"
        state.message = f"win:{winner.display_name}"
        state.phase = PokerPhase.finished
        return

    # Evaluate all hands
    scored: list[tuple[tuple, PokerSeat]] = []
    for s in contenders:
        rank, _ = best_five_from_seven(s.hole_cards, state.community_cards)
        scored.append((rank, s))
    scored.sort(key=lambda x: x[0], reverse=True)

    best_rank = scored[0][0]
    winners = [s for rank, s in scored if rank == best_rank]

    split_amount = state.pot / len(winners)
    for s in state.seats:
        if s.status == SeatStatus.empty:
            continue
        if s in winners:
            s.result = "win"
            s.payout = split_amount
            s.chips += split_amount
        elif s.status == SeatStatus.folded:
            s.result = "loss"
        else:
            s.result = "loss"

    hand_name = HAND_NAMES.get(best_rank[0], "")
    winner_names = ", ".join(w.display_name for w in winners)
    state.message = f"win:{winner_names}:{hand_name}"
    state.phase = PokerPhase.finished


# ── Bot policy ────────────────────────────────────────────────────────────────

class SimplePokerBotPolicy:
    """Heuristic bot: pre-flop uses hole card strength; post-flop uses hand rank."""

    name = "heuristic_poker"

    def choose_action(
        self,
        seat: PokerSeat,
        state: PokerState,
        rng: random.Random | None = None,
    ) -> tuple[PokerAction, float]:
        rng = rng or random.Random()
        hole = seat.hole_cards
        community = state.community_cards
        call_amount = state.current_bet - seat.bet_phase

        # Can we check?
        can_check = call_amount <= 0

        # Estimate hand strength 0-1
        strength = _hand_strength(hole, community)

        if strength < 0.2:
            if can_check:
                return PokerAction.check, 0.0
            return PokerAction.fold, 0.0
        elif strength < 0.45:
            if can_check:
                return PokerAction.check, 0.0
            if call_amount <= seat.chips * 0.15:
                return PokerAction.call, 0.0
            return PokerAction.fold, 0.0
        elif strength < 0.65:
            if can_check:
                # Sometimes bet
                if rng.random() < 0.3:
                    amt = min(state.big_blind * 2, seat.chips)
                    return PokerAction.raise_, state.current_bet + amt
                return PokerAction.check, 0.0
            return PokerAction.call, 0.0
        else:
            # Strong hand — raise or call
            if rng.random() < 0.5:
                amt = min(state.current_bet + state.big_blind * 3, seat.chips)
                return PokerAction.raise_, amt
            if not can_check:
                return PokerAction.call, 0.0
            return PokerAction.check, 0.0


def _hand_strength(hole: list[str], community: list[str]) -> float:
    """Rough 0-1 hand strength estimate."""
    if not community:
        # Pre-flop: use hole card ranks
        vals = sorted([RANK_VALUE[_card_rank(c)] for c in hole], reverse=True)
        # Pair
        if vals[0] == vals[1]:
            return 0.55 + vals[0] * 0.03
        # High cards
        return (vals[0] + vals[1] * 0.5) / 25.0
    rank, _ = best_five_from_seven(hole, community)
    # Map hand category 0-8 to 0-1
    return (rank[0] * 12 + rank[1][0] if rank[1] else rank[0] * 12) / 110.0


def advance_poker_bots(
    state: PokerState,
    policy: SimplePokerBotPolicy | None = None,
    *,
    rng: random.Random | None = None,
) -> list[tuple[int, PokerAction, float]]:
    """Play all consecutive bot turns until human or phase/hand end.
    Returns list of (seat_index, action, raise_amount) events."""
    policy = policy or SimplePokerBotPolicy()
    rng = rng or random.Random()
    events: list[tuple[int, PokerAction, float]] = []
    max_iters = 50
    i = 0
    while state.phase not in (PokerPhase.showdown, PokerPhase.finished) and i < max_iters:
        i += 1
        idx = state.active_seat_index
        if idx is None:
            break
        seat = state.seats[idx]
        if seat.is_human:
            break
        if seat.status != SeatStatus.active:
            # skip to next
            nxt = _next_active_after(state, idx)
            state.active_seat_index = nxt
            continue
        action, amount = policy.choose_action(seat, state, rng)
        apply_poker_action(state, idx, action, amount)
        events.append((idx, action, amount))
    return events
