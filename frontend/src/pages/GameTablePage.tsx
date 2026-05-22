import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import TableLayout from "../components/TableLayout";
import { LIVE_TABLES } from "../data/games";
import { useDealAnimation } from "../hooks/useDealAnimation";
import { useAuth } from "../hooks/useAuth";
import { useGameSocket } from "../hooks/useGameSocket";
import { getWallet } from "../services/api";
import type { SeatStatePayload } from "../types/api";

const CHIP_PRESETS = [10, 25, 50, 100, 500];

export default function GameTablePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const tableId = searchParams.get("table") ?? "default";
  const solo = searchParams.get("solo") === "1";
  const botCountParam = parseInt(searchParams.get("bots") ?? "0", 10);

  const location = useLocation();
  const tableName = (location.state as { tableName?: string } | null)?.tableName;
  const minBet = (location.state as { minBet?: number } | null)?.minBet ?? 10;
  const botCount = solo ? 0 : (Number.isNaN(botCountParam) ? 0 : botCountParam);

  const { token } = useAuth();
  const navigate = useNavigate();
  const [balance, setBalance] = useState(0);
  const [bet, setBet] = useState(minBet);

  const tableMeta = LIVE_TABLES.find((t) => t.id === tableId);

  const {
    statusLabel,
    tableState,
    error,
    retentionAlert,
    clearRetentionAlert,
    connect,
    newRound,
    hit,
    stand,
  } = useGameSocket(sessionId ?? null, tableId, solo, botCount);

  const { dealingCards, isDealing, resetDeal } = useDealAnimation(tableState);

  const seats: SeatStatePayload[] = useMemo(() => {
    if (tableState?.seats?.length) return tableState.seats;
    return [];
  }, [tableState]);

  const humanSeatIndex = tableState?.human_seat_index ?? 0;
  const canPlay = tableState?.phase === "player_turn" && tableState.active_seat_index === humanSeatIndex;

  useEffect(() => {
    if (!token) navigate("/login", { state: { from: "/stoły" } });
  }, [token, navigate]);

  useEffect(() => {
    if (sessionId && token) connect();
  }, [sessionId, tableId, token, connect]);

  useEffect(() => {
    getWallet().then((w) => setBalance(w.balance)).catch(() => undefined);
  }, [tableState]);

  function handleNewRound() {
    resetDeal();
    newRound(bet);
  }

  return (
    <div className="game-room">
      <div className="game-room-topbar container">
        <div>
          <Link to="/stoły" className="back-link">← Stoły na żywo</Link>
          <h1>{tableName ?? tableMeta?.name ?? "Blackjack"}</h1>
          <p className="table-subtitle">
            {tableMeta?.dealerName ?? "Krupier"} · {solo ? "Gra solo" : `${botCount + 1} graczy przy stole`}
          </p>
        </div>
        <div className="game-room-stats">
          <div className="stat-pill">
            <span>Saldo</span>
            <strong>{balance.toLocaleString("pl-PL")} Ż</strong>
          </div>
          <div className="stat-pill stat-pill--live">
            <span>Status</span>
            <strong>{statusLabel}</strong>
          </div>
        </div>
      </div>

      {retentionAlert && (
        <div className="toast toast--success container" onClick={clearRetentionAlert}>
          {retentionAlert}
        </div>
      )}

      <div className="felt-container container">
        <TableLayout
          tableState={tableState}
          seats={seats}
          humanSeatIndex={humanSeatIndex}
          activeSeatIndex={tableState?.active_seat_index}
          dealingCards={dealingCards}
          hideDealerHole={tableState?.phase === "player_turn"}
        />
      </div>

      <div className="game-controls container">
        <div className="bet-panel">
          <span className="panel-label">Zakład</span>
          <div className="chip-presets">
            {CHIP_PRESETS.filter((n) => n >= (tableMeta?.minBet ?? 1) && n <= (tableMeta?.maxBet ?? 10000)).map((n) => (
              <button
                key={n}
                type="button"
                className={`casino-chip ${bet === n ? "casino-chip--active" : ""}`}
                onClick={() => setBet(n)}
              >
                {n}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="btn btn-gold"
            onClick={handleNewRound}
            disabled={isDealing || statusLabel !== "Stół na żywo"}
          >
            Nowa runda
          </button>
        </div>
        <div className="action-panel">
          <button type="button" className="btn btn-action" onClick={hit} disabled={!canPlay || isDealing}>
            Dobierz
          </button>
          <button type="button" className="btn btn-action btn-action--stand" onClick={stand} disabled={!canPlay || isDealing}>
            Pas
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
      </div>
    </div>
  );
}
