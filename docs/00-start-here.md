# 00 — Start Here: What AEGIS Is and What Is Already Built

> **Who this is for:** someone opening this project for the first time, even if they have never built software before.
> **What you will know after reading it:** what AEGIS does, every file that exists today, how one piece of data travels through the code, why each technology was picked, and what is still missing.
>
> **Status of this document:** describes the repository as of commit `baa0d70` (7 automated tests passing).

---

## 1. AEGIS in one minute

Every app you use (Instagram, your bank, Gmail) writes down little notes about what happens inside it:
"user-123 typed the wrong password", "user-123 logged in", "someone tried to open the admin page and was refused".
Each note is called an **event**.

One event on its own usually means nothing. Everybody mistypes a password sometimes.
But a **pattern** of events can mean trouble:

```text
10:00:01  user-123  wrong password
10:00:03  user-123  wrong password
10:00:05  user-123  wrong password
10:00:09  user-123  logged in          <- did someone guess the password?
10:00:15  user-123  opened admin page  <- why would they need admin?
```

**AEGIS is a program that reads these events, notices suspicious patterns, and groups them into an "incident" that a human (a security analyst) can investigate.**

The whole journey AEGIS will eventually handle:

```text
 Event arrives  ->  Checked  ->  Saved  ->  Rules look for patterns  ->  Detection
                                                                            |
 Analyst investigates in a web dashboard  <-  Incident  <-  Related detections grouped
```

**Real-life equivalent:** professional tools that do this are called **SIEMs** (Security Information and Event Management), for example Splunk, Elastic Security and Microsoft Sentinel. AEGIS is a small, understandable version of the same idea.

---

## 2. What is built today (and what is not)

| Part of the journey | Built? | Where |
|---|---|---|
| Event arrives over the internet | ✅ Yes | `backend/app/api/v1/events.py` |
| Event is checked (validated) | ✅ Yes | `backend/app/schemas.py` |
| Event is saved permanently | ✅ Yes | `backend/app/models.py`, `backend/app/db.py`, Neon PostgreSQL |
| Saved events can be listed / fetched | ✅ Yes | `backend/app/api/v1/events.py` |
| Health check ("is the app alive?") | ✅ Yes | `backend/app/api/health.py` |
| Automated tests | ✅ 7 tests | `backend/tests/test_events.py` |
| Database version history | ✅ Yes | `backend/alembic/` |
| Detection rules | ❌ Not yet | (a practice version existed in Lesson 7, later removed) |
| Correlation, incidents | ❌ Not yet | |
| Login, passwords, roles | ❌ Not yet | |
| Web dashboard | ❌ Not yet | |
| Docker, cloud hosting, CI | ❌ Not yet | |

So: **the "front door" and the "filing cabinet" exist. The "brain" (detection) and the "screen" (dashboard) do not yet.**

---

## 3. Map of every folder and file

```text
AEGIS/
├── README.md                 Project landing page on GitHub
├── .gitignore                List of files Git must NEVER upload (passwords, .venv, caches)
├── pytest.ini                Tells the test tool where the code and tests live
├── requirements-dev.txt      OLD list of test tools from Lesson 7 (now duplicated, see section 8)
│
├── learning/                 Your Python practice scripts (Lessons 1–6). Not part of the app.
│
├── docs/                     Documentation (you are reading one)
│   ├── 00-start-here.md      This file
│   ├── 01..03-*.md           Short early lesson notes
│   └── development-log.md    Diary of finished milestones
│
└── backend/                  THE ACTUAL APPLICATION
    ├── .env                  Secret database address. Exists on your PC only. Never on GitHub.
    ├── requirements.txt      Libraries the app needs to run
    ├── requirements-dev.txt  The above + libraries needed only for testing
    ├── alembic.ini           Settings for Alembic (database versioning tool)
    ├── alembic/
    │   ├── env.py            Tells Alembic how to connect to our database
    │   └── versions/
    │       └── cbf2b017960c_create_events_table.py   "Version 1" of the database: create the events table
    ├── app/
    │   ├── main.py           The starting point. Creates the app and plugs in all the routes.
    │   ├── db.py             Opens the connection to PostgreSQL
    │   ├── deps.py           Hands each request its own database "session"
    │   ├── models.py         Describes the events TABLE (what is stored in the database)
    │   ├── schemas.py        Describes the event JSON (what clients send and receive)
    │   └── api/
    │       ├── health.py     /health/live and /health/ready
    │       └── v1/
    │           └── events.py POST and GET for /api/v1/events
    └── tests/
        └── test_events.py    7 automatic checks
```

