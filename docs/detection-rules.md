# Detection Rules: How AEGIS Spots Suspicious Activity

> **What you will know after reading this:** what a detection is, how each of the 5 rules works, how the "sliding window" algorithm finds patterns, how AEGIS avoids duplicate alerts, how the code is organised, and how to explain all of it in an interview.
>
> **Code:** `backend/app/detection/rules.py` (the rules), `backend/app/detection/engine.py` (runs them and saves results), `backend/app/api/v1/detections.py` (read them).
> **Tests:** `test_rules.py` (21 unit tests), `test_detection_engine.py` (9), `test_detections_api.py` (6).
>
> **Since this was written:**
> - a sixth detector, **ML-001** (machine learning), runs next to these rules ([ml.md](ml.md));
> - detections are now grouped into **incidents** ([architecture.md](architecture.md));
> - all endpoints need a **login** ([auth.md](auth.md)).
>
> The rule logic below is unchanged.

---

## 1. The big idea in one picture

```text
   EVENTS (facts)                         DETECTIONS (findings)
   ──────────────                         ─────────────────────
   10:00:00  user-123  login failed  ┐
   10:00:01  user-123  login failed  │
   10:00:02  user-123  login failed  ├──►  AUTH-001  "5 failed logins for user-123
   10:00:03  user-123  login failed  │      between 10:00:00 and 10:00:04
   10:00:04  user-123  login failed  ┘      (rule: at least 5 within 5 min)"
```

- An **event** says *what happened*. It is a fact, not an opinion.
- A **detection** says *this looks suspicious, and here is why*. It is an opinion backed by evidence.
- A **rule** is the recipe that turns events into detections.

Later, **incidents** will group related detections into one investigation (e.g. AUTH-001 + AUTH-002 + ACCOUNT-001 for the same user within an hour = "possible account takeover").

**Real life:** this is exactly how professional tools work. Splunk calls them "correlation searches", Elastic Security calls them "detection rules", Microsoft Sentinel calls them "analytics rules". A common open format for writing such rules is called **Sigma**.

---

## 2. The 5 rules

| Code | Name | Fires when | Severity | Why it matters |
|---|---|---|---|---|
| **AUTH-001** | Repeated failed logins | ≥ 5 `auth.login.failed` for one account within 5 min | medium | Someone may be guessing the password (**brute force**) |
| **AUTH-002** | Failed logins followed by success | ≥ 3 failed logins, then `auth.login.success`, all within 10 min | **high** | The guessing may have **worked** |
| **ACCESS-001** | Repeated access denied | ≥ 5 events with `outcome = denied` for one account within 5 min | medium | Someone is probing for things they're not allowed to do |
| **ACCOUNT-001** | Sensitive account change | Any `account.permission.changed` | **high** | Attackers often give themselves admin rights after breaking in |
| **API-001** | Unusual request volume | ≥ 100 `api.request` for one account within 1 min | medium | Scripts/bots scraping data or attacking, not a human clicking |
| **ML-001** | Anomalous activity (machine learning) | Isolation Forest or extreme-value check flags a 10-min window | medium | Catches combinations no single rule covers. See [ml.md](ml.md) |

