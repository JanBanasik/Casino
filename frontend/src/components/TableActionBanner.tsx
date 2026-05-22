interface TableActionBannerProps {
  message: string;
  subMessage?: string;
  actions?: { label: string; onClick: () => void; disabled?: boolean; variant?: "gold" | "action" | "stand" }[];
}

export default function TableActionBanner({ message, subMessage, actions }: TableActionBannerProps) {
  return (
    <div className="table-action-banner" role="status" aria-live="polite">
      <p className="table-action-banner__text">{message}</p>
      {subMessage && <p className="table-action-banner__sub">{subMessage}</p>}
      {actions && actions.length > 0 && (
        <div className="table-action-banner__actions">
          {actions.map((a) => (
            <button
              key={a.label}
              type="button"
              className={`btn ${
                a.variant === "gold"
                  ? "btn-gold"
                  : a.variant === "stand"
                    ? "btn-action btn-action--stand"
                    : "btn-action"
              }`}
              onClick={a.onClick}
              disabled={a.disabled}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
