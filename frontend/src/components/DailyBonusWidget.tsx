import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useDailyBonus, formatCountdown } from "../hooks/useDailyBonus";

/** Pinned side reminder for the daily bonus — claim CTA when ready, otherwise a
 *  live countdown to the next one. Shown only to signed-in players. */
export default function DailyBonusWidget() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { status, claimable, secondsLeft, loading, claim } = useDailyBonus();
  const [busy, setBusy] = useState(false);
  const [justClaimed, setJustClaimed] = useState<number | null>(null);
  const [hidden, setHidden] = useState(false);

  if (!token || loading || !status || hidden) return null;

  async function onClaim() {
    setBusy(true);
    try {
      const res = await claim();
      if (res.granted) setJustClaimed(Math.round(res.amount));
    } catch {
      navigate("/konto");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className={`daily-widget ${claimable ? "daily-widget--ready" : ""}`}>
      <button
        type="button"
        className="daily-widget__close"
        aria-label="Ukryj"
        onClick={() => setHidden(true)}
      >
        ×
      </button>
      <div className="daily-widget__icon" aria-hidden>🎁</div>
      <div className="daily-widget__body">
        <div className="daily-widget__title">Dzienny bonus</div>
        {justClaimed !== null ? (
          <div className="daily-widget__sub">Odebrano +{justClaimed.toLocaleString("pl-PL")} Ż 🎉</div>
        ) : claimable ? (
          <>
            <div className="daily-widget__sub">
              Gotowy do odbioru: +{Math.round(status.next_amount).toLocaleString("pl-PL")} Ż
            </div>
            <button type="button" className="btn btn-gold btn-sm" disabled={busy} onClick={onClaim}>
              {busy ? "Odbieram…" : "Odbierz teraz"}
            </button>
          </>
        ) : (
          <div className="daily-widget__sub">
            Następny za <strong className="daily-widget__timer">{formatCountdown(secondsLeft)}</strong>
          </div>
        )}
      </div>
    </aside>
  );
}
