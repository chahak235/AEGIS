from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import Event

client = TestClient(app)


@pytest.fixture
def actor():
    """A unique actor per test, and cleanup of its events afterwards."""
    actor_id = f"test-{uuid4()}"
    yield actor_id
    with SessionLocal() as session:
        session.execute(delete(Event).where(Event.actor_id == actor_id))
        session.commit()


def make_event(actor_id, **overrides):
    event = {
        "event_type": "auth.login.failed",
        "occurred_at": "2026-10-11T10:00:01Z",
        "source": "web-app",
        "actor_id": actor_id,
        "resource": "/login",
        "outcome": "failure",
        "details": {"ip": "10.0.0.5"},
    }
    event.update(overrides)
    return event


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_create_event_returns_201_with_id(actor):
    response = client.post("/api/v1/events", json=make_event(actor))
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert "ingested_at" in body


def test_bad_outcome_is_rejected(actor):
    response = client.post("/api/v1/events", json=make_event(actor, outcome="banana"))
    assert response.status_code == 422


def test_bad_event_type_is_rejected(actor):
    response = client.post("/api/v1/events", json=make_event(actor, event_type="Auth Login"))
    assert response.status_code == 422


def test_get_event_by_id(actor):
    created = client.post("/api/v1/events", json=make_event(actor)).json()
    response = client.get(f"/api/v1/events/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_unknown_event_is_404():
    response = client.get("/api/v1/events/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_list_respects_limit(actor):
    for _ in range(3):
        client.post("/api/v1/events", json=make_event(actor))
    response = client.get("/api/v1/events?limit=2")
    assert response.status_code == 200
    assert len(response.json()) <= 2
