"""European Roulette Engine — single zero, numbers 0-36."""
from __future__ import annotations

import enum
import random
from dataclasses import dataclass

# European roulette colour layout
RED_NUMBERS: frozenset[int] = frozenset(
    {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
)
BLACK_NUMBERS: frozenset[int] = frozenset(
    {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
)

# Physical wheel order (European wheel sequence)
WHEEL_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26,
]


def number_color(n: int) -> str:
    if n == 0:
        return "green"
    return "red" if n in RED_NUMBERS else "black"


def number_dozen(n: int) -> str | None:
    if n == 0:
        return None
    if n <= 12:
        return "1st"
    if n <= 24:
        return "2nd"
    return "3rd"


def number_column(n: int) -> str | None:
    if n == 0:
        return None
    col = ((n - 1) % 3) + 1
    return {1: "1st", 2: "2nd", 3: "3rd"}[col]


class BetType(str, enum.Enum):
    straight = "straight"      # single number — pays 35:1
    split = "split"            # two adjacent numbers — pays 17:1
    street = "street"          # three numbers in a row — pays 11:1
    corner = "corner"          # four numbers — pays 8:1
    dozen = "dozen"            # 1st/2nd/3rd dozen — pays 2:1
    column = "column"          # 1st/2nd/3rd column — pays 2:1
    red_black = "red_black"    # red or black — pays 1:1
    odd_even = "odd_even"      # odd or even — pays 1:1
    low_high = "low_high"      # 1-18 or 19-36 — pays 1:1


# Payout multipliers (net, excluding original stake)
PAYOUT_MULTIPLIER: dict[BetType, int] = {
    BetType.straight: 35,
    BetType.split: 17,
    BetType.street: 11,
    BetType.corner: 8,
    BetType.dozen: 2,
    BetType.column: 2,
    BetType.red_black: 1,
    BetType.odd_even: 1,
    BetType.low_high: 1,
}


@dataclass
class RouletteBet:
    bet_type: BetType
    amount: float
    number: int | None = None          # for straight
    numbers: list[int] | None = None   # for split/street/corner
    # "red"/"black", "odd"/"even", "low"/"high", "1st"/"2nd"/"3rd"
    choice: str | None = None


def spin(rng: random.Random | None = None) -> int:
    rng = rng or random.Random()
    return rng.randint(0, 36)


def _bet_wins(result: int, bet: RouletteBet) -> bool:
    bt = bet.bet_type
    if bt == BetType.straight:
        return result == bet.number
    if bt == BetType.split:
        return result in (bet.numbers or [])
    if bt == BetType.street:
        return result in (bet.numbers or [])
    if bt == BetType.corner:
        return result in (bet.numbers or [])
    if bt == BetType.dozen:
        return number_dozen(result) == bet.choice
    if bt == BetType.column:
        return number_column(result) == bet.choice
    if bt == BetType.red_black:
        return number_color(result) == bet.choice
    if bt == BetType.odd_even:
        if result == 0:
            return False
        return ("odd" if result % 2 == 1 else "even") == bet.choice
    if bt == BetType.low_high:
        if result == 0:
            return False
        return ("low" if result <= 18 else "high") == bet.choice
    return False


def evaluate_bets(result: int, bets: list[RouletteBet]) -> list[dict]:
    """Return per-bet evaluation: {bet_type, amount, payout, won}."""
    out = []
    for bet in bets:
        won = _bet_wins(result, bet)
        mult = PAYOUT_MULTIPLIER[bet.bet_type]
        payout = bet.amount * (mult + 1) if won else 0.0  # includes original stake on win
        out.append({
            "bet_type": bet.bet_type.value,
            "amount": bet.amount,
            "payout": payout,
            "won": won,
        })
    return out


def total_payout(result: int, bets: list[RouletteBet]) -> float:
    """Returns sum of payouts (0 means total loss of all stakes)."""
    return sum(
        bet.amount * (PAYOUT_MULTIPLIER[bet.bet_type] + 1)
        if _bet_wins(result, bet) else 0.0
        for bet in bets
    )


def total_staked(bets: list[RouletteBet]) -> float:
    return sum(b.amount for b in bets)
