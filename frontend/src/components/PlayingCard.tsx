import type { CSSProperties } from "react";

interface PlayingCardProps {
  card: string;
  hidden?: boolean;
  dealing?: boolean;
  revealing?: boolean;
  pending?: boolean;
  compact?: boolean;
  dealFrom?: { x: number; y: number };
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

export default function PlayingCard({
  card,
  hidden,
  dealing,
  revealing,
  pending,
  compact,
  dealFrom,
}: PlayingCardProps) {
  const cls = [
    "playing-card",
    compact ? "playing-card--compact" : "",
    dealing ? "playing-card--dealing" : "",
    revealing ? "playing-card--reveal" : "",
    hidden ? "playing-card--back" : "",
    pending ? "playing-card--pending" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const style: CSSProperties | undefined =
    dealing && dealFrom
      ? {
          ["--from-x" as string]: `${dealFrom.x}px`,
          ["--from-y" as string]: `${dealFrom.y}px`,
        }
      : undefined;

  if (hidden) {
    return <div className={cls} style={style} aria-hidden />;
  }

  const { rank, suit, red } = cardLabel(card);
  return (
    <div
      className={`${cls} ${red ? "playing-card--red" : "playing-card--black"}`}
      style={style}
    >
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
