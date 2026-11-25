# Testing: What Is Tested, How, and How to Run It

> **155 automated tests:** 143 backend (pytest) + 12 frontend (Vitest). CI runs all of them on every push.

## 1. Why so many tests?

A test is a small program that uses your code and **insists** on the result (`assert`). Run them after every change
and you know in seconds whether something that used to work broke ("regression").
In interviews, "how do you know it works?" → "here are the tests, including the ones proving it refuses what it should".

## 2. Kinds of tests in AEGIS

| Kind | What it checks | Needs a database? | Examples |
|---|---|---|---|
| **Unit** | One function's logic | No (milliseconds) | `test_rules.py`, `test_incident_lifecycle.py`, ML features, password hashing, rate limiter |
| **Integration / API** | Request → API → database → response | Yes (`@pytest.mark.db`) | `test_events.py`, `test_incidents.py`, `test_auth.py` |
| **End-to-end through the engine** | Events in → detections → incidents → audit | Yes | `test_detection_engine.py`, `test_audit.py`, `test_ml.py` (last test) |
| **Frontend unit** | Formatting, error messages, scenario shapes | No | `frontend/src/*.test.ts` |
| **Smoke (CI)** | The Docker stack starts and answers | Docker | `.github/workflows/ci.yml` → "Smoke test" |

## 3. What each file covers

| File | Tests | Highlights |
|---|---|---|
| `test_rules.py` | 21 | Window edges (exactly 5:00 vs 5:01), merging 7 failures into one group, out-of-order input, every rule positive AND negative |
| `test_incident_lifecycle.py` | 17 | Every allowed and forbidden status move, severity escalation and cap |
| `test_events.py` | 14 | Validation (bad outcome, bad type, no timezone, 8 KB limit), idempotent retry, readiness with a fake broken DB |
| `test_detection_engine.py` | 9 | 4 vs 5 failures, extending instead of duplicating, late events, retries not double-counting, **event saved even if detection crashes** |
| `test_detections_api.py` | 6 | Filters, evidence order, 404, rule catalogue |
| `test_incidents.py` | 16 | Correlation (same story → 1 incident, other account → separate, 3 hours later → new, resolved not reopened), every API rule |
| `test_audit.py` | 7 | Every action recorded in order; rejected changes leave no record; **PostgreSQL refuses UPDATE/DELETE** |
| `test_auth.py` | 26 | Forged, unsigned (`alg: none`), expired and garbage tokens; same error for unknown user vs wrong password; roles; deactivated user locked out mid-session; API keys send-only, shown once, revocable; AEGIS detects brute force on itself |
| `test_ratelimit_observability.py` | 14 | Limiter (memory AND Redis via fakeredis), fail-open, 429 + Retry-After, request IDs, JSON logs, metrics labels, CORS allow/deny |
| `test_ml.py` | 11 | Feature counts, model loads, few false alarms on unseen normal data, attacks caught, explanation honesty, self-disable on mismatched model, provenance saved |
| `test_stats.py` | 2 | Overview numbers move correctly; login required |

## 4. The test database (why tests never touch real data)

- Tests create and delete rows, so they use **`TEST_DATABASE_URL`**, a separate, throw-away database.
- `backend/tests/conftest.py`:
  - **refuses to start** if `TEST_DATABASE_URL` equals the real `DATABASE_URL`;
  - points the whole app at the test database;
  - runs all Alembic migrations on it (so migrations are tested too);
  - creates two test users (`test-admin`, `test-analyst`).
- No `TEST_DATABASE_URL`? Database tests are **skipped, loudly**: the reason is printed for each. The unit tests still run.
- Each test uses a fresh made-up account (`test-<uuid>`) and deletes everything it created afterwards.
- The ML detector is switched **off** for rule tests (so they test exact rule behaviour) and **on** for tests marked `@pytest.mark.ml`.

## 5. How to run

From the project folder, with the virtual environment active:

```powershell
python -m pytest                                   # everything
python -m pytest backend/tests/test_rules.py       # one file
python -m pytest -k "auth and expired"             # tests whose name matches
python -m pytest -x                                # stop at the first failure
python -m pytest --durations=5                     # show the 5 slowest tests
ruff check backend ml                              # lint
```

Clicking way: Cursor/VS Code → **Testing** panel (flask icon) → ▶ (needs the Python extension).

Frontend (in `frontend/`):

```powershell
npm test            # Vitest
npm run typecheck   # TypeScript compiler, no output files
npm run build       # what CI and Docker build
```

Expected: **143 passed** (with a test database) or **70 passed, 73 skipped** (without); frontend **12 passed**.

## 6. How a good test is written here

```python
def test_resolving_needs_a_resolution(actor):          # 1. the name says the rule
    five_failures(actor)                                # 2. Arrange: create the situation
    url = f"/api/v1/incidents/{incidents_for(actor)[0]['id']}"
    response = client.patch(url, json={"status": "resolved"})   # 3. Act
    assert response.status_code == 422                  # 4. Assert: one clear expectation
```

- **Arrange / Act / Assert** keeps tests readable.
- **Negative tests first for security:** proving the wrong person is refused matters more than proving the right one gets in.
- **Prove a test can fail:** break the code on purpose (e.g. change `>=` to `>`) and watch the test go red. This was done in Lesson 7.

## 7. Not yet tested (roadmap)

- **Load tests:** e.g. k6 or Locust, sending 1000 events/s and measuring p95 latency.
- **Browser end-to-end tests:** Playwright clicking through the dashboard.
- **Accessibility tests:** axe.
- **Chaos tests:** stop Redis or PostgreSQL mid-run in Docker. Today, these failures are covered by unit tests with fakes.

Real numbers from any of these will be recorded here, with the machine and method used.
