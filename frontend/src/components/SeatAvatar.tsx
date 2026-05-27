import type { CSSProperties } from "react";
import type { SeatStatePayload } from "../types/api";
import { avatarColor, dealOffsetFromDealer } from "../data/games";
import PlayingCard from "./PlayingCard";

interface SeatAvatarProps {
  seatIndex: number;
  displayName: string;
  avatarKey: string;
  isHuman: boolean;
  isEmpty?: boolean;
  isActive?: boolean;
  isInactive?: boolean;   // tura kogoś innego — przyciemniony
  isSelectable?: boolean;
  onSelect?: () => void;
  hand?: string[];
  bet?: number;
  result?: string | null;
  dealingCards?: Set<string>;
  revealingCards?: Set<string>;
  pendingCards?: Set<string>;
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
  isInactive,
  isSelectable,
  onSelect,
  hand = [],
  bet,
  result,
  dealingCards,
  revealingCards,
  pendingCards,
  style,
  compact,
}: SeatAvatarProps) {
  if (isEmpty) {
    return (
      <button
        type="button"
        className={`seat-node seat-node--empty ${isSelectable ? "seat-node--selectable" : ""}`}
        style={style}
        onClick={isSelectable ? onSelect : undefined}
        disabled={!isSelectable}
        aria-label={isSelectable ? `Usiądź na miejscu ${seatIndex + 1}` : "Wolne miejsce"}
      >
        <div className="seat-avatar seat-avatar--empty">+</div>
        <span className="seat-name">{isSelectable ? "Usiądź tutaj" : "Wolne"}</span>
      </button>
    );
  }

  const initials = isHuman ? "TY" : displayName.slice(0, 2).toUpperCase();
  const resultClass = result === "win" ? "seat-node--win" : result === "loss" ? "seat-node--loss" : "";
  const dealFrom = dealOffsetFromDealer(seatIndex, compact);

  return (
    <div
      className={`seat-node ${isHuman ? "seat-node--you" : ""} ${isActive ? "seat-node--active" : ""} ${isInactive ? "seat-node--inactive" : ""} ${resultClass}`}
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
          {hand.map((c, i) => {
            const key = `seat-${seatIndex}-${i}`;
            return (
              <PlayingCard
                key={`${c}-${i}`}
                card={c}
                compact={compact}
                pending={pendingCards?.has(key)}
                dealing={dealingCards?.has(key)}
                revealing={revealingCards?.has(key)}
                dealFrom={dealFrom}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

export type { SeatStatePayload };
