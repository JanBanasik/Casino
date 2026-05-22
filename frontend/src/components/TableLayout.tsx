import type { CSSProperties } from "react";
import type { SeatStatePayload, TableStatePayload } from "../types/api";
import {
  HUMAN_SEAT_SLOT,
  SEAT_COUNT,
  seatPosition,
} from "../data/games";
import PlayingCard from "./PlayingCard";
import SeatAvatar from "./SeatAvatar";

interface TableLayoutProps {
  tableState: TableStatePayload | null;
  seats: SeatStatePayload[];
  humanSeatIndex: number;
  activeSeatIndex: number | null | undefined;
  dealingCards: Set<string>;
  hideDealerHole: boolean;
}

function slotForSeat(seatIndex: number, humanSeatIndex: number): number {
  const offset = HUMAN_SEAT_SLOT - humanSeatIndex;
  return (seatIndex + offset + SEAT_COUNT) % SEAT_COUNT;
}

export default function TableLayout({
  tableState,
  seats,
  humanSeatIndex,
  activeSeatIndex,
  dealingCards,
  hideDealerHole,
}: TableLayoutProps) {
  const dealerHand = tableState?.dealer_hand ?? [];
  const hiddenCount = hideDealerHole ? (tableState?.dealer_hidden_count ?? 0) : 0;

  const seatBySlot = new Map<number, SeatStatePayload>();
  seats.forEach((s) => {
    seatBySlot.set(slotForSeat(s.seat_index, humanSeatIndex), s);
  });

  return (
    <div className="table-layout">
      <div className="card-shoe" aria-hidden>
        <div className="card-shoe-stack" />
      </div>

      <div className="casino-table">
        <div className="table-rim" />
        <div className="felt-texture" />

        <div className="dealer-zone">
          <span className="zone-label">Krupier</span>
          <div className="hand-row">
            {dealerHand.map((c, i) => (
              <PlayingCard
                key={`d-${c}-${i}`}
                card={c}
                dealing={dealingCards.has(`dealer-${i}`)}
              />
            ))}
            {Array.from({ length: hiddenCount }).map((_, i) => (
              <PlayingCard
                key={`dh-${i}`}
                card=""
                hidden
                dealing={dealingCards.has(`dealer-hidden-${i}`)}
              />
            ))}
            {!tableState && (
              <span className="placeholder-text">Postaw zakład, aby rozpocząć rundę</span>
            )}
          </div>
        </div>

        <div className="seats-ellipse">
          {Array.from({ length: SEAT_COUNT }).map((_, slot) => {
            const seat = seatBySlot.get(slot);
            const pos = seatPosition(slot);
            const style: CSSProperties = {
              left: `${pos.x}%`,
              top: `${pos.y}%`,
              transform: `translate(-50%, -50%) rotate(${pos.rotate}deg)`,
            };
            if (seat) {
              return (
                <SeatAvatar
                  key={seat.seat_index}
                  seatIndex={seat.seat_index}
                  displayName={seat.display_name}
                  avatarKey={seat.avatar_key}
                  isHuman={seat.is_human}
                  isActive={activeSeatIndex === seat.seat_index}
                  hand={seat.hand}
                  bet={seat.bet}
                  result={seat.result}
                  dealingCards={dealingCards}
                  style={style}
                  compact
                />
              );
            }
            return <SeatAvatar key={`empty-${slot}`} seatIndex={slot} displayName="" avatarKey="" isHuman={false} isEmpty style={style} />;
          })}
        </div>

        {tableState?.message && (
          <p className="round-message table-message">{resultMessage(tableState.message)}</p>
        )}
      </div>
    </div>
  );
}

function resultMessage(msg: string): string {
  const map: Record<string, string> = {
    win: "Wygrana!",
    loss: "Przegrana",
    draw: "Remis",
    player_bust: "Fura!",
    dealer_bust: "Krupier ma furę!",
  };
  return map[msg] ?? msg;
}
