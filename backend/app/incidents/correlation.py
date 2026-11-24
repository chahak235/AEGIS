"""Correlation: decide which incident a detection belongs to.

The rule (deterministic, so anyone can predict and check the result):

  A detection joins an incident when ALL of these are true:
    1. same account (actor_id),
    2. the incident is still active (open / acknowledged / investigating),
    3. the incident's latest activity is no more than CORRELATION_WINDOW (1 hour)
       before the detection started.
  Otherwise a NEW incident is created.

Why "same account" and not just "close in time"? Two unrelated users failing
their logins at 10:00 are two stories, not one. Merging them would mislead the
analyst. Time alone is not evidence of a connection.

Why not reopen resolved incidents? An analyst already reached a conclusion.
New activity is a new question, so it gets a new incident, and nobody's
finished work is silently changed.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.detection.catalogue import ALL_RULES
from app.incidents.lifecycle import (
    ACTIVE_STATUSES,
    CORRELATION_WINDOW,
    incident_severity,
    incident_title,
)
from app.models import Detection, Incident
from app.observability import INCIDENTS_CREATED

RULE_NAMES = {rule.code: rule.name for rule in ALL_RULES}


def correlate(session: Session, detection: Detection) -> Incident:
    """Attach the detection to the right incident (creating one if needed)."""
    if detection.incident is not None:
        # An existing detection that grew: just refresh its incident's summary.
        refresh_summary(detection.incident)
        return detection.incident

    incident = session.scalars(
        select(Incident)
        .where(
            Incident.actor_id == detection.actor_id,
            Incident.status.in_(ACTIVE_STATUSES),
            Incident.last_seen >= detection.window_start - CORRELATION_WINDOW,
        )
        .order_by(Incident.last_seen.desc())
        .limit(1)
    ).first()

    created = incident is None
    if created:
        incident = Incident(
            id=uuid4(),  # set now (not at save time) so the audit record can refer to it
            actor_id=detection.actor_id,
            status="open",
            title="",
            severity=detection.severity,
            correlation_reason="",
            first_seen=detection.window_start,
            last_seen=detection.window_end,
            detections=[],
        )
        session.add(incident)

    incident.detections.append(detection)
    refresh_summary(incident)

    # Automatic actions are audited too, with actor "system".
    if created:
        INCIDENTS_CREATED.labels(incident.severity).inc()
        audit.record(session, actor=audit.SYSTEM, action="incident.created",
                     target_type="incident", target_id=incident.id,
                     details={"rule_code": detection.rule_code, "severity": incident.severity})
    else:
        audit.record(session, actor=audit.SYSTEM, action="incident.detection_added",
                     target_type="incident", target_id=incident.id,
                     details={"rule_code": detection.rule_code, "severity": incident.severity})
    return incident


def refresh_summary(incident: Incident) -> None:
    """Recompute title, severity, time range and reason from the detections."""
    detections = incident.detections
    rule_codes = [d.rule_code for d in sorted(detections, key=lambda d: d.window_start)]
    distinct = len(set(rule_codes))

    incident.first_seen = min(d.window_start for d in detections)
    incident.last_seen = max(d.window_end for d in detections)
    incident.severity = incident_severity((d.severity for d in detections), distinct)
    incident.title = incident_title(
        incident.actor_id, (RULE_NAMES.get(code, code) for code in rule_codes)
    )

    window_minutes = int(CORRELATION_WINDOW.total_seconds() // 60)
    if len(detections) == 1:
        reason = f"Created from a single {rule_codes[0]} detection for account {incident.actor_id}."
    else:
        reason = (
            f"{len(detections)} detections ({', '.join(dict.fromkeys(rule_codes))}) grouped: "
            f"all concern account {incident.actor_id} and each began within "
            f"{window_minutes} min of the incident's previous activity."
        )
    if distinct >= 3:
        reason += f" Severity raised one level because {distinct} different rules fired."
    incident.correlation_reason = reason
