import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import PlayingCard from "../components/PlayingCard";
import { avatarColor, seatPosition } from "../data/games";
import { useAuth } from "../hooks/useAuth";
import { usePokerSocket } from "../hooks/usePokerSocket";
import { createPokerSession, getWallet } from "../services/api";
import type { PokerSeatPayload } from "../types/api";

const POKER_SEAT_POSITIONS = [
  { x: 12, y: 68 },
  { x: 24, y: 78 },
  { x: 37, y: 84 },
  { x: 50, y: 86 },
  { x: 63, y: 84 },
  { x: 76, y: 78 },
];

function phaseLabel(phase: string): string {
  const map: Record<string, string> = {
    waiting: "Oczekiwanie",
    pre_flop: "Pre-flop",
    flop: "Flop",
    turn: "Turn",
    river: "River",
    showdown: "Showdown",
    finished: "Koniec rundy",
  };
  return map[phase] ?? phase;
}

function handResultLabel(result: string | null): string {
  if (!result) return "";
  const map: Record<string, string> = {
    win: "Wygrana!",
    loss: "Przegrana",
    fold: "Spasował",
    push: "Remis",
    royal_flush: "Royal Flush!",
    straight_flush: "Poker!",
    four_of_a_kind: "Kareta",
    full_house: "Full",
    flush: "Kolor",
    straight: "Strit",
    three_of_a_kind: "Trójka",
    two_pair: "Dwie pary",
    pair: "Para",
    high_card: "Najwyższa karta",
  };
  return map[result] ?? result;
}

