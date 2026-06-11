"""Unit tests for the pure Texas Hold'em engine (no DB/Redis)."""
import random

from app.engine.poker import (
    PokerAction,
    PokerPhase,
    SeatStatus,
    SimplePokerBotPolicy,
    _hand_strength,
    apply_poker_action,
    best_five_from_seven,
    hand_rank,
    new_poker_round,
)


# ── Hand ranking ────────────────────────────────────────────────────────────
def test_hand_rank_categories():
    cat = lambda cards: hand_rank(cards)[0]  # noqa: E731
    assert cat(["6H", "7H", "8H", "9H", "10H"]) == 8  # straight flush
    assert cat(["9C", "9D", "9H", "9S", "2C"]) == 7  # four of a kind
    assert cat(["9C", "9D", "9H", "2C", "2D"]) == 6  # full house
    assert cat(["2H", "5H", "7H", "9H", "JH"]) == 5  # flush
    assert cat(["6H", "7D", "8C", "9S", "10H"]) == 4  # straight
    assert cat(["9C", "9D", "9H", "2C", "5D"]) == 3  # three of a kind
    assert cat(["9C", "9D", "2H", "2C", "5D"]) == 2  # two pair
    assert cat(["9C", "9D", "2H", "3C", "5D"]) == 1  # one pair
    assert cat(["2C", "5D", "7H", "9S", "JC"]) == 0  # high card


def test_wheel_straight_is_five_high():
    rank = hand_rank(["AH", "2D", "3C", "4S", "5H"])
    assert rank[0] == 4  # straight
    # A-2-3-4-5 ranks as five-high, below 6-high straight.
    assert rank < hand_rank(["2H", "3D", "4C", "5S", "6H"])


def test_hand_rank_strict_ordering():
    ladder = [
        ["2C", "5D", "7H", "9S", "JC"],   # high card
        ["9C", "9D", "2H", "3C", "5D"],   # pair
        ["9C", "9D", "2H", "2C", "5D"],   # two pair
        ["9C", "9D", "9H", "2C", "5D"],   # trips
        ["6H", "7D", "8C", "9S", "10H"],  # straight
        ["2H", "5H", "7H", "9H", "JH"],   # flush
        ["9C", "9D", "9H", "2C", "2D"],   # full house
        ["9C", "9D", "9H", "9S", "2C"],   # quads
        ["6H", "7H", "8H", "9H", "10H"],  # straight flush
    ]
    ranks = [hand_rank(h) for h in ladder]
    assert ranks == sorted(ranks)
    # Categories ascend 0..8, one per rung — strictly increasing.
    categories = [r[0] for r in ranks]
    assert categories == list(range(9))


def test_kicker_ordering_pairs_and_kickers():
    # A higher pair beats a lower pair regardless of kickers.
    pair_kings = hand_rank(["KC", "KD", "5C", "3C", "2C"])
    pair_deuces_ace = hand_rank(["2C", "2D", "AC", "KH", "QH"])
    assert pair_kings > pair_deuces_ace

    # Same pair → higher kicker wins.
    aces_king = hand_rank(["AC", "AD", "KC", "5C", "2C"])
    aces_queen = hand_rank(["AS", "AH", "QC", "5D", "2D"])
    assert aces_king > aces_queen

    # Two pair → top pair decides, then second pair, then kicker.
    kk_qq = hand_rank(["KC", "KD", "QC", "QD", "2C"])
    kk_jj = hand_rank(["KS", "KH", "JC", "JD", "AC"])
    assert kk_qq > kk_jj

    # Full house ranked by the trips, not the pair.
    nines_full = hand_rank(["9C", "9D", "9H", "2C", "2D"])
    eights_full_aces = hand_rank(["8C", "8D", "8H", "AC", "AD"])
    assert nines_full > eights_full_aces


def test_best_five_from_seven_picks_full_house():
    rank, best = best_five_from_seven(
        ["AH", "AD"], ["AC", "KD", "KS", "2C", "7H"]
    )
    assert rank[0] == 6  # aces full of kings
    assert len(best) == 5


# ── Round init ──────────────────────────────────────────────────────────────
def test_new_round_posts_blinds_and_deals():
    state = new_poker_round(
        human_name="Me", human_id="u1", bot_count=2,
        small_blind=10, big_blind=20, rng=random.Random(1),
    )
    assert state.phase == PokerPhase.pre_flop
    occupied = [s for s in state.seats if s.status != SeatStatus.empty]
    assert len(occupied) == 3  # human + 2 bots
    assert all(len(s.hole_cards) == 2 for s in occupied)
    # Pot equals the two blinds; current bet is the big blind.
    assert state.pot == 30
    assert state.current_bet == 20


# ── Full hand flow ──────────────────────────────────────────────────────────
def _play_to_completion(state, rng, max_actions=400):
    policy = SimplePokerBotPolicy()
    for _ in range(max_actions):
        if state.phase in (PokerPhase.showdown, PokerPhase.finished):
            return
        idx = state.active_seat_index
        if idx is None:
            return
        seat = state.seats[idx]
        if seat.is_human:
            call_amount = state.current_bet - seat.bet_phase
            action = PokerAction.call if call_amount > 0 else PokerAction.check
            apply_poker_action(state, idx, action)
        else:
            act, amt = policy.choose_action(seat, state, rng)
            apply_poker_action(state, idx, act, amt)
    raise AssertionError("hand did not terminate")


def test_full_hand_terminates_and_conserves_chips():
    buy_in = 1000.0
    for seed in range(20):
        rng = random.Random(seed)
        state = new_poker_round(
            human_name="Me", human_id="u1", bot_count=2, buy_in=buy_in,
            small_blind=10, big_blind=20, rng=rng,
        )
        occupied = [s for s in state.seats if s.status != SeatStatus.empty]
        _play_to_completion(state, rng)

        assert state.phase == PokerPhase.finished
        # Chips are conserved: the pot is redistributed, nothing created/destroyed.
        total_chips = sum(s.chips for s in occupied)
        assert round(total_chips, 6) == round(len(occupied) * buy_in, 6)
        # Exactly the winner(s) are flagged as win.
        assert any(s.result == "win" for s in occupied)


def test_cannot_act_out_of_turn():
    state = new_poker_round(
        human_name="Me", human_id="u1", bot_count=1, rng=random.Random(3)
    )
    wrong_seat = next(
        s.seat_index for s in state.seats
        if s.status != SeatStatus.empty and s.seat_index != state.active_seat_index
    )
    try:
        apply_poker_action(state, wrong_seat, PokerAction.check)
        raise AssertionError("expected not_your_turn")
    except ValueError as e:
        assert str(e) == "not_your_turn"


# ── Hand strength heuristic ─────────────────────────────────────────────────
def test_hand_strength_preflop_pair_beats_junk():
    pocket_aces = _hand_strength(["AH", "AD"], [])
    junk = _hand_strength(["2C", "7D"], [])
    assert pocket_aces > junk
    assert 0.0 <= junk < pocket_aces <= 1.0
