import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./useAuth";
import { claimDaily, getDailyStatus } from "../services/api";
import type { BonusGrantResponse, DailyStatusResponse } from "../types/api";

export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(sec)}`;
}

interface DailyBonus {
  status: DailyStatusResponse | null;
  claimable: boolean;
  secondsLeft: number;
  loading: boolean;
  claim: () => Promise<BonusGrantResponse>;
  refresh: () => Promise<void>;
}

/** Live daily-bonus status with a 1s countdown to the next claim window. */
export function useDailyBonus(): DailyBonus {
  const { token } = useAuth();
  const [status, setStatus] = useState<DailyStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(() => Date.now());

  const refresh = useCallback(async () => {
    if (!token) {
      setStatus(null);
      setLoading(false);
      return;
    }
    try {
      setStatus(await getDailyStatus());
    } catch {
      // ignore — keep last known status
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // 1s tick drives the countdown display.
  useEffect(() => {
    if (!token) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [token]);

  const nextAt = status?.next_available_at
    ? new Date(status.next_available_at).getTime()
    : null;
  const secondsLeft = nextAt ? Math.max(0, Math.floor((nextAt - now) / 1000)) : 0;
  const claimable = Boolean(status?.available) || (nextAt !== null && secondsLeft === 0);

  // When the countdown elapses, pull fresh status so `available` flips to true.
  useEffect(() => {
    if (status && !status.available && nextAt !== null && secondsLeft === 0) {
      refresh();
    }
  }, [secondsLeft, status, nextAt, refresh]);

  const claim = useCallback(async () => {
    const res = await claimDaily();
    await refresh();
    return res;
  }, [refresh]);

  return { status, claimable, secondsLeft, loading, claim, refresh };
}
