import { describe, expect, it } from "vitest";
import { errorMessage } from "./api";

describe("errorMessage", () => {
  it("uses a plain detail string", () => {
    expect(errorMessage({ detail: "Incident not found" }, 404)).toBe("Incident not found");
  });
  it("turns FastAPI validation errors into field: message", () => {
    const body = { detail: [{ loc: ["body", "outcome"], msg: "Input should be 'success', 'failure' or 'denied'" }] };
    expect(errorMessage(body, 422)).toBe("outcome: Input should be 'success', 'failure' or 'denied'");
  });
  it("falls back to the status code", () => {
    expect(errorMessage(null, 500)).toBe("Request failed (500)");
  });
});
