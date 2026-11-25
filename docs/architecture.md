# Architecture: How AEGIS Fits Together, and Why

> For each piece: **what it is**, **why we use it**, **what would happen without it**, **alternatives**, and **real-life use**.
> If a word is new, check [glossary.md](glossary.md).

---

## 1. The whole system on one page

```text
                       ┌──────────────────────────── Browser ───────────────────────────┐
                       │  React + TypeScript dashboard (frontend/)                       │
                       │  pages ──► src/api.ts ──(HTTPS + JWT)──┐                       │
                       └────────────────────────────────────────┼───────────────────────┘
                                                                │
  Other applications ──(HTTPS + X-API-Key)──┐                   │
                                            ▼                   ▼
                          ┌──────────────────────────────────────────────────┐
                          │ FastAPI backend (backend/app)                    │
                          │                                                  │
                          │  middleware: request ID · JSON log · metrics ·   │
                          │              security headers · CORS             │
                          │  auth: deps.py (JWT / API key / roles)           │
                          │  ratelimit.py ─────────────────────────► Redis   │
                          │                                                  │
                          │  api/v1/events ──► ingest.py ──► detection/engine│
                          │                                     │            │
                          │                     rules.py (5 rules)           │
                          │                     ml/detector.py (ML-001)      │
                          │                                     ▼            │
                          │                     incidents/correlation.py     │
                          │                                     │            │
                          │  api/v1/incidents, detections,      │  audit.py  │
                          │  users, stats, audit ◄──────────────┘            │
                          └──────────────────────┬───────────────────────────┘
                                                 │ SQLAlchemy (one session per request)
                                                 ▼
                             PostgreSQL: events · detections · detection_events ·
                             incidents · incident_notes · audit_logs · users · api_keys

   Prometheus ──scrapes /metrics──► Grafana dashboards          GitHub Actions: lint · tests · builds
```

## 2. One event's journey (the core flow)

1. **Arrives**: `POST /api/v1/events` with an `X-API-Key` (systems) or a login token (people).
2. **Middleware**:
   - gives the request an ID;
   - starts a timer;
   - after the response: writes one JSON log line and updates metrics.
3. **Who is sending?** `get_event_sender` checks the API key hash or the JWT → else **401**.
4. **Rate limit**: max 1200 events/minute per sender → else **429** with `Retry-After`.
5. **Validation**: Pydantic checks types, lengths, allowed values, timezone, 8 KB `details` limit → else **422**.
6. **Save**: `ingest.py` stores the event and **commits**. From here the event is safe, whatever happens next.
   - Retry with the same `event_id` → returns the stored one (**200**), saves nothing.
7. **Detect**: `engine.run_detection`:
   - loads this account's events from 10 min before to 10 min after;
   - runs every rule plus ML-001;
   - keeps matches that include the new event;
   - **creates or extends** detections (no duplicates).
8. **Correlate**: `correlation.correlate` puts each detection into the account's active incident (activity within 1 h),
   or opens a new one. It recomputes severity/title/reason and writes an audit record (actor `system`).
9. **One transaction**: detections + incident + audit records are committed together. If detection crashes:
   - this transaction is rolled back and the error is logged;
   - the event from step 6 is still saved.
10. **Response**: **201** with the stored event.

## 3. The building blocks

### Python + FastAPI + Uvicorn (the API)
- **What:**
  - Python runs the logic.
  - FastAPI turns Python functions into HTTP endpoints.
  - Uvicorn is the server that listens on a port and hands requests to FastAPI.
- **Why FastAPI:** type hints become validation **and** documentation (`/docs`) for free. It also has built-in dependency injection (`Depends`) for sessions and auth.
- **Without it:** we'd parse JSON, validate, write docs and wire authentication by hand in every endpoint.
- **Alternatives:**
  - Django REST Framework: batteries included, heavier.
  - Flask: minimal, more manual work.
  - Node/Express or Go: different language.
- **Real life:** Netflix, Uber and Microsoft use FastAPI for internal services.

### Pydantic (validation)
- **What:** describes data shapes. Anything that doesn't fit is refused with a clear message.
- **Why:** security systems must never trust input. Bad data stored today breaks detection tomorrow.
- **Without it:** typos like `"faliure"` get stored, and the rule that counts failures silently misses attacks.

### PostgreSQL + SQLAlchemy + Alembic (data)
- **What:**
  - PostgreSQL stores data in related tables.
  - SQLAlchemy lets Python talk to it.
  - Alembic versions the table structure.
- **Why PostgreSQL:**
  - The data is naturally linked (incident → detections → events).
  - We need *integrity*: foreign keys, unique keys, transactions.
  - JSONB gives flexibility for `details`.
  - Triggers can enforce rules even against buggy code (the audit log).
- **Without a relational DB:** links and "all-or-nothing" saves would have to be re-built by hand.
- **Alternatives:**
  - MySQL: similar.
  - MongoDB: flexible documents, weaker links.
  - Elasticsearch: excellent log search, used by real SIEMs, but heavier and not a source of truth.
- **Real life:** PostgreSQL is one of the most used databases in the world (Instagram, Reddit, Stripe).

### Rules + ML (detection)
- **Rules** (`detection/rules.py`) are pure functions: events in → matching groups out.
  - Exact, explainable, cheap.
  - Blind to anything nobody wrote a rule for.
