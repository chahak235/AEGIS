import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Empty, ErrorBox, Loading, PageHeader, Pager } from "../components/ui";
import { formatTime } from "../format";
import { useAsync } from "../useAsync";

const LIMIT = 50;

export function EventsPage() {
  const [params, setParams] = useSearchParams();
  const actor = params.get("actor_id") ?? "";
  const type = params.get("event_type") ?? "";
  const offset = Number(params.get("offset") ?? 0);
  const events = useAsync(() => api.events({ actor_id: actor, event_type: type, limit: LIMIT, offset }), [actor, type, offset]);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("offset");
    setParams(next);
  }

  return (
    <>
      <PageHeader title="Events" subtitle="Raw facts as received, newest first." />
      <div className="filters">
        <input placeholder="Account (exact), then Enter" defaultValue={actor} aria-label="Account"
          onKeyDown={(e) => e.key === "Enter" && setFilter("actor_id", (e.target as HTMLInputElement).value.trim())} />
        <input placeholder="Event type, e.g. auth.login.failed" defaultValue={type} aria-label="Event type"
          onKeyDown={(e) => e.key === "Enter" && setFilter("event_type", (e.target as HTMLInputElement).value.trim())} />
      </div>
      {events.error && <ErrorBox message={events.error} onRetry={events.reload} />}
      {events.loading && !events.data && <Loading />}
      {events.data?.length === 0 && <Empty>No events match these filters.</Empty>}
      {events.data && events.data.length > 0 && (
        <div className="card flush">
          <table>
            <thead><tr><th>When</th><th>Type</th><th>Account</th><th>Resource</th><th>Outcome</th><th>Source</th></tr></thead>
            <tbody>
              {events.data.map((e) => (
                <tr key={e.id}>
                  <td>{formatTime(e.occurred_at)}</td>
                  <td><code>{e.event_type}</code></td>
                  <td>{e.actor_id}</td>
                  <td>{e.resource ?? "—"}</td>
                  <td><span className={`outcome-label ${e.outcome}`}>{e.outcome}</span></td>
                  <td className="muted">{e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {events.data && (
        <Pager offset={offset} limit={LIMIT} count={events.data.length}
          onChange={(o) => { const n = new URLSearchParams(params); n.set("offset", String(o)); setParams(n); }} />
      )}
    </>
  );
}
