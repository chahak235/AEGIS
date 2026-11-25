import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { ErrorBox, Loading, PageHeader, SeverityBadge, SourceBadge, StatusBadge, Empty } from "../components/ui";
import { formatTime, humanize, shortId, timeAgo } from "../format";
import type { IncidentDetail, IncidentStatus, Resolution } from "../types";
import { useAsync } from "../useAsync";

// The same state machine as backend/app/incidents/lifecycle.py.
// The backend is the real judge (it answers 409 to a forbidden move); this copy
// only decides which buttons to show, so analysts aren't offered moves that would fail.
const NEXT: Record<IncidentStatus, IncidentStatus[]> = {
  open: ["acknowledged", "investigating", "resolved"],
  acknowledged: ["investigating", "resolved"],
  investigating: ["resolved"],
  resolved: ["closed", "investigating"],
  closed: [],
};
const RESOLUTIONS: Resolution[] = ["true_positive", "false_positive", "benign", "duplicate"];

export function IncidentDetailPage() {
  const { id = "" } = useParams();
  const incident = useAsync(() => api.incident(id), [id]);
  const audit = useAsync(() => api.incidentAudit(id), [id]);

  if (incident.error) return <ErrorBox message={incident.error} onRetry={incident.reload} />;
  if (!incident.data) return <Loading />;
  const i = incident.data;
  const refresh = () => { incident.reload(); audit.reload(); };

  return (
    <>
      <p><Link to="/incidents">← All incidents</Link></p>
      <PageHeader
        title={i.title}
        subtitle={<>Incident {shortId(i.id)} · account <strong>{i.actor_id}</strong> · activity {formatTime(i.first_seen)} – {formatTime(i.last_seen)}</>}
        actions={<><SeverityBadge severity={i.severity} /><StatusBadge status={i.status} /></>}
      />

      <div className="grid detail">
        <div className="stack">
          <section className="card">
            <h2>Why these were grouped</h2>
            <p>{i.correlation_reason}</p>
            {i.resolution && (
              <p><strong>Conclusion:</strong> {humanize(i.resolution)}{i.resolution_note ? ` — ${i.resolution_note}` : ""}</p>
            )}
          </section>

          <section className="card">
            <h2>Detections ({i.detections.length})</h2>
            {i.detections.map((d) => (
              <div key={d.id} className="detection">
                <div className="row wrap">
                  <strong>{d.rule_code}</strong>
                  <SeverityBadge severity={d.severity} />
                  <SourceBadge source={d.source_type} score={d.anomaly_score} />
                  <span className="muted small">{d.event_count} events</span>
                </div>
                <p>{d.explanation}</p>
              </div>
            ))}
          </section>

          <section className="card">
            <h2>Timeline ({i.timeline.length} events)</h2>
            <ol className="timeline">
              {i.timeline.map((e) => (
                <li key={e.id} className={`outcome-${e.outcome}`}>
                  <span className="time">{formatTime(e.occurred_at)}</span>
                  <span className="event-type">{e.event_type}</span>
                  <span className="muted">{e.resource ?? ""}</span>
                  <span className={`outcome-label ${e.outcome}`}>{e.outcome}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <div className="stack">
          <Actions incident={i} onChanged={refresh} />
          <Notes incident={i} onAdded={refresh} />
          <section className="card">
            <h2>History</h2>
            {audit.error && <ErrorBox message={audit.error} />}
            <ul className="audit">
              {audit.data?.map((a) => (
                <li key={a.id}>
                  <span className="muted small">{timeAgo(a.occurred_at)}</span>{" "}
                  <strong>{a.actor}</strong> {humanize(a.action.replace("incident.", ""))}
                  {describeDetails(a.details)}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}

function describeDetails(details: Record<string, unknown>): string {
  if ("from" in details && "to" in details) return `: ${details.from ?? "nobody"} → ${details.to ?? "nobody"}`;
  if ("rule_code" in details) return ` (${details.rule_code})`;
  return "";
}

function Actions({ incident, onChanged }: { incident: IncidentDetail; onChanged: () => void }) {
  const { user } = useAuth();
  const [resolving, setResolving] = useState(false);
  const [resolution, setResolution] = useState<Resolution>("true_positive");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function change(changes: Parameters<typeof api.updateIncident>[1]) {
    setBusy(true);
    setError(null);
    try {
      await api.updateIncident(incident.id, changes);
      setResolving(false);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const next = NEXT[incident.status];
  return (
    <section className="card">
      <h2>Actions</h2>
      <p className="muted small">Assigned to: <strong>{incident.assigned_to ?? "nobody"}</strong></p>
      <div className="row wrap">
        {incident.assigned_to !== user?.username && incident.status !== "closed" && (
          <button className="btn" disabled={busy} onClick={() => change({ assigned_to: user!.username })}>Assign to me</button>
        )}
        {incident.assigned_to && incident.status !== "closed" && (
          <button className="btn" disabled={busy} onClick={() => change({ assigned_to: null })}>Unassign</button>
        )}
      </div>
      <div className="row wrap space-top">
        {next.filter((s) => s !== "resolved").map((s) => (
          <button key={s} className="btn" disabled={busy} onClick={() => change({ status: s })}>
            {incident.status === "resolved" && s === "investigating" ? "Reopen" : `Mark ${s}`}
          </button>
        ))}
        {next.includes("resolved") && !resolving && (
          <button className="btn primary" disabled={busy} onClick={() => setResolving(true)}>Resolve…</button>
        )}
        {next.length === 0 && <span className="muted">Closed incidents can't be changed.</span>}
      </div>
      {resolving && (
        <form className="stack space-top" onSubmit={(e: FormEvent) => { e.preventDefault(); change({ status: "resolved", resolution, resolution_note: note || undefined }); }}>
          <label>
            Conclusion
            <select value={resolution} onChange={(e) => setResolution(e.target.value as Resolution)}>
              {RESOLUTIONS.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}
            </select>
          </label>
          <label>
            What did you find? (optional)
            <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="row">
            <button className="btn primary" disabled={busy}>Resolve incident</button>
            <button type="button" className="btn" onClick={() => setResolving(false)}>Cancel</button>
          </div>
        </form>
      )}
      {error && <ErrorBox message={error} />}
    </section>
  );
}

function Notes({ incident, onAdded }: { incident: IncidentDetail; onAdded: () => void }) {
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addNote(incident.id, body);
      setBody("");
      onAdded();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Notes</h2>
      {incident.notes.length === 0 && <Empty>No notes yet.</Empty>}
      <ul className="notes">
        {incident.notes.map((n) => (
          <li key={n.id}>
            <div className="muted small"><strong>{n.author}</strong> · {formatTime(n.created_at)}</div>
            <div className="note-body">{n.body}</div>
          </li>
        ))}
      </ul>
      {incident.status !== "closed" && (
        <form onSubmit={add} className="stack">
          <textarea rows={3} placeholder="What did you check? What did you find?" value={body}
            onChange={(e) => setBody(e.target.value)} required maxLength={5000} aria-label="New note" />
          <button className="btn" disabled={busy || !body.trim()}>Add note</button>
          <p className="muted small">Notes are permanent: they can't be edited or deleted.</p>
        </form>
      )}
      {error && <ErrorBox message={error} />}
    </section>
  );
}
