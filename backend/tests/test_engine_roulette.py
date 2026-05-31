"""Unit tests for the pure European roulette engine (no DB/Redis)."""
import random

from app.engine.roulette import (
    BLACK_NUMBERS,
    PAYOUT_MULTIPLIER,
    RED_NUMBERS,
    BetType,
    RouletteBet,
    evaluate_bets,
    number_color,
    number_column,
    number_dozen,
    spin,
    total_payout,
    total_staked,
)


# ── Wheel layout ────────────────────────────────────────────────────────────
def test_color_layout_is_complete_and_disjoint():
    assert len(RED_NUMBERS) == 18
    assert len(BLACK_NUMBERS) == 18
    assert RED_NUMBERS.isdisjoint(BLACK_NUMBERS)
    # Every non-zero number 1..36 is exactly one colour.
    assert RED_NUMBERS | BLACK_NUMBERS == set(range(1, 37))


def test_number_color():
    assert number_color(0) == "green"
    for n in RED_NUMBERS:
        assert number_color(n) == "red"
    for n in BLACK_NUMBERS:
        assert number_color(n) == "black"


def test_number_dozen():
    assert number_dozen(0) is None
    assert number_dozen(1) == "1st"
    assert number_dozen(12) == "1st"
    assert number_dozen(13) == "2nd"
    assert number_dozen(24) == "2nd"
    assert number_dozen(25) == "3rd"
    assert number_dozen(36) == "3rd"


def test_number_column():
    assert number_column(0) is None
    assert number_column(1) == "1st"
    assert number_column(2) == "2nd"
    assert number_column(3) == "3rd"
    assert number_column(34) == "1st"
    assert number_column(35) == "2nd"
    assert number_column(36) == "3rd"


# ── Spin ────────────────────────────────────────────────────────────────────
def test_spin_in_range_and_deterministic():
    rng = random.Random(42)
    results = [spin(rng) for _ in range(1000)]
    assert all(0 <= r <= 36 for r in results)
    # Seeded RNG must be reproducible.
    assert [spin(random.Random(7)) for _ in range(5)] == [
        spin(random.Random(7)) for _ in range(5)
    ]


# ── Inside bets ─────────────────────────────────────────────────────────────
def test_straight_bet_pays_35_to_1():
    bet = RouletteBet(bet_type=BetType.straight, amount=10, number=17)
    # Win: stake + 35x net = 36x.
    assert total_payout(17, [bet]) == 360.0
    # Loss.
    assert total_payout(18, [bet]) == 0.0


def test_split_street_corner_match_number_set():
    for bt, nums in [
        (BetType.split, [1, 2]),
        (BetType.street, [1, 2, 3]),
        (BetType.corner, [1, 2, 4, 5]),
    ]:
        bet = RouletteBet(bet_type=bt, amount=10, numbers=nums)
        assert total_payout(nums[0], [bet]) == 10 * (PAYOUT_MULTIPLIER[bt] + 1)
        assert total_payout(36, [bet]) == 0.0


# ── Outside bets ────────────────────────────────────────────────────────────
def test_red_black_bet():
    red = RouletteBet(bet_type=BetType.red_black, amount=10, choice="red")
    assert total_payout(1, [red]) == 20.0  # 1 is red
    assert total_payout(2, [red]) == 0.0  # 2 is black
    assert total_payout(0, [red]) == 0.0  # green loses


def test_dozen_and_column_pay_2_to_1():
    dozen = RouletteBet(bet_type=BetType.dozen, amount=10, choice="2nd")
    assert total_payout(13, [dozen]) == 30.0
    assert total_payout(1, [dozen]) == 0.0
    column = RouletteBet(bet_type=BetType.column, amount=10, choice="1st")
    assert total_payout(1, [column]) == 30.0
    assert total_payout(2, [column]) == 0.0


def test_zero_loses_all_even_money_bets():
    bets = [
        RouletteBet(bet_type=BetType.red_black, amount=5, choice="red"),
        RouletteBet(bet_type=BetType.red_black, amount=5, choice="black"),
        RouletteBet(bet_type=BetType.odd_even, amount=5, choice="odd"),
        RouletteBet(bet_type=BetType.odd_even, amount=5, choice="even"),
        RouletteBet(bet_type=BetType.low_high, amount=5, choice="low"),
        RouletteBet(bet_type=BetType.low_high, amount=5, choice="high"),
    ]
    # The single zero is the house edge — every even-money bet loses on 0.
    assert total_payout(0, bets) == 0.0


def test_odd_even_and_low_high():
    odd = RouletteBet(bet_type=BetType.odd_even, amount=10, choice="odd")
    assert total_payout(3, [odd]) == 20.0
    assert total_payout(4, [odd]) == 0.0
    high = RouletteBet(bet_type=BetType.low_high, amount=10, choice="high")
    assert total_payout(19, [high]) == 20.0
    assert total_payout(18, [high]) == 0.0


# ── Aggregates ──────────────────────────────────────────────────────────────
def test_evaluate_bets_shape_and_total_staked():
    bets = [
        RouletteBet(bet_type=BetType.straight, amount=10, number=7),
        RouletteBet(bet_type=BetType.red_black, amount=20, choice="black"),
    ]
    rows = evaluate_bets(7, bets)
    assert [r["won"] for r in rows] == [True, False]
    assert rows[0]["payout"] == 360.0
    assert rows[1]["payout"] == 0.0
    assert total_staked(bets) == 30.0
    # total_payout must equal the sum of per-bet payouts.
    assert total_payout(7, bets) == sum(r["payout"] for r in rows)
