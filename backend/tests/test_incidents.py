"""Incidents end to end: events in -> detections -> incidents -> analyst actions."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.db

client = TestClient(app)
T0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)


def send(actor_id, event_type="auth.login.failed", at=T0, outcome="failure"):
    response = client.post("/api/v1/events", json={
        "event_type": event_type,
        "occurred_at": at.isoformat(),
        "source": "test",
        "actor_id": actor_id,
        "outcome": outcome,
    })
    assert response.status_code == 201, response.text


def five_failures(actor_id, start=T0):
    for i in range(5):
        send(actor_id, at=start + timedelta(seconds=i))


def incidents_for(actor_id):
    return client.get(f"/api/v1/incidents?actor_id={actor_id}").json()


def only_incident(actor_id):
    [incident] = incidents_for(actor_id)
    return client.get(f"/api/v1/incidents/{incident['id']}").json()


# --- Correlation -------------------------------------------------------------

def test_first_detection_opens_an_incident(actor):
    five_failures(actor)
    incident = only_incident(actor)
    assert incident["status"] == "open"
    assert incident["severity"] == "medium"
    assert [d["rule_code"] for d in incident["detections"]] == ["AUTH-001"]
    assert len(incident["timeline"]) == 5
    assert "single AUTH-001" in incident["correlation_reason"]


def test_related_detections_join_the_same_incident(actor):
    five_failures(actor)
    send(actor, "auth.login.success", at=T0 + timedelta(seconds=30), outcome="success")
    send(actor, "account.permission.changed", at=T0 + timedelta(minutes=5), outcome="success")
    incident = only_incident(actor)  # still ONE incident
    codes = sorted(d["rule_code"] for d in incident["detections"])
    assert codes == ["ACCOUNT-001", "AUTH-001", "AUTH-002"]
    # 3 different rules -> highest (high) raised one level:
    assert incident["severity"] == "critical"
    assert "Severity raised" in incident["correlation_reason"]
    # Timeline: each event once, in time order (failed logins count for 2 rules).
    times = [e["occurred_at"] for e in incident["timeline"]]
    assert len(times) == 7 and times == sorted(times)


def test_activity_hours_later_opens_a_new_incident(actor):
    five_failures(actor, start=T0)
    five_failures(actor, start=T0 + timedelta(hours=3))
    assert len(incidents_for(actor)) == 2


def test_different_accounts_never_share_an_incident(actor):
    other = actor + "-other"
    try:
        five_failures(actor)
        five_failures(other)
        assert len(incidents_for(actor)) == 1
        assert len(incidents_for(other)) == 1
    finally:
        from conftest import delete_everything_for
        delete_everything_for(other)


def test_resolved_incident_is_not_reopened_by_new_activity(actor):
    five_failures(actor)
    [incident] = incidents_for(actor)
    client.patch(f"/api/v1/incidents/{incident['id']}",
                 json={"status": "resolved", "resolution": "false_positive"})
    send(actor, "account.permission.changed", at=T0 + timedelta(minutes=1), outcome="success")
    statuses = sorted(i["status"] for i in incidents_for(actor))
    assert statuses == ["open", "resolved"]


# --- Analyst actions ---------------------------------------------------------

def test_status_flow_and_assignment(actor):
    five_failures(actor)
    incident_id = incidents_for(actor)[0]["id"]
    url = f"/api/v1/incidents/{incident_id}"

    r = client.patch(url, json={"status": "acknowledged", "assigned_to": "analyst-1"})
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged" and r.json()["assigned_to"] == "analyst-1"

    r = client.patch(url, json={"status": "resolved", "resolution": "true_positive",
                                "resolution_note": "Password reset, attacker IP blocked."})
    assert r.status_code == 200
    assert r.json()["resolution"] == "true_positive"
    assert r.json()["resolved_at"] is not None

    assert client.patch(url, json={"status": "closed"}).status_code == 200


def test_invalid_transition_is_409(actor):
    five_failures(actor)
    url = f"/api/v1/incidents/{incidents_for(actor)[0]['id']}"
    r = client.patch(url, json={"status": "closed"})  # open -> closed is not allowed
    assert r.status_code == 409
    assert "Allowed from 'open'" in r.json()["detail"]


def test_resolving_needs_a_resolution(actor):
    five_failures(actor)
    url = f"/api/v1/incidents/{incidents_for(actor)[0]['id']}"
    assert client.patch(url, json={"status": "resolved"}).status_code == 422


def test_resolution_without_resolving_is_rejected(actor):
    five_failures(actor)
    url = f"/api/v1/incidents/{incidents_for(actor)[0]['id']}"
    assert client.patch(url, json={"resolution": "benign"}).status_code == 422


def test_reopen_clears_the_old_conclusion(actor):
    five_failures(actor)
    url = f"/api/v1/incidents/{incidents_for(actor)[0]['id']}"
    client.patch(url, json={"status": "resolved", "resolution": "benign"})
    r = client.patch(url, json={"status": "investigating"})
    assert r.json()["status"] == "investigating"
    assert r.json()["resolution"] is None and r.json()["resolved_at"] is None


def test_unassign_with_null(actor):
    five_failures(actor)
    url = f"/api/v1/incidents/{incidents_for(actor)[0]['id']}"
    client.patch(url, json={"assigned_to": "analyst-1"})
    assert client.patch(url, json={"assigned_to": None}).json()["assigned_to"] is None


def test_notes_are_added_in_order(actor):
    five_failures(actor)
    incident_id = incidents_for(actor)[0]["id"]
    for text in ["Checked the IP: it is a VPN exit node.", "User confirms it was not them."]:
        r = client.post(f"/api/v1/incidents/{incident_id}/notes", json={"body": text})
        assert r.status_code == 201
    notes = client.get(f"/api/v1/incidents/{incident_id}").json()["notes"]
    assert [n["body"][:7] for n in notes] == ["Checked", "User co"]


def test_empty_note_is_rejected(actor):
    five_failures(actor)
    incident_id = incidents_for(actor)[0]["id"]
    assert client.post(f"/api/v1/incidents/{incident_id}/notes", json={"body": ""}).status_code == 422


def test_closed_incident_takes_no_notes(actor):
    five_failures(actor)
    incident_id = incidents_for(actor)[0]["id"]
    url = f"/api/v1/incidents/{incident_id}"
    client.patch(url, json={"status": "resolved", "resolution": "benign"})
    client.patch(url, json={"status": "closed"})
    assert client.post(f"{url}/notes", json={"body": "late"}).status_code == 409


def test_unknown_incident_is_404():
    assert client.get("/api/v1/incidents/00000000-0000-0000-0000-000000000000").status_code == 404


def test_queue_filters(actor):
    five_failures(actor)
    assert len(client.get(f"/api/v1/incidents?actor_id={actor}&status=open").json()) == 1
    assert client.get(f"/api/v1/incidents?actor_id={actor}&status=closed").json() == []
    assert client.get("/api/v1/incidents?severity=extreme").status_code == 422
