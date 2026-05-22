import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import TableActionBanner from "../components/TableActionBanner";
import TableLayout from "../components/TableLayout";
import { LIVE_TABLES } from "../data/games";
import { useDealAnimation } from "../hooks/useDealAnimation";
import { useAuth } from "../hooks/useAuth";
import { useGameSocket } from "../hooks/useGameSocket";
import { getWallet } from "../services/api";
import type { LobbySeatPayload, SeatStatePayload } from "../types/api";

const CHIP_PRESETS = [10, 25, 50, 100, 500];

function resultLabel(msg: string | null | undefined): string {
  const map: Record<string, string> = {
    win: "Wygrana!",
    loss: "Przegrana",
    draw: "Remis",
    player_bust: "Fura — przegrana",
    dealer_bust: "Krupier ma furę!",
  };
  return msg ? (map[msg] ?? msg) : "Koniec rundy";
}

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
    lastSeatAction,
    clearRetentionAlert,
    connect,
    sit,
    placeBet,
    hit,
    stand,
  } = useGameSocket(sessionId ?? null, tableId, solo, botCount);

  const { dealingCards, revealingCards, isDealing, resetDeal } = useDealAnimation(tableState);

  const mySeatIndex = tableState?.my_seat_index ?? null;
  const isSeated = mySeatIndex !== null && mySeatIndex !== undefined;
  const roundPlaying =
    tableState?.round_in_progress ||
    tableState?.table_phase === "playing" ||
    (tableState?.phase !== "idle" && tableState?.phase !== undefined && tableState?.phase !== "finished");
  const waitingForRound = Boolean(tableState?.waiting_for_round);
  const tableIdle = !roundPlaying && tableState?.table_phase !== "playing";

  const seats: SeatStatePayload[] = useMemo(() => {
    if (tableState?.seats?.length) return tableState.seats;
    return [];
  }, [tableState]);

  const lobbySeats: (LobbySeatPayload | null)[] = useMemo(() => {
    const raw = tableState?.lobby_seats;
    if (raw?.length === 7) return raw;
    return Array.from({ length: 7 }, () => null);
  }, [tableState]);

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

  useEffect(() => {
    getWallet().then((w) => setBalance(w.balance)).catch(() => undefined);
  }, [tableState]);

  function handlePlaceBet() {
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
      return {
        message: "Twoja kolej — co robisz?",
        subMessage: "Split niedostępny w tej wersji",
        actions: [
          { label: "Dobierz", onClick: hit, disabled: isDealing, variant: "action" as const },
          { label: "Pas", onClick: stand, disabled: isDealing, variant: "stand" as const },
        ],
      };
    }
    if (roundPlaying && tableState?.phase === "dealer_turn") {
      return {
        message: "Krupier rozgrywa swoją rękę…",
        subMessage: "Za chwilę zobaczysz wynik rundy",
      };
    }
    if (roundPlaying && tableState?.phase === "finished") {
      return {
        message: resultLabel(tableState.message),
        subMessage: "Postaw zakład, aby zagrać ponownie",
        actions: tableIdle
          ? undefined
          : [
              {
                label: `Graj za ${bet} Ż`,
                onClick: handlePlaceBet,
                disabled: isDealing || statusLabel !== "Stół na żywo",
                variant: "gold" as const,
              },
            ],
      };
    }
    if (lastSeatAction && roundPlaying) {
      const name = lastSeatAction.display_name;
      const act = lastSeatAction.action === "HIT" ? "dobiera kartę" : "pasuje";
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
      <div className="game-room-topbar container">
        <div>
          <Link to="/stoły" className="back-link">← Stoły na żywo</Link>
          <h1>{tableName ?? tableMeta?.name ?? "Blackjack"}</h1>
          <p className="table-subtitle">
            {tableMeta?.dealerName ?? "Krupier"} · {solo ? "Gra solo" : `Do ${botCount + 1} graczy`}
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
          lobbySeats={lobbySeats}
          mySeatIndex={mySeatIndex}
          activeSeatIndex={tableState?.active_seat_index}
          dealingCards={dealingCards}
          revealingCards={revealingCards}
          hideDealerHole={tableState?.phase === "player_turn"}
          canPickSeat={!isSeated && statusLabel === "Stół na żywo"}
          onPickSeat={sit}
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
                onClick={() => setBet(n)}
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

function mapError(code: string): string {
  const map: Record<string, string> = {
    seat_taken: "To miejsce jest już zajęte.",
    not_seated: "Najpierw wybierz miejsce przy stole.",
    round_in_progress: "Trwa runda — poczekaj na jej zakończenie.",
    insufficient_balance: "Niewystarczające saldo.",
    not_your_turn: "To nie twoja kolej.",
  };
  return map[code] ?? code;
}
