// Small reusable building blocks. Using the same badge / error box everywhere
// keeps the app consistent (see docs/ui-rulebook.md).

import type { ReactNode } from "react";
import { humanize } from "../format";
import type { IncidentStatus, Severity } from "../types";

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  return <span className={`badge sev-${severity}`}>{humanize(severity)}</span>;
}

export function StatusBadge({ status }: { status: IncidentStatus | string }) {
  return <span className={`badge status-${status}`}>{humanize(status)}</span>;
}

export function SourceBadge({ source, score }: { source: "rule" | "ml"; score?: number | null }) {
  if (source === "ml") {
    return (
      <span className="badge source-ml" title="Found by the machine-learning model">
        ML{score != null ? ` · score ${score.toFixed(3)}` : ""}
      </span>
    );
  }
  return <span className="badge source-rule" title="Found by a hand-written rule">Rule</span>;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="muted pad" role="status">{label}</div>;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <strong>Something went wrong.</strong> {message}
      {onRetry && <button className="btn small" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

export function Pager({ offset, limit, count, onChange }: { offset: number; limit: number; count: number; onChange: (offset: number) => void }) {
  return (
    <div className="pager">
      <button className="btn small" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>← Newer</button>
      <span className="muted">Showing {count === 0 ? 0 : offset + 1}–{offset + count}</span>
      <button className="btn small" disabled={count < limit} onClick={() => onChange(offset + limit)}>Older →</button>
    </div>
  );
}
