import { describe, expect, it } from "vitest";
import { humanize, shortId, timeAgo } from "./format";

describe("timeAgo", () => {
  const now = new Date("2026-11-24T12:00:00Z");
  it("says 'just now' under a minute", () => {
    expect(timeAgo("2026-11-24T11:59:30Z", now)).toBe("just now");
  });
  it("counts minutes, hours and days", () => {
    expect(timeAgo("2026-11-24T11:55:00Z", now)).toBe("5 min ago");
    expect(timeAgo("2026-11-24T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2026-11-23T12:00:00Z", now)).toBe("1 day ago");
  });
  it("handles missing values", () => {
    expect(timeAgo(null, now)).toBe("—");
  });
});

describe("humanize", () => {
  it("turns codes into words", () => {
    expect(humanize("true_positive")).toBe("True positive");
    expect(humanize("incident.status_changed")).toBe("Incident status changed");
  });
});

it("shortId keeps the first 8 characters", () => {
  expect(shortId("1234567890abcdef")).toBe("12345678");
});
