import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import LiveTableCard from "../components/LiveTableCard";
import { LIVE_TABLES, type LiveTable } from "../data/games";
import { createSession, createPokerSession } from "../services/api";
import { useAuth } from "../hooks/useAuth";

const POKER_TABLES = [
  {
    id: "poker-table-1",
    name: "Stół Pokerowy I",
    blinds: "5 / 10 Ż",
    players: 4,
    max: 6,
    featured: true,
  },
  {
    id: "poker-table-2",
    name: "Stół Pokerowy II",
    blinds: "10 / 20 Ż",
    players: 2,
    max: 6,
    featured: false,
  },
  {
    id: "poker-vip",
    name: "High Roller Poker",
    blinds: "50 / 100 Ż",
    players: 1,
    max: 6,
    featured: false,
  },
];

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

  async function handleJoinPoker(tableId: string) {
    if (!token) {
      navigate("/login", { state: { from: "/stoły" } });
      return;
    }
    setError(null);
    setJoiningId(tableId);
    try {
      const session = await createPokerSession();
      navigate(`/poker/${session.id}?table=${tableId}&bots=3`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się dołączyć do stołu pokerowego");
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

      {/* ── Blackjack ── */}
      <article className="solo-card">
        <div>
          <span className="live-badge">SOLO</span>
          <h2>Blackjack solo</h2>
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

      <h2 className="page-section-title">Blackjack — stoły wieloosobowe</h2>
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

      {/* ── Poker ── */}
      <div style={{ marginTop: "2.5rem" }}>
        <h2 className="page-section-title" id="poker">Texas Hold'em — stoły pokerowe</h2>
        <div className="live-tables-grid">
          {POKER_TABLES.map((pt) => (
            <div
              key={pt.id}
              className={`live-table-card ${pt.featured ? "live-table-card--featured" : ""}`}
            >
              <div className="live-table-header">
                <div>
                  <h3>{pt.name}</h3>
                  <p className="live-dealer">Blindy: {pt.blinds}</p>
                </div>
                <span className="level-badge level-standard">POKER</span>
              </div>
              <div className="seats-row">
                {Array.from({ length: pt.max }).map((_, i) => (
                  <div
                    key={i}
                    className={`seat-dot ${i < pt.players ? "seat-dot--taken" : "seat-dot--free"}`}
                  />
                ))}
              </div>
              <p className="seats-label">
                {pt.players}/{pt.max} graczy
              </p>
              <div className="live-table-actions">
                <button
                  type="button"
                  className="btn btn-gold btn-block"
                  disabled={joiningId === pt.id}
                  onClick={() => handleJoinPoker(pt.id)}
                >
                  {joiningId === pt.id ? "Dołączanie…" : "Dołącz do stołu"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Roulette ── */}
      <div style={{ marginTop: "2.5rem" }}>
        <h2 className="page-section-title">Ruletka</h2>
        <div
          className="solo-card"
          style={{ background: "linear-gradient(135deg, #3d1010, #1a0808)", borderColor: "rgba(180, 30, 30, 0.4)" }}
        >
          <div>
            <span className="live-badge" style={{ background: "#991111" }}>LIVE</span>
            <h2>Ruletka Europejska</h2>
            <p>37 numerów, europejskie zasady — postaw zakład i zakręć kołem.</p>
          </div>
          <Link to="/roulette" className="btn btn-gold">
            Graj w ruletkę
          </Link>
        </div>
      </div>
    </div>
  );
}
