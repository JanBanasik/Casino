import type { LiveTable } from "../data/games";

interface LiveTableCardProps {
  table: LiveTable;
  onJoin: (table: LiveTable) => void;
  onJoinSolo?: (table: LiveTable) => void;
  joining?: boolean;
}

export default function LiveTableCard({ table, onJoin, onJoinSolo, joining }: LiveTableCardProps) {
  const freeSeats = table.seatsTotal - table.seatsTaken;

  return (
    <article className={`live-table-card ${table.featured ? "live-table-card--featured" : ""}`}>
      <div className="live-table-header">
        <div>
          <span className="live-badge live-badge--sm">LIVE</span>
          <h3>{table.name}</h3>
          <p className="live-dealer">{table.dealerName}</p>
        </div>
        <span className={`level-badge level-${table.dealerLevel}`}>
          {table.dealerLevel === "vip" ? "VIP" : table.dealerLevel === "hard" ? "PRO" : "STD"}
        </span>
      </div>

      <div className="seats-row">
        {Array.from({ length: table.seatsTotal }).map((_, i) => (
          <span
            key={i}
            className={`seat-dot ${i < table.seatsTaken ? "seat-dot--taken" : "seat-dot--free"}`}
          />
        ))}
      </div>
      <p className="seats-label">
        {table.seatsTaken}/{table.seatsTotal} graczy · {freeSeats} wolnych miejsc
      </p>

      <div className="live-table-meta">
        <span>Stawka {table.minBet}–{table.maxBet.toLocaleString("pl-PL")} Ż</span>
      </div>

      <div className="live-table-actions">
        <button
          type="button"
          className="btn btn-gold btn-block"
          disabled={joining}
          onClick={() => onJoin(table)}
        >
          {joining ? "Dołączanie…" : "Dołącz do stołu"}
        </button>
        {onJoinSolo && (
          <button
            type="button"
            className="btn btn-outline-gold btn-block"
            disabled={joining}
            onClick={() => onJoinSolo(table)}
          >
            Graj solo
          </button>
        )}
      </div>
    </article>
  );
}
