# Interview Guide: Explaining AEGIS with Confidence

> Practise these out loud. Good answers have four parts: **what I built → why this way → the trade-off → what I'd do next.**
> Never claim more than is true: interviewers respect "here's the limitation, and here's my plan".

## 1. The 60-second pitch

> "AEGIS is a security event platform I built end to end.
>
> - Applications send events like failed logins to a FastAPI backend. It validates them and stores them in PostgreSQL. Retries can't create duplicates.
> - Five explainable detection rules and an Isolation Forest anomaly model look for attacks.
> - Related findings for the same account are grouped into incidents, so analysts get a short queue instead of an alert flood.
> - Analysts work incidents in a React/TypeScript dashboard through a strict status workflow. Every action goes into an audit log that PostgreSQL itself refuses to modify.
> - It has Argon2 and JWT authentication with roles, rate limiting, structured logging and Prometheus metrics, Docker, CI, and about 155 automated tests.
> - The ML part is evaluated honestly on synthetic data against a rules baseline.
>
> Along the way I hit and fixed real problems, like training/serving skew in the model and a transaction-timestamp ordering bug in the audit log."

## 2. Likely questions, with the core of a good answer

### Architecture
- **Walk me through what happens when an event arrives.**
  Auth (API key/JWT) → rate limit → Pydantic validation → commit the event → rules + ML on that account's ±10 min → create or extend detections → correlate into an incident → audit records, all in one transaction → 201. → [architecture.md §2](architecture.md)
- **Why a monolith and not microservices?**
  One team, one deployable, shared transactions, simpler debugging. Modules are already separated, so detection could become its own worker if load demanded it.
- **What happens if detection crashes?**
  The event is committed first, so nothing is lost. The detection transaction rolls back and the error is logged. There's a test for exactly this.
- **How would you scale it?**
  - Put events on a queue (Redis Streams/Kafka) with detection workers.
  - Make the API horizontally scalable (stateless + Redis rate limits).
  - Partition `events` by time.
  - Add read replicas for the dashboard.

### Data
- **Why PostgreSQL?**
  Relationships plus integrity (foreign keys, transactions, triggers), and JSONB for flexible details. Elasticsearch would suit full-text log search, but it isn't a source of truth.
- **Why a link table for evidence?**
  It's many-to-many. Foreign keys stop evidence from silently disappearing, and the reverse lookup is indexed.
- **How do you make the audit log tamper-resistant?**
  A PostgreSQL trigger blocks UPDATE/DELETE, and audit records are written in the same transaction as the change. Deletion only works with an explicit session flag, for retention.
- **Interesting bug?**
  Audit entries came back in random order: one flaky test in three runs. PostgreSQL's `now()` is the transaction *start* time, so records written together tied. I added an identity `seq` column for exact ordering.

### Detection
- **How do your rules avoid alert floods?**
  - Overlapping matches merge.
  - The same rule, account and overlapping time extends one detection.
  - Idempotent ingestion.
  - Correlation groups detections into incidents.
- **Complexity of the window check?**
  Sort O(n log n), then a two-pointer scan O(n).
- **Out-of-order events?**
  The engine looks both before *and* after the event's time, so a late event still completes a pattern.

### ML
- **Why Isolation Forest, and what are its limits?**
  - It needs no attack labels and is fast and small.
  - Trees can't extrapolate. My evaluation showed it missed brute force entirely, so I added a z-score extreme-value check.
  - ML-001 is the OR of both. → [ml.md](ml.md)
- **How did you pick the threshold?**
  A 1% false-alarm budget measured on validation normals. Test data was used only once, for final numbers.
- **What's training/serving skew? Did you hit it?**
  Yes. Live detection scored partial windows that training never saw: 7% false alarms instead of about 1%. The fix was sharing the windowing function between training and live code.
- **Can you trust your numbers?**
  Only on synthetic data. Real attackers try to look normal. Next steps: real traffic, measuring alarm rate, and analyst feedback as labels.

### Security
- **Authentication vs authorization?** 401 vs 403; JWT and API keys vs roles. → [auth.md](auth.md)
- **How do you store passwords?** Argon2id: salted, slow, rehash on upgrade.
- **Is a JWT encrypted? How do you revoke one?** It's signed, not encrypted. Revocation: short expiry plus an active-user check on every request.
- **What stops brute force?**
  - Rate limits per IP and per username, checked before the password.
  - Identical error and timing for unknown users.
  - AEGIS detects the attack on itself via its own rules.
- **Why is hiding a button not security?** Anyone can call the API with curl. Only backend checks count, and the tests prove 403s.
- **A secret leaked to GitHub: what now?** Rotate it first. Git history keeps the old commit; then clean up and check the audit log.

### Engineering practice
- **How do you know it works?**
  - 155 tests, with security tests focused on refusals.
  - CI runs them with a real PostgreSQL on every push.
  - Migrations are tested up/down/up.
- **How do you keep tests from damaging data?**
  A separate test database. The suite refuses to start if it equals the real one.
- **What's in your CI?** Lint, backend tests, `alembic check`, frontend typecheck/test/build, Docker build, and a full-stack smoke test.

## 3. Questions to expect about gaps (and good answers)

| Question | Honest answer |
|---|---|
| Is it deployed? | Not yet: deployment is planned and documented (Cloud Run + Vercel). Locally it runs fully in Docker Compose. |
| Real data? | Synthetic only; I'd start real use with alarm-rate measurement and re-tuning. |
| Load-tested? | Not yet; k6 is next, and I'll publish p95 latency with the test conditions. |
| Kubernetes? | Not needed for this scale (Cloud Run covers it); planned as a learning extension. |

## 4. Before an interview

- [ ] Run the Simulator live and talk through one incident page.
- [ ] Open `rules.py` and explain `sliding_window_groups` line by line.
- [ ] Explain one migration file and the audit trigger.
- [ ] Re-read [ml-evaluation.md](ml-evaluation.md) and know the per-attack table.
- [ ] Be able to draw the architecture diagram from memory.
