"""Tests for reading detections through the API."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import Detection, Event

client = TestClient(app)
T0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def actor_with_detection():
    """An account with 5 failed logins, so it has exactly one AUTH-001 detection."""
    actor_id = f"test-{uuid4()}"
    for i in range(5):
        client.post("/api/v1/events", json={
            "event_type": "auth.login.failed",
            "occurred_at": (T0 + timedelta(seconds=i)).isoformat(),
            "source": "test",
            "actor_id": actor_id,
            "outcome": "failure",
        })
    yield actor_id
    with SessionLocal() as session:
        session.execute(delete(Detection).where(Detection.actor_id == actor_id))
        session.execute(delete(Event).where(Event.actor_id == actor_id))
        session.commit()


@pytest.mark.db
def test_list_detections_filtered_by_actor(actor_with_detection):
    response = client.get(f"/api/v1/detections?actor_id={actor_with_detection}")
    assert response.status_code == 200
    [detection] = response.json()
    assert detection["rule_code"] == "AUTH-001"
    assert detection["event_count"] == 5
    assert "events" not in detection  # lists stay small; evidence is in the detail view


@pytest.mark.db
def test_filters_combine(actor_with_detection):
    url = f"/api/v1/detections?actor_id={actor_with_detection}&rule_code=AUTH-002"
    assert client.get(url).json() == []


@pytest.mark.db
def test_detection_detail_includes_evidence_in_time_order(actor_with_detection):
    [summary] = client.get(f"/api/v1/detections?actor_id={actor_with_detection}").json()
    detail = client.get(f"/api/v1/detections/{summary['id']}").json()
    times = [e["occurred_at"] for e in detail["events"]]
    assert len(times) == 5
    assert times == sorted(times)


@pytest.mark.db
def test_unknown_detection_is_404():
    response = client.get("/api/v1/detections/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.db
def test_bad_severity_filter_is_rejected():
    assert client.get("/api/v1/detections?severity=extreme").status_code == 422


def test_rule_catalogue_lists_every_rule():
    # No database needed: the catalogue comes straight from the code.
    rules = client.get("/api/v1/rules").json()
    assert [r["code"] for r in rules] == ["AUTH-001", "AUTH-002", "ACCESS-001", "ACCOUNT-001", "API-001"]
    auth001 = rules[0]
    assert auth001["threshold"] == 5 and auth001["window_seconds"] == 300
