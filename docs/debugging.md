# Debugging: How to Find and Fix Problems

> Start with the symptom table. Then learn the method (section 3): it works for problems no table lists.

## 1. Symptom → cause → fix

### Setup

| You see | Likely cause | Fix |
|---|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled` | Windows blocks scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once) |
| `ModuleNotFoundError: No module named 'fastapi'` | Virtual env not active | `.\.venv\Scripts\Activate.ps1` (look for `(.venv)` in the prompt) |
| `KeyError: 'DATABASE_URL'` | No `backend/.env` | Copy `backend/.env.example` to `.env` and fill it in |
| `JWT_SECRET is missing or shorter than 32 characters` | `.env` lacks a real secret | `python -c "import secrets; print(secrets.token_urlsafe(48))"`, paste as `JWT_SECRET=` |
| `Can't locate revision` / `relation "users" does not exist` | Database behind the code | `cd backend` then `alembic upgrade head` |
| Tests: `SKIPPED ... TEST_DATABASE_URL is not set` | No test database configured | [setup.md](setup.md) step 4 |
| Tests: `TEST_DATABASE_URL is the same as DATABASE_URL` | Safety stop | Point it at a separate database |

### Running

| You see | Likely cause | Fix |
|---|---|---|
| Dashboard: "Cannot reach the AEGIS API" | Backend not running | Start `uvicorn app.main:app --reload` in `backend/` |
| Dashboard keeps sending you to login | Token expired (30 min), or the user was deactivated | Log in again; check the user on Admin |
| 401 on every request in `/docs` | Not authorized | Click **Authorize** and log in |
| 403 | Your role can't do this | Admin-only endpoint; log in as an admin |
| 409 on PATCH incident | Move not allowed by the state machine | The message lists the allowed moves |
| 422 | Input failed validation | Read `detail`: it names the field (`occurred_at: Input should have timezone info`) |
| 429 | Rate limit | Wait `Retry-After` seconds |
| `/health/ready` → 503 | Database unreachable | Check Wi-Fi / Neon status / `DATABASE_URL` |
| ML-001 never fires; log says "ML model not available" | Model file missing, or a different scikit-learn version | `pip install -r backend/requirements.txt`; if features changed, `python ml/train.py` |
| A detection you expected is missing | Below threshold, or a different account | Check the rule catalogue; check exact `actor_id`; check times have a timezone |

### Docker

| You see | Fix |
|---|---|
| `Set POSTGRES_PASSWORD in .env` | Copy root `.env.example` → `.env` and fill it in |
| `/bin/sh^M: not found` in the api container | The script got Windows line endings: `.gitattributes` prevents it; re-checkout or convert to LF |
| Port already in use (5432/8000/8080) | Something else uses it: stop it, or change the left number in `ports:` |
| `docker compose logs api` shows `connection refused` to db | Database still starting: Compose waits for health; check `docker compose ps` |

## 2. Where to look

1. **The error message itself.** Read it all, bottom line first in Python tracebacks:
   - the **last line** is the error;
   - the lines above show the path through the code.
2. **The response:** status code + `detail`. In the browser: F12 → **Network** → click the request → Response.
3. **The request ID:** every response has `X-Request-ID`. Search the API's log for it; every log line of that request carries it.
4. **The API log:** the terminal running uvicorn (or `docker compose logs -f api`). One JSON line per request: method, route, status, duration.
5. **The database:** Neon console → **Tables**, or SQL:
   `select * from incidents order by created_at desc limit 5;`
6. **History:** the incident's **History** panel, or `GET /api/v1/audit` (admin) shows who changed what.
7. **Metrics:** Grafana shows when errors or latency started rising.

## 3. The method (works for any bug)

1. **Reproduce it** reliably. The smallest steps that make it happen. Write them down.
2. **Read the evidence:** message, status code, logs. Don't guess yet.
3. **Form one hypothesis** ("the timestamp has no timezone").
4. **Test it cheaply:** a print/log line, a single `pytest -k` test, one request in `/docs`.
5. **Fix the cause, not the symptom.**
6. **Write a test** that fails without your fix and passes with it, so the bug can never silently return.
7. **Write it down** in the development log if it taught you something.

## 4. Real bugs found while building AEGIS (and how)

| Bug | How it showed | Root cause | Fix |
|---|---|---|---|
| Audit records in random order | A test failed 1 run in 3 ("flaky") | PostgreSQL `now()` = transaction *start* time, so records in one transaction had identical timestamps | Ordering column `seq` that only increases |
| ML false alarms 7% live vs 1% in training | A test on unseen data | **Training/serving skew**: live code checked partial windows, training didn't | Training uses the live windowing function |
| Isolation Forest missed brute force (0%) | Evaluation table | Trees can't extrapolate beyond training values | Added an extreme-value (z-score) check |
| Unit tests took 4 minutes with no database | Timing | One "no-database" test logged in, which needs the database | Marked it `db` |
| Lint fix changed the ML training data | Re-ran training and compared metadata | Reordering two random-number calls changes the generated data | Restored the order; training is reproducible again |

## 5. Handy commands

```powershell
alembic current                                   # which migration is the DB on?
python -m pytest -x -k incident -vv               # verbose, stop at first failure
docker compose ps                                 # container status and health
docker compose logs -f api                        # follow the API's logs
curl.exe -i http://127.0.0.1:8000/health/ready    # quick health check with headers
```