- **ML-001** (`ml/detector.py`) learns what normal looks like and flags what's far from it.
  - Catches unusual combinations.
  - It's statistical, so it can be wrong.
- **Why both:** each covers the other's blind spot. The evaluation report shows this with numbers ([ml-evaluation.md](ml-evaluation.md)).
- **Real life:** every serious SIEM ships both (Splunk correlation searches + ML toolkit; Elastic rules + anomaly jobs).

### Correlation → incidents
- **What:** groups detections that tell one story into one incident.
- **The rule:** same account + incident still active + within 1 hour.
- **Why "same account" and not just "close in time":** two strangers failing to log in at 10:00 are two stories. Merging them would mislead the analyst.
- **Why not reopen resolved incidents:** an analyst already reached a conclusion. New activity is a new question.

### Audit log (append-only)
- **What:** who did what, when. It's written in the **same transaction** as the change it describes.
- **Why a database trigger:** application code can have bugs. A PostgreSQL trigger refuses UPDATE/DELETE on `audit_logs` whatever the app does.
- **Real life:** compliance standards (SOC 2, ISO 27001, PCI DSS) require tamper-resistant audit trails.

### Login, roles, API keys
- See [auth.md](auth.md).
- People log in with a password (stored as an Argon2 hash) and get a short-lived JWT.
- Systems use API keys that can only send events.
- Roles:
  - **analyst**: work incidents;
  - **admin**: plus users, keys and the full audit log.

### Redis (rate limiting)
- **What:** an in-memory data store, shared by all copies of the API.
- **Why:** rate limits must be counted in one place, or 3 API copies would allow 3× the limit.
- **Without Redis:** AEGIS falls back to per-process memory counting. That's correct for a single server, and documented as weaker for several.

### Observability
- **What:**
  - Request IDs, JSON log lines and Prometheus metrics (`/metrics`).
  - Grafana shows the metrics as charts.
- **Why:**
  - Logs answer "what happened to *this* request?".
  - Metrics answer "how is the system doing overall?".
- **Rule:** metric labels use route **templates** (`/incidents/{incident_id}`), never raw IDs. Otherwise every incident would create a new time series and overload Prometheus.

### React + TypeScript (dashboard)
- **What:** the analyst's screen.
  - React builds the UI from components.
  - TypeScript checks the code before it runs.
- **Why TypeScript:** `types.ts` mirrors the API's schemas. A typo like `incident.titel` fails the build instead of the demo.
- **Rule:** the frontend never decides security. It hides buttons for convenience; the backend refuses anyway.

### Docker, Compose, GitHub Actions (delivery)
- **Docker:** packages each part with everything it needs, so it runs the same everywhere.
- **Compose:** starts all parts together (database, Redis, API, dashboard, monitoring).
- **GitHub Actions:** on every push, runs the linter, all tests against a real PostgreSQL, the frontend build, and a smoke test of the whole stack.

## 4. Key design decisions (and their trade-offs)

| Decision | Chosen | Alternative | Why / trade-off |
|---|---|---|---|
| Shape of the backend | **Modular monolith** (one app, clear modules) | Microservices | Simpler to run, test and debug; modules can be split out later if measurements justify it |
| When detection runs | **Synchronously** right after saving | Queue + background worker | Simple and immediately consistent. Cost: the sender waits ~ms per event. Next step at scale: queue |
| Detection scope | **Per account** (actor_id) | Per IP, per resource | Clear stories. Misses attackers spreading guesses over many accounts (documented) |
| Duplicate alerts | **Extend** overlapping detections | New alert each time | Prevents alert fatigue. Two simultaneous requests could still race (documented) |
| Evidence links | **Link table** `detection_events` | JSON list of IDs | Foreign keys protect integrity; reverse lookups are indexed |
| Audit integrity | **DB trigger** | App code only | Survives app bugs. Deletion only with an explicit session switch (retention/tests) |
| Session model | **JWT in sessionStorage** | httpOnly cookie | Simple and stateless. Readable by page scripts, so no third-party scripts (see [security.md](security.md)) |
| ML model | **Isolation Forest + z-score** | Autoencoder, One-Class SVM | Fast, small, explainable. Trees don't extrapolate, so the z-score covers extremes |
| ID type | **UUID** | 1, 2, 3… | Unguessable, created without asking the database |

## 5. Code layout (backend)

```text
backend/app/
  main.py            builds the app: middleware, CORS, routers
  config.py          settings from environment variables
  db.py, deps.py     database connection; per-request session; auth dependencies
  models.py          all tables
  schemas.py         all request/response shapes
  security.py        Argon2, JWT, API keys
  ratelimit.py       sliding-window limiter (Redis / memory)
  observability.py   request IDs, JSON logs, metrics, /metrics
  audit.py           record(...) helper
  ingest.py          save event + run detection
  cli.py             create-user command
  detection/         rules.py · engine.py · catalogue.py
  incidents/         lifecycle.py · correlation.py
  ml/                features.py · detector.py · model/
  api/health.py, api/v1/*.py   the endpoints
```

The **pure-logic** files (`rules.py`, `lifecycle.py`, `features.py`) import nothing from the database. They're tested in milliseconds without one.
