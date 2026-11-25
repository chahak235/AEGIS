import { describe, expect, it } from "vitest";
import { SCENARIOS } from "./scenarios";

const start = new Date("2026-11-24T10:00:00Z");

describe("simulator scenarios", () => {
  it("each builds valid events for the given account", () => {
    for (const s of SCENARIOS) {
      const events = s.build("demo-x", start);
      expect(events.length).toBeGreaterThan(0);
      for (const e of events) {
        expect(e.actor_id).toBe("demo-x");
        expect(e.event_type).toMatch(/^[a-z]+(\.[a-z]+)+$/); // same pattern the API enforces
        expect(["success", "failure", "denied"]).toContain(e.outcome);
        expect(e.occurred_at.endsWith("Z")).toBe(true); // always with a timezone
      }
    }
  });

  it("brute force has enough failures for AUTH-001 (5 within 5 minutes)", () => {
    const events = SCENARIOS.find((s) => s.id === "brute-force")!.build("a", start);
    const failures = events.filter((e) => e.event_type === "auth.login.failed");
    const span = Date.parse(failures.at(-1)!.occurred_at) - Date.parse(failures[0].occurred_at);
    expect(failures.length).toBeGreaterThanOrEqual(5);
    expect(span).toBeLessThanOrEqual(5 * 60 * 1000);
  });

  it("account takeover ends failures with a success, then a permission change", () => {
    const types = SCENARIOS.find((s) => s.id === "account-takeover")!.build("a", start).map((e) => e.event_type);
    expect(types.indexOf("auth.login.success")).toBeGreaterThan(types.lastIndexOf("auth.login.failed"));
    expect(types.at(-1)).toBe("account.permission.changed");
  });

  it("the normal scenario expects no detections", () => {
    expect(SCENARIOS.find((s) => s.id === "normal")!.expect).toEqual([]);
  });
});
