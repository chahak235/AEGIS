# AEGIS Development Log

## Phase 0: Environment and repository
- Created Python virtual environment, Git repository, .gitignore, README.
- Initial commit pushed to GitHub (verified in Lesson 1).

## Phase 1, Lesson 1: First Python script
- Learned: terminal, current directory, what the Python interpreter does, what a virtual environment does.
- Implemented: learning/first_script.py (prints a message, an example event type, and the interpreter path).
- Verified: script runs using the interpreter inside .venv.
- Limitations: no tests yet; nothing AEGIS-specific is implemented.

## Phase 1, Lesson 2: Variables and data types
- Learned: variables, str/int/float/bool/None, comparison operators, f-strings.
- Implemented: learning/lesson2_types.py (an example event as variables, plus a threshold comparison).
- Verified: output matched the expected result.
- Debugging practised: TypeError (str + int), NameError (typo), assignment vs comparison.
- Limitations: values are hard-coded; no real event structure yet.

## Phase 1, Lesson 3: Conditions and string basics
- Learned: if/elif/else, indentation, and/or/not, .lower(), .startswith(), f-strings.
- Implemented: learning/lesson3_conditions.py (normalizes an event type, applies a threshold rule with a severity ladder).
- Verified: output matched the expected result.
- Limitations: one hard-coded event; no loops yet, so cannot process many events.

## Phase 1, Lesson 4: Lists and loops
- Learned: lists, indexing (including negative), len(), append(), for loops, enumerate, the counter pattern.
- Implemented: learning/lesson4_loops.py (counts failed logins across a list of events and applies a threshold).
- Verified: output matched the expected result (5 failures, detection raised).
- Limitations: counts all events together; ignores which account and time window, so it is not a real AUTH-001 yet.

## Phase 1, Lesson 5: Dictionaries
- Learned: dict key-value pairs, d[key] vs d.get(key, default), .items(), nested list of dicts, per-key counting.
- Implemented: learning/lesson5_dicts.py (events as dicts, failed logins counted per account, threshold rule applied per account).
- Verified: output matched the expected result (user-123 detected, user-456 not).
- Limitations: no timestamps, so no time window yet; data is still hard-coded.

## Phase 1, Lesson 6: Functions
- Learned: def, parameters vs arguments, return vs print, default and keyword arguments, docstrings, local scope.
- Implemented: learning/lesson6_functions.py (count_failed_by_actor, detect_repeated_failures returning explainable detection dicts, make_event helper).
- Verified: output matched the expected result.
- Limitations: no time window or timestamps; no automated tests yet (manual checking only).

## Phase 1, Lesson 7: Modules, packages and first tests
- Learned: modules vs packages, import forms, sys.path, pytest basics, assert, arrange/act/assert, boundary testing.
- Implemented: backend/app/rules.py (AUTH-001 simplified rule, helpers), backend/tests/test_rules.py (8 tests), pytest.ini, requirements-dev.txt.
- Verified: 8 tests pass. Deliberately introduced a >= to > bug; 2 tests failed as expected; bug reverted and all 8 passed again.
- Limitations: rule ignores timestamps and time windows; events are minimal dicts without validation.
- Later: rules.py was removed (commit 84d88f0) and test_rules.py disabled (commit d059448) while the API was being built. AUTH-001 will be rebuilt properly, with time windows, in the detection phase.

## Phase 4: First FastAPI application (commits 3ac098b – 1ca8582)
- Implemented: backend/app/main.py, home route, /health/live and /health/ready, event schema (Pydantic), POST/GET /api/v1/events, GET /api/v1/events/{id}, routers under /api/v1.
- Verified: pytest tests using FastAPI TestClient.
- Limitations at the time: events kept only in memory (lost on restart).

## Phase 5–6: PostgreSQL, SQLAlchemy and Alembic (commits b2704d6 – baa0d70)
- Implemented: Neon PostgreSQL connection (backend/app/db.py, secret in backend/.env), Event model with indexes on (actor_id, occurred_at) and (event_type, occurred_at), one session per request (deps.py), pagination (limit/offset), first Alembic migration cbf2b017960c creating the events table.
- Verified: 7 tests passing against the database.
- Limitations at the time: tests used the real database; see the review below.

## Review and hardening (commits c33fb71 – 9029029)
- Wrote docs/00-start-here.md: a full walkthrough of the code and a review listing 9 problems.
- Fixed:
  - occurred_at must include a timezone (AwareDatetime).
  - /health/ready runs SELECT 1 and answers 503 if the database is unreachable.
  - details limited to 8 KB.
  - Optional client event_id: a retried event is stored once (201 first time, 200 on retry).
  - Dropped the unused severity_hint column (migration 30fd34b8e04c; table had 0 rows, nothing lost).
  - Removed the duplicate root requirements-dev.txt.
  - Tests now use a separate database (TEST_DATABASE_URL), refuse to run without one, and apply Alembic migrations to it first. Added docker-compose.yml with a throw-away test PostgreSQL and backend/.env.example.
