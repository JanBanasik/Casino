import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ConfettiBurst from "../components/ConfettiBurst";
import SoundToggle from "../components/SoundToggle";
import TableActionBanner from "../components/TableActionBanner";
import TableLayout from "../components/TableLayout";
import { LIVE_TABLES } from "../data/games";
import { useCountUp } from "../hooks/useCountUp";
import { sound } from "../lib/sound";
import { useDealAnimation } from "../hooks/useDealAnimation";
import { useAmbientTable } from "../hooks/useAmbientTable";
import { useAuth } from "../hooks/useAuth";
import { useGameSocket } from "../hooks/useGameSocket";
import { getWallet } from "../services/api";
import { DifficultyBadge } from "../components/DifficultyPicker";
import { useReportRoundActivity } from "../hooks/useGameActivity";
import type { Difficulty, LobbySeatPayload, SeatStatePayload } from "../types/api";

const CHIP_PRESETS = [10, 25, 50, 100, 500];

function cardRank(card: string): string {
  return card.slice(0, -1);
}

function canSplitHand(hand: string[], alreadySplit: boolean, balance: number, bet: number): boolean {
  if (alreadySplit || hand.length !== 2) return false;
  if (cardRank(hand[0]) !== cardRank(hand[1])) return false;
  return balance >= bet;
}

