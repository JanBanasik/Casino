import { useEffect, useRef, useState } from "react";
import type { LobbySeatPayload } from "../types/api";
import { PLAYER_NAMES, avatarColor } from "../data/games";

// Fake cards for ambient dealing
const FAKE_CARDS = [
  ["AS", "KH"],
  ["7D", "QC"],
  ["JH", "9S"],
  ["3D", "AC"],
  ["KC", "8H"],
  ["2S", "6D"],
];

const FAKE_DEALER_HAND = ["TH", "3S"];

const AMBIENT_MIN_MS = 18000;   // min 18s between ambient rounds
const AMBIENT_MAX_MS = 28000;   // max 28s
const AMBIENT_SHOW_MS = 6000;   // show for 6s

export interface AmbientSeat {
  seatIndex: number;
  displayName: string;
  avatarKey: string;
  hand: string[];
}

interface AmbientTableState {
  ambientSeats: AmbientSeat[];
  ambientDealerHand: string[];
  isAmbientDealing: boolean;
}

/**
 * Simulates a fake blackjack round for visual atmosphere when the table is idle.
 * Every 10-15 seconds, "deals" fake cards to occupied bot seats and the dealer.
 * After 5 seconds, clears them.
 */
export function useAmbientTable(
  tableIdle: boolean,
  lobbySeats: (LobbySeatPayload | null)[],
): AmbientTableState {
  const [isAmbientDealing, setIsAmbientDealing] = useState(false);
  const [ambientDealerHand, setAmbientDealerHand] = useState<string[]>([]);
  const [ambientSeats, setAmbientSeats] = useState<AmbientSeat[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Build bot seats from lobby data (exclude human seat or use generated bots)
  const getBotSeats = (): AmbientSeat[] => {
    const filled: AmbientSeat[] = [];
    lobbySeats.forEach((seat, idx) => {
      if (seat && !seat.is_human) {
        filled.push({
          seatIndex: idx,
          displayName: seat.display_name,
          avatarKey: seat.avatar_key,
          hand: [],
        });
      }
    });

    // If no lobby seats, generate some bots at fixed positions
    if (filled.length === 0) {
      const botPositions = [0, 1, 2, 4, 5];
      botPositions.forEach((slotIdx, i) => {
        const name = PLAYER_NAMES[i % PLAYER_NAMES.length];
        filled.push({
          seatIndex: slotIdx,
          displayName: name,
          avatarKey: name,
          hand: [],
        });
      });
    }

    return filled;
  };

  useEffect(() => {
    if (!tableIdle) {
      // Clear ambient state when real game starts
      setIsAmbientDealing(false);
      setAmbientDealerHand([]);
      setAmbientSeats([]);
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    function runAmbientRound() {
      const bots = getBotSeats();

      // Deal fake cards
      setIsAmbientDealing(true);
      setAmbientDealerHand(FAKE_DEALER_HAND);
      setAmbientSeats(
        bots.map((bot, i) => ({
          ...bot,
          hand: FAKE_CARDS[i % FAKE_CARDS.length],
        })),
      );

      // Clear after AMBIENT_SHOW_MS
      timerRef.current = setTimeout(() => {
        setIsAmbientDealing(false);
        setAmbientDealerHand([]);
        setAmbientSeats(bots.map((bot) => ({ ...bot, hand: [] })));

        // Schedule next round
        const delay = AMBIENT_MIN_MS + Math.random() * (AMBIENT_MAX_MS - AMBIENT_MIN_MS);
        timerRef.current = setTimeout(runAmbientRound, delay);
      }, AMBIENT_SHOW_MS);
    }

    // Start first ambient round after a longer delay (avoids confusion after real round ends)
    const initialDelay = 8000 + Math.random() * 6000;
    timerRef.current = setTimeout(runAmbientRound, initialDelay);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableIdle]);

  // When lobby seats change (without tableIdle changing), rebuild ambient seats
  useEffect(() => {
    if (!tableIdle || isAmbientDealing) return;
    setAmbientSeats(getBotSeats().map((bot) => ({ ...bot, hand: [] })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lobbySeats, tableIdle]);

  return { ambientSeats, ambientDealerHand, isAmbientDealing };
}

// Re-export avatarColor for use in ambient display
export { avatarColor };
