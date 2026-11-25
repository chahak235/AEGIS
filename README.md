# AEGIS

**Security event processing, detection and incident management, built to be understood.**

AEGIS receives security events from applications (failed logins, denied requests, permission changes…),
finds suspicious patterns with **hand-written rules** and a **machine-learning model**, groups related
findings into **incidents**, and gives analysts a **web dashboard** to investigate and resolve them,
with every action recorded in an **append-only audit log**.

```text
 Application ──events──► API ──► stored ──► rules + ML ──► detections ──► incidents ──► analyst dashboard
   (or AEGIS itself)    (FastAPI)  (PostgreSQL)                              (grouped)     (React)
```

> **Honest status:** a working prototype with real tests, not a commercial SIEM.
> All ML numbers come from **synthetic** data (see [docs/ml-evaluation.md](docs/ml-evaluation.md)).
> Cloud hosting is documented but not yet deployed. Everything marked ✅ below runs and is tested.

---

## What works today

| Capability | Status | Where to read more |
|---|---|---|
| Event ingestion with validation, size limits and idempotent retries | ✅ | [docs/api.md](docs/api.md) |
| 5 detection rules (brute force, takeover, probing, permission change, request flood) | ✅ | [docs/detection-rules.md](docs/detection-rules.md) |
| ML-001 anomaly detector (Isolation Forest + extreme-value check) with evaluation report | ✅ | [docs/ml.md](docs/ml.md) |
| Correlation of detections into incidents, with severity escalation | ✅ | [docs/architecture.md](docs/architecture.md) |
| Incident workflow: status state machine, assignment, notes, resolution | ✅ | [docs/feature-guide.md](docs/feature-guide.md) |
| Append-only audit log enforced by a PostgreSQL trigger | ✅ | [docs/database.md](docs/database.md) |
| Login (Argon2 + JWT), analyst/admin roles, API keys for event senders | ✅ | [docs/auth.md](docs/auth.md) |
| Rate limiting (Redis or in-memory), JSON logs with request IDs, Prometheus metrics | ✅ | [docs/security.md](docs/security.md) |
| React + TypeScript dashboard (7 pages incl. an attack simulator) | ✅ | [docs/ui-rulebook.md](docs/ui-rulebook.md) |
| Docker images, Docker Compose stack, Grafana dashboard, GitHub Actions CI | ✅ written, ⏳ first run on GitHub | [docs/deployment.md](docs/deployment.md) |
| Hosting on Google Cloud Run + Vercel | ⏳ guide written, not deployed | [docs/deployment.md](docs/deployment.md) |
| Kubernetes, mobile app | 🔜 planned | [docs/roadmap.md](docs/roadmap.md) |

**Tests:** 143 backend tests (pytest) + 12 frontend tests (Vitest). See [docs/testing.md](docs/testing.md).

---

## Quick start (Windows, PowerShell)

Full step-by-step guide with explanations: **[docs/setup.md](docs/setup.md)**.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
copy backend\.env.example backend\.env      # then fill in DATABASE_URL and JWT_SECRET
cd backend
alembic upgrade head                         # create the tables
python -m app.cli create-user admin --role admin
uvicorn app.main:app --reload                # API on http://127.0.0.1:8000/docs
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev                                  # dashboard on http://localhost:5173
```

Or run everything in containers: `docker compose --profile app up -d --build` → http://localhost:8080.

---

## Technology and why each one is here

| Layer | Technology | Why (one line) |
|---|---|---|
| API | Python, **FastAPI**, Uvicorn | Automatic validation and interactive docs from type hints |
| Validation | **Pydantic** | Untrusted input is checked before any code touches it |
| Database | **PostgreSQL** (Neon in the cloud), **SQLAlchemy 2**, **Alembic** | Relational data with integrity rules; versioned schema changes |
| Detection | Pure-Python rules, **scikit-learn** Isolation Forest | Explainable rules first; ML adds coverage for unusual combinations |
| Security | **Argon2id**, **JWT** (PyJWT), API keys, **Redis** rate limiting | Industry-standard building blocks, each with tests for the failure cases |
| Frontend | **React 19**, **TypeScript**, Vite, React Router | Typed UI that consumes the typed API |
| Operations | **Docker**, Docker Compose, **Prometheus**, **Grafana**, **GitHub Actions** | Reproducible runs, observable behaviour, automatic checks |

Every choice, its alternatives and its trade-offs are explained in [docs/architecture.md](docs/architecture.md).

---

## Repository map

```text
backend/          FastAPI app (app/), database migrations (alembic/), tests (tests/)
frontend/         React + TypeScript dashboard
ml/               Synthetic data generator and model training script
infrastructure/   Prometheus and Grafana configuration
docs/             All documentation (start with docs/00-start-here.md)
.github/          CI workflow
docker-compose.yml
```

## Documentation

New here? Read in this order:

1. [00-start-here.md](docs/00-start-here.md): the big picture and a walk through the code
2. [glossary.md](docs/glossary.md): every technical word in one place
3. [architecture.md](docs/architecture.md): how the parts fit and why
4. [feature-guide.md](docs/feature-guide.md): use every feature, click by click

Reference: [product-plan](docs/product-plan.md) · [roadmap](docs/roadmap.md) · [setup](docs/setup.md) ·
[api](docs/api.md) · [database](docs/database.md) · [auth](docs/auth.md) · [security](docs/security.md) ·
[detection-rules](docs/detection-rules.md) · [ml](docs/ml.md) · [ml-evaluation](docs/ml-evaluation.md) ·
[integration](docs/integration.md) · [ui-rulebook](docs/ui-rulebook.md) · [testing](docs/testing.md) ·
[debugging](docs/debugging.md) · [deployment](docs/deployment.md) · [mcp](docs/mcp.md) ·
[interview-guide](docs/interview-guide.md) · [development-log](docs/development-log.md)

Rules for AI coding assistants working in this repo: [AGENTS.md](AGENTS.md).