- Verified: 14 tests pass against a database other than DATABASE_URL; tests refuse to start when TEST_DATABASE_URL is missing.
- Limitations: whole-request size is not limited yet (only details); the Docker test database has not yet been run on this PC because Docker Desktop is not installed yet.

## Phase 8: Rule-based detection
- Implemented:
  - backend/app/detection/rules.py: 5 rules (AUTH-001, AUTH-002, ACCESS-001, ACCOUNT-001, API-001), a sliding-window (two-pointer) matcher, and an explanation sentence per rule.
  - backend/app/detection/engine.py: runs the rules after every new event, looking 10 min either side; extends an existing detection (same rule, account, overlapping time) instead of creating duplicates.
  - detections + detection_events tables (migration 68178dad4e86); evidence events cannot be deleted while a detection uses them.
  - GET /api/v1/detections (filters), GET /api/v1/detections/{id} (with evidence), GET /api/v1/rules.
  - Test setup: unit tests run without a database; database tests are marked `db` and skipped, with the reason shown, when TEST_DATABASE_URL is missing.
- Verified: 50 tests pass (21 rule unit tests, 9 engine tests, 6 API tests, 14 event tests). Without a test database: 22 pass, 28 skipped. Test runs leave no rows behind.
- Limitations: per-account rules only; dedup is not safe against two simultaneous requests; detection runs inside the web request; no API-002 yet. See docs/detection-rules.md section 8.

## Phase 9: Incidents and correlation
- Implemented:
  - incidents + incident_notes tables (migration f127a7e04de5);
  - correlation by account + active status + 1-hour window;
  - severity escalation when 3+ distinct rules fire;
  - status state machine (409 on invalid moves), assignment, resolution, append-only notes;
  - incidents API with timeline.
- Verified: lifecycle unit tests + 16 API tests.

## Phase 10: Audit log
- Implemented: audit_logs with a PostgreSQL trigger that refuses UPDATE and DELETE (migration 614add3979a4). Every analyst action and system action is recorded in the same transaction as the change.
- Bug found: a flaky test (1 in 3 runs) showed audit entries in random order. PostgreSQL's now() is the transaction START time, so entries written together tied. Fix: an identity `seq` column for exact ordering.

## Phase 11: Authentication and authorization
- Implemented:
  - users (Argon2id) and api_keys (SHA-256, shown once, revocable), migration 0f4cdd3c708d;
  - JWT login with fixed algorithm/issuer/audience and an active-user check on every request;
  - analyst/admin roles on whole routers;
  - create-user CLI.
- AEGIS records its own login attempts as events, so AUTH-001 detects brute force against AEGIS itself.
- Verified: 26 auth tests, mostly refusals (forged, unsigned, expired tokens; wrong roles; deactivated users; revoked keys).

## Phase 12: Rate limiting and observability
- Implemented:
  - sliding-window rate limiter (Redis, with in-memory fail-open fallback) on login and event sending;
  - request IDs, JSON logs, Prometheus metrics with route-template labels;
  - security headers and CORS.

## Phase 13–14: Machine learning (ML-001)
- Implemented:
  - synthetic generator (normal + 5 attack kinds);
  - shared feature extraction;
  - Isolation Forest + extreme-value check;
  - detection provenance columns (migration ae65ba2fb14c);
  - evaluation report (docs/ml-evaluation.md).
- Lessons found by evaluation:
  1. Isolation Forest alone caught 0% of brute force and scraping: trees can't extrapolate. Fix: add a z-score check.
  2. Live false alarms were 7% vs about 1% in training: training/serving skew in the windowing. Fix: training uses the live windowing function.
- Result on synthetic test data: ML-001 recall 0.907 at 0.9% false-positive rate; rules OR ML recall 0.944.

## Phase 15–16: Dashboard
- Implemented: React 19 + TypeScript dashboard with login, overview, incidents, incident detail (actions, notes, history), detections (+ rule catalogue), events, attack simulator, admin (users, API keys); stats endpoint.
- Verified:
  - typecheck, 12 Vitest tests, production build;
  - end-to-end scenarios through the dev proxy (takeover → AUTH-002 + ACCOUNT-001 + one incident; normal user → no detections).
- Not yet done: a visual check in a real browser.

## Phase 17–19: Delivery (written, first run pending)
- Implemented:
  - Dockerfiles (non-root API, two-stage nginx dashboard);
  - Docker Compose profiles (app, monitoring);
  - Prometheus + provisioned Grafana dashboard;
  - GitHub Actions CI (ruff, pytest with PostgreSQL, alembic check, frontend build, Docker smoke test);
  - ruff lint config;
  - .gitattributes for LF scripts.
- Limitation: Docker wasn't installed on the development PC, so the images and Compose stack have not been run yet; CI will run them on the next push.

## Documentation
- Added:
  - product-plan, roadmap, architecture, database, api, auth, security;
  - ml, ui-rulebook, feature-guide, integration, testing, debugging;
  - deployment, mcp (design), glossary, interview-guide;
  - AGENTS.md / CLAUDE.md;
  - a rewritten README and setup guide.
