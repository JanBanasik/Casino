import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import LiveTableCard from "../components/LiveTableCard";
import { LIVE_TABLES, type LiveTable } from "../data/games";
import { createSession } from "../services/api";
import { useAuth } from "../hooks/useAuth";

export default function LiveCasinoPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [joiningId, setJoiningId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleJoin(table: LiveTable, solo: boolean) {
    if (!token) {
      navigate("/login", { state: { from: "/stoły" } });
      return;
    }
    setError(null);
    setJoiningId(table.id);
    try {
      const session = await createSession("blackjack");
      const botCount = solo ? 0 : Math.max(0, table.seatsTaken - 1);
      const params = new URLSearchParams({
        table: table.id,
        ...(solo ? { solo: "1" } : { bots: String(botCount) }),
      });
      navigate(`/graj/${session.id}?${params.toString()}`, {
        state: { tableName: solo ? `${table.name} — Solo` : table.name, minBet: table.minBet },
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się dołączyć do stołu");
    } finally {
      setJoiningId(null);
    }
  }

  async function handleSoloQuick() {
    if (!token) {
      navigate("/login", { state: { from: "/stoły" } });
      return;
    }
    setError(null);
    setJoiningId("solo");
    try {
      const session = await createSession("blackjack");
      navigate(`/graj/${session.id}?table=default&solo=1`, {
        state: { tableName: "Blackjack — Gra solo", minBet: 10 },
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się rozpocząć gry");
    } finally {
      setJoiningId(null);
    }
  }

  const totalPlayers = LIVE_TABLES.reduce((a, t) => a + t.seatsTaken, 0);

  return (
    <div className="container page">
      <div className="page-header">
        <div>
          <h1>Stoły na żywo</h1>
          <p>Dołącz do pełnego stołu albo zagraj solo przeciwko krupierowi.</p>
        </div>
        <span className="live-indicator live-indicator--lg">
          <span className="live-dot" /> LIVE · {totalPlayers} graczy online
        </span>
      </div>

      {!token && (
        <div className="banner banner--info">
          Zaloguj się, aby zająć miejsce przy stole. <Link to="/login">Zaloguj</Link> lub{" "}
          <Link to="/register">zarejestruj</Link>.
        </div>
      )}

      {error && <div className="banner banner--error">{error}</div>}

      <article className="solo-card">
        <div>
          <span className="live-badge">SOLO</span>
          <h2>Gra solo</h2>
          <p>Tylko ty i krupier — idealne na szybką rundę bez czekania.</p>
        </div>
        <button
          type="button"
          className="btn btn-gold"
          disabled={joiningId === "solo"}
          onClick={handleSoloQuick}
        >
          {joiningId === "solo" ? "Dołączanie…" : "Graj solo"}
        </button>
      </article>

      <h2 className="page-section-title">Stoły wieloosobowe</h2>
      <div className="live-tables-grid">
        {LIVE_TABLES.map((table) => (
          <LiveTableCard
            key={table.id}
            table={table}
            onJoin={(t) => handleJoin(t, false)}
            onJoinSolo={(t) => handleJoin(t, true)}
            joining={joiningId === table.id}
          />
        ))}
      </div>
    </div>
  );
}
