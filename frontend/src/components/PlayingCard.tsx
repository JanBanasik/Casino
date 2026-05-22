interface PlayingCardProps {
  card: string;
  hidden?: boolean;
  dealing?: boolean;
  compact?: boolean;
}

function cardLabel(card: string): { rank: string; suit: string; red: boolean } {
  const rank = card.slice(0, -1);
  const suitChar = card.slice(-1);
  const suits: Record<string, string> = { C: "♣", D: "♦", H: "♥", S: "♠" };
  return {
    rank,
    suit: suits[suitChar] ?? suitChar,
    red: suitChar === "D" || suitChar === "H",
  };
}

export default function PlayingCard({ card, hidden, dealing, compact }: PlayingCardProps) {
  const cls = [
    "playing-card",
    compact ? "playing-card--compact" : "",
    dealing ? "playing-card--dealing" : "",
    hidden ? "playing-card--back" : "",
  ]
    .filter(Boolean)
    .join(" ");

  if (hidden) {
    return <div className={cls} aria-hidden />;
  }

  const { rank, suit, red } = cardLabel(card);
  return (
    <div className={`${cls} ${red ? "playing-card--red" : "playing-card--black"}`}>
      <div className="playing-card-corner playing-card-corner--tl">
        <span className="playing-card-rank">{rank}</span>
        <span className="playing-card-suit">{suit}</span>
      </div>
      <span className="playing-card-center">{suit}</span>
      <div className="playing-card-corner playing-card-corner--br">
        <span className="playing-card-rank">{rank}</span>
        <span className="playing-card-suit">{suit}</span>
      </div>
    </div>
  );
}

export function cardLabelText(card: string): string {
  const { rank, suit } = cardLabel(card);
  return `${rank}${suit}`;
}