> **Why are there empty `__init__.py` files?** They tell Python "this folder is a **package**", which means other files can `import` from it (e.g. `from app.models import Event`). Without them, newer Python can often still find things, but being explicit avoids confusing import errors.

---

## 4. Follow one event through the code (the most important section)

Imagine a program sends this to AEGIS:

```json
{
  "event_type": "auth.login.failed",
  "occurred_at": "2026-10-11T10:00:01Z",
  "source": "web-app",
  "actor_id": "user-123",
  "resource": "/login",
  "outcome": "failure",
  "details": {"ip": "10.0.0.5"}
}
```

This is **JSON**, a plain-text way to write data as `"name": value` pairs. Almost every web API speaks JSON.

### Step 1 — The request arrives (HTTP)

The sender makes an **HTTP request**: `POST http://127.0.0.1:8000/api/v1/events` with the JSON as the **body**.

- **HTTP** is the language browsers and servers use to talk. A request has a **method** (what kind of action), a **URL/path** (which thing), and optionally a **body** (data).
- **Methods** are verbs:

  | Method | Meaning | Restaurant analogy | AEGIS example |
  |---|---|---|---|
  | `GET` | Give me something | "Show me the menu" | list events |
  | `POST` | Here is something new | "Here is my order" | submit an event |
  | `PATCH` | Change part of something | "No onions on my order" | change incident status (later) |
  | `DELETE` | Remove something | "Cancel my order" | (rarely used in security data) |

- The server answers with a **status code**, a 3-digit number:
  `200` OK · `201` Created · `404` Not Found · `422` your data is invalid · `500` the server crashed.

### Step 2 — Uvicorn receives it

**Uvicorn** is a **web server**. It sits on port `8000`, listens for network traffic, and passes each request to our Python app.
Think of Uvicorn as the **restaurant door and the waiter**, and FastAPI as the **kitchen's organisation system**.

You start it with: `uvicorn app.main:app --reload` ("in file `app/main.py`, run the object called `app`; restart when I save files").

### Step 3 — FastAPI finds the right function (`main.py` → `events.py`)

`main.py` creates the app and **plugs in routers**:

```python
app = FastAPI(title="AEGIS", version="0.1.0")
app.include_router(health.router)
app.include_router(events.router)
```

A **router** is a group of related URLs. `events.py` says "everything in me starts with `/api/v1/events`":

```python
router = APIRouter(prefix="/api/v1/events", tags=["events"])

@router.post("", response_model=EventOut, status_code=201)
def create_event(event: EventIn, session: Session = Depends(get_session)):
```

The line starting with `@` is a **decorator**: it means "when a `POST` arrives at `/api/v1/events`, run `create_event`".

> **Why `/api/v1/`?** `v1` = version 1. If one day we must change the event format in a way that breaks old senders, we can add `/api/v2/` and keep `v1` working. This is called **API versioning**; GitHub, Stripe and Google all do it.

### Step 4 — The JSON is checked (`schemas.py`, Pydantic)

Notice the parameter `event: EventIn`. Because of that one type hint, FastAPI uses **Pydantic** to check the incoming JSON against this description:

```python
class EventIn(BaseModel):
    event_type: str = Field(pattern=r"^[a-z]+(\.[a-z]+)+$")   # like "auth.login.failed"
    occurred_at: datetime                                      # must be a real date-time
    source: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    resource: Optional[str] = Field(default=None, max_length=200)
    outcome: Literal["success", "failure", "denied"]           # only these 3 words allowed
    details: dict = Field(default_factory=dict)                # free-form extra info
```

If anything is wrong (e.g. `"outcome": "banana"`), FastAPI **refuses automatically** with status `422` and a message saying which field is wrong. Our function never even runs.

- **Why validate?** A security system must never trust input. Bad data stored today breaks detection tomorrow, and attackers deliberately send weird input.
- **What if we didn't?** Typos like `"faliure"` would be saved, the rule "count failures" would miss them, and an attack could go unnoticed.
- **Alternatives:** writing `if` checks by hand (slow, error-prone), Marshmallow, JSON Schema. Pydantic is the standard choice with FastAPI.
- **The pattern** `^[a-z]+(\.[a-z]+)+$` is a **regular expression**: "lowercase words joined by dots, at least two words". So `auth.login.failed` passes and `Auth Login` fails.

