// Attack scenarios for the Simulator page. Each one builds the events a real
// application would send, so you can watch AEGIS detect them live.
// Pure functions: no network here, which makes them easy to test (scenarios.test.ts).

import type { NewEvent } from "./types";

export interface Scenario {
  id: string;
  name: string;
  story: string;
  expect: string[]; // detections we expect AEGIS to raise
  build: (actor: string, start: Date) => NewEvent[];
}

function at(start: Date, seconds: number): string {
  return new Date(start.getTime() + seconds * 1000).toISOString();
}

function event(actor: string, time: string, event_type: string, outcome: NewEvent["outcome"], resource: string): NewEvent {
  return { event_type, occurred_at: time, source: "simulator", actor_id: actor, outcome, resource };
}

export const SCENARIOS: Scenario[] = [
  {
    id: "brute-force",
    name: "Password guessing (brute force)",
    story: "Someone tries 8 wrong passwords for one account within a minute.",
    expect: ["AUTH-001", "ML-001"],
    build: (actor, start) =>
      Array.from({ length: 8 }, (_, i) => event(actor, at(start, i * 6), "auth.login.failed", "failure", "/login")),
  },
  {
    id: "account-takeover",
    name: "Account takeover",
    story: "4 failed logins, then a successful one, then the account gives itself new permissions.",
    expect: ["AUTH-002", "ACCOUNT-001"],
    build: (actor, start) => [
      ...Array.from({ length: 4 }, (_, i) => event(actor, at(start, i * 5), "auth.login.failed", "failure", "/login")),
      event(actor, at(start, 25), "auth.login.success", "success", "/login"),
      event(actor, at(start, 60), "account.permission.changed", "success", "/admin/roles"),
    ],
  },
  {
    id: "privilege-probing",
    name: "Privilege probing",
    story: "A logged-in account keeps trying admin pages it isn't allowed to open.",
    expect: ["ACCESS-001", "ML-001"],
    build: (actor, start) =>
      ["/admin", "/admin/users", "/admin/roles", "/admin/export", "/internal/keys", "/internal/config"].map(
        (resource, i) => event(actor, at(start, i * 8), "api.request", "denied", resource)),
  },
  {
    id: "normal",
    name: "Normal user (should stay quiet)",
    story: "Logs in once and browses a few pages. No alarm expected: this checks for false positives.",
    expect: [],
    build: (actor, start) => [
      event(actor, at(start, 0), "auth.login.success", "success", "/login"),
      ...["/api/v1/profile", "/api/v1/orders", "/api/v1/products", "/api/v1/cart"].map(
        (resource, i) => event(actor, at(start, 20 + i * 30), "api.request", "success", resource)),
    ],
  },
];

export function randomActor(): string {
  return `demo-${Math.random().toString(36).slice(2, 8)}`;
}
