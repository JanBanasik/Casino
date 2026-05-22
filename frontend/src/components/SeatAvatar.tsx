import type { CSSProperties } from "react";
import type { SeatStatePayload } from "../types/api";
import { avatarColor } from "../data/games";
import PlayingCard from "./PlayingCard";

interface SeatAvatarProps {
  seatIndex: number;
  displayName: string;
  avatarKey: string;
  isHuman: boolean;
  isEmpty?: boolean;
  isActive?: boolean;
  hand?: string[];
  bet?: number;
  result?: string | null;
  dealingCards?: Set<string>;
  style?: CSSProperties;
  compact?: boolean;
}

export default function SeatAvatar({
  seatIndex,
  displayName,
  avatarKey,
  isHuman,
  isEmpty,
  isActive,
  hand = [],
  bet,
  result,
  dealingCards,
  style,
  compact,
}: SeatAvatarProps) {
  if (isEmpty) {
    return (
      <div className="seat-node seat-node--empty" style={style}>
        <div className="seat-avatar seat-avatar--empty">+</div>
        <span className="seat-name">Wolne miejsce</span>
      </div>
    );
  }

  const initials = isHuman ? "TY" : displayName.slice(0, 2).toUpperCase();
  const resultClass = result === "win" ? "seat-node--win" : result === "loss" ? "seat-node--loss" : "";

  return (
    <div
      className={`seat-node ${isHuman ? "seat-node--you" : ""} ${isActive ? "seat-node--active" : ""} ${resultClass}`}
      style={style}
    >
      <div
        className={`seat-avatar ${isHuman ? "seat-avatar--you" : ""}`}
        style={!isHuman ? { background: avatarColor(avatarKey) } : undefined}
      >
        {initials}
      </div>
      <span className="seat-name">{isHuman ? "Ty" : displayName}</span>
      {bet !== undefined && bet > 0 && <span className="seat-bet">{bet} Ż</span>}
      {hand.length > 0 && (
        <div className="seat-hand">
          {hand.map((c, i) => (
            <PlayingCard
              key={`${c}-${i}`}
              card={c}
              compact={compact}
              dealing={dealingCards?.has(`seat-${seatIndex}-${i}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export type { SeatStatePayload };
