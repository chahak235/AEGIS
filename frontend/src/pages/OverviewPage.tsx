import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Loading, PageHeader, SeverityBadge, StatusBadge, Empty } from "../components/ui";
import { timeAgo } from "../format";
import type { Severity } from "../types";
import { useAsync } from "../useAsync";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

export function OverviewPage() {
  const stats = useAsync(() => api.stats(), []);
  const recent = useAsync(() => api.incidents({ status: "open", limit: 5 }), []);

  if (stats.error) return <ErrorBox message={stats.error} onRetry={stats.reload} />;
  if (!stats.data) return <Loading />;
  const s = stats.data;
  const active = SEVERITIES.reduce((sum, sev) => sum + (s.active_incidents_by_severity[sev] ?? 0), 0);
  const ruleCounts = Object.entries(s.detections_last_24h_by_rule).sort((a, b) => b[1] - a[1]);
  const maxRule = Math.max(1, ...ruleCounts.map(([, n]) => n));

  return (
    <>
      <PageHeader title="Overview" subtitle="What needs attention right now." />

      <section className="grid stats">
        <div className="card stat">
          <div className="muted">Active incidents</div>
          <div className="stat-number">{active}</div>
          <div className="row wrap">
            {SEVERITIES.map((sev) => (s.active_incidents_by_severity[sev] ?? 0) > 0 && (
              <span key={sev}><SeverityBadge severity={sev} /> {s.active_incidents_by_severity[sev]}</span>
            ))}
          </div>
        </div>
        <div className="card stat">
          <div className="muted">Unassigned (active)</div>
          <div className="stat-number">{s.unassigned_active_incidents}</div>
          <Link to="/incidents?status=open">Open the queue →</Link>
        </div>
        <div className="card stat">
          <div className="muted">Events received (24 h)</div>
          <div className="stat-number">{s.events_last_24h}</div>
          <Link to="/events">Browse events →</Link>
        </div>
      </section>

      <section className="grid two">
        <div className="card">
          <h2>Newest open incidents</h2>
          {recent.error && <ErrorBox message={recent.error} />}
          {recent.data?.length === 0 && <Empty>No open incidents. Try the Simulator to create some.</Empty>}
          <ul className="list">
            {recent.data?.map((i) => (
              <li key={i.id}>
                <Link to={`/incidents/${i.id}`} className="list-link">
                  <SeverityBadge severity={i.severity} />
                  <span className="grow">{i.title}</span>
                  <span className="muted small">{timeAgo(i.last_seen)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Detections in the last 24 h</h2>
          {ruleCounts.length === 0 && <Empty>No detections in the last 24 hours.</Empty>}
          {ruleCounts.map(([rule, n]) => (
            <div key={rule} className="bar-row">
              <Link to={`/detections?rule_code=${rule}`} className="bar-label">{rule}</Link>
              <div className="bar"><div style={{ width: `${(n / maxRule) * 100}%` }} /></div>
              <span className="bar-value">{n}</span>
            </div>
          ))}
          <h2 className="space-top">Incidents by status</h2>
          <div className="row wrap">
            {Object.entries(s.incidents_by_status).map(([status, n]) => (
              <Link key={status} to={`/incidents?status=${status}`}><StatusBadge status={status} /> {n}</Link>
            ))}
            {Object.keys(s.incidents_by_status).length === 0 && <span className="muted">No incidents yet.</span>}
          </div>
        </div>
      </section>
    </>
  );
}
