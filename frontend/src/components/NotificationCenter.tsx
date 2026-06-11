import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useGameActivity } from "../hooks/useGameActivity";
import { ackNotification, getNotifications } from "../services/api";
import type { NotificationItem } from "../types/api";

const ICONS: Record<string, string> = {
  welcome: "🎉",
  daily: "📅",
  loss_refund: "🎁",
  rescue: "🛟",
  purchase: "💳",
  withdrawal: "🏦",
};

export default function NotificationCenter() {
  const { token } = useAuth();
  const { roundActive } = useGameActivity();
  const [queue, setQueue] = useState<NotificationItem[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const res = await getNotifications();
      setQueue(res.notifications);
    } catch {
      // ignore — will retry on next tick/round end
    }
  }, [token]);

  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;
  useEffect(() => {
    if (!token) {
      setQueue([]);
      return;
    }
    refreshRef.current();
    const id = setInterval(() => refreshRef.current(), 30_000);
    return () => clearInterval(id);
  }, [token]);

  // The moment a round ends, pull in any bonus earned during it so the modal can
  // pop right at the table (no need to leave for the home page).
  useEffect(() => {
    if (!roundActive) refreshRef.current();
  }, [roundActive]);

  // Only suppressed while a round is actively in progress — shown at the table
  // between rounds, before sitting down, and after a game finishes.
  if (!token || roundActive || queue.length === 0) return null;

  const current = queue[0];

  async function accept() {
    setBusy(true);
    try {
      await ackNotification(current.id);
    } catch {
      // even if the ack request fails, advance locally to avoid a stuck modal
    } finally {
      setQueue((q) => q.slice(1));
      setBusy(false);
    }
  }

  return (
    <div className="notif-overlay" role="dialog" aria-modal="true" aria-labelledby="notif-title">
      <div className="notif-card">
        <div className="notif-icon" aria-hidden>{ICONS[current.kind] ?? "🔔"}</div>
        <h2 id="notif-title" className="notif-title">{current.title}</h2>
        <p className="notif-body">{current.body}</p>
        {current.amount > 0 && (
          <div className="notif-amount">+{Math.round(current.amount).toLocaleString("pl-PL")} Ż</div>
        )}
        <button type="button" className="btn btn-gold btn-block" disabled={busy} onClick={accept}>
          {busy ? "…" : "Odbieram"}
        </button>
        {queue.length > 1 && (
          <p className="notif-count">Pozostałe powiadomienia: {queue.length - 1}</p>
        )}
      </div>
    </div>
  );
}
