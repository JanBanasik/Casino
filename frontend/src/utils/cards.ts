export function calcHandValue(hand: string[]): number {
  let val = 0, aces = 0;
  for (const c of hand) {
    const rank = c.slice(0, -1);
    if (rank === "A") { val += 11; aces++; }
    else if (["K", "Q", "J", "T"].includes(rank)) val += 10;
    else { const n = parseInt(rank, 10); if (n) val += n; }
    while (val > 21 && aces > 0) { val -= 10; aces--; }
  }
  return val;
}
