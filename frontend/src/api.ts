// The ONE place the dashboard talks to the backend.
// Pages never call fetch() themselves; they call api.something(). Benefits:
//  - the login token is attached in one place;
//  - errors are turned into readable messages in one place;
//  - when the backend address changes, only this file cares.

import type {
  ApiKey, AuditEntry, Detection, DetectionDetail, EventRecord, Incident, IncidentDetail,
  IncidentStatus, NewEvent, Note, Resolution, Role, Rule, Stats, User,
} from "./types";

// Empty in development (the Vite proxy forwards /api to the backend).
// In production, set VITE_API_URL to the hosted API address.
const BASE_URL: string = import.meta.env.VITE_API_URL ?? "";
const TOKEN_KEY = "aegis.token";

// Where the login token lives. sessionStorage is cleared when the browser tab
// closes. Trade-off: any script running on the page could read it, so the
// dashboard must never run untrusted scripts. (An httpOnly cookie hides the
// token from scripts but needs CSRF protection: documented in docs/security.md.)
let token: string | null = safeGet(TOKEN_KEY);
let onUnauthorized: () => void = () => {};

function safeGet(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function setToken(value: string | null): void {
  token = value;
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode): keep the token in memory only */
  }
}

export function hasToken(): boolean {
  return token !== null;
}

/** Called when the API says 401 (token missing/expired): the app logs out. */
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** FastAPI errors are {"detail": "text"} or {"detail": [{loc, msg}, ...]} for validation. */
export function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = (d.loc ?? []).filter((p) => p !== "body").join(".");
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

async function request<T>(method: string, path: string, body?: unknown, form?: URLSearchParams): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(BASE_URL + path, {
      method,
      headers,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the AEGIS API. Is the backend running?");
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    if (response.status === 401 && !path.endsWith("/auth/login")) onUnauthorized();
    throw new ApiError(response.status, errorMessage(data, response.status));
  }
  return data as T;
}

function query(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") q.set(key, String(value));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; expires_in: number }>(
      "POST", "/api/v1/auth/login", undefined, new URLSearchParams({ username, password })),
  me: () => request<User>("GET", "/api/v1/auth/me"),

  stats: () => request<Stats>("GET", "/api/v1/stats"),

  incidents: (p: { status?: string; severity?: string; actor_id?: string; assigned_to?: string; limit?: number; offset?: number }) =>
    request<Incident[]>("GET", "/api/v1/incidents" + query(p)),
  incident: (id: string) => request<IncidentDetail>("GET", `/api/v1/incidents/${id}`),
  updateIncident: (id: string, changes: { status?: IncidentStatus; assigned_to?: string | null; resolution?: Resolution; resolution_note?: string }) =>
    request<IncidentDetail>("PATCH", `/api/v1/incidents/${id}`, changes),
  addNote: (id: string, body: string) => request<Note>("POST", `/api/v1/incidents/${id}/notes`, { body }),
  incidentAudit: (id: string) => request<AuditEntry[]>("GET", `/api/v1/incidents/${id}/audit`),

  detections: (p: { rule_code?: string; actor_id?: string; severity?: string; source_type?: string; limit?: number; offset?: number }) =>
    request<Detection[]>("GET", "/api/v1/detections" + query(p)),
  detection: (id: string) => request<DetectionDetail>("GET", `/api/v1/detections/${id}`),
  rules: () => request<Rule[]>("GET", "/api/v1/rules"),

  events: (p: { actor_id?: string; event_type?: string; limit?: number; offset?: number }) =>
    request<EventRecord[]>("GET", "/api/v1/events" + query(p)),
  sendEvent: (event: NewEvent) => request<EventRecord>("POST", "/api/v1/events", event),

  users: () => request<User[]>("GET", "/api/v1/users"),
  createUser: (u: { username: string; password: string; role: Role }) => request<User>("POST", "/api/v1/users", u),
  updateUser: (id: string, changes: { role?: Role; is_active?: boolean }) =>
    request<User>("PATCH", `/api/v1/users/${id}`, changes),

  apiKeys: () => request<ApiKey[]>("GET", "/api/v1/api-keys"),
  createApiKey: (name: string) => request<ApiKey & { key: string }>("POST", "/api/v1/api-keys", { name }),
  revokeApiKey: (id: string) => request<ApiKey>("POST", `/api/v1/api-keys/${id}/revoke`),
};
