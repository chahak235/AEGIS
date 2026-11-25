# Database: Tables, Links, Rules and Migrations

> PostgreSQL 16 (Neon in the cloud, Docker locally). Models: `backend/app/models.py`. History: `backend/alembic/versions/`.

## 1. The tables and how they connect

```text
 users                    api_keys
 (people who log in)      (systems that send events)

 events ◄──────────── detection_events ────────────► detections ──── incident_id ───► incidents ◄── incident_notes
 (facts)               (link table: which events      (findings)       (many detections        (investigations)    (analyst notes)
                        are evidence for which                          → one incident)
                        detection)

 audit_logs  (who did what to which target: append-only, linked by target_type + target_id)
```

| Table | One row is… | Key columns |
|---|---|---|
| `events` | something that happened | `id` (UUID), `event_type`, `occurred_at` (tz), `ingested_at`, `actor_id`, `resource`, `outcome`, `details` (JSONB) |
| `detections` | a finding by a rule or the model | `rule_code`, `severity`, `actor_id`, `window_start/end`, `event_count`, `explanation`, `source_type`, `model_version`, `anomaly_score`, `incident_id` |
| `detection_events` | one "this event is evidence for that detection" link | `detection_id`, `event_id` (together the primary key) |
| `incidents` | one investigation | `title`, `actor_id`, `severity`, `status`, `assigned_to`, `correlation_reason`, `first_seen/last_seen`, `resolution`, `resolved_at` |
| `incident_notes` | one analyst note | `incident_id`, `author`, `body`, `created_at` |
| `audit_logs` | one recorded action | `seq` (ordering), `actor`, `action`, `target_type`, `target_id`, `details` (JSONB) |
| `users` | a person | `username` (unique), `password_hash` (Argon2), `role`, `is_active`, `last_login_at` |
| `api_keys` | a sending system's key | `name`, `prefix`, `key_hash` (SHA-256, unique), `is_active`, `last_used_at` |

## 2. Relationships in plain words

- **One-to-many:** one incident has many detections. Stored as `detections.incident_id`.
  - If an incident is deleted, its detections stay and point to nothing (`ON DELETE SET NULL`).
- **Many-to-many:** a detection has many events, and an event can be evidence for several detections (a failed login counts for AUTH-001 *and* AUTH-002).
  - Stored in its own link table, `detection_events`.
- **Why not a JSON list of event IDs inside the detection?** The database couldn't check those events exist, and "which detections use this event?" would mean scanning every detection.

## 3. Rules the database enforces (constraints and triggers)

| Rule | How | What happens if broken |
|---|---|---|
| Every row has a unique ID | Primary keys | Insert refused |
| Usernames and API-key hashes are unique | `UNIQUE` | Insert refused (API answers 409) |
| Evidence can't vanish | FK `detection_events.event_id → events.id` with default `NO ACTION` | Deleting an event that is evidence is refused |
| Deleting a detection removes its links | FK `ON DELETE CASCADE` | Links removed automatically |
| Audit log is append-only | Trigger `audit_logs_append_only` | `UPDATE` always refused; `DELETE` refused unless the session sets `aegis.allow_audit_delete = 'on'` (retention/tests only) |
| Audit order is exact | `seq` identity column (1, 2, 3…) | n/a (timestamps alone can tie inside one transaction) |

> **Why enforce in the database and not only in Python?** Code has bugs, and there may one day be other
> programs, or a person with SQL access. Rules inside PostgreSQL hold no matter who connects.

## 4. Indexes: why queries stay fast

An index is like the index at the back of a book: the database jumps to the right rows instead of reading all of them.
Each index below exists because a **specific query** needs it:

| Index | Serves this question |
|---|---|
| `events (actor_id, occurred_at)` | "This account's events between 10:00 and 10:20" (every detection run) |
| `events (event_type, occurred_at)` | Filtering events by type |
| `detections (rule_code, actor_id, window_start)` | "Is there already an AUTH-001 detection for this account around now?" (dedup) |
| `detections (window_end)` | Newest detections first |
| `detections (incident_id)` | An incident's detections |
| `detection_events (event_id)` | "Which detections use this event?" |
| `incidents (actor_id, status, last_seen)` | "Is there an active incident for this account?" (correlation) |
| `incidents (status, last_seen)` | The incident queue |
| `audit_logs (target_type, target_id, seq)` | One incident's history |

**Trade-off:** every index speeds up reads but slows down writes a little and uses disk. So we only add indexes that a real query uses.

## 5. Time: two timestamps on every event

- `occurred_at`: when it **happened** at the source. Sent by the client, **must include a timezone**.
- `ingested_at`: when AEGIS **received** it. Set by PostgreSQL.

They differ when events arrive late (offline phone, retries, batching). Detection uses `occurred_at`; debugging delays uses both.
Everything is stored as `timestamptz` (an absolute moment), so "10:00 in India" and "04:30 in London" are the same value.

## 6. Transactions: all or nothing

A **transaction** groups changes so that either all of them are saved, or none are.

- Saving an event is its own transaction, committed **before** detection, so a detection bug can't lose the event.
- Detection + correlation + audit records form **one** transaction: there is never a detection without its incident, or an incident change without its audit record.
- PostgreSQL's `now()` returns the transaction's **start** time, so records written in one transaction share a timestamp. That's why `audit_logs` orders by `seq`.

## 7. Migrations (Alembic)

| Revision | What it did |
|---|---|
| `cbf2b017960c` | create `events` |
| `30fd34b8e04c` | drop unused `severity_hint` (checked: 0 rows had a value) |
| `68178dad4e86` | create `detections`, `detection_events` |
| `f127a7e04de5` | create `incidents`, `incident_notes`; link detections to incidents |
| `614add3979a4` | create append-only `audit_logs` + trigger |
| `0f4cdd3c708d` | create `users`, `api_keys` |
| `ae65ba2fb14c` | add `source_type`, `model_version`, `anomaly_score` to detections |

Commands (from `backend/`):

```powershell
alembic upgrade head          # apply everything not yet applied
alembic current               # which version is the database on?
alembic history               # list all versions
alembic downgrade -1          # undo the latest (careful: may drop data)
alembic revision --autogenerate -m "describe the change"   # after editing models.py
alembic check                 # do models.py and the migrations agree?
```

Every migration in this project was tested **up → down → up** before use.

## 8. Retention (future)

Events grow forever today. Real systems:
- keep raw events for a fixed time (e.g. 90 days);
- *partition* the `events` table by month, so old months can be dropped instantly;
- keep detections, incidents and audit logs longer.

This is on the roadmap.