export default function GameTablePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const tableId = searchParams.get("table") ?? "default";
  const solo = searchParams.get("solo") === "1";
  const botCountParam = parseInt(searchParams.get("bots") ?? "0", 10);
  const difficulty = (searchParams.get("difficulty") ?? "medium") as Difficulty;

  const location = useLocation();
  const tableName = (location.state as { tableName?: string } | null)?.tableName;
  const minBet = (location.state as { minBet?: number } | null)?.minBet ?? 10;
  const botCount = solo ? 0 : (Number.isNaN(botCountParam) ? 0 : botCountParam);

  const { token } = useAuth();
  const navigate = useNavigate();
  const [balance, setBalance] = useState(0);
  const [bet, setBet] = useState(minBet);
  const [roundResult, setRoundResult] = useState<{
    label: string;
    net: number;
    type: "win" | "loss" | "draw";
    big: boolean;
  } | null>(null);
  const [confettiKey, setConfettiKey] = useState(0);
  const prevPhaseRef = useRef<string | undefined>(undefined);

  const tableMeta = LIVE_TABLES.find((t) => t.id === tableId);

  const {
    status,
    statusLabel,
    tableState,
    error,
    lastSeatAction,
    connect,
    sit,
    placeBet,
    hit,
    stand,
    double,
    split,
  } = useGameSocket(sessionId ?? null, tableId, solo, botCount, difficulty);

  const { pendingCards, dealingCards, revealingCards, isDealing, resetDeal } = useDealAnimation(tableState);

  const mySeatIndex = tableState?.my_seat_index ?? null;
  const isSeated = mySeatIndex !== null && mySeatIndex !== undefined;
  const roundPlaying = Boolean(
    tableState?.round_in_progress || tableState?.table_phase === "playing",
  );
  const waitingForRound = Boolean(tableState?.waiting_for_round);
  const tableIdle = !roundPlaying;

  // Bonus notifications stay hidden only while a hand is actually being played.
  useReportRoundActivity(roundPlaying);

  const seats: SeatStatePayload[] = useMemo(() => {
    if (tableState?.seats?.length) return tableState.seats;
    return [];
  }, [tableState]);

  const lobbySeats: (LobbySeatPayload | null)[] = useMemo(() => {
    const raw = tableState?.lobby_seats;
    if (raw?.length === 7) return raw;
    return Array.from({ length: 7 }, () => null);
  }, [tableState]);

  // Solo: strip decorative ambient bots the backend adds for atmosphere.
  const displayLobbySeats = useMemo(() => {
    if (!solo) return lobbySeats;
    return lobbySeats.map((s) => (s?.is_human ? s : null));
  }, [lobbySeats, solo]);

  const { ambientSeats, ambientDealerHand, isAmbientDealing } = useAmbientTable(
    tableIdle,
    displayLobbySeats,
    solo,
  );

  const humanSeatIndex = mySeatIndex ?? tableState?.human_seat_index ?? 0;
  const canPlay =
    roundPlaying &&
    tableState?.phase === "player_turn" &&
    tableState.active_seat_index === humanSeatIndex &&
    !waitingForRound;

  useEffect(() => {
    if (!token) navigate("/login", { state: { from: "/stoły" } });
  }, [token, navigate]);

  useEffect(() => {
    if (sessionId && token) connect();
  }, [sessionId, tableId, token, connect]);

  // Refresh the balance only on phase transitions (not on every card), and wait
  // for the animation to land before showing the settled amount — on a finished
  // round that means after the dealer reveal + result overlay (like roulette).
  const balancePhaseRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const phase = tableState?.phase;
    if (phase === balancePhaseRef.current) return;
    balancePhaseRef.current = phase;
    const delay = phase === "finished" ? 1500 : 400;
    const t = setTimeout(() => {
      getWallet().then((w) => setBalance(w.balance)).catch(() => undefined);
    }, delay);
    return () => clearTimeout(t);
  }, [tableState?.phase]);

  // Show win/loss overlay when round finishes — skip initial load snapshot
  useEffect(() => {
    const currentPhase = tableState?.phase;
    const prev = prevPhaseRef.current;
    prevPhaseRef.current = currentPhase;

    // Only show overlay when transitioning INTO "finished", not on initial load
    if (currentPhase !== "finished" || prev === "finished" || prev === undefined) return;
    if (!tableState?.message) return;

    const msg = tableState.message;
    const labelMap: Record<string, string> = {
      win: "Wygrana!", loss: "Przegrana", draw: "Remis",
      player_bust: "Fura!", dealer_bust: "Krupier ma furę!",
    };
    const mySeat = tableState.seats?.find((s) => s.seat_index === mySeatIndex);
    const net = (mySeat?.payout ?? 0) - (mySeat?.bet ?? 0);
    const type = net > 0 ? "win" : net < 0 ? "loss" : "draw";
    const big = net >= (mySeat?.bet ?? 0) * 2 || net >= 200;

    setRoundResult({ label: labelMap[msg] ?? msg, net, type, big });
    if (type === "win") {
      sound.play(big ? "bigwin" : "win");
      setConfettiKey((k) => k + 1);
    } else if (type === "loss") {
      sound.play("lose");
    } else {
      sound.play("draw");
    }
    const t = setTimeout(() => setRoundResult(null), 2600);
    return () => clearTimeout(t);
  }, [tableState?.phase, tableState?.message]);

  // Clear deal animation and stale cards when the table returns to idle.
  useEffect(() => {
    if (tableIdle) resetDeal();
  }, [tableIdle, resetDeal]);

  // Card-slide tick whenever new cards animate onto the felt.
  const prevDealCountRef = useRef(0);
  useEffect(() => {
    const count = dealingCards.size + revealingCards.size;
    if (count > prevDealCountRef.current) sound.play("deal");
    prevDealCountRef.current = count;
  }, [dealingCards, revealingCards]);

  // A bot acting plays a soft cue so the table feels alive.
  useEffect(() => {
    if (!lastSeatAction) return;
    sound.play(lastSeatAction.action === "STAND" ? "click" : "deal");
  }, [lastSeatAction]);

  function handlePlaceBet() {
    sound.play("chip");
    resetDeal();
    placeBet(bet);
  }

  function bannerContent(): { message: string; subMessage?: string; actions?: Parameters<typeof TableActionBanner>[0]["actions"] } {
    if (!isSeated) {
      return {
        message: "Wybierz wolne miejsce przy stole",
        subMessage: "Kliknij + na wybranym siedzeniu, aby dołączyć",
      };
    }
    if (waitingForRound) {
      return {
        message: "Czekasz na koniec bieżącej rundy",
        subMessage: "Usiądź wygodnie — zagrasz, gdy krupier zakończy rozdawanie",
      };
    }
    if (tableIdle) {
      return {
        message: "Postaw zakład, aby dołączyć do rundy",
        subMessage: `Minimalny zakład: ${tableMeta?.minBet ?? minBet} Ż`,
        actions: [
          {
            label: `Graj za ${bet} Ż`,
            onClick: handlePlaceBet,
            disabled: isDealing || statusLabel !== "Stół na żywo",
            variant: "gold" as const,
          },
        ],
      };
    }
    if (canPlay) {
      const activeHand = tableState?.player_hand ?? [];
      const handLen = activeHand.length;
      const alreadySplit = Boolean(tableState?.player_hands?.length);
      const currentBet = tableState?.bet ?? bet;
      const canDouble = handLen === 2 && balance >= currentBet;
      const canSplit = canSplitHand(activeHand, alreadySplit, balance, currentBet);
      const actions: Parameters<typeof TableActionBanner>[0]["actions"] = [
        { label: "Dobierz", onClick: hit, disabled: isDealing, variant: "action" as const },
        { label: "Pas", onClick: stand, disabled: isDealing, variant: "stand" as const },
      ];
      if (canDouble) {
        actions.push({
          label: `Podwój ×2 (${currentBet} Ż)`,
          onClick: double,
          disabled: isDealing,
          variant: "gold" as const,
        });
      }
      if (canSplit) {
        actions.push({
          label: `Split (${currentBet} Ż)`,
          onClick: split,
          disabled: isDealing,
          variant: "gold" as const,
        });
      }
      let subMessage = "Split niedostępny w tej wersji";
      if (alreadySplit) {
        subMessage = `Grasz rękę ${(tableState?.active_hand_index ?? 0) + 1} z ${tableState?.player_hands?.length ?? 2}`;
      } else if (canSplit && canDouble) {
        subMessage = "Para — możesz podzielić (split) lub podwoić stawkę";
      } else if (canDouble) {
        subMessage = "Podwój, aby podbić stawkę i dobrać dokładnie jedną kartę";
      } else if (canSplit) {
        subMessage = "Para — podziel rękę na dwie niezależne stawki";
      }
      return {
        message: alreadySplit ? "Twoja kolej — split" : "Twoja kolej — co robisz?",
        subMessage,
        actions,
      };
    }
    if (roundPlaying && tableState?.phase === "dealer_turn") {
      return {
        message: "Krupier rozgrywa swoją rękę…",
        subMessage: "Za chwilę zobaczysz wynik rundy",
      };
    }
    if (lastSeatAction && roundPlaying) {
      const name = lastSeatAction.display_name;
      const actMap: Record<string, string> = {
        HIT: "dobiera kartę",
        STAND: "pasuje",
        DOUBLE: "podwaja stawkę",
        SPLIT: "dzieli parę",
      };
      const act = actMap[lastSeatAction.action] ?? "gra";
      return {
        message: `${name} — ${act}`,
        subMessage:
          tableState?.active_seat_index === humanSeatIndex
            ? "Twoja kolej — możesz dobrać lub spasować"
            : "Obserwujesz rundę przy stole",
      };
    }
    if (roundPlaying) {
      return {
        message: "Trwa runda przy stole",
        subMessage:
          tableState?.active_seat_index != null
            ? `Kolej: miejsce ${(tableState.active_seat_index ?? 0) + 1}`
            : undefined,
      };
    }
    return { message: "Połączono ze stołem" };
  }

  const banner = bannerContent();

  return (
    <div className="game-room">
      <ConfettiBurst fireKey={confettiKey} big={roundResult?.big ?? false} />
      {roundResult && <RoundResultOverlay result={roundResult} />}
      <div className="game-room-topbar container">
        <div>
          <Link to="/stoły" className="back-link">← Stoły na żywo</Link>
          <h1>{tableName ?? tableMeta?.name ?? "Blackjack"}</h1>
          <p className="table-subtitle">
            {tableMeta?.dealerName ?? "Krupier"} · {solo ? "Gra solo" : `Do ${botCount + 1} graczy`}
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

      {status !== "connected" && !tableState && (
        <div className="table-connecting container">
          <span className="table-connecting__spinner" aria-hidden />
          <span>
            {status === "error" ? "Brak połączenia ze stołem…" : "Łączenie ze stołem…"}
          </span>
        </div>
      )}

      <div className="felt-container container">
        <TableLayout
          tableState={tableState}
          seats={seats}
          lobbySeats={displayLobbySeats}
          mySeatIndex={mySeatIndex}
          activeSeatIndex={tableState?.active_seat_index}
          pendingCards={pendingCards}
          dealingCards={dealingCards}
          revealingCards={revealingCards}
          hideDealerHole={roundPlaying && tableState?.phase === "player_turn"}
          canPickSeat={!isSeated && statusLabel === "Stół na żywo"}
          onPickSeat={sit}
          ambientSeats={ambientSeats}
          ambientDealerHand={ambientDealerHand}
          isAmbientDealing={isAmbientDealing}
        />

        <TableActionBanner
          message={banner.message}
          subMessage={banner.subMessage}
          actions={banner.actions}
        />

        {isSeated && tableIdle && !waitingForRound && (
          <div className="table-bet-chips">
            {CHIP_PRESETS.filter(
              (n) => n >= (tableMeta?.minBet ?? 1) && n <= (tableMeta?.maxBet ?? 10000),
            ).map((n) => (
              <button
                key={n}
                type="button"
                className={`casino-chip ${bet === n ? "casino-chip--active" : ""}`}
                onClick={() => {
                  sound.play("chip");
                  setBet(n);
                }}
              >
                {n}
              </button>
            ))}
          </div>
        )}

        {error && <p className="form-error table-error">{mapError(error)}</p>}
      </div>
    </div>
  );
}

