import { useCallback, useEffect, useRef, useState } from "react";
import type { TableStatePayload } from "../types/api";

const DEAL_STAGGER_MS = 400;  // ms między każdą kartą
const REVEAL_MS = 550;
const DEAL_MS = 650;

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

/** Dobranie w trakcie rundy — bez animacji przesuwu. */
function isMidRoundHit(prev: TableStatePayload | null, added: string[]): boolean {
  if (!prev || added.length !== 1) return false;
  const key = added[0];
  return (
    key.startsWith("seat-") &&
    prev.phase === "player_turn" &&
    prev.table_phase === "playing"
  );
}

/**
 * Round-robin order: seat-0-0, seat-1-0, ..., dealer-0, seat-0-1, seat-1-1, ..., dealer-1
 */
function reorderDealKeys(keys: string[]): string[] {
  const byCardIndex: Map<number, string[]> = new Map();
  for (const key of keys) {
    const match = /-(\d+)$/.exec(key);
    const idx = match ? parseInt(match[1], 10) : 0;
    if (!byCardIndex.has(idx)) byCardIndex.set(idx, []);
    byCardIndex.get(idx)!.push(key);
  }
  const result: string[] = [];
  const sortedRounds = Array.from(byCardIndex.keys()).sort((a, b) => a - b);
  for (const round of sortedRounds) {
    const roundKeys = byCardIndex.get(round)!;
    const seatKeys = roundKeys.filter((k) => k.startsWith("seat-")).sort((a, b) => {
      const ai = parseInt(a.split("-")[1], 10);
      const bi = parseInt(b.split("-")[1], 10);
      return ai - bi;
    });
    const dealerKeys = roundKeys.filter((k) => k.startsWith("dealer-"));
    result.push(...seatKeys, ...dealerKeys);
  }
  return result;
}

export function useDealAnimation(tableState: TableStatePayload | null) {
  const prevRef = useRef<TableStatePayload | null>(null);
  const isFirstLoadRef = useRef(true);
  // Cards that have been added to state but haven't started animating yet → invisible
  const [pendingCards, setPendingCards] = useState<Set<string>>(new Set());
  const [dealingCards, setDealingCards] = useState<Set<string>>(new Set());
  const [revealingCards, setRevealingCards] = useState<Set<string>>(new Set());
  const [isDealing, setIsDealing] = useState(false);

  const hideDealerHole = tableState?.phase === "player_turn";

  useEffect(() => {
    if (!tableState) {
      prevRef.current = null;
      isFirstLoadRef.current = true;
      setPendingCards(new Set());
      setDealingCards(new Set());
      setRevealingCards(new Set());
      setIsDealing(false);
      return;
    }

    // Skip animation for the initial WS snapshot (joining mid-round or idle table)
    if (isFirstLoadRef.current) {
      isFirstLoadRef.current = false;
      prevRef.current = tableState;
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

    const reordered = reorderDealKeys(toDeal);
    const items: DealItem[] = reordered.map((key, i) => ({
      key,
      delay: i * DEAL_STAGGER_MS,
    }));

    // Immediately hide ALL new cards (pending) before their deal animation starts
    const pending = new Set(reordered);
    setPendingCards(pending);
    setIsDealing(true);
    const active = new Set<string>();

    items.forEach(({ key, delay }) => {
      timers.push(
        setTimeout(() => {
          // Move card from pending → dealing (now visible + animating)
          pending.delete(key);
          setPendingCards(new Set(pending));
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
        setPendingCards(new Set());
      }, totalMs),
    );

    prevRef.current = tableState;

    return () => timers.forEach(clearTimeout);
  }, [tableState, hideDealerHole]);

  const resetDeal = useCallback(() => {
    prevRef.current = null;
    isFirstLoadRef.current = true;
    setPendingCards(new Set());
    setDealingCards(new Set());
    setRevealingCards(new Set());
    setIsDealing(false);
  }, []);

  return { pendingCards, dealingCards, revealingCards, isDealing, resetDeal };
}
