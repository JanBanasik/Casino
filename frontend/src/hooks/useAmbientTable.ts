import { useEffect, useRef, useState } from "react";
import type { LobbySeatPayload } from "../types/api";
import { avatarColor } from "../data/games";

// Ambient dealing draws fresh random hands each round from a shuffled deck so the
// idle table never shows the same cards twice in a row.
const RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"];
const SUITS = ["C", "D", "H", "S"];

function drawAmbientDeal(seatCount: number): { dealer: string[]; hands: string[][] } {
  const deck: string[] = [];
  for (const r of RANKS) for (const s of SUITS) deck.push(`${r}${s}`);
  // Fisher–Yates shuffle
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  let k = 0;
  const dealer = [deck[k++], deck[k++]];
  const hands: string[][] = [];
  for (let s = 0; s < seatCount; s++) hands.push([deck[k++], deck[k++]]);
  return { dealer, hands };
}

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
  solo = false,
): AmbientTableState {
  const [isAmbientDealing, setIsAmbientDealing] = useState(false);
  const [ambientDealerHand, setAmbientDealerHand] = useState<string[]>([]);
  const [ambientSeats, setAmbientSeats] = useState<AmbientSeat[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Build bot seats from lobby ambient occupants (decorative only, never in solo).
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
    return filled;
  };

  useEffect(() => {
    if (solo || !tableIdle) {
      // Clear ambient state when real game starts
      setIsAmbientDealing(false);
      setAmbientDealerHand([]);
      setAmbientSeats([]);
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    function runAmbientRound() {
      const bots = getBotSeats();
      const deal = drawAmbientDeal(bots.length);

      // Deal fresh random cards
      setIsAmbientDealing(true);
      setAmbientDealerHand(deal.dealer);
      setAmbientSeats(
        bots.map((bot, i) => ({
          ...bot,
          hand: deal.hands[i] ?? [],
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
  }, [tableIdle, solo]);

  // When lobby seats change (without tableIdle changing), rebuild ambient seats
  useEffect(() => {
    if (solo || !tableIdle || isAmbientDealing) return;
    setAmbientSeats(getBotSeats().map((bot) => ({ ...bot, hand: [] })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lobbySeats, tableIdle, solo]);

  return { ambientSeats, ambientDealerHand, isAmbientDealing };
}

// Re-export avatarColor for use in ambient display
export { avatarColor };