### Step 5 — A database session is handed over (`deps.py`)

The second parameter `session: Session = Depends(get_session)` is **dependency injection**: "before running me, FastAPI, please call `get_session` and give me what it returns".

```python
def get_session():
    with SessionLocal() as session:
        yield session        # give it to the endpoint ... and after the endpoint finishes,
                             # the "with" block closes the session automatically
```

- A **session** is like a **shopping basket** for database changes: you put changes in, then `commit()` (pay at the till) to make them permanent.
- **Why one session per request?** Two users' requests must not mix their half-finished changes.
- **What if we forgot to close sessions?** Each holds a database connection; after a while the database runs out of connections and the app freezes.

### Step 6 — The event becomes a database row (`models.py`, SQLAlchemy)

```python
row = Event(**event.model_dump())   # turn the checked JSON into an Event object
session.add(row)                    # put it in the basket
session.commit()                    # make it permanent in PostgreSQL
session.refresh(row)                # re-read it, to get values the DATABASE filled in
return row
```

`Event` (in `models.py`) describes the **table**:

| Column | Type | Why it exists |
|---|---|---|
| `id` | UUID | Unique ID, generated by us (e.g. `3f2a…`) |
| `event_type` | text | What happened |
| `occurred_at` | time with timezone | When it **happened** at the source |
| `ingested_at` | time with timezone, set by the database | When AEGIS **received** it. Different from above: events can arrive late. |
| `source` | text | Which system sent it |
| `actor_id` | text | Which account did it |
| `resource` | text, optional | What it touched (`/login`, `/admin`) |
| `outcome` | text | success / failure / denied |
| `details` | JSONB | Flexible extra data (IP address, browser…) |
| `severity_hint` | text, optional | Unused leftover (see section 8) |

Plus two **indexes**:
- `(actor_id, occurred_at)` and `(event_type, occurred_at)`.
- An **index** is like the index at the back of a book: instead of reading every page to find "user-123", the database jumps straight there.
- They match the questions detection rules will ask, e.g. "all events of user-123 in the last 5 minutes".

