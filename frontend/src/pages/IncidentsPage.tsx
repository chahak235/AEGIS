import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Empty, ErrorBox, Loading, PageHeader, Pager, SeverityBadge, StatusBadge } from "../components/ui";
import { timeAgo } from "../format";
import { useAsync } from "../useAsync";

const LIMIT = 25;

export function IncidentsPage() {
  // Filters live in the URL (?status=open&severity=high), so a filtered view can be bookmarked or shared.
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const severity = params.get("severity") ?? "";
  const actor = params.get("actor_id") ?? "";
  const offset = Number(params.get("offset") ?? 0);

  const incidents = useAsync(
    () => api.incidents({ status, severity, actor_id: actor, limit: LIMIT, offset }),
    [status, severity, actor, offset],
  );

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("offset");
    setParams(next);
  }

  return (
    <>
      <PageHeader title="Incidents" subtitle="Investigations, most recent activity first." />
      <div className="filters">
        <select value={status} onChange={(e) => setFilter("status", e.target.value)} aria-label="Status">
          <option value="">All statuses</option>
          {["open", "acknowledged", "investigating", "resolved", "closed"].map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={severity} onChange={(e) => setFilter("severity", e.target.value)} aria-label="Severity">
          <option value="">All severities</option>
          {["critical", "high", "medium", "low"].map((s) => <option key={s}>{s}</option>)}
        </select>
        <input placeholder="Account (exact)" defaultValue={actor} aria-label="Account"
          onKeyDown={(e) => e.key === "Enter" && setFilter("actor_id", (e.target as HTMLInputElement).value.trim())} />
      </div>

      {incidents.error && <ErrorBox message={incidents.error} onRetry={incidents.reload} />}
      {incidents.loading && !incidents.data && <Loading />}
      {incidents.data && incidents.data.length === 0 && <Empty>No incidents match these filters.</Empty>}
      {incidents.data && incidents.data.length > 0 && (
        <div className="card flush">
          <table>
            <thead>
              <tr><th>Severity</th><th>Incident</th><th>Status</th><th>Assigned</th><th>Last activity</th></tr>
            </thead>
            <tbody>
              {incidents.data.map((i) => (
                <tr key={i.id}>
                  <td><SeverityBadge severity={i.severity} /></td>
                  <td><Link to={`/incidents/${i.id}`}>{i.title}</Link></td>
                  <td><StatusBadge status={i.status} /></td>
                  <td>{i.assigned_to ?? <span className="muted">—</span>}</td>
                  <td title={i.last_seen}>{timeAgo(i.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {incidents.data && (
        <Pager offset={offset} limit={LIMIT} count={incidents.data.length}
          onChange={(o) => { const n = new URLSearchParams(params); n.set("offset", String(o)); setParams(n); }} />
      )}
    </>
  );
}
