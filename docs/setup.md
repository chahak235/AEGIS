# Setup: Run AEGIS on Your Own Computer (Windows)

> **Goal:** from a fresh Windows PC to "the app runs, I can log in, and all tests pass".
> Wherever possible, the clicking way is shown first. Terminal commands are for PowerShell inside Cursor (**Terminal → New Terminal**).
> Want everything in containers instead? See [deployment.md](deployment.md) §2.

---

## What you need installed

| Tool | What it is | Why AEGIS needs it | Check it is installed |
|---|---|---|---|
| **Python 3.12** | The language of the backend | Runs the API, tests, ML training | `python --version` |
| **Node.js 22** (+ npm) | JavaScript runtime | Builds and runs the dashboard | `node --version` |
| **Git** | Saves versions of your code | History, and uploading to GitHub | `git --version` |
| **Cursor** (or VS Code) | Code editor | Editing, built-in terminal, Git buttons, Testing panel | open it |
| **Docker Desktop** | Runs software in "containers" | Test database (and, optionally, the whole stack) | shows **Engine running** |
| **A Neon account** | PostgreSQL in the cloud, free tier | The **real** database for the app | console.neon.tech |

---

## 1. Get the code

**Clicking way:** Cursor → **File → Open Folder → `D:\AEGIS`**.
Fresh PC: Cursor start screen → **Clone repo** → `https://github.com/chahak235/AEGIS.git`.

## 2. Backend libraries (Python virtual environment)

```powershell
python -m venv .venv
```
```powershell
.\.venv\Scripts\Activate.ps1
```
```powershell
pip install -r backend\requirements-dev.txt
```

- **Virtual environment (`.venv`):** a private folder of libraries just for this project.
  - *Why:* projects need different library versions. *Without it:* versions clash ("works on my PC").
  - *Alternatives:* `uv`, `poetry`, `conda`.
- Your prompt starts with `(.venv)` once it's active. Activate again in every new terminal.
- `requirements-dev.txt` = what the app needs (`requirements.txt`) + test tools (pytest, httpx, fakeredis, ruff).

## 3. Secrets: `backend/.env`

1. In Cursor's file list, copy `backend/.env.example` and name the copy `backend/.env`.
2. `DATABASE_URL`: Neon → your project → **Connect** → copy the connection string.
3. `JWT_SECRET`: a long random value. Generate one:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
4. `TEST_DATABASE_URL`: see step 5.

`.env` is git-ignored: it never reaches GitHub. `.env.example` is committed, so it holds placeholders only.

## 4. Create the tables and your admin account

```powershell
cd backend
```
```powershell
alembic upgrade head
```
```powershell
python -m app.cli create-user admin --role admin
```

- `alembic upgrade head` applies every database change not yet in your Neon database. It's safe to repeat.
- `create-user` asks for a password twice, without showing it on screen (12+ characters).

## 5. A separate test database

Tests create and delete data, so they must **never** run against the real database.
- `TEST_DATABASE_URL` missing → database tests are **skipped** (the reason is printed).
- `TEST_DATABASE_URL` equal to `DATABASE_URL` → tests **refuse to start**.

**Option A: Docker (recommended: fast, offline)**
1. Open Docker Desktop and wait for **Engine running**.
2. In the project folder: `docker compose up -d`. This starts only the small test database.
3. In `backend/.env`: `TEST_DATABASE_URL=postgresql://aegis:aegis_test_only@localhost:5433/aegis_test`.

**Option B: a Neon branch (no Docker)**
1. Neon → **Branches** → **Create branch**, name it `test`.
2. Copy its connection string into `TEST_DATABASE_URL`.

## 6. Run the tests

From the project folder (`D:\AEGIS`):

```powershell
python -m pytest
```

Expected: **143 passed** with a test database, or **70 passed, 73 skipped** without one.
Clicking way: **Testing** panel (flask icon) → ▶. Details: [testing.md](testing.md).

## 7. Start the API

```powershell
cd backend
```
```powershell
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs**, click **Authorize**, and log in with your admin. Every endpoint now has **Try it out**.
Stop with **Ctrl+C**.

## 8. Start the dashboard (second terminal)

```powershell
cd frontend
```
```powershell
npm install
```
```powershell
npm run dev
```

Open **http://localhost:5173**, log in, then try **Simulator** → **Account takeover** → **Run scenario**.
The dev server forwards `/api` to the backend on port 8000, so both must be running.
Click-by-click tour of everything: [feature-guide.md](feature-guide.md).

---

## Troubleshooting

See [debugging.md](debugging.md) for the full table. The most common:

| You see | Fix |
|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once) |
| `KeyError: 'DATABASE_URL'` | Step 3 |
| `JWT_SECRET is missing or shorter than 32 characters` | Step 3, point 3 |
| `relation "users" does not exist` | Step 4 (`alembic upgrade head`) |
| Dashboard: "Cannot reach the AEGIS API" | Step 7: the backend isn't running |
