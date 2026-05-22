import type { CSSProperties } from "react";
import type { LobbySeatPayload, SeatStatePayload, TableStatePayload } from "../types/api";
import { DEALER_DEAL_OFFSET, SEAT_COUNT, seatPosition } from "../data/games";
import PlayingCard from "./PlayingCard";
import SeatAvatar from "./SeatAvatar";

interface TableLayoutProps {
  tableState: TableStatePayload | null;
  seats: SeatStatePayload[];
  lobbySeats: (LobbySeatPayload | null)[];
  mySeatIndex: number | null | undefined;
  activeSeatIndex: number | null | undefined;
  dealingCards: Set<string>;
  revealingCards: Set<string>;
  hideDealerHole: boolean;
  canPickSeat: boolean;
  onPickSeat: (slot: number) => void;
}

export default function TableLayout({
  tableState,
  seats,
  lobbySeats,
  mySeatIndex,
  activeSeatIndex,
  dealingCards,
  revealingCards,
  hideDealerHole,
  canPickSeat,
  onPickSeat,
}: TableLayoutProps) {
  const dealerHand = tableState?.dealer_hand ?? [];
  const hiddenCount = hideDealerHole ? (tableState?.dealer_hidden_count ?? 0) : 0;
  const roundPlaying = tableState?.table_phase === "playing" || tableState?.round_in_progress;

  const gameSeatByIndex = new Map<number, SeatStatePayload>();
  seats.forEach((s) => gameSeatByIndex.set(s.seat_index, s));

  return (
    <div className="table-layout">
      <div className="casino-table">
        <div className="table-rim" />
        <div className="felt-texture" />

        <div className="card-shoe" aria-hidden>
          <div className="card-shoe-stack" />
        </div>

        <div className="dealer-zone">
          <span className="zone-label">Krupier</span>
          <div className="hand-row hand-row--dealer">
            {dealerHand.map((c, i) => (
              <PlayingCard
                key={`d-${c}-${i}`}
                card={c}
                dealing={dealingCards.has(`dealer-${i}`)}
                revealing={revealingCards.has(`dealer-${i}`)}
                dealFrom={DEALER_DEAL_OFFSET}
              />
            ))}
            {Array.from({ length: hiddenCount }).map((_, i) => (
              <PlayingCard
                key={`dh-${i}`}
                card=""
                hidden
                dealing={dealingCards.has(`dealer-hidden-${i}`)}
                dealFrom={DEALER_DEAL_OFFSET}
              />
            ))}
            {!roundPlaying && dealerHand.length === 0 && (
              <span className="placeholder-text placeholder-text--dealer">Stół gotowy</span>
            )}
          </div>
        </div>

        <div className="seats-row">
          {Array.from({ length: SEAT_COUNT }).map((_, slot) => {
            const pos = seatPosition(slot);
            const style: CSSProperties = {
              left: `${pos.x}%`,
              top: `${pos.y}%`,
              transform: "translate(-50%, -50%)",
            };
            const lobby = lobbySeats[slot] ?? null;
            const gameSeat = gameSeatByIndex.get(slot);
            const occupant = gameSeat ?? lobby;

            if (!occupant) {
              return (
                <SeatAvatar
                  key={`empty-${slot}`}
                  seatIndex={slot}
                  displayName=""
                  avatarKey=""
                  isHuman={false}
                  isEmpty
                  isSelectable={canPickSeat}
                  onSelect={() => onPickSeat(slot)}
                  style={style}
                />
              );
            }

            const isHuman = occupant.is_human && slot === mySeatIndex;
            return (
              <SeatAvatar
                key={`seat-${slot}-${occupant.display_name}`}
                seatIndex={slot}
                displayName={occupant.display_name}
                avatarKey={occupant.avatar_key}
                isHuman={isHuman}
                isActive={roundPlaying && activeSeatIndex === slot}
                hand={gameSeat?.hand ?? []}
                bet={gameSeat?.bet}
                result={gameSeat?.result}
                dealingCards={dealingCards}
                revealingCards={revealingCards}
                style={style}
                compact
              />
            );
          })}
        </div>

        {tableState?.message && tableState.message !== "wait_round_end" && (
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
