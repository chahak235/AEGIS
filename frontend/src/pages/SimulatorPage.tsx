import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, PageHeader, SeverityBadge, StatusBadge } from "../components/ui";
import { randomActor, SCENARIOS, type Scenario } from "../scenarios";
import type { Detection, Incident } from "../types";

interface Result {
  scenario: Scenario;
  actor: string;
  sent: number;
  detections: Detection[];
  incidents: Incident[];
}

export function SimulatorPage() {
  const [running, setRunning] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(scenario: Scenario) {
    const actor = randomActor(); // a fresh made-up account, so runs never mix
    const events = scenario.build(actor, new Date());
    setRunning(scenario.id);
    setResult(null);
    setError(null);
    try {
      for (let i = 0; i < events.length; i++) {
        await api.sendEvent(events[i]); // one by one, like a real application would
        setProgress(Math.round(((i + 1) / events.length) * 100));
      }
      const [detections, incidents] = await Promise.all([
        api.detections({ actor_id: actor }),
        api.incidents({ actor_id: actor }),
      ]);
      setResult({ scenario, actor, sent: events.length, detections, incidents });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(null);
      setProgress(0);
    }
  }

  return (
    <>
      <PageHeader title="Simulator"
        subtitle="Send realistic event sequences and watch AEGIS detect them. Each run uses a new made-up account." />
      <div className="grid two">
        {SCENARIOS.map((s) => (
          <div key={s.id} className="card">
            <h2>{s.name}</h2>
            <p>{s.story}</p>
            <p className="muted small">
              Expected: {s.expect.length ? s.expect.join(", ") : "no detections"}
            </p>
            <button className="btn primary" disabled={running !== null} onClick={() => run(s)}>
              {running === s.id ? `Sending… ${progress}%` : "Run scenario"}
            </button>
          </div>
        ))}
      </div>

      {error && <ErrorBox message={error} />}
      {result && (
        <section className="card space-top">
          <h2>Result: {result.scenario.name}</h2>
          <p>Sent {result.sent} events for account <code>{result.actor}</code>.</p>
          <h3>Detections ({result.detections.length})</h3>
          {result.detections.length === 0 ? <p className="muted">None, as expected for normal activity.</p> : (
            <ul className="list">
              {result.detections.map((d) => (
                <li key={d.id}><strong>{d.rule_code}</strong> <SeverityBadge severity={d.severity} /> {d.explanation}</li>
              ))}
            </ul>
          )}
          <h3>Incidents ({result.incidents.length})</h3>
          <ul className="list">
            {result.incidents.map((i) => (
              <li key={i.id}>
                <Link to={`/incidents/${i.id}`} className="list-link">
                  <SeverityBadge severity={i.severity} /> <span className="grow">{i.title}</span> <StatusBadge status={i.status} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
