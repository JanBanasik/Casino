import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ConfettiBurst from "../components/ConfettiBurst";
import PlayingCard from "../components/PlayingCard";
import SoundToggle from "../components/SoundToggle";
import { avatarColor, seatPosition } from "../data/games";
import { useCountUp } from "../hooks/useCountUp";
import { sound } from "../lib/sound";
import { useAuth } from "../hooks/useAuth";
import { usePokerSocket } from "../hooks/usePokerSocket";
import { createPokerSession, getGameConfig, getWallet } from "../services/api";
import { DifficultyBadge } from "../components/DifficultyPicker";
import { useReportRoundActivity } from "../hooks/useGameActivity";
import type { Difficulty, PokerSeatPayload } from "../types/api";

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

const POKER_BUY_INS = [50, 100, 250, 500];

function PokerPotDisplay({ pot }: { pot: number }) {
  const animated = Math.round(useCountUp(pot, pot, 500, true));
  return <div className="poker-pot-display">Pula: {animated.toLocaleString("pl-PL")} Ż</div>;
}

function mapPokerError(code: string): string {
  const map: Record<string, string> = {
    insufficient_balance: "Niewystarczające saldo na buy-in.",
    not_seated: "Najpierw zajmij miejsce przy stole.",
    hand_in_progress: "Rozdanie już trwa.",
    no_active_hand: "Brak aktywnego rozdania.",
    buyin_below_minimum: "Buy-in poniżej minimum stołu.",
    buyin_above_maximum: "Buy-in powyżej maksimum stołu.",
  };
  return map[code] ?? code;
}

function formatPokerMessage(message: string): string {
  // Engine emits "win:Name" or "win:Name1, Name2:HandName".
  const parts = message.split(":");
  if (parts[0] !== "win") return message;
  const names = parts[1] ?? "";
  const hand = parts[2];
  const multi = names.includes(",");
  const verb = multi ? "Wygrywają" : "Wygrywa";
  return hand ? `${verb}: ${names} — ${hand}` : `${verb}: ${names}`;
}

