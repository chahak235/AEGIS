"""The audit log: every change to an incident is recorded, and records can't be altered."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db import SessionLocal
from app.main import app
from conftest import auth_headers
from app.models import AuditLog

pytestmark = pytest.mark.db

# Logged in as the test analyst (see conftest.py).
client = TestClient(app, headers=auth_headers("analyst"))
T0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)


def incident_for(actor_id):
    for i in range(5):
        client.post("/api/v1/events", json={
            "event_type": "auth.login.failed",
            "occurred_at": (T0 + timedelta(seconds=i)).isoformat(),
            "source": "test", "actor_id": actor_id, "outcome": "failure",
        })
    [incident] = client.get(f"/api/v1/incidents?actor_id={actor_id}").json()
    return incident["id"]


def history(incident_id):
    return client.get(f"/api/v1/incidents/{incident_id}/audit").json()


def test_incident_creation_is_audited_as_system(actor):
    incident_id = incident_for(actor)
    [entry] = history(incident_id)
    assert entry["action"] == "incident.created"
    assert entry["actor"] == "system"
    assert entry["details"]["rule_code"] == "AUTH-001"


def test_analyst_actions_are_audited_in_order(actor):
    incident_id = incident_for(actor)
    url = f"/api/v1/incidents/{incident_id}"
    client.patch(url, json={"status": "acknowledged", "assigned_to": "test-analyst"})
    client.post(f"{url}/notes", json={"body": "Looking into it."})
    client.patch(url, json={"status": "resolved", "resolution": "benign"})

    actions = [e["action"] for e in history(incident_id)]
    assert actions == [
        "incident.created",
        "incident.status_changed",
        "incident.assigned",
        "incident.note_added",
        "incident.status_changed",
    ]
    last = history(incident_id)[-1]
    assert last["details"] == {"from": "acknowledged", "to": "resolved", "resolution": "benign"}


def test_reopen_keeps_the_old_conclusion_in_the_audit_log(actor):
    incident_id = incident_for(actor)
    url = f"/api/v1/incidents/{incident_id}"
    client.patch(url, json={"status": "resolved", "resolution": "false_positive"})
    client.patch(url, json={"status": "investigating"})
    assert history(incident_id)[-1]["details"]["previous_resolution"] == "false_positive"


def test_no_change_means_no_audit_record(actor):
    incident_id = incident_for(actor)
    url = f"/api/v1/incidents/{incident_id}"
    client.patch(url, json={"assigned_to": "test-admin"})
    client.patch(url, json={"assigned_to": "test-admin"})  # same value again
    assert [e["action"] for e in history(incident_id)].count("incident.assigned") == 1


def test_rejected_change_leaves_no_audit_record(actor):
    incident_id = incident_for(actor)
    client.patch(f"/api/v1/incidents/{incident_id}", json={"status": "closed"})  # 409
    assert [e["action"] for e in history(incident_id)] == ["incident.created"]


def test_audit_search_by_target(actor):
    incident_id = incident_for(actor)
    admin = TestClient(app, headers=auth_headers("admin"))
    rows = admin.get(f"/api/v1/audit?target_type=incident&target_id={incident_id}").json()
    assert len(rows) == 1


def test_database_refuses_to_edit_audit_records(actor):
    incident_id = incident_for(actor)
    with SessionLocal() as session:
        entry = session.scalars(select(AuditLog).where(AuditLog.target_id == incident_id)).first()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("UPDATE audit_logs SET actor = 'someone-else' WHERE id = :id"),
                            {"id": entry.id})
        session.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": entry.id})
        session.rollback()
