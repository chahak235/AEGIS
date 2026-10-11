import pytest
from fastapi.testclient import TestClient

from app.api.v1.events import EVENTS
from app.main import app

client = TestClient(app)

VALID_EVENT = {
    "event_type": "auth.login.failed",
    "occurred_at": "2026-10-11T10:00:01Z",
    "source": "web-app",
    "actor_id": "user-123",
    "resource": "/login",
    "outcome": "failure",
    "details": {"ip": "10.0.0.5"},
}


@pytest.fixture(autouse=True)
def clean_storage():
    EVENTS.clear()


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_create_event_returns_201_with_id():
    response = client.post("/api/v1/events", json=VALID_EVENT)
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert "ingested_at" in body


def test_bad_outcome_is_rejected():
    bad = {**VALID_EVENT, "outcome": "banana"}
    response = client.post("/api/v1/events", json=bad)
    assert response.status_code == 422


def test_bad_event_type_is_rejected():
    bad = {**VALID_EVENT, "event_type": "Auth Login"}
    response = client.post("/api/v1/events", json=bad)
    assert response.status_code == 422


def test_get_event_by_id():
    created = client.post("/api/v1/events", json=VALID_EVENT).json()
    response = client.get(f"/api/v1/events/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_unknown_event_is_404():
    response = client.get("/api/v1/events/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