You can see this table live at **`GET /api/v1/rules`** (open http://127.0.0.1:8000/docs).

> **Are these numbers "correct"?** There is no universal correct threshold. 5 failures in 5 minutes is a reasonable starting point for a prototype. In real companies, thresholds are **tuned**: too low means too many false alarms, too high means real attacks are missed. That trade-off is the core of detection engineering.

### Words you need

| Word | Meaning | Example |
|---|---|---|
| **Window** | The maximum time span the matching events may cover | 5 minutes |
| **Threshold** | How many matching events are needed inside one window | 5 |
| **True positive** | Rule fired and it really was an attack | Bot guessing passwords |
| **False positive** | Rule fired but it was harmless | User forgot password after holidays |
| **False negative** | Attack happened, rule stayed quiet | Attacker guesses slowly: 1 try every 10 min |
| **Severity** | How urgently a human should look | high > medium > low |

Every rule has false positives and false negatives. That's why AEGIS says *"looks suspicious, here is the evidence"* and never *"you were hacked"*.

---

## 3. How a window rule works: the sliding window

Question: *"Are there at least 5 failed logins that all fit inside some 5-minute span?"*

**Naive way:** for every event, look at every other event. With 10,000 events that's 100 million comparisons.

**Sliding window ("two pointers"):** sort the events by time, then move a window across them like a magnifying glass:

```text
time ─►  e0   e1   e2   e3   e4   e5        e6
          ↑i                   ↑j
          └── span ≤ 5 min ────┘   j - i + 1 = 5 events  → MATCH

Move j right by one. If e[j] - e[i] > 5 min, move i right until it fits again.
```

- `j` (right pointer) visits each event once.
- `i` (left pointer) only ever moves right.
- So the work is about **n steps** after sorting (written **O(n)**), not n² (n × n).

Code: `sliding_window_groups()` in `rules.py`.

**Edge case:** the window is **inclusive**. Events exactly 5:00 apart still count; 5:01 apart do not. There are tests for both: `test_window_is_inclusive_at_the_edge` and `test_window_one_second_too_wide_does_not_match`.

**Overlaps are merged:** 7 failures in a row contain three overlapping groups of 5 (e0–e4, e1–e5, e2–e6). The function merges them into **one group of 7**. One attack = one finding.

---

## 4. How the code is organised (and why)

```text
POST /api/v1/events
        │
        ▼
events.py ── save event ── COMMIT ──► event is safe in PostgreSQL
        │
        ▼  (separately, inside try/except)
engine.py  run_detection(session, event)
        │  1. fetch this account's events from 10 min before to 10 min after
        │  2. give them to every rule ─────────────► rules.py (pure logic)
        │  3. keep only matches that include the new event
        │  4. create a new detection OR extend an existing one
        ▼
detections + detection_events tables
        │
        ▼
GET /api/v1/detections, GET /api/v1/detections/{id}
```

### Decision 1: rules are pure functions, separate from the database

`rules.py` never imports the database. A rule receives a list of events and returns groups.

- **Why:** testable in milliseconds with fake events (21 tests run in 0.1 s, no database). Easy to read: one file = all the logic an analyst cares about.
- **What if not:** rules mixed with SQL become hard to test (every test needs a database) and hard to change.
- **The `EventLike` Protocol:** a rule doesn't care whether it gets a real database `Event` or a test `FakeEvent`, only that it has `id`, `event_type`, `occurred_at`, `actor_id` and `outcome`. This is called **duck typing** ("if it walks like a duck…").

### Decision 2: rules are data in a list (`RULES`)

Each rule is a `Rule` object with a code, name, severity, window, threshold, a `find` function and an `explain` function. Most rules are built by one helper, `count_rule(...)`.

- **Why:** adding a rule is adding one entry. The API's `/api/v1/rules` page reads the same list, so documentation can never drift away from the code.
- **Alternatives:** rules as YAML files (like Sigma), rules stored in the database and editable in the UI, or SQL queries. Those are more flexible but harder to test. We can move there later if editing rules without redeploying becomes a need.

### Decision 3: detection runs right after the event is saved, but can't lose it

```python
session.commit()                       # 1. event is permanently saved
try:
    detection_engine.run_detection(session, row)   # 2. then detection
except Exception:
    session.rollback()
    logger.exception(...)              # 3. a rule bug is logged, the event is NOT lost
```

- **Why this order:** the event is the evidence. Losing evidence because of a bug in a rule would be the worst outcome. Test: `test_event_is_saved_even_if_detection_crashes`.
- **Trade-off (synchronous):** the sender waits while rules run. Fine at prototype scale. At high volume you'd put events on a **queue** (Redis, RabbitMQ, Kafka) and let a separate **worker** run detection in the background. That's the usual next step, and a good interview talking point.

### Decision 4: look around, not just back

The engine fetches events from **10 minutes before to 10 minutes after** the new event (`LOOKAROUND` = the longest rule window).

- **Why "after" too?** Events can arrive **late and out of order** (a phone was offline and sends its events later). If the 5th failure arrives after the others but *happened* before them, the pattern is still found. Test: `test_late_event_still_completes_the_pattern`.

### Decision 5: one story = one detection (deduplication)

Before creating a detection, the engine asks: *is there already a detection with the same rule, same account, and an overlapping time range?*
- **Yes:** extend it. Add the new evidence, widen the time range, rewrite the explanation ("6 failed logins…", then "7 failed logins…").
- **No:** create a new one.

- **Why:** without this, 20 failed logins would raise 16 separate alerts. Analysts who get flooded start ignoring alerts. This is called **alert fatigue**, a real cause of missed breaches.
- **Plus idempotency from earlier:** a retried event (same `event_id`) returns early and never re-runs the rules, so it can't inflate the count. Test: `test_retried_event_does_not_count_twice`.

---

## 5. The database tables

```text
events                     detection_events (link table)        detections
──────                     ─────────────────────────────        ──────────
id  ◄───────────────────── event_id                             id
event_type                 detection_id ──────────────────────► rule_code
occurred_at                PRIMARY KEY (detection_id, event_id) severity
actor_id ...                                                    actor_id
                                                                window_start / window_end
                                                                event_count
                                                                explanation
                                                                created_at / updated_at
```

**Why a link table?** One detection has many events, and one event can be evidence for many detections (a failed login counts for both AUTH-001 and AUTH-002). That's a **many-to-many** relationship. Relational databases model it with a third table holding pairs of IDs.

- **Alternative:** store a list of event IDs inside the detection (a JSON array). Simpler, but the database can't check that those events exist, and "which detections use this event?" becomes slow.
- **Foreign keys** make PostgreSQL enforce the links:
  - delete a detection → its links are deleted too (`ON DELETE CASCADE`);
  - try to delete an event that is evidence → PostgreSQL **refuses**. Evidence must not disappear silently.
- **Indexes:**
  - `(rule_code, actor_id, window_start)` makes the dedup question fast;
  - `window_end` makes "newest first" fast;
  - `event_id` on the link table makes "detections for this event" fast.
- **`explanation` is stored, not computed later:** the sentence records what the rule said *at that time*, even if thresholds change next month. That matters for audits.

Migration: `68178dad4e86_create_detections_and_detection_events_.py`.

---

## 6. The API

| Method | Path | What you get |
|---|---|---|
| `GET` | `/api/v1/detections` | Newest first. Optional filters: `rule_code`, `actor_id`, `severity` (low/medium/high), plus `limit`/`offset` |
| `GET` | `/api/v1/detections/{id}` | One detection **plus its evidence events**, oldest first. `404` if unknown |
| `GET` | `/api/v1/rules` | The rule catalogue (code, name, description, severity, window, threshold) |

**Why does the list leave out the events?** A list of 50 detections × hundreds of events each would be huge. The list is a summary; the detail view has the evidence.

**N+1 queries:** loading 1 detection, then 1 query per evidence event, is called the **N+1 problem** (1 + N queries). `selectinload` fetches all evidence in one extra query instead.

---

## 7. Try it yourself (clicking)

1. Start the app (see [setup.md](setup.md), step 7) and open **http://127.0.0.1:8000/docs**. Click **Authorize** and log in first.
   (Easier: the dashboard's **Simulator** page runs these scenarios with one click.)
2. `GET /api/v1/rules` → **Try it out** → **Execute**: the 5 rules.
3. `POST /api/v1/events` → **Try it out**. Paste this and **Execute** it **5 times**, changing the seconds each time (`:01`, `:02`, …):
   ```json
   {
     "event_type": "auth.login.failed",
     "occurred_at": "2026-11-24T10:00:01Z",
     "source": "demo",
     "actor_id": "alice",
     "outcome": "failure"
   }
   ```
4. `GET /api/v1/detections` with `actor_id` = `alice` → one **AUTH-001** detection, `event_count: 5`.
5. Send a 6th failure → still **one** detection, now `event_count: 6`.
6. Send `"event_type": "auth.login.success"`, `"outcome": "success"` → a new **AUTH-002** (high).
7. Copy a detection's `id` into `GET /api/v1/detections/{detection_id}` → the evidence events.
8. Neon dashboard → **Tables** → `detections` and `detection_events`: the same data, as rows.

---

## 8. Known limitations (be honest about these in interviews)

| Limitation | Why it exists | Possible fix |
|---|---|---|
| Rules look at **one account at a time** | Simple and fast | Rules per IP address (many accounts, one attacker: "password spraying") |
| A slow attacker (1 guess every 10 min) is never caught | Fixed windows | Longer windows, or ML anomaly detection (planned) |
| Two requests arriving at the exact same moment could create two detections for one story | No database lock on the dedup check | A unique constraint or row lock; or a single background worker |
| Detection runs inside the web request | Simplicity | Queue + background worker |
| Thresholds are set in code | Simplicity, testability | Config file or database, editable by admins |
| No API-002 (repeated client errors) yet | Needs HTTP status codes in events first | Add a `status_code` convention to `details` |

---

## 9. Interview questions this prepares you for

- **"How does your detection engine work?"** Section 4: save first, then fetch nearby events, run pure rules, keep matches with the new event, create or extend.
- **"How do you avoid alert floods?"** Overlapping groups merge (section 3); same rule + account + overlapping time extends one detection (decision 5); idempotent ingestion.
- **"What's the time complexity of your window check?"** O(n log n) to sort, O(n) for the two-pointer scan.
- **"How do you handle events arriving out of order?"** Look around, not just back (decision 4).
- **"What happens if a rule crashes?"** The event is already committed; detection errors are logged (decision 3).
- **"Why a link table instead of a JSON list?"** Integrity via foreign keys, and fast reverse lookup (section 5).
- **"How would you scale it?"** Queue + workers, per-rule indexes, partitioning events by time.
- **"Rules vs machine learning?"** Rules catch *known* patterns and are easy to explain. ML catches *unusual* patterns nobody wrote a rule for, but is harder to explain. Good systems use both, which is the plan for AEGIS.
