import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { createRouletteSession, getWallet, rouletteSpin } from "../services/api";
import type { RouletteBetRequest } from "../services/api";
import type { RoulettePayoutItem, RouletteSpinResult } from "../types/api";

// European roulette — red numbers
const RED_NUMBERS = new Set([
  1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36,
]);

function getNumberColor(n: number): "green" | "red" | "black" {
  if (n === 0) return "green";
  return RED_NUMBERS.has(n) ? "red" : "black";
}

// European roulette wheel order (clockwise starting from 0)
const WHEEL_ORDER = [
  0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
  5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
];

const CHIP_VALUES = [5, 10, 25, 50, 100, 500];

interface Bet {
  position: string;
  betType: string;
  amount: number;
  label: string;
  number?: number;
  choice?: string;
}

// The betting grid rows — columns 1-36 in 3 rows (bottom to top)
// Row 1 (bottom): 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34
// Row 2 (middle): 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35
// Row 3 (top):    3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36
const GRID_ROWS = [
  [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
  [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
  [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
];

export default function RoulettePage() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [balance, setBalance] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedChip, setSelectedChip] = useState(10);
  const [bets, setBets] = useState<Bet[]>([]);
  const [spinning, setSpinning] = useState(false);
  const [wheelDeg, setWheelDeg] = useState(0);
  const [spinResult, setSpinResult] = useState<RouletteSpinResult | null>(null);
  const [resultVisible, setResultVisible] = useState(false);
  const [winningNumber, setWinningNumber] = useState<number | null>(null);
  const wheelRef = useRef<HTMLDivElement>(null);
  const currentDegRef = useRef(0);

  useEffect(() => {
    if (!token) navigate("/login", { state: { from: "/roulette" } });
  }, [token, navigate]);

  useEffect(() => {
    if (!token) return;
    getWallet().then((w) => setBalance(w.balance)).catch(() => undefined);
    createRouletteSession()
      .then((s) => setSessionId(s.id))
      .catch(() => undefined);
  }, [token]);

  const totalBet = bets.reduce((sum, b) => sum + b.amount, 0);

  function placeBet(position: string, betType: string, label: string, number?: number, choice?: string) {
    if (spinning) return;
    setBets((prev) => {
      const existing = prev.findIndex((b) => b.position === position);
      if (existing >= 0) {
        const updated = [...prev];
        updated[existing] = { ...updated[existing], amount: updated[existing].amount + selectedChip };
        return updated;
      }
      return [...prev, { position, betType, amount: selectedChip, label, number, choice }];
    });
  }

  function removeBet(position: string) {
    setBets((prev) => prev.filter((b) => b.position !== position));
  }

  function clearBets() {
    if (!spinning) setBets([]);
  }

  function betAmountAt(position: string): number {
    return bets.find((b) => b.position === position)?.amount ?? 0;
  }

  async function handleSpin() {
    if (!sessionId || bets.length === 0 || spinning) return;
    setSpinning(true);
    setResultVisible(false);
    setSpinResult(null);
    setWinningNumber(null);

    try {
      const betRequests: RouletteBetRequest[] = bets.map((b) => ({
        bet_type: b.betType,
        amount: b.amount,
        number: b.number,
        choice: b.choice,
      }));

      const result = await rouletteSpin(sessionId, betRequests);

      // Calculate wheel rotation
      const numberIndex = WHEEL_ORDER.indexOf(result.result);
      const degPerSlot = 360 / WHEEL_ORDER.length;
      const landingAngle = numberIndex * degPerSlot;
      // Spin 6+ full rotations then land
      const fullRotations = (Math.ceil(currentDegRef.current / 360) + 6) * 360;
      const finalDeg = fullRotations + (360 - landingAngle);
      currentDegRef.current = finalDeg;

      setWheelDeg(finalDeg);

      // After animation (4s), show result
      setTimeout(() => {
        setWinningNumber(result.result);
        setSpinResult(result);
        setResultVisible(true);
        setBalance(result.new_balance);
        setSpinning(false);
      }, 4200);
    } catch (e) {
      setSpinning(false);
    }
  }

  // Generate conic gradient for wheel
  const totalSlots = WHEEL_ORDER.length;
  const degPerSlot = 360 / totalSlots;
  const conicParts = WHEEL_ORDER.map((n, i) => {
    const color = getNumberColor(n);
    const cssColor = color === "red" ? "#c01818" : color === "green" ? "#1a7a30" : "#111";
    const start = i * degPerSlot;
    const end = start + degPerSlot;
    return `${cssColor} ${start.toFixed(2)}deg ${end.toFixed(2)}deg`;
  });
  const conicGradient = `conic-gradient(${conicParts.join(", ")})`;

  const resultColor = winningNumber !== null ? getNumberColor(winningNumber) : null;

  return (
    <div className="roulette-page">
      <div className="container">
        <div className="game-room-topbar">
          <div>
            <Link to="/stoły" className="back-link">← Stoły na żywo</Link>
            <h1 style={{ fontFamily: "var(--font-display)", margin: "0.25rem 0 0", fontSize: "1.75rem" }}>
              Ruletka Europejska
            </h1>
            <p className="table-subtitle">37 numerów · Min. zakład: 5 Ż</p>
          </div>
          <div className="game-room-stats">
            <div className="stat-pill">
              <span>Saldo</span>
              <strong>{balance.toLocaleString("pl-PL")} Ż</strong>
            </div>
            <div className="stat-pill">
              <span>Zakład</span>
              <strong style={{ color: totalBet > balance ? "#ef4444" : undefined }}>
                {totalBet} Ż
              </strong>
            </div>
          </div>
        </div>

        <div className="roulette-main-layout">
        {/* Wheel column */}
        <div className="roulette-wheel-container">
          <div className="roulette-wheel-wrapper">
            <div
              ref={wheelRef}
              className="roulette-wheel"
              style={{
                background: conicGradient,
                transform: `rotate(${wheelDeg}deg)`,
                transition: spinning ? "transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)" : "none",
              }}
            />
            {/* SVG number overlay — rotates with wheel */}
            <svg
              className="roulette-numbers-svg"
              viewBox="0 0 280 280"
              style={{
                transform: `rotate(${wheelDeg}deg)`,
                transition: spinning ? "transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)" : "none",
              }}
            >
              {WHEEL_ORDER.map((n, i) => {
                const angleDeg = (i * 360) / WHEEL_ORDER.length - 90;
                const rad = (angleDeg * Math.PI) / 180;
                const r = 108;
                const cx = 140 + r * Math.cos(rad);
                const cy = 140 + r * Math.sin(rad);
                const color = getNumberColor(n);
                const textColor = color === "red" ? "#ffffff" : "#ffffff";
                return (
                  <text
                    key={n}
                    x={cx}
                    y={cy}
                    textAnchor="middle"
                    dominantBaseline="central"
                    transform={`rotate(${angleDeg + 90}, ${cx}, ${cy})`}
                    fill={textColor}
                    fontSize="9"
                    fontWeight="700"
                    fontFamily="system-ui, sans-serif"
                    style={{ userSelect: "none", pointerEvents: "none" }}
                  >
                    {n}
                  </text>
                );
              })}
            </svg>
            <div className="roulette-ball-marker" />
          </div>

          <div className="roulette-result-display">
            {winningNumber !== null ? (
              <>
                <div className={`roulette-result-number roulette-result-number--${resultColor}`}>
                  {winningNumber}
                </div>
                <div className="roulette-result-label">
                  {resultColor === "red" ? "CZERWONE" : resultColor === "black" ? "CZARNE" : "ZERO"}
                </div>
              </>
            ) : (
              <div className="roulette-result-number" style={{ color: "var(--text-muted)", fontSize: "1.5rem" }}>
                {spinning ? "…" : "—"}
              </div>
            )}
          </div>
        </div>

        {/* Bets column */}
        <div>
        {/* Chip selector */}
        <div className="roulette-chip-selector">
          <span className="roulette-chip-selector-label">Żeton:</span>
          {CHIP_VALUES.map((v) => (
            <button
              key={v}
              type="button"
              className={`casino-chip ${selectedChip === v ? "casino-chip--active" : ""}`}
              onClick={() => setSelectedChip(v)}
              disabled={spinning}
            >
              {v}
            </button>
          ))}
        </div>

        {/* Betting grid */}
        <div className="roulette-grid-container">
          <div className="roulette-grid">
            {/* Zero */}
            <div
              className="roulette-cell roulette-cell--green"
              style={{ gridRow: "1 / 4", gridColumn: "1" }}
              onClick={() => placeBet("0", "straight", "0", 0)}
              onContextMenu={(e) => { e.preventDefault(); removeBet("0"); }}
              title="Kliknij prawym — usuń zakład"
            >
              0
              {betAmountAt("0") > 0 && (
                <div className="roulette-cell-chip">{betAmountAt("0")}</div>
              )}
            </div>

            {/* Numbers 1-36 in 3 rows */}
            {GRID_ROWS.map((row, rowIdx) =>
              row.map((n, colIdx) => {
                const color = getNumberColor(n);
                const pos = `n${n}`;
                const betAmt = betAmountAt(pos);
                return (
                  <div
                    key={n}
                    className={`roulette-cell roulette-cell--${color} ${winningNumber === n ? "roulette-cell--selected" : ""}`}
                    style={{ gridRow: rowIdx + 1, gridColumn: colIdx + 2 }}
                    onClick={() => placeBet(pos, "straight", String(n), n)}
                    onContextMenu={(e) => { e.preventDefault(); removeBet(pos); }}
                    title={`${n} — ${color === "red" ? "czerwone" : "czarne"}`}
                  >
                    {n}
                    {betAmt > 0 && <div className="roulette-cell-chip">{betAmt}</div>}
                  </div>
                );
              })
            )}
          </div>

          {/* Outside bets */}
          <div className="roulette-outside-bets" style={{ marginTop: "6px" }}>
            {[
              { pos: "dozen1", type: "dozen", label: "1-12", choice: "1st" },
              { pos: "dozen2", type: "dozen", label: "13-24", choice: "2nd" },
              { pos: "dozen3", type: "dozen", label: "25-36", choice: "3rd" },
            ].map((b) => (
              <div
                key={b.pos}
                className={`roulette-outside-bet roulette-outside-bet--dozen ${betAmountAt(b.pos) > 0 ? "roulette-outside-bet--selected" : ""}`}
                onClick={() => placeBet(b.pos, b.type, b.label, undefined, b.choice)}
                onContextMenu={(e) => { e.preventDefault(); removeBet(b.pos); }}
              >
                {b.label}
                {betAmountAt(b.pos) > 0 && (
                  <span style={{ marginLeft: "0.35rem", fontSize: "0.65rem" }}>
                    ({betAmountAt(b.pos)})
                  </span>
                )}
              </div>
            ))}
          </div>

          <div className="roulette-outside-bets" style={{ marginTop: "4px" }}>
            {[
              { pos: "low", type: "low_high", label: "1–18", choice: "low" },
              { pos: "even", type: "odd_even", label: "Parzyste", choice: "even" },
              { pos: "red", type: "red_black", label: "Czerwone", choice: "red" },
              { pos: "black", type: "red_black", label: "Czarne", choice: "black" },
              { pos: "odd", type: "odd_even", label: "Nieparzyste", choice: "odd" },
              { pos: "high", type: "low_high", label: "19–36", choice: "high" },
            ].map((b) => {
              let extraClass = "roulette-outside-bet--half";
              if (b.type === "color" && b.choice === "red") extraClass = "roulette-outside-bet--color-red";
              if (b.type === "color" && b.choice === "black") extraClass = "roulette-outside-bet--color-black";
              if (b.type === "parity") extraClass = "roulette-outside-bet--parity";
              const betAmt = betAmountAt(b.pos);
              return (
                <div
                  key={b.pos}
                  className={`roulette-outside-bet ${extraClass} ${betAmt > 0 ? "roulette-outside-bet--selected" : ""}`}
                  onClick={() => placeBet(b.pos, b.type, b.label, undefined, b.choice)}
                  onContextMenu={(e) => { e.preventDefault(); removeBet(b.pos); }}
                >
                  {b.label}
                  {betAmt > 0 && (
                    <span style={{ marginLeft: "0.35rem", fontSize: "0.65rem" }}>
                      ({betAmt})
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Controls */}
        <div className="roulette-controls" style={{ marginTop: "1rem" }}>
          <div className="roulette-bet-summary">
            Łączny zakład: <strong>{totalBet} Ż</strong>
            {totalBet > balance && (
              <span style={{ color: "#ef4444", marginLeft: "0.5rem" }}>
                (Niewystarczające saldo)
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: "0.65rem" }}>
            <button
              type="button"
              className="btn btn-outline-gold"
              onClick={clearBets}
              disabled={spinning || bets.length === 0}
            >
              Wyczyść
            </button>
            <button
              type="button"
              className="btn btn-gold btn-lg"
              onClick={handleSpin}
              disabled={spinning || bets.length === 0 || totalBet > balance || !sessionId}
            >
              {spinning ? "Kręcę…" : "ZAKRĘĆ"}
            </button>
          </div>
        </div>

        {/* Payout summary */}
        {resultVisible && spinResult && (
          <div
            className={`roulette-payout-toast ${spinResult.net >= 0 ? "roulette-payout-toast--win" : "roulette-payout-toast--loss"}`}
          >
            {spinResult.net >= 0
              ? `Wygrałeś ${spinResult.net.toLocaleString("pl-PL")} Ż!`
              : `Przegrano ${Math.abs(spinResult.net).toLocaleString("pl-PL")} Ż`}

            <div className="roulette-payout-list">
              {spinResult.payouts.map((p: RoulettePayoutItem, i: number) => (
                <div
                  key={i}
                  className={`roulette-payout-item ${p.won ? "roulette-payout-item--won" : "roulette-payout-item--lost"}`}
                >
                  <span>{p.bet_type}{p.won ? " ✓" : " ✗"}</span>
                  <span>{p.won ? `+${p.payout}` : `-${p.amount}`} Ż</span>
                </div>
              ))}
            </div>
          </div>
        )}
        </div>{/* end bets column */}
        </div>{/* end roulette-main-layout */}
      </div>
    </div>
  );
}
