"""The detection engine: runs the rules when an event arrives and saves results.

The flow for one new event:

  1. Fetch the same account's events from LOOKAROUND before to LOOKAROUND after
     the new event's time (so late, out-of-order events are handled too).
  2. Give those events to every rule.
  3. Keep only matches that include the new event (older matches were already
     handled when their own events arrived).
  4. For each match, either EXTEND an existing detection for the same rule,
     account and overlapping time, or CREATE a new one.
  5. Put each new or grown detection into an incident (app/incidents/correlation.py).

Step 4 is "deduplication": 7 failed logins in a row produce ONE detection that
grows from 5 to 7 events, not three separate alerts. Analysts drown in
duplicate alerts ("alert fatigue"), so this matters as much as the rules.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.catalogue import ALL_RULES, LOOKAROUND
from app.detection.rules import Group, Rule
from app.incidents.correlation import correlate
from app.models import Detection, Event
from app.observability import DETECTIONS


def run_detection(session: Session, event: Event) -> list[Detection]:
    """Run every rule for a newly saved event. Returns detections created or updated."""
    nearby = session.scalars(
        select(Event).where(
            Event.actor_id == event.actor_id,
            Event.occurred_at >= event.occurred_at - LOOKAROUND,
            Event.occurred_at <= event.occurred_at + LOOKAROUND,
        )
    ).all()

    touched: list[Detection] = []
    for rule in ALL_RULES:
        for group in rule.find(nearby):
            if any(e.id == event.id for e in group):
                detection = _create_or_extend(session, rule, group)
                if detection not in touched:
                    touched.append(detection)

    # Step 5: group each new or grown detection into an incident (correlation).
    session.flush()  # send pending inserts so the correlation query can see them
    for detection in touched:
        correlate(session, detection)

    # Everything above is ONE transaction: detections and incidents are saved
    # together, or (if anything fails) not at all. No half-finished state.
    session.commit()
    return touched


def _create_or_extend(session: Session, rule: Rule, group: Group) -> Detection:
    start, end = group[0].occurred_at, group[-1].occurred_at

    # Same rule + same account + time ranges overlap  =>  same story, same detection.
    existing = session.scalars(
        select(Detection)
        .where(
            Detection.rule_code == rule.code,
            Detection.actor_id == group[0].actor_id,
            Detection.window_start <= end,
            Detection.window_end >= start,
        )
        .order_by(Detection.window_start)
        .limit(1)
    ).first()

    if existing is None:
        DETECTIONS.labels(rule.code, "created").inc()
        detection = Detection(
            rule_code=rule.code,
            severity=rule.severity,
            actor_id=group[0].actor_id,
            window_start=start,
            window_end=end,
            event_count=len(group),
            explanation=rule.explain(group),
            events=list(group),
            source_type=rule.source_type,
            model_version=rule.model_version,
            anomaly_score=rule.score(group) if rule.score else None,
        )
        session.add(detection)
        return detection

    # Extend: add the new evidence, widen the time range, rewrite the explanation.
    DETECTIONS.labels(rule.code, "extended").inc()
    evidence = {e.id: e for e in existing.events}
    for e in group:
        evidence.setdefault(e.id, e)
    ordered = sorted(evidence.values(), key=lambda e: (e.occurred_at, str(e.id)))
    existing.events = ordered
    existing.window_start = ordered[0].occurred_at
    existing.window_end = ordered[-1].occurred_at
    existing.event_count = len(ordered)
    existing.explanation = rule.explain(ordered)
    if rule.score:
        existing.anomaly_score = rule.score(ordered)
    return existing
