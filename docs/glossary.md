# Glossary: Every Technical Word, in Plain English

> Alphabetical. "→" points to the doc that explains it in depth.

| Term | Plain-English meaning |
|---|---|
| **Alembic** | Tool that records every change to the database structure as a numbered step, so any database can be brought to the same shape. → database.md |
| **Alert fatigue** | When analysts get so many alarms they start ignoring them. AEGIS fights it with deduplication and incidents. |
| **Anomaly detection** | Finding things that are unusual compared with "normal", without a hand-written rule. → ml.md |
| **API** | A set of URLs one program calls to ask another program to do something. The "waiter" between programs. |
| **API key** | A long secret string a *system* (not a person) sends to prove who it is. → auth.md |
| **Argon2id** | A deliberately slow password-hashing algorithm, recommended by OWASP. → auth.md |
| **Audit log** | A permanent record of who did what, when. AEGIS's can't be edited (database trigger). |
| **Authentication / Authorization** | "Who are you?" (401 if unknown) / "Are you allowed?" (403 if not). |
| **Backoff (exponential)** | Waiting longer between each retry (1 s, 2 s, 4 s…) so a struggling server can recover. |
| **CI (Continuous Integration)** | Automatically running checks (lint, tests, builds) on every push. → GitHub Actions |
| **Container / image** | An image is a packaged app plus everything it needs; a container is a running copy of it. → Docker |
| **Correlation** | Deciding that several findings belong to the same story (same account, close in time). |
| **CORS** | Browser rule: a page may only call an API on another address if the API allows that page. |
| **CSP (Content-Security-Policy)** | Header telling the browser which scripts/styles may run on a page, limiting injected-script attacks. |
| **CSRF** | Attack where another site makes your browser send a request using your cookies. Relevant if tokens are moved into cookies. |
| **Dependency injection** | FastAPI prepares things a function needs (database session, current user) and passes them in (`Depends`). |
| **Detection** | A finding: "this group of events matches rule X". Has an explanation and evidence. |
| **Docker / Docker Compose** | Docker runs containers; Compose starts several containers together from one file. → deployment.md |
| **Endpoint / route** | One URL plus method, e.g. `POST /api/v1/events`. |
| **Event** | A record that something happened (a login, a denied request). A fact, not an opinion. |
| **F1, precision, recall** | Precision: share of alarms that were real. Recall: share of attacks caught. F1: their balance. → ml.md |
| **False positive / negative** | Alarm on something harmless / no alarm on a real attack. |
| **FastAPI** | Python library for building APIs, with automatic validation and docs from type hints. |
| **Feature (ML)** | A number describing something (e.g. "failed logins in 10 minutes") that a model reads. |
| **Foreign key** | A column that must point to an existing row in another table. The database enforces it. |
| **Grafana** | Tool that draws charts and dashboards from metrics. |
| **Hash** | One-way scramble of data. You can check a value against it but not reverse it. |
| **Health check (liveness / readiness)** | "Is the process alive?" / "Can it serve requests right now (database reachable)?" |
| **HTTP method** | The verb of a request: GET (read), POST (create), PATCH (change part), DELETE (remove). |
| **HTTP status code** | 3-digit result: 2xx success, 4xx caller's problem, 5xx server's problem. → api.md |
| **Idempotency** | Doing something twice has the same effect as once. AEGIS: same `event_id` → stored once. |
| **Incident** | An investigation grouping related detections, with status, assignee, notes and a conclusion. |
| **Index (database)** | A lookup structure that makes searching by certain columns fast, like a book's index. |
| **Isolation Forest** | ML algorithm that isolates unusual points with random splits; anomalies need fewer splits. → ml.md |
| **JSON / JSONB** | Text data format `{"key": "value"}` / PostgreSQL's binary JSON column type that can be searched. |
| **JWT** | Signed token holding claims (who, role, expiry). Readable by anyone, forgeable only with the secret. → auth.md |
| **Lint / linter (ruff)** | A tool that reads code and flags likely bugs and mess without running it. |
| **MCP** | Model Context Protocol: standard for letting AI assistants call tools. → mcp.md |
| **Metrics / Prometheus** | Numbers about the running system collected over time / the tool that collects them from `/metrics`. |
| **Middleware** | Code that runs around every request (AEGIS: request ID, logging, metrics, headers). |
| **Migration** | One recorded, repeatable change to the database structure. |
| **Modular monolith** | One deployable app, internally split into clean modules. The opposite of many microservices. |
| **ORM (SQLAlchemy)** | Lets you work with database rows as Python objects instead of writing SQL by hand. |
| **Pagination** | Returning results in pages (`limit`, `offset`) instead of everything at once. |
| **Pydantic** | Library that checks data against a description (types, lengths, allowed values). |
| **Rate limiting** | Allowing at most N requests per key in a time window; extra requests get 429. |
| **Redis** | Very fast in-memory data store; AEGIS uses it for shared rate-limit counters. |
| **Request ID** | A unique ID per request, returned in `X-Request-ID` and written on every log line of that request. |
| **Role (RBAC)** | Role-based access control: permissions come from your role (analyst, admin). |
| **Salt** | Random data mixed into a password hash so identical passwords get different hashes. |
| **Severity** | How urgent: low, medium, high, critical. |
| **SIEM** | Security Information and Event Management: professional tools doing what AEGIS does at scale (Splunk, Elastic, Sentinel). |
| **Sliding window** | Looking at events within a moving time span (e.g. any 5 minutes). → detection-rules.md |
| **SPA** | Single-page app: one HTML page; JavaScript switches the views (React Router). |
| **State machine** | A fixed set of states and allowed moves between them (incident statuses). |
| **Synthetic data** | Generated, made-up data with known labels. Useful but easier than real life. |
| **Training / serving skew** | When a model is trained on data computed differently from the data it sees live. A classic ML bug. |
| **Transaction** | A group of database changes that all happen or none do. |
| **Trigger (database)** | Code inside PostgreSQL that runs on insert/update/delete. AEGIS uses one to protect the audit log. |
| **TypeScript** | JavaScript plus types, checked before the code runs. |
| **UUID** | 128-bit random ID, practically unique and unguessable. |
| **Uvicorn** | The server program that listens on a port and passes requests to FastAPI. |
| **Validation** | Checking input before trusting it. |
| **Virtual environment (.venv)** | A private set of Python libraries for one project. |
| **z-score** | How many standard deviations a value is from the average. 3+ is already rare. |
