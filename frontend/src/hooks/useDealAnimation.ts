import { useCallback, useEffect, useRef, useState } from "react";
import type { TableStatePayload } from "../types/api";

const DEAL_STAGGER_MS = 100;
const REVEAL_MS = 400;
const DEAL_MS = 320;

interface DealItem {
  key: string;
  delay: number;
}

function collectKeys(state: TableStatePayload | null, hideDealerHole: boolean): string[] {
  if (!state) return [];
  const keys: string[] = [];
  state.dealer_hand.forEach((_, i) => keys.push(`dealer-${i}`));
  if (hideDealerHole) {
    for (let i = 0; i < state.dealer_hidden_count; i++) keys.push(`dealer-hidden-${i}`);
  }
  state.seats?.forEach((seat) => {
    seat.hand.forEach((_, i) => keys.push(`seat-${seat.seat_index}-${i}`));
  });
  if (!state.seats?.length) {
    state.player_hand.forEach((_, i) => keys.push(`seat-human-${i}`));
  }
  return keys;
}

function isHoleReveal(prevKeys: Set<string>, added: string[]): string[] {
  const reveals: string[] = [];
  for (const key of added) {
    const match = /^dealer-(\d+)$/.exec(key);
    if (!match) continue;
    const idx = match[1];
    if (prevKeys.has(`dealer-hidden-${idx}`)) {
      reveals.push(key);
    }
  }
  return reveals;
}

/** Dobranie w trakcie rundy — bez animacji przesuwu (tylko pojawia się karta). */
function isMidRoundHit(prev: TableStatePayload | null, added: string[]): boolean {
  if (!prev || added.length !== 1) return false;
  const key = added[0];
  return (
    key.startsWith("seat-") &&
    prev.phase === "player_turn" &&
    prev.table_phase === "playing"
  );
}

export function useDealAnimation(tableState: TableStatePayload | null) {
  const prevRef = useRef<TableStatePayload | null>(null);
  const [dealingCards, setDealingCards] = useState<Set<string>>(new Set());
  const [revealingCards, setRevealingCards] = useState<Set<string>>(new Set());
  const [isDealing, setIsDealing] = useState(false);

  const hideDealerHole = tableState?.phase === "player_turn";

  useEffect(() => {
    if (!tableState) {
      prevRef.current = null;
      setDealingCards(new Set());
      setRevealingCards(new Set());
      setIsDealing(false);
      return;
    }

    const prev = prevRef.current;
    const prevHideHole = prev?.phase === "player_turn";
    const prevKeys = new Set(collectKeys(prev, prevHideHole));
    const newKeys = collectKeys(tableState, hideDealerHole);
    const added = newKeys.filter((k) => !prevKeys.has(k));

    if (added.length === 0) {
      prevRef.current = tableState;
      return;
    }

    if (isMidRoundHit(prev, added)) {
      prevRef.current = tableState;
      return;
    }

    const reveals = isHoleReveal(prevKeys, added);
    const revealSet = new Set(reveals);
    const toDeal = added.filter((k) => !revealSet.has(k));

    const timers: ReturnType<typeof setTimeout>[] = [];

    if (reveals.length > 0) {
      setRevealingCards(revealSet);
      timers.push(setTimeout(() => setRevealingCards(new Set()), REVEAL_MS));
    }

    if (toDeal.length === 0) {
      prevRef.current = tableState;
      return () => timers.forEach(clearTimeout);
    }

    const items: DealItem[] = toDeal.map((key, i) => ({
      key,
      delay: i * DEAL_STAGGER_MS,
    }));

    setIsDealing(true);
    const active = new Set<string>();
    setDealingCards(active);

    items.forEach(({ key, delay }) => {
      timers.push(
        setTimeout(() => {
          active.add(key);
          setDealingCards(new Set(active));
        }, delay),
      );
    });

    const totalMs = items.length * DEAL_STAGGER_MS + DEAL_MS;
    timers.push(
      setTimeout(() => {
        setIsDealing(false);
        setDealingCards(new Set());
      }, totalMs),
    );

    prevRef.current = tableState;

    return () => timers.forEach(clearTimeout);
  }, [tableState, hideDealerHole]);

  const resetDeal = useCallback(() => {
    prevRef.current = null;
    setDealingCards(new Set());
    setRevealingCards(new Set());
    setIsDealing(false);
  }, []);

  return { dealingCards, revealingCards, isDealing, resetDeal };
}
