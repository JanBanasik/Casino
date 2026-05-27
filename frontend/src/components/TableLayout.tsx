import type { CSSProperties } from "react";
import type { LobbySeatPayload, SeatStatePayload, TableStatePayload } from "../types/api";
import { DEALER_DEAL_OFFSET, SEAT_COUNT, seatPosition } from "../data/games";
import type { AmbientSeat } from "../hooks/useAmbientTable";
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
  pendingCards: Set<string>;
  hideDealerHole: boolean;
  canPickSeat: boolean;
  onPickSeat: (slot: number) => void;
  // Ambient table simulation
  ambientSeats?: AmbientSeat[];
  ambientDealerHand?: string[];
  isAmbientDealing?: boolean;
}

export default function TableLayout({
  tableState,
  seats,
  lobbySeats,
  mySeatIndex,
  activeSeatIndex,
  dealingCards,
  revealingCards,
  pendingCards,
  hideDealerHole,
  canPickSeat,
  onPickSeat,
  ambientSeats = [],
  ambientDealerHand = [],
  isAmbientDealing = false,
}: TableLayoutProps) {
  const dealerHand = tableState?.dealer_hand ?? [];
  const hiddenCount = hideDealerHole ? (tableState?.dealer_hidden_count ?? 0) : 0;
  const roundPlaying = tableState?.table_phase === "playing" || tableState?.round_in_progress;

  // Use ambient dealer hand when idle and no real game
  const displayDealerHand = roundPlaying ? dealerHand : (ambientDealerHand.length > 0 ? ambientDealerHand : dealerHand);

  const gameSeatByIndex = new Map<number, SeatStatePayload>();
  seats.forEach((s) => gameSeatByIndex.set(s.seat_index, s));

  // Map ambient seats by index for easy lookup
  const ambientSeatByIndex = new Map<number, AmbientSeat>();
  ambientSeats.forEach((s) => ambientSeatByIndex.set(s.seatIndex, s));

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
            {displayDealerHand.map((c, i) => (
              <PlayingCard
                key={`d-${c}-${i}`}
                card={c}
                pending={roundPlaying ? pendingCards.has(`dealer-${i}`) : false}
                dealing={!roundPlaying && isAmbientDealing ? true : dealingCards.has(`dealer-${i}`)}
                revealing={revealingCards.has(`dealer-${i}`)}
                dealFrom={DEALER_DEAL_OFFSET}
              />
            ))}
            {Array.from({ length: hiddenCount }).map((_, i) => (
              <PlayingCard
                key={`dh-${i}`}
                card=""
                hidden
                pending={pendingCards.has(`dealer-hidden-${i}`)}
                dealing={dealingCards.has(`dealer-hidden-${i}`)}
                dealFrom={DEALER_DEAL_OFFSET}
              />
            ))}
            {!roundPlaying && displayDealerHand.length === 0 && (
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
            const ambientSeat = ambientSeatByIndex.get(slot);
            const occupant = gameSeat ?? lobby;

            // Show ambient seat when no real occupant and table is idle
            if (!occupant && ambientSeat && !roundPlaying) {
              return (
                <SeatAvatar
                  key={`ambient-${slot}`}
                  seatIndex={slot}
                  displayName={ambientSeat.displayName}
                  avatarKey={ambientSeat.avatarKey}
                  isHuman={false}
                  hand={ambientSeat.hand}
                  style={style}
                  compact
                />
              );
            }

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
            const isActiveSeat = roundPlaying && activeSeatIndex === slot;
            // Dim others when a specific seat is active (not during deal phase when activeSeatIndex is null)
            const isInactiveSeat =
              roundPlaying &&
              activeSeatIndex !== null &&
              activeSeatIndex !== undefined &&
              !isActiveSeat;
            return (
              <SeatAvatar
                key={`seat-${slot}-${occupant.display_name}`}
                seatIndex={slot}
                displayName={occupant.display_name}
                avatarKey={occupant.avatar_key}
                isHuman={isHuman}
                isActive={isActiveSeat}
                isInactive={isInactiveSeat}
                hand={gameSeat?.hand ?? []}
                bet={gameSeat?.bet}
                result={gameSeat?.result}
                dealingCards={dealingCards}
                revealingCards={revealingCards}
                pendingCards={pendingCards}
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
