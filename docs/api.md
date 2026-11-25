# API Reference

> Live, clickable version: run the backend and open **http://127.0.0.1:8000/docs**.
> Click **Authorize**, log in, then **Try it out** on any endpoint.
> All bodies are JSON. All times are ISO 8601 **with a timezone** (`2026-11-24T10:00:00Z`).

## Who may call what

| Caller | How they prove it | Can use |
|---|---|---|
| Anyone | nothing | `/`, `/health/*`, `POST /api/v1/auth/login` |
| A system (event source) | header `X-API-Key: aeg_xxxx_...` | `POST /api/v1/events` only |
| Analyst | header `Authorization: Bearer <JWT>` | events, detections, rules, incidents, notes, stats |
| Admin | same, role `admin` | all of the above + users, API keys, full audit log |

**Errors (all endpoints):** `{"detail": "..."}`. Validation errors (422) list each bad field.

| Code | Meaning in AEGIS |
|---|---|
| 200 OK / 201 Created | Worked (201 = something new was stored) |
| 401 Unauthorized | Not logged in, bad/expired token, bad API key |
| 403 Forbidden | Logged in, but your role can't do this |
| 404 Not Found | No such ID |
| 409 Conflict | Valid request, but not allowed in the current state (e.g. `open` → `closed`, duplicate username) |
| 422 Unprocessable | Input failed validation |
| 429 Too Many Requests | Rate limit hit; wait `Retry-After` seconds |
| 503 Service Unavailable | `/health/ready` only: database unreachable |

Every response carries `X-Request-ID`. Quote it when reporting a problem: it finds the matching log lines.

## Health

| Method | Path | Returns |
|---|---|---|
| GET | `/health/live` | `{"status":"alive"}`: the process runs (never touches the DB) |
| GET | `/health/ready` | `{"status":"ready","database":"ok"}`, or **503** if the DB is unreachable |

## Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/v1/auth/login` | **form** fields `username`, `password` | `{"access_token","token_type":"bearer","expires_in":1800}` |
| GET | `/api/v1/auth/me` | | the logged-in user (never the hash) |

Login is rate-limited: 20 tries / 5 min per IP and 10 / 5 min per username.

## Events

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/events` | API key **or** login. 201 new, **200** if `event_id` already stored (safe retry). 1200/min per sender |
| GET | `/api/v1/events?actor_id=&event_type=&limit=50&offset=0` | newest first; `limit` 1–200 |
| GET | `/api/v1/events/{event_id}` | |

Event body:

```jsonc
{
  "event_type": "auth.login.failed",          // lowercase words joined by dots
  "occurred_at": "2026-11-24T10:00:01Z",      // timezone REQUIRED
  "source": "web-app",                        // 1-100 chars
  "actor_id": "user-123",                     // the account; 1-100 chars
  "resource": "/login",                       // optional, max 200
  "outcome": "failure",                       // success | failure | denied
  "details": {"ip": "10.0.0.5"},              // optional, max 8 KB as JSON
  "event_id": "8d1c4a6e-..."                  // optional UUID: makes retries safe
}
```

Event types the rules understand: `auth.login.failed`, `auth.login.success`, `account.permission.changed`, `api.request`.
Any `outcome: "denied"` counts for ACCESS-001.

## Detections and rules

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/detections?rule_code=&actor_id=&severity=&source_type=&limit=&offset=` | newest first; `source_type` = `rule` \| `ml` |
| GET | `/api/v1/detections/{id}` | plus `events`: the evidence, oldest first |
| GET | `/api/v1/rules` | the catalogue: code, name, description, severity, window, threshold, source |

## Incidents

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/incidents?status=&severity=&actor_id=&assigned_to=&limit=&offset=` | most recent activity first |
| GET | `/api/v1/incidents/{id}` | plus `detections`, `timeline` (all evidence, each event once), `notes` |
| PATCH | `/api/v1/incidents/{id}` | any of `status`, `assigned_to` (`null` = unassign), `resolution`, `resolution_note` |
| POST | `/api/v1/incidents/{id}/notes` | `{"body": "..."}` (1–5000 chars). 409 if the incident is closed |
| GET | `/api/v1/incidents/{id}/audit` | the incident's history, oldest first |

PATCH rules:
- `status` must follow the state machine, otherwise **409**. The message lists the allowed moves.
- `status: "resolved"` needs a `resolution` (`true_positive`, `false_positive`, `benign`, `duplicate`), otherwise **422**.
- A `resolution` without `status: "resolved"` → **422**.
- `assigned_to` must be an active user's username → else **422**.

```text
open ──► acknowledged ──► investigating ──► resolved ──► closed
  └──────────► investigating / resolved        └──► investigating (reopen)
```

## Stats

| GET | `/api/v1/stats` | incidents by status, active incidents by severity, detections (24 h) by rule, events (24 h), unassigned active incidents |
|---|---|---|

## Admin only

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/audit?actor=&action=&target_type=&target_id=&limit=&offset=` | the whole audit log, newest first |
| GET / POST | `/api/v1/users` | create: `{"username","password" (12+),"role"}`; 409 if taken |
| PATCH | `/api/v1/users/{id}` | `role`, `is_active`, `password`. You can't demote or deactivate yourself (409) |
| GET / POST | `/api/v1/api-keys` | create: `{"name"}` → the response contains `key` **once** |
| POST | `/api/v1/api-keys/{id}/revoke` | switches the key off permanently (kept for history) |

## Operations

| GET | `/metrics` | Prometheus format; hidden from `/docs`. Keep it on an internal network in production |
|---|---|---|