function handResultLabel(result: string | null | undefined): string {
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
  const difficulty = (searchParams.get("difficulty") ?? "medium") as Difficulty;

  const { token } = useAuth();
  const navigate = useNavigate();
  const [balance, setBalance] = useState(0);
  const [buyIn, setBuyIn] = useState(100);
  const [pokerMinBuyin, setPokerMinBuyin] = useState(50);
  const [raiseAmount, setRaiseAmount] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(urlSessionId ?? null);
  const [connecting, setConnecting] = useState(false);
  const [confettiKey, setConfettiKey] = useState(0);
  const [bigWin, setBigWin] = useState(false);

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
  } = usePokerSocket(sessionId, tableId, botCount, difficulty);

  // A hand is "active" only while betting streets are running.
  const pokerActive = ["pre_flop", "flop", "turn", "river"].includes(pokerState?.phase ?? "");
  useReportRoundActivity(pokerActive);

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

  // Refresh the balance on phase transitions only (buy-in at hand start, payout
  // at the end) — not on every action — and let the result land before showing
  // the settled amount.
  const balancePhaseRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const ph = pokerState?.phase;
    if (ph === balancePhaseRef.current) return;
    balancePhaseRef.current = ph;
    const delay = ph === "finished" ? 800 : 300;
    const t = setTimeout(() => {
      getWallet().then((w) => setBalance(w.balance)).catch(() => undefined);
    }, delay);
    return () => clearTimeout(t);
  }, [pokerState?.phase]);

  useEffect(() => {
    getGameConfig().then((c) => setPokerMinBuyin(c.poker_min_buyin)).catch(() => undefined);
  }, []);

  // A table's minimum buy-in is the larger of the global floor and its big blind.
  const tableMinBuyin = Math.max(pokerMinBuyin, pokerState?.big_blind ?? 20);

  useEffect(() => {
    const affordable =
      [...POKER_BUY_INS].reverse().find((b) => b >= tableMinBuyin && b <= balance) ??
      POKER_BUY_INS.find((b) => b >= tableMinBuyin) ??
      POKER_BUY_INS[0];
    setBuyIn(affordable);
  }, [balance, tableMinBuyin]);

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

  const canStartHand =
    !pokerState?.round_in_progress &&
    (phase === "waiting" || phase === "finished" || pokerState?.table_phase === "idle");
  const affordableBuyIns = POKER_BUY_INS.filter((b) => b >= tableMinBuyin && b <= balance);
  const isMyTurn =
    pokerState?.active_seat_index !== null &&
    pokerState?.active_seat_index === mySeatIndex;
  const mySeat = seats.find((s) => s.seat_index === mySeatIndex);
  const canCheck = isMyTurn && mySeat != null && mySeat.bet_phase >= (pokerState?.current_bet ?? 0);
  const callAmount = pokerState?.current_bet ?? 0;
  const minRaise = pokerState?.min_raise ?? (pokerState?.big_blind ?? 10) * 2;
  const pot = pokerState?.pot ?? 0;
  const myChips = mySeat?.chips ?? 0;
  const toCall = Math.max(0, callAmount - (mySeat?.bet_phase ?? 0));
  const maxRaise = (mySeat?.bet_phase ?? 0) + myChips;
  const raiseStep = pokerState?.big_blind ?? 10;

  // Card-flip cue as the board advances (flop → turn → river).
  const prevRevealedRef = useRef(0);
  useEffect(() => {
    if (revealedCount > prevRevealedRef.current) sound.play("flip");
    prevRevealedRef.current = revealedCount;
  }, [revealedCount]);

  // Win/lose chime when the hand resolves.
  const prevPokerPhaseRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const prev = prevPokerPhaseRef.current;
    prevPokerPhaseRef.current = phase;
    if (phase !== "finished" || prev === "finished" || prev === undefined) return;
    const mine = seats.find((s) => s.seat_index === mySeatIndex);
    if (mine?.result === "win") {
      const big = (mine.payout ?? 0) >= (pokerState?.big_blind ?? 10) * 20;
      sound.play(big ? "bigwin" : "win");
      setBigWin(big);
      setConfettiKey((k) => k + 1);
    } else if (mine?.result === "loss") {
      sound.play("lose");
    }
  }, [phase, seats, mySeatIndex, pokerState?.big_blind]);

  function setRaisePreset(kind: "min" | "half_pot" | "pot" | "all_in") {
    if (!pokerState || !mySeat) return;
    let target = minRaise;
    if (kind === "half_pot") target = Math.max(minRaise, pot * 0.5 + callAmount);
    if (kind === "pot") target = Math.max(minRaise, pot + callAmount);
    if (kind === "all_in") target = mySeat.bet_phase + myChips;
    target = Math.min(target, mySeat.bet_phase + myChips);
    setRaiseAmount(Math.round(target));
  }

  function renderSeat(seat: PokerSeatPayload, posIdx: number) {
    const pos = POKER_SEAT_POSITIONS[posIdx] ?? seatPosition(posIdx);
    const isHuman = seat.seat_index === mySeatIndex;
    const isActive = pokerState?.active_seat_index === seat.seat_index;
    const isDealerBtn = pokerState?.dealer_seat_index === seat.seat_index;
    const isSB = pokerState && posIdx === ((pokerState.dealer_seat_index + 1) % seats.length);
    const isBB = pokerState && posIdx === ((pokerState.dealer_seat_index + 2) % seats.length);
    const initials = isHuman ? "TY" : seat.display_name.slice(0, 2).toUpperCase();
    const folded = seat.status === "folded";
    const isShowdown = phase === "showdown" || phase === "finished";

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

        {/* Hole cards — bots' cards flip face-up at showdown */}
        {seat.hole_cards.length > 0 && (
          <div className="poker-hole-cards">
            {seat.hole_cards.map((c, i) => (
              <PlayingCard
                key={`poker-hole-${seat.seat_index}-${i}`}
                card={c === "??" ? "" : c}
                hidden={c === "??"}
                revealing={isShowdown && !isHuman && c !== "??"}
                compact
              />
            ))}
          </div>
        )}

        {/* Showdown result */}
        {(phase === "showdown" || phase === "finished") && seat.result && (
          <span
            className={`seat-bet seat-bet--${seat.result === "win" ? "win" : seat.result === "fold" ? "fold" : "loss"} ${seat.result === "win" ? "poker-result-flourish" : ""}`}
          >
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
      <ConfettiBurst fireKey={confettiKey} big={bigWin} />
      <div className="container">
        <div className="game-room-topbar">
          <div>
            <Link to="/stoły" className="back-link">← Stoły na żywo</Link>
            <h1>Texas Hold'em</h1>
            <p className="table-subtitle">
              Do {botCount + 1} graczy · Blindy: {pokerState?.small_blind ?? 5}/{pokerState?.big_blind ?? 10} Ż
              {" · "}
              <DifficultyBadge value={difficulty} />
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
            <SoundToggle />
            <Link to="/stoły" className="btn btn-ghost btn-sm leave-table-btn">
              Opuść stół
            </Link>
          </div>
        </div>

        {/* Phase banner — re-animates on each phase change */}
        <div style={{ textAlign: "center", marginBottom: "1rem" }}>
          <span key={phase} className="poker-phase-banner poker-phase-banner--enter">
            {phaseLabel(phase)}
          </span>
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
                // Flop cards (0-2) cascade in; turn/river flip immediately.
                const delay = i < 3 ? i * 0.13 : 0;
                return (
                  <div
                    key={`community-${i}`}
                    className="poker-community-card poker-community-card--reveal"
                    style={{ animationDelay: `${delay}s` }}
                  >
                    <PlayingCard card={card} />
                  </div>
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
          {(pokerState?.pot ?? 0) > 0 && <PokerPotDisplay pot={pokerState!.pot} />}

          {/* Seats */}
          {seats.map((seat, idx) => renderSeat(seat, idx))}
        </div>

        {/* Action panel — only shown on human's turn */}
        {isSeated && isMyTurn && mySeat?.status !== "folded" && (
          <div className="poker-action-panel">
            <span className="panel-label">
              Twoja kolej — {mySeat?.chips ?? 0} Ż
              {toCall > 0 && ` · do wyrównania: ${toCall} Ż`}
            </span>
            <button
              type="button"
              className="btn btn-action btn-action--stand"
              onClick={() => {
                sound.play("fold");
                fold();
              }}
            >
              Pas (Fold)
            </button>
            {canCheck ? (
              <button
                type="button"
                className="btn btn-action"
                onClick={() => {
                  sound.play("check");
                  check();
                }}
              >
                Sprawdź (Check)
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-action"
                onClick={() => {
                  sound.play("chip");
                  call();
                }}
              >
                Wyrównaj {toCall > 0 ? toCall : callAmount} Ż
              </button>
            )}
            <div className="poker-raise-row">
              <div className="poker-raise-presets">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRaisePreset("min")}>
                  Min {minRaise} Ż
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRaisePreset("half_pot")}>
                  ½ puli
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRaisePreset("pot")}>
                  Pula
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRaisePreset("all_in")}>
                  All-in
                </button>
              </div>
              <div className="poker-raise-stepper">
                <button
                  type="button"
                  className="poker-raise-step"
                  aria-label="Zmniejsz stawkę"
                  onClick={() => {
                    sound.play("click");
                    setRaiseAmount((v) => Math.max(minRaise, v - raiseStep));
                  }}
                >
                  −
                </button>
                <input
                  type="number"
                  className="poker-raise-input"
                  value={raiseAmount}
                  min={minRaise}
                  max={maxRaise}
                  onChange={(e) =>
                    setRaiseAmount(
                      Math.max(minRaise, Math.min(maxRaise, Number(e.target.value) || minRaise)),
                    )
                  }
                />
                <button
                  type="button"
                  className="poker-raise-step"
                  aria-label="Zwiększ stawkę"
                  onClick={() => {
                    sound.play("click");
                    setRaiseAmount((v) => Math.min(maxRaise, v + raiseStep));
                  }}
                >
                  +
                </button>
              </div>
              <button
                type="button"
                className="btn btn-gold"
                onClick={() => {
                  sound.play("raise");
                  raise(raiseAmount);
                }}
                disabled={raiseAmount < minRaise}
              >
                Podbij do {raiseAmount} Ż
              </button>
            </div>
          </div>
        )}

        {/* Start hand button when waiting */}
        {canStartHand && (
          <div className="poker-action-panel">
            {!isSeated ? (
              <p style={{ color: "var(--text-muted)", margin: 0 }}>
                Dołącz do stołu — wybierz miejsce
              </p>
            ) : affordableBuyIns.length === 0 ? (
              <p style={{ color: "#ef4444", margin: 0 }}>
                Ten stół (blindy {pokerState?.small_blind ?? 5}/{pokerState?.big_blind ?? 10})
                wymaga buy-inu co najmniej {tableMinBuyin} Ż — masz {balance} Ż.
              </p>
            ) : (
              <>
                <span className="panel-label">
                  Wybierz buy-in i rozpocznij rozdanie (min. {tableMinBuyin} Ż)
                </span>
                <div className="poker-buyin-chips">
                  {POKER_BUY_INS.map((amount) => (
                    <button
                      key={amount}
                      type="button"
                      className={`casino-chip ${buyIn === amount ? "casino-chip--active" : ""}`}
                      disabled={amount > balance || amount < tableMinBuyin}
                      onClick={() => setBuyIn(amount)}
                    >
                      {amount}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="btn btn-gold btn-lg"
                  onClick={() => {
                    sound.play("chip");
                    startHand(buyIn, botCount);
                  }}
                  disabled={
                    buyIn > balance || buyIn < tableMinBuyin || statusLabel !== "Stół na żywo"
                  }
                >
                  Rozpocznij ({buyIn} Ż)
                </button>
              </>
            )}
          </div>
        )}

        {/* Showdown result */}
        {phase === "finished" && pokerState?.message && (
          <div className="poker-result-banner">
            {formatPokerMessage(pokerState.message)}
          </div>
        )}

        {error && (
          <p className="form-error" style={{ textAlign: "center", marginTop: "0.75rem" }}>
            {mapPokerError(error)}
          </p>
        )}
      </div>
    </div>
  );
}
