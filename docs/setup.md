# Setup: Run AEGIS on Your Own Computer (Windows)

> **Goal:** from a fresh Windows PC to "the app runs and all tests pass".
> Wherever possible, the clicking way is shown first. Terminal commands are for PowerShell inside Cursor (**Terminal → New Terminal**).

---

## What you need installed

| Tool | What it is | Why AEGIS needs it | Check it is installed |
|---|---|---|---|
| **Python 3.12** | The programming language the backend is written in | Runs all backend code | `python --version` |
| **Git** | Saves versions of your code | History, and uploading to GitHub | `git --version` |
| **Cursor** (or VS Code) | Code editor | Reading/editing code, built-in terminal and Git buttons | open it |
| **Docker Desktop** | Runs software in isolated "containers" | Runs the throw-away **test database** | Docker Desktop shows **Engine running** |
| **A Neon account** | PostgreSQL hosted in the cloud, free tier | The **real** database for the app | log in at console.neon.tech |

---

## 1. Get the code

**Clicking way:** in Cursor, **File → Open Folder → `D:\AEGIS`** (if you already have it).
Fresh PC: on the Cursor start screen choose **Clone repo** and paste `https://github.com/chahak235/AEGIS.git`.

## 2. Create the virtual environment and install libraries

```powershell
python -m venv .venv
```
```powershell
.\.venv\Scripts\Activate.ps1
```
```powershell
pip install -r backend\requirements-dev.txt
```

- **Virtual environment (`.venv`)**: a private folder of Python libraries just for this project.
  - *Why:* project A may need FastAPI version 1 and project B version 2. Without separate environments they fight.
  - *What if not:* everything installs globally, versions clash, and "works on my PC" bugs appear.
  - *Alternatives:* `conda`, `poetry`, `uv`.
- `requirements-dev.txt` = everything in `requirements.txt` (what the app needs to **run**) **plus** test tools (`pytest`, `httpx`).
- After activating, your terminal line starts with `(.venv)`. If you open a new terminal, activate again.

## 3. Add your secrets: `backend/.env`

1. In Cursor's file list, right-click `backend/.env.example` → **Copy**, then right-click `backend` → **Paste**. Rename the copy to `.env`.
2. Fill in `DATABASE_URL`: Neon dashboard → your project → **Connect** → copy the connection string.
3. Fill in `TEST_DATABASE_URL` (next step).

`.env` is listed in `.gitignore`, so Git will never upload it. `.env.example` **is** uploaded, so it only contains placeholders.

## 4. Start the test database

Tests create and delete data. They must **never** run against the real database, so they use a separate one.
If `TEST_DATABASE_URL` is missing, or equals `DATABASE_URL`, the tests refuse to start. That is deliberate.

**Option A: Docker (recommended: fast, works offline)**
1. Open Docker Desktop and wait for **Engine running**.
2. In Cursor's terminal, in the `D:\AEGIS` folder: `docker compose up -d`
3. In Docker Desktop → **Containers**, you will see `aegis` → `test-db` with a green dot. You can stop/start it with the buttons there.
4. In `backend/.env`: `TEST_DATABASE_URL=postgresql://aegis:aegis_test_only@localhost:5433/aegis_test`

The test database keeps its data in memory, so it is empty every time the container restarts. Tests set it up themselves by running the Alembic migrations.

**Option B: a Neon branch (no Docker)**
1. Neon dashboard → **Branches** → **Create branch**, name it `test`.
2. Open the branch → **Connect** → copy its connection string into `TEST_DATABASE_URL`.

## 5. Bring the real database up to date

```powershell
cd backend
```
```powershell
alembic upgrade head
```

This applies any database changes (migrations) that are not yet in your Neon database. Safe to run any time: if everything is already applied, it does nothing.

## 6. Run the tests

From the `D:\AEGIS` folder:

```powershell
python -m pytest
```

**Clicking way:** in Cursor, open the **Testing** panel (flask icon on the left), then press the ▶ button. Install the Python extension if the panel is empty.

Expected: **14 passed**.

## 7. Run the app and click it

From the `backend` folder:

```powershell
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** in your browser. Every endpoint is listed there with **Try it out** buttons.

Quick checks:
- `GET /health/ready` → `{"status": "ready", "database": "ok"}`
- `POST /api/v1/events` → `201`. Click **Execute** again with the same `event_id` → `200`, and the event is still stored only once.

Stop the app with **Ctrl+C** in the terminal.

---

## Troubleshooting

| You see | Meaning | Fix |
|---|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled` | Windows blocks scripts by default | Run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `TEST_DATABASE_URL is not set` | Step 4 not done | Add it to `backend/.env` |
| `connection refused ... 5433` | Test database not running | Start Docker Desktop, then `docker compose up -d` |
| `KeyError: 'DATABASE_URL'` | No `backend/.env`, or the line is missing | Step 3 |
| `ModuleNotFoundError: No module named 'fastapi'` | Virtual environment not active | `.\.venv\Scripts\Activate.ps1` |
| `/health/ready` returns 503 | App cannot reach Neon | Check Wi-Fi and `DATABASE_URL` |