> **What is SQLAlchemy?** An **ORM** (Object-Relational Mapper). It lets us write Python (`Event(...)`, `session.add`) and it writes the **SQL** (the database's language, e.g. `INSERT INTO events ...`) for us.
> **Alternatives:** raw SQL with `psycopg` (more control, more typing), SQLModel, Django ORM, Tortoise.
> **Why UUID and not 1, 2, 3…?** Numbers reveal how many events exist and are easy to guess (`/events/1`, `/events/2`…). UUIDs can also be created without asking the database first.
> **Why JSONB for `details`?** Different event types carry different extras. A fixed column for each would be messy; JSONB stores flexible JSON that PostgreSQL can still search.

### Step 7 — The answer goes back (`EventOut`)

`response_model=EventOut` makes FastAPI send back the event **plus** `id` and `ingested_at`, with status **201 Created**.

```text
Sender --POST JSON--> Uvicorn --> FastAPI router --> Pydantic check --> create_event()
                                                         | 422 if bad          |
                                                                        SQLAlchemy session
                                                                               |
Sender <--201 + saved event--  FastAPI  <-------------------------------  PostgreSQL (Neon)
```

### Reading events back

- `GET /api/v1/events?limit=50&offset=0` → newest first, 50 at a time. This is **pagination**: like pages of Google results, so we never send a million rows at once. `limit` is capped at 200.
- `GET /api/v1/events/{id}` → one event, or `404` if the ID doesn't exist.

---

## 5. Where the data actually lives: PostgreSQL on Neon

- **PostgreSQL** is a **relational database**: data is stored in **tables** (like Excel sheets) with strict column types, and tables can be linked to each other.
- **Neon** is a company that runs PostgreSQL **in the cloud for you** (free tier). Your app connects to it over the internet.
- The address + password is in `backend/.env` as `DATABASE_URL=postgresql://...`. `db.py` reads it with **python-dotenv**.

**Why PostgreSQL?**
- Security data needs to be **correct and permanent**. PostgreSQL has **transactions** (all-or-nothing saves) and **constraints** (rules the data must obey).
- Our data is naturally linked: incident → detections → events. Relational databases are built for links.
- **Alternatives:** MySQL (similar, also fine), MongoDB (flexible documents, weaker at links between records), Elasticsearch (great for searching logs, used by real SIEMs, but heavier to run).

**Why the password is in `.env` and not in the code:** code goes to GitHub, and GitHub can be public. Anyone who sees a database password can read or delete your data. Bots scan GitHub for leaked passwords within minutes. `.gitignore` lists `.env` so Git never uploads it.

---

## 6. Alembic: version control for the database

Git remembers every version of your **code**. **Alembic** remembers every version of your **database structure**.

- Each change (create a table, add a column) is a small Python file in `alembic/versions/` with an `upgrade()` (apply) and a `downgrade()` (undo).
- Running `alembic upgrade head` applies every version that hasn't been applied yet. PostgreSQL keeps a tiny table `alembic_version` that remembers which version it is on.
- **Why?** On a new laptop, a teammate's PC or the cloud, one command recreates the exact same tables. No clicking around, nothing forgotten.
- **What if we didn't?** Someone changes a table by hand, forgets to tell anyone, and the deployed app crashes with "column does not exist".
- **Alternatives:** writing SQL scripts by hand, Django migrations, Flyway, Liquibase.

Today there is exactly one version: `cbf2b017960c — create events table`.

---

## 7. Tests: robots that check your code (`pytest`)

`backend/tests/test_events.py` contains 7 tests. Each test is a function starting with `test_` that **acts like a user** and **asserts** (insists) on the result:

```python
def test_bad_outcome_is_rejected(actor):
    response = client.post("/api/v1/events", json=make_event(actor, outcome="banana"))
    assert response.status_code == 422      # if this is not true, the test FAILS
```

- `TestClient(app)` sends fake HTTP requests to the app **without** starting Uvicorn.
- The `actor` **fixture** creates a unique fake account name per test and **deletes its events afterwards**, so tests clean up after themselves.
- **Why tests?** Every time you change something, 7 checks run in seconds and tell you if you broke something that used to work. In interviews, "how did you know it worked?" → "tests".

| Test | What it proves |
|---|---|
| `test_health_live` | The app is alive |
| `test_create_event_returns_201_with_id` | A good event is saved and gets an ID |
| `test_bad_outcome_is_rejected` | `outcome="banana"` → 422 |
| `test_bad_event_type_is_rejected` | `"Auth Login"` → 422 |
| `test_get_event_by_id` | Saved events can be read back |
| `test_unknown_event_is_404` | Missing IDs → 404 |
| `test_list_respects_limit` | `limit=2` returns at most 2 |

Run them from the `D:\AEGIS` folder with `.venv\Scripts\python -m pytest`. Result today: **7 passed** (about 27 seconds, because each test talks to Neon over the internet).

---

## 8. Honest health check: problems found in the current code

Nothing here is a disaster, and the tests pass. But a professional reviewer would point these out, so we fix them before building on top.

| # | Problem | Why it matters | Planned fix |
|---|---|---|---|
| 1 | **Tests write into the real database** (the same Neon DB the app uses) | A buggy cleanup could delete real data; tests are slow (internet) and fail if Wi-Fi is down | A separate **test database** (local PostgreSQL in Docker) |
| 2 | `occurred_at` accepts times **without a timezone** (`2026-10-11T10:00:01`) | "10:00" in India and "10:00" in London are 5.5 hours apart, so time-window rules would be wrong | Require timezone (Pydantic `AwareDatetime`) |
| 3 | `/health/ready` always says "ready", even if the database is down | Cloud platforms would send traffic to a broken app | Actually test the database connection |
| 4 | `severity_hint` column exists but nothing uses it | Dead columns confuse readers | Remove it with a new Alembic migration (needs your OK) |
| 5 | `details` has no size limit | Someone could send a 100 MB event and fill the database | Limit request/field size |
| 6 | Sending the same event twice saves it twice | Network retries create duplicates, which create fake "5 failed logins" alerts | Optional client-sent event ID with a uniqueness rule |
| 7 | Two `requirements-dev.txt` files (root and `backend/`) | Confusing: which one is real? | Keep `backend/` one; delete root one (needs your OK) |
| 8 | Lesson 7's `rules.py` (first AUTH-001 rule) was removed in commit `84d88f0`, but `development-log.md` still describes it, and the log stops at Lesson 7 | The diary doesn't match reality | Update the log; rebuild the rule properly in the detection phase |
| 9 | A deprecation warning from the test client | Harmless today; may break in a future library update | Revisit when upgrading libraries |

---

## 9. Glossary (every term used above)

| Term | Plain-English meaning |
|---|---|
| **API** | A set of URLs a program can call to ask another program to do something. The "waiter" between programs. |
| **Endpoint / route** | One specific URL + method, e.g. `POST /api/v1/events`. |
| **HTTP** | The language of the web: requests (method, path, body) and responses (status code, body). |
| **JSON** | Text format for data: `{"name": "value"}`. |
| **Status code** | 3-digit result number: 2xx good, 4xx your fault, 5xx server's fault. |
| **Server / Uvicorn** | The program that listens on a port and passes requests to the app. |
| **Port** | A numbered "door" on a computer. Our app uses 8000. |
| **FastAPI** | Python library for building APIs quickly, with automatic checking and the `/docs` page. |
| **Pydantic** | Library that checks data matches a description (types, lengths, allowed values). |
| **Validation** | Checking input before trusting it. |
| **Database** | Program that stores data permanently and answers questions about it. |
| **PostgreSQL** | A popular, free relational database. |
| **Table / row / column** | Sheet / line / heading, like Excel. |
| **Primary key** | The column that uniquely identifies each row (`id`). |
| **Index** | A lookup shortcut that makes searches fast. |
| **SQL** | The language for talking to relational databases. |
| **ORM / SQLAlchemy** | Lets you use Python objects instead of writing SQL by hand. |
| **Session / commit** | Basket of database changes / making them permanent. |
| **Transaction** | A group of changes that either all happen or none happen. |
| **Migration / Alembic** | A recorded, repeatable change to the database structure. |
| **Neon** | A company hosting PostgreSQL in the cloud. |
| **Environment variable / `.env`** | Settings (especially secrets) kept outside the code. |
| **Virtual environment (`.venv`)** | A private copy of Python + libraries just for this project. |
| **Dependency injection (`Depends`)** | FastAPI prepares something (like a DB session) and hands it to your function. |
| **Pagination** | Returning results in pages (`limit`, `offset`). |
| **UUID** | A random, practically unique 128-bit ID. |
| **Test / assert / fixture** | Automatic check / "this must be true" / reusable setup and cleanup for tests. |
| **Event** | A record that something happened. |
| **Detection** | A finding that a suspicious pattern occurred (not built yet). |
| **Incident** | An investigation grouping related detections and events (not built yet). |
| **SIEM** | Professional security platforms that do what AEGIS does, at huge scale. |

---

## 10. Try it yourself (by clicking)

1. In Cursor: **Terminal → New Terminal**, then:
   `.\.venv\Scripts\Activate.ps1` → `cd backend` → `uvicorn app.main:app --reload`
2. Open **http://127.0.0.1:8000/docs** in your browser. This page is generated by FastAPI from the code you just read.
3. Open `POST /api/v1/events` → **Try it out** → **Execute**. You get `201`.
4. Change `"outcome"` to `"banana"` → **Execute**. You get `422`. That is Pydantic (Step 4) protecting the database.
5. Open `GET /api/v1/events` → **Execute**. Your event is there, newest first.
6. Log in at **console.neon.tech** → your project → **Tables** → `events`. The same row, sitting in PostgreSQL.

---

## 11. Interview questions this document prepares you for

- *Walk me through what happens when an event is submitted.* → Section 4, steps 1–7.
- *Why do you store both `occurred_at` and `ingested_at`?* → Events can arrive late or out of order; detection uses when it happened, debugging uses when we got it.
- *Why PostgreSQL and not MongoDB?* → Section 5.
- *How do you keep secrets out of Git?* → `.env` + `.gitignore`; and if one ever leaks, you **rotate** (change) it, because deleting the file does not remove it from Git history.
- *Why Alembic?* → Section 6.
- *How do you know your API works?* → Section 7.
- *What would you improve?* → Section 8. Knowing your own weaknesses is a strong interview answer.
