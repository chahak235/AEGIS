"""The Overview numbers."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import auth_headers

pytestmark = pytest.mark.db
client = TestClient(app, headers=auth_headers("analyst"))


def test_stats_count_new_activity(actor):
    before = client.get("/api/v1/stats").json()
    now = datetime.now(timezone.utc)
    for i in range(5):
        client.post("/api/v1/events", json={
            "event_type": "auth.login.failed", "occurred_at": (now + timedelta(seconds=i)).isoformat(),
            "source": "test", "actor_id": actor, "outcome": "failure"})
    after = client.get("/api/v1/stats").json()

    assert after["events_last_24h"] == before["events_last_24h"] + 5
    rule = after["detections_last_24h_by_rule"]
    assert rule.get("AUTH-001", 0) == before["detections_last_24h_by_rule"].get("AUTH-001", 0) + 1
    assert after["incidents_by_status"].get("open", 0) == before["incidents_by_status"].get("open", 0) + 1
    assert after["unassigned_active_incidents"] == before["unassigned_active_incidents"] + 1


def test_stats_need_login():
    assert TestClient(app).get("/api/v1/stats").status_code == 401
