import { useCallback, useEffect, useRef, useState } from "react";
import type { TableStatePayload } from "../types/api";

const DEAL_STAGGER_MS = 120;

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

export function useDealAnimation(tableState: TableStatePayload | null) {
  const prevRef = useRef<TableStatePayload | null>(null);
  const [dealingCards, setDealingCards] = useState<Set<string>>(new Set());
  const [isDealing, setIsDealing] = useState(false);

  const hideDealerHole = tableState?.phase === "player_turn";

  useEffect(() => {
    if (!tableState) {
      prevRef.current = null;
      setDealingCards(new Set());
      setIsDealing(false);
      return;
    }

    const prev = prevRef.current;
    const prevKeys = new Set(collectKeys(prev, prev?.phase === "player_turn"));
    const newKeys = collectKeys(tableState, hideDealerHole);
    const added = newKeys.filter((k) => !prevKeys.has(k));

    if (added.length === 0) {
      prevRef.current = tableState;
      return;
    }

    const items: DealItem[] = added.map((key, i) => ({
      key,
      delay: i * DEAL_STAGGER_MS,
    }));

    setIsDealing(true);
    const active = new Set<string>();
    setDealingCards(active);

    const timers: ReturnType<typeof setTimeout>[] = [];
    items.forEach(({ key, delay }) => {
      timers.push(
        setTimeout(() => {
          active.add(key);
          setDealingCards(new Set(active));
        }, delay),
      );
    });

    timers.push(
      setTimeout(() => {
        setIsDealing(false);
        setDealingCards(new Set());
      }, items.length * DEAL_STAGGER_MS + 300),
    );

    prevRef.current = tableState;

    return () => timers.forEach(clearTimeout);
  }, [tableState, hideDealerHole]);

  const resetDeal = useCallback(() => {
    prevRef.current = null;
    setDealingCards(new Set());
    setIsDealing(false);
  }, []);

  return { dealingCards, isDealing, resetDeal };
}
