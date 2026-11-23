"""End-to-end tests for the detection engine: send events through the API,
then look in the database for the detections they should (or should not) create.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.v1 import events as events_module
from app.db import SessionLocal
from app.main import app
from app.models import Detection, Event

pytestmark = pytest.mark.db

client = TestClient(app)
T0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)




def send(actor_id, event_type="auth.login.failed", at=T0, outcome="failure", **extra):
    body = {
        "event_type": event_type,
        "occurred_at": at.isoformat(),
        "source": "test",
        "actor_id": actor_id,
        "outcome": outcome,
        **extra,
    }
    response = client.post("/api/v1/events", json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


def detections_for(actor_id, rule_code=None):
    with SessionLocal() as session:
        stmt = select(Detection).where(Detection.actor_id == actor_id)
        if rule_code:
            stmt = stmt.where(Detection.rule_code == rule_code)
        return session.scalars(stmt).all()


def test_four_failures_create_no_detection(actor):
    for i in range(4):
        send(actor, at=T0 + timedelta(seconds=i))
    assert detections_for(actor) == []


def test_five_failures_create_one_auth001_detection(actor):
    for i in range(5):
        send(actor, at=T0 + timedelta(seconds=i))
    [detection] = detections_for(actor)
    assert detection.rule_code == "AUTH-001"
    assert detection.event_count == 5
    assert "5 failed logins" in detection.explanation


def test_more_failures_extend_the_same_detection(actor):
    for i in range(7):
        send(actor, at=T0 + timedelta(seconds=i))
    [detection] = detections_for(actor)   # still ONE detection...
    assert detection.event_count == 7     # ...now with 7 pieces of evidence
    assert detection.window_end == T0 + timedelta(seconds=6)


def test_late_event_still_completes_the_pattern(actor):
    for i in range(1, 5):
        send(actor, at=T0 + timedelta(seconds=i))
    send(actor, at=T0)  # arrives last, but happened first
    [detection] = detections_for(actor)
    assert detection.window_start == T0


def test_retried_event_does_not_count_twice(actor):
    for i in range(4):
        send(actor, at=T0 + timedelta(seconds=i))
    repeated_id = str(uuid4())
    send(actor, at=T0 + timedelta(seconds=4), event_id=repeated_id)
    send(actor, at=T0 + timedelta(seconds=4), event_id=repeated_id)  # retry
    [detection] = detections_for(actor)
    assert detection.event_count == 5


def test_failures_then_success_creates_auth002(actor):
    for i in range(3):
        send(actor, at=T0 + timedelta(seconds=i))
    send(actor, "auth.login.success", at=T0 + timedelta(seconds=30), outcome="success")
    [detection] = detections_for(actor)
    assert detection.rule_code == "AUTH-002"
    assert detection.severity == "high"
    assert detection.event_count == 4


def test_permission_change_creates_account001(actor):
    send(actor, "account.permission.changed", outcome="success")
    [detection] = detections_for(actor, "ACCOUNT-001")
    assert detection.event_count == 1


def test_other_accounts_are_not_mixed_in(actor):
    other = f"test-{uuid4()}"
    try:
        for i in range(3):
            send(actor, at=T0 + timedelta(seconds=i))
            send(other, at=T0 + timedelta(seconds=i))
        assert detections_for(actor) == []  # 3 + 3 is not 5 for one account
    finally:
        with SessionLocal() as session:
            session.execute(delete(Event).where(Event.actor_id == other))
            session.commit()


def test_event_is_saved_even_if_detection_crashes(actor, monkeypatch):
    def broken(session, event):
        raise RuntimeError("bug in a rule")

    monkeypatch.setattr(events_module.detection_engine, "run_detection", broken)
    created = send(actor)
    assert client.get(f"/api/v1/events/{created['id']}").status_code == 200
