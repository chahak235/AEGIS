import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Empty, ErrorBox, Loading, PageHeader, Pager, SeverityBadge, SourceBadge } from "../components/ui";
import { timeAgo } from "../format";
import { useAsync } from "../useAsync";

const LIMIT = 25;

export function DetectionsPage() {
  const [params, setParams] = useSearchParams();
  const rule = params.get("rule_code") ?? "";
  const source = params.get("source_type") ?? "";
  const offset = Number(params.get("offset") ?? 0);

  const rules = useAsync(() => api.rules(), []);
  const detections = useAsync(
    () => api.detections({ rule_code: rule, source_type: source, limit: LIMIT, offset }),
    [rule, source, offset],
  );

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("offset");
    setParams(next);
  }

  return (
    <>
      <PageHeader title="Detections" subtitle="Findings from rules and the ML model, newest first." />
      <div className="filters">
        <select value={rule} onChange={(e) => setFilter("rule_code", e.target.value)} aria-label="Rule">
          <option value="">All rules</option>
          {rules.data?.map((r) => <option key={r.code} value={r.code}>{r.code} · {r.name}</option>)}
        </select>
        <select value={source} onChange={(e) => setFilter("source_type", e.target.value)} aria-label="Source">
          <option value="">Rules and ML</option>
          <option value="rule">Rules only</option>
          <option value="ml">ML only</option>
        </select>
      </div>

      {detections.error && <ErrorBox message={detections.error} onRetry={detections.reload} />}
      {detections.loading && !detections.data && <Loading />}
      {detections.data?.length === 0 && <Empty>No detections match these filters.</Empty>}
      {detections.data && detections.data.length > 0 && (
        <div className="card flush">
          <table>
            <thead><tr><th>Rule</th><th>Severity</th><th>Account</th><th>Why</th><th>When</th></tr></thead>
            <tbody>
              {detections.data.map((d) => (
                <tr key={d.id}>
                  <td><strong>{d.rule_code}</strong><br /><SourceBadge source={d.source_type} /></td>
                  <td><SeverityBadge severity={d.severity} /></td>
                  <td>{d.actor_id}</td>
                  <td className="explanation">{d.explanation}</td>
                  <td title={d.window_end}>{timeAgo(d.window_end)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {detections.data && (
        <Pager offset={offset} limit={LIMIT} count={detections.data.length}
          onChange={(o) => { const n = new URLSearchParams(params); n.set("offset", String(o)); setParams(n); }} />
      )}

      <details className="card space-top">
        <summary><strong>Rule catalogue</strong>: what every code means</summary>
        <table>
          <thead><tr><th>Code</th><th>Name</th><th>Fires when</th><th>Severity</th></tr></thead>
          <tbody>
            {rules.data?.map((r) => (
              <tr key={r.code}>
                <td><strong>{r.code}</strong></td>
                <td>{r.name} {r.source_type === "ml" && <SourceBadge source="ml" />}</td>
                <td>{r.description}{r.source_type === "rule" && r.threshold > 1 &&
                  <span className="muted"> ({r.threshold}+ within {Math.round(r.window_seconds / 60)} min)</span>}</td>
                <td><SeverityBadge severity={r.severity} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
