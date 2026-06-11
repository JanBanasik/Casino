import { useEffect, useState } from "react";
import { getGameConfig } from "../services/api";
import type { Difficulty } from "../types/api";

const DIFFICULTY_META: Record<
  Difficulty,
  { label: string; short: string; icon: string; hint: string }
> = {
  easy: { label: "Łatwy", short: "Łatwy", icon: "🍀", hint: "Boty grają losowo — dobre na rozgrzewkę" },
  medium: { label: "Średni", short: "Średni", icon: "🎯", hint: "Boty grają poprawną strategią" },
  hard: { label: "Trudny", short: "Trudny", icon: "🔥", hint: "Boty sterowane wytrenowanym modelem RL" },
};

const ORDER: Difficulty[] = ["easy", "medium", "hard"];

/** Format a multiplier the Polish way: 1 → "×1", 0.75 → "×0,75". */
function formatMult(n: number): string {
  const s = Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
  return `×${s}`;
}

/** Live payout multipliers from the backend (cached); falls back to neutral 1×. */
function useWinMultipliers(): Record<Difficulty, number> | null {
  const [m, setM] = useState<Record<Difficulty, number> | null>(null);
  useEffect(() => {
    getGameConfig()
      .then((c) =>
        setM({
          easy: c.win_multiplier_easy,
          medium: c.win_multiplier_medium,
          hard: c.win_multiplier_hard,
        }),
      )
      .catch(() => undefined);
  }, []);
  return m;
}

export default function DifficultyPicker({
  value,
  onChange,
  disabled = false,
}: {
  value: Difficulty;
  onChange: (d: Difficulty) => void;
  disabled?: boolean;
}) {
  const mult = useWinMultipliers();
  return (
    <div className="difficulty-picker" role="group" aria-label="Poziom przeciwników">
      <span className="difficulty-picker__label">Poziom przeciwników</span>
      <div className="difficulty-picker__options">
        {ORDER.map((d) => (
          <button
            key={d}
            type="button"
            disabled={disabled}
            className={`difficulty-chip difficulty-chip--${d} ${value === d ? "difficulty-chip--active" : ""}`}
            onClick={() => onChange(d)}
            title={DIFFICULTY_META[d].hint}
          >
            <span aria-hidden>{DIFFICULTY_META[d].icon}</span> {DIFFICULTY_META[d].label}
            {mult && <span className="difficulty-chip__mult">wygrane {formatMult(mult[d])}</span>}
          </button>
        ))}
      </div>
      <p className="difficulty-picker__hint">
        {DIFFICULTY_META[value].hint}
        {mult && ` · wygrane ${formatMult(mult[value])}`}
      </p>
    </div>
  );
}

export function DifficultyBadge({ value }: { value: Difficulty }) {
  const meta = DIFFICULTY_META[value];
  return (
    <span className={`difficulty-badge difficulty-badge--${value}`}>
      <span aria-hidden>{meta.icon}</span> {meta.short}
    </span>
  );
}
