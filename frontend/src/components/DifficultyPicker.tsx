import type { Difficulty } from "../types/api";

const DIFFICULTY_META: Record<
  Difficulty,
  { label: string; short: string; icon: string; hint: string }
> = {
  easy: { label: "Łatwy", short: "Łatwy", icon: "🍀", hint: "Boty grają losowo — dobre na rozgrzewkę" },
  medium: { label: "Średni", short: "Średni", icon: "🎯", hint: "Boty grają poprawną strategią" },
  hard: { label: "Trudny", short: "Trudny", icon: "🔥", hint: "Boty sterowane modelem RL (liczą karty)" },
};

const ORDER: Difficulty[] = ["easy", "medium", "hard"];

export default function DifficultyPicker({
  value,
  onChange,
  disabled = false,
}: {
  value: Difficulty;
  onChange: (d: Difficulty) => void;
  disabled?: boolean;
}) {
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
          </button>
        ))}
      </div>
      <p className="difficulty-picker__hint">{DIFFICULTY_META[value].hint}</p>
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
