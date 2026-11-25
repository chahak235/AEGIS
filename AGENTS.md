# Rules for AI coding agents (and humans) working on AEGIS

These rules apply to any assistant (Claude, Copilot, Cursor…) that edits this repository.
They exist because AEGIS is a **learning project**: the owner must understand every change.

## 1. The non-negotiables

1. **No secrets in code. Ever.**
   - Passwords, API keys, tokens and database URLs live in `backend/.env` or the root `.env` (both git-ignored).
   - Only placeholders go into `*.env.example`.
   - Tests use clearly fake values (`test-only-secret-…`).
   - If a secret is ever committed, it must be **rotated** (changed), not just deleted: Git history keeps it.
2. **Ask before deleting anything**: files, database columns, tables, data, branches. Say what will be lost.
   Check first (e.g. "this column has 0 rows with a value"), and prefer reversible options.
3. **Run the tests before saying something works.**
   - Backend: `python -m pytest` from the project folder (database tests need `TEST_DATABASE_URL`).
   - Frontend: `npm run typecheck`, `npm test` and `npm run build` in `frontend/`.
   - Lint: `ruff check backend ml`.
   - Report failures honestly, with the output.
4. **Follow the roadmap order** in [docs/roadmap.md](docs/roadmap.md). Don't jump ahead to Kubernetes while the basics are broken.
5. **Never commit or push.** The owner commits and pushes themself. Hand over ready-to-paste
   `git add` / `git commit` / `git push` commands in small groups, one meaningful change each.
   Commit messages must not contain AI attribution lines.
6. **Tests never touch the real database.** They use `TEST_DATABASE_URL` only (see `backend/tests/conftest.py`).

## 2. How to make a change

1. Read the relevant doc in `docs/` and the code you are about to change.
2. Make the smallest change that solves the problem.
3. Add or update tests: a positive case AND a negative case (what must be refused).
4. Database change? Add an Alembic migration:
   - `alembic revision --autogenerate -m "..."`, then read the generated file;
   - name your constraints;
   - test `upgrade` → `downgrade -1` → `upgrade`.
5. Update the docs that describe the changed behaviour, and add a line to `docs/development-log.md`.
6. Explain the change in plain language: **what** it does, **why**, **what happens without it**, **alternatives**.

## 3. Code conventions

- **Python 3.12.** Type hints everywhere; Pydantic schemas for anything crossing the API boundary.
- **Pure logic is kept apart from the database** (`detection/rules.py`, `incidents/lifecycle.py`, `ml/features.py`),
  so it can be unit-tested without one.
- **Security decisions are made in the backend.** The frontend only hides buttons for convenience.
- **Every analyst/admin change** writes an audit record in the **same transaction** (`app/audit.py`).
- **Comments explain *why*, not *what*.** The owner is learning, so a short "why" next to anything non-obvious is welcome.
- **Frontend:** all API calls go through `src/api.ts`. Colours come from CSS variables in `src/styles.css`.
  Follow [docs/ui-rulebook.md](docs/ui-rulebook.md).

## 4. Where things are

| You want to… | Look in |
|---|---|
| Add an endpoint | `backend/app/api/v1/` + register it in `backend/app/main.py` |
| Add a detection rule | `backend/app/detection/rules.py` (+ tests in `backend/tests/test_rules.py`) |
| Change incident statuses | `backend/app/incidents/lifecycle.py` **and** `frontend/src/pages/IncidentDetailPage.tsx` |
| Change the database | `backend/app/models.py` + a new Alembic migration |
| Retrain the model | `python ml/train.py` (regenerates the model and `docs/ml-evaluation.md`) |
| Change who can do what | `backend/app/deps.py` (`any_user`, `admin_only`) + `docs/auth.md` |
