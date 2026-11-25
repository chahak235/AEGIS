# Roadmap: Step by Step, with Real Status

> ✅ done and tested · ⏳ written but not yet run end-to-end · 🔜 next · 💤 later / optional
> Rule: finish and test a step before starting the next one (see [AGENTS.md](../AGENTS.md)).

## Phase 0–1: Foundations ✅
- Python, virtual environment, Git, GitHub. Lessons 1–7 in `learning/` ✅
- First FastAPI app, health endpoint, first tests ✅

## Phase 2: Events in, safely stored ✅
- Event schema with validation: types, lengths, allowed outcomes, timezone required ✅
- PostgreSQL on Neon, SQLAlchemy models, Alembic migrations ✅
- Pagination, size limits, idempotent retries (`event_id`) ✅
- Tests on a separate test database; they refuse to touch the real one ✅

## Phase 3: Detection ✅
- Rule engine with a sliding-window matcher (O(n)) ✅
- AUTH-001, AUTH-002, ACCESS-001, ACCOUNT-001, API-001 with positive and negative tests ✅
- Deduplication: one growing detection instead of an alert flood ✅
- Detections API + rule catalogue ✅

## Phase 4: Incidents ✅
- Correlation (same account, active incident, within 1 hour) ✅
- Severity escalation when 3+ different rules fire ✅
- Status state machine, assignment, resolution, append-only notes ✅
- Append-only audit log enforced by a PostgreSQL trigger ✅

## Phase 5: Security ✅
- Users with Argon2id password hashes; JWT login; analyst/admin roles ✅
- API keys (hashed, shown once, revocable) for event senders ✅
- Rate limiting on login and event sending (Redis or in-memory fallback) ✅
- AEGIS records its own login attempts as events, so it detects attacks on itself ✅

## Phase 6: Machine learning ✅
- Synthetic data generator (normal + 5 attack kinds) ✅
- Features shared by training and live detection (no training/serving skew) ✅
- Isolation Forest + extreme-value check = ML-001; thresholds chosen on validation data ✅
- Evaluation report vs the rules baseline, with limitations ✅

## Phase 7: Dashboard ✅
- React + TypeScript: login, overview, incidents, incident detail, detections, events, simulator, admin ✅
- Verified end to end through the dev proxy ✅ (visual check in a browser: do it yourself, see the feature guide)

## Phase 8: Operations ⏳
- JSON logs with request IDs, Prometheus metrics, security headers, CORS ✅
- Dockerfiles, Docker Compose (app + monitoring profiles), Grafana dashboard ⏳ (needs Docker Desktop to run)
- GitHub Actions: lint, tests with PostgreSQL, frontend build, Docker build + smoke test ⏳ (runs on your next push)

## Phase 9: Deployment 🔜
1. Run the full stack locally with Docker Compose and click through it.
2. Backend → Google Cloud Run; database stays on Neon (or Cloud SQL).
3. Frontend → Vercel with `VITE_API_URL` set; add the Vercel address to `CORS_ORIGINS`.
4. Secrets in Google Secret Manager / Vercel environment variables.
5. Budget alert on the Google Cloud account.

Guide: [deployment.md](deployment.md).

## Phase 10: Hardening 🔜
- Run Alembic migrations as a separate job, not at every container start
- Background queue + worker for detection (Redis/RQ or Celery) so ingestion stays fast under load
- Refresh tokens, or httpOnly cookie sessions with CSRF protection
- Load test with k6 or Locust; record real numbers in `docs/testing.md`
- Per-IP rules (password spraying across many accounts)

## Phase 11: Advanced and optional 💤
- MCP server so AI assistants can query incidents (design in [mcp.md](mcp.md))
- Kubernetes (K3s / Docker Desktop's Kubernetes): deployments, probes, rollouts
- Feedback loop: analyst verdicts (false positive / true positive) → retraining data
- Mobile app (React Native) using the same API