export default function PokerTablePage() {
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const tableId = searchParams.get("table") ?? "poker-default";
  const botCountParam = parseInt(searchParams.get("bots") ?? "3", 10);
  const botCount = Number.isNaN(botCountParam) ? 3 : botCountParam;

  const { token } = useAuth();
  const navigate = useNavigate();
  const [balance, setBalance] = useState(0);
  const [raiseAmount, setRaiseAmount] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(urlSessionId ?? null);
  const [connecting, setConnecting] = useState(false);

  const {
    statusLabel,
    pokerState,
    error,
    connect,
    sit,
    startHand,
    fold,
    check,
    call,
    raise,
  } = usePokerSocket(sessionId, tableId, botCount);

  useEffect(() => {
    if (!token) navigate("/login", { state: { from: "/stoły" } });
  }, [token, navigate]);

  useEffect(() => {
    if (!token) return;
    async function init() {
      if (sessionId) {
        connect();
        return;
      }
      setConnecting(true);
      try {
        const session = await createPokerSession();
        setSessionId(session.id);
      } catch {
        // Will show error
      } finally {
        setConnecting(false);
      }
    }
    init();
  }, [token]);

  useEffect(() => {
    if (sessionId && token) connect();
  }, [sessionId, token, connect]);

  useEffect(() => {
    getWallet().then((w) => setBalance(w.balance)).catch(() => undefined);
  }, [pokerState]);

  useEffect(() => {
    if (pokerState) {
      const minRaise = pokerState.min_raise ?? pokerState.big_blind * 2;
      setRaiseAmount(minRaise);
    }
  }, [pokerState]);

  // Auto-sit at seat 0 when connected and not yet seated
  useEffect(() => {
    if (pokerState && pokerState.my_seat_index === null && sessionId) {
      sit(0);
    }
  }, [pokerState?.my_seat_index, sessionId, sit]);

  const mySeatIndex = pokerState?.my_seat_index ?? pokerState?.human_seat_index ?? null;
  const isSeated = mySeatIndex !== null && mySeatIndex !== undefined;
  const phase = pokerState?.phase ?? "waiting";
  const seats = pokerState?.seats ?? [];
  const communityCards = pokerState?.community_cards ?? [];
  const revealedCount =
    phase === "flop" ? 3
    : phase === "turn" ? 4
    : phase === "river" || phase === "showdown" || phase === "finished" ? 5
    : 0;

  const isMyTurn =
    pokerState?.active_seat_index !== null &&
    pokerState?.active_seat_index === mySeatIndex;
  const mySeat = seats.find((s) => s.seat_index === mySeatIndex);
  const canCheck = isMyTurn && pokerState && pokerState.current_bet === 0;
  const callAmount = pokerState?.current_bet ?? 0;

  function renderSeat(seat: PokerSeatPayload, posIdx: number) {
    const pos = POKER_SEAT_POSITIONS[posIdx] ?? seatPosition(posIdx);
    const isHuman = seat.seat_index === mySeatIndex;
    const isActive = pokerState?.active_seat_index === seat.seat_index;
    const isDealerBtn = pokerState?.dealer_seat_index === seat.seat_index;
    const isSB = pokerState && posIdx === ((pokerState.dealer_seat_index + 1) % seats.length);
    const isBB = pokerState && posIdx === ((pokerState.dealer_seat_index + 2) % seats.length);
    const initials = isHuman ? "TY" : seat.display_name.slice(0, 2).toUpperCase();
    const folded = seat.status === "folded";

    return (
      <div
        key={`poker-seat-${seat.seat_index}`}
        className={`poker-seat-node ${isActive ? "poker-seat-node--active" : ""} ${folded ? "poker-seat-node--folded" : ""}`}
        style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
      >
        {isDealerBtn && (
          <div className="poker-dealer-button" style={{ top: "-14px", right: "-14px", position: "absolute" }}>
            D
          </div>
        )}
        {isSB && !isDealerBtn && (
          <div className="poker-blind-chip poker-blind-chip--sb" style={{ top: "-14px", left: "-14px", position: "absolute" }}>
            SB
          </div>
        )}
        {isBB && !isSB && (
          <div className="poker-blind-chip poker-blind-chip--bb" style={{ top: "-14px", left: "-14px", position: "absolute" }}>
            BB
          </div>
        )}

        <div
          className={`seat-avatar ${isHuman ? "seat-avatar--you" : ""}`}
          style={!isHuman ? { background: avatarColor(seat.avatar_key) } : undefined}
        >
          {initials}
        </div>
        <span className="seat-name">{isHuman ? "Ty" : seat.display_name}</span>
        <span className="poker-seat-chips">{seat.chips.toLocaleString("pl-PL")} Ż</span>
        {seat.bet_total > 0 && (
          <span className="poker-seat-bet">{seat.bet_total} Ż</span>
        )}

        {/* Hole cards */}
        {seat.hole_cards.length > 0 && (
          <div className="poker-hole-cards">
            {seat.hole_cards.map((c, i) => (
              <PlayingCard
                key={`poker-hole-${seat.seat_index}-${i}`}
                card={c === "??" ? "" : c}
                hidden={c === "??"}
                compact
              />
            ))}
          </div>
        )}

        {/* Showdown result */}
        {(phase === "showdown" || phase === "finished") && seat.result && (
          <span className={`seat-bet ${seat.result === "win" ? "" : ""}`}>
            {handResultLabel(seat.result)}
          </span>
        )}
      </div>
    );
  }

  if (connecting) {
    return (
      <div className="container page">
        <p className="loading-text">Tworzenie sesji pokerowej…</p>
      </div>
    );
  }

  return (
    <div className="poker-page">
      <div className="container">
        <div className="game-room-topbar">
          <div>
            <Link to="/stoły" className="back-link">← Stoły na żywo</Link>
            <h1 style={{ fontFamily: "var(--font-display)", margin: "0.25rem 0 0", fontSize: "1.75rem" }}>Texas Hold'em</h1>
            <p className="table-subtitle">
              Do {botCount + 1} graczy · Blindy: {pokerState?.small_blind ?? 5}/{pokerState?.big_blind ?? 10} Ż
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
            <Link to="/stoły" className="btn btn-ghost btn-sm leave-table-btn">
              Opuść stół
            </Link>
          </div>
        </div>

        {/* Phase banner */}
        <div style={{ textAlign: "center", marginBottom: "1rem" }}>
          <span className="poker-phase-banner">{phaseLabel(phase)}</span>
        </div>

        {/* Poker table */}
        <div className="poker-table-oval">
          <div className="table-rim" />
          <div className="felt-texture" />

          {/* Community cards center */}
          <div className="poker-community-cards">
            {Array.from({ length: 5 }).map((_, i) => {
              const card = communityCards[i];
              if (card) {
                return (
                  <PlayingCard key={`community-${i}`} card={card} />
                );
              }
              if (i < revealedCount) {
                return <PlayingCard key={`community-h-${i}`} card="" hidden />;
              }
              return (
                <div key={`community-ph-${i}`} className="poker-card-placeholder" />
              );
            })}
          </div>

          {/* Pot */}
          {(pokerState?.pot ?? 0) > 0 && (
            <div className="poker-pot-display">
              Pula: {pokerState!.pot.toLocaleString("pl-PL")} Ż
            </div>
          )}

          {/* Seats */}
          {seats.map((seat, idx) => renderSeat(seat, idx))}
        </div>

        {/* Action panel — only shown on human's turn */}
        {isSeated && isMyTurn && mySeat?.status !== "folded" && (
          <div className="poker-action-panel">
            <span className="panel-label">Twoja kolej — {mySeat?.chips ?? 0} Ż</span>
            <button type="button" className="btn btn-action btn-action--stand" onClick={fold}>
              Pas (Fold)
            </button>
            {canCheck ? (
              <button type="button" className="btn btn-action" onClick={check}>
                Sprawdź (Check)
              </button>
            ) : (
              <button type="button" className="btn btn-action" onClick={call}>
                Wyrównaj {callAmount} Ż
              </button>
            )}
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <input
                type="number"
                className="poker-raise-input"
                value={raiseAmount}
                min={pokerState?.min_raise ?? 0}
                max={mySeat?.chips ?? 0}
                onChange={(e) => setRaiseAmount(Number(e.target.value))}
              />
              <button
                type="button"
                className="btn btn-gold"
                onClick={() => raise(raiseAmount)}
                disabled={raiseAmount < (pokerState?.min_raise ?? 0)}
              >
                Podbij
              </button>
            </div>
          </div>
        )}

        {/* Start hand button when waiting */}
        {!pokerState?.round_in_progress && phase === "waiting" && (
          <div className="poker-action-panel">
            {!isSeated ? (
              <p style={{ color: "var(--text-muted)", margin: 0 }}>
                Dołącz do stołu — wybierz miejsce
              </p>
            ) : (
              <>
                <span className="panel-label">Gotowy do gry</span>
                <button
                  type="button"
                  className="btn btn-gold btn-lg"
                  onClick={() => startHand(500, botCount)}
                >
                  Rozpocznij rozdanie
                </button>
              </>
            )}
          </div>
        )}

        {/* Showdown result */}
        {phase === "finished" && pokerState?.message && (
          <div className="poker-result-banner">
            {pokerState.message}
          </div>
        )}

        {error && (
          <p className="form-error" style={{ textAlign: "center", marginTop: "0.75rem" }}>
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
