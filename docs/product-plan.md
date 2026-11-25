# Product Plan

> What AEGIS is for, who uses it, what it must do, and how we judge whether it works.
> Engineering details live in [architecture.md](architecture.md); progress lives in [roadmap.md](roadmap.md).

## 1. The problem

Every application writes down what happens inside it: logins, failed logins, refused requests, permission changes.
These records are **events**. A busy application produces millions of them.

Two problems follow:

1. **Needle in a haystack.** One failed login means nothing (people mistype passwords). Five in a row, then a
   success, then the account makes itself an admin: that's a story worth investigating. Humans can't read
   millions of lines to find these stories.
2. **Alert floods.** Naive tools raise an alarm for every suspicious line. Analysts drown and start ignoring alarms
   ("alert fatigue"), which is how real breaches get missed.

**AEGIS turns raw events into a short list of explained, grouped investigations.**

```text
    1,000,000 events  ──►  50 detections  ──►  8 incidents  ──►  1 analyst can actually handle this
     (facts)              (suspicious        (related findings
                           patterns)          grouped as stories)
```

(These numbers are an illustration, not a measurement.)

## 2. Who uses it

| Person | What they need | How AEGIS serves them |
|---|---|---|
| **Security analyst** | See what needs attention, understand why, record the investigation | Incident queue, incident detail with timeline and explanations, notes, status workflow |
| **Admin** | Control who can log in and which systems may send events | User management, API keys, full audit log |
| **Application / system** (not a person) | Report events reliably | `POST /api/v1/events` with an API key, safe retries |
| **Engineer running AEGIS** | Know the system is healthy | Health checks, JSON logs with request IDs, Prometheus metrics, Grafana dashboard |

## 3. Core user journeys

1. **Detect:** an application sends events → AEGIS stores them → rules and the ML model raise detections.
2. **Triage:** the analyst opens the incident queue, sorted by most recent activity, filtered by severity/status.
3. **Investigate:** the analyst opens an incident and reads:
   - *why* it exists (each detection's explanation, and the grouping reason);
   - *what happened* (timeline of evidence events);
   - *who did what so far* (history).
4. **Act and record:** assign to self → mark investigating → add notes → resolve with a conclusion
   (true positive, false positive, benign, duplicate) → close.
5. **Audit:** an admin can later see every action, by whom, when. Nobody can quietly rewrite it.

## 4. Requirements

### Functional (what it must do)

| # | Requirement | Status |
|---|---|---|
| F1 | Accept events over HTTP with strict validation and clear errors | ✅ |
| F2 | Never store the same event twice when a sender retries | ✅ (with client `event_id`) |
| F3 | Detect known patterns with explainable rules | ✅ 5 rules |
| F4 | Detect unusual activity no rule describes | ✅ ML-001 |
| F5 | Group related detections of one account into one incident; never merge different accounts | ✅ |
| F6 | Incident lifecycle with enforced, valid status changes | ✅ state machine, 409 on invalid move |
| F7 | Append-only notes and audit history | ✅ (audit enforced in the database) |
| F8 | Logins with roles (analyst/admin); keys for machines | ✅ |
| F9 | A dashboard covering all of the above | ✅ |

### Non-functional (how well it must do it)

| # | Requirement | How it is met |
|---|---|---|
| N1 | **Explainable:** every finding says why | Explanation text on every detection; correlation reason on every incident |
| N2 | **Secure by default** | Login on all data endpoints; Argon2 passwords; rate limits; secrets only in env |
| N3 | **Never lose an event**, even if detection crashes | Event committed before detection runs; tested |
| N4 | **Tested** | 155 automated tests; CI on every push |
| N5 | **Observable** | Request IDs, JSON logs, metrics, health checks |
| N6 | **Reproducible** | Pinned model version, seeded ML training, Docker, migrations |
| N7 | **Honest** | Limitations documented next to every feature |

## 5. Explicit non-goals

AEGIS does **not** try to replace Splunk, Elastic Security or Microsoft Sentinel, parse every log format,
guarantee it catches every attack, or claim real-world ML accuracy from synthetic data.
These boundaries keep the project finishable and its claims defensible.

## 6. How we know it works (success measures)

- The full journey (events → detection → incident → resolve) works through the dashboard. ✅
- Each rule has tests for when it must fire AND when it must stay quiet. ✅
- The normal-user simulator scenario raises **no** alarm. ✅
- ML evaluation is reported on a held-out test set, with limitations. ✅
- A fresh machine can run it from the docs alone. (Next: verify on a clean PC.)
- Hosted version reachable over HTTPS. (Next: deployment.)