function RoundResultOverlay({
  result,
}: {
  result: { label: string; net: number; type: "win" | "loss" | "draw"; big: boolean };
}) {
  const animated = useCountUp(Math.abs(result.net), result.label);
  const rounded = Math.round(animated);
  const amountStr =
    result.type === "draw"
      ? "Remis"
      : `${result.type === "win" ? "+" : "−"}${rounded.toLocaleString("pl-PL")} Ż`;
  return (
    <div className="round-result-overlay">
      <div
        className={`round-result-card ${result.big ? "round-result-card--jackpot" : ""}`}
      >
        <div className={`round-result-card__label round-result-card__label--${result.type}`}>
          {result.label}
        </div>
        <div className={`round-result-card__amount round-result-card__amount--${result.type}`}>
          {amountStr}
        </div>
      </div>
    </div>
  );
}

function mapError(code: string): string {
  const map: Record<string, string> = {
    seat_taken: "To miejsce jest już zajęte.",
    not_seated: "Najpierw wybierz miejsce przy stole.",
    round_in_progress: "Trwa runda — poczekaj na jej zakończenie.",
    insufficient_balance: "Niewystarczające saldo.",
    not_your_turn: "To nie twoja kolej.",
    double_not_allowed: "Podwojenie możliwe tylko przy dwóch kartach.",
    double_only_initial: "Podwojenie możliwe tylko przy dwóch kartach.",
    split_not_allowed: "Split możliwy tylko przy parze na dwóch kartach.",
  };
  return map[code] ?? code;
}
