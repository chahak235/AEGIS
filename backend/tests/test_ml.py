"""The ML detector (ML-001): features, the trained model, and its place in the engine."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.detection.catalogue import RULES_BY_CODE
from app.main import app
from app.ml import detector
from app.ml.features import FEATURE_NAMES, extract
from app.models import Detection
from conftest import auth_headers

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml"))
from synthetic import Generator  # noqa: E402

T0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
gen = Generator(seed=7)  # a different seed from training: data the model never saw


# --- Features (no database) ------------------------------------------------------

def test_features_count_what_they_say():
    window = gen.brute_force()
    features = dict(zip(FEATURE_NAMES, extract(window), strict=True))
    assert features["failed_logins"] == len(window) == features["event_count"]
    assert features["failure_ratio"] == 1.0
    assert features["distinct_resources"] == 1


def test_empty_window_has_zero_features():
    assert extract([]) == [0.0] * len(FEATURE_NAMES)


# --- The trained model (no database) -------------------------------------------------

def test_model_loads_and_is_in_the_catalogue():
    assert detector.load() is not None
    assert RULES_BY_CODE["ML-001"].source_type == "ml"


def test_most_normal_windows_are_not_flagged():
    flagged = sum(bool(detector.find(gen.normal())) for _ in range(150))
    assert flagged / 150 < 0.05  # trained for ~1% false alarms; leave room for randomness


@pytest.mark.parametrize("attack", ["brute_force", "scraping", "privilege_probing", "low_and_slow"])
def test_attacks_are_flagged(attack):
    caught = sum(bool(detector.find(getattr(gen, attack)())) for _ in range(10))
    assert caught >= 9


def test_explanation_is_honest_and_specific():
    window = gen.brute_force()
    text = detector.explain(sorted(window, key=lambda e: e.occurred_at))
    assert "iforest-v1" in text
    assert "failed_logins" in text
    assert "not proof" in text


def test_model_with_mismatched_features_switches_itself_off(tmp_path, monkeypatch):
    import json
    import shutil

    for name in ("isolation_forest.joblib", "metadata.json"):
        shutil.copy(detector.MODEL_DIR / name, tmp_path / name)
    meta = json.loads((tmp_path / "metadata.json").read_text())
    meta["feature_names"] = ["something", "else"]
    (tmp_path / "metadata.json").write_text(json.dumps(meta))

    monkeypatch.setattr(detector, "MODEL_DIR", tmp_path)
    detector.load.cache_clear()
    try:
        assert detector.load() is None
        assert detector.find(gen.brute_force()) == []
    finally:
        monkeypatch.undo()
        detector.load.cache_clear()


# --- In the live engine (database) -----------------------------------------------------

@pytest.mark.db
@pytest.mark.ml
def test_engine_saves_ml_detection_with_provenance(actor):
    client = TestClient(app, headers=auth_headers("analyst"))
    for i in range(10):
        client.post("/api/v1/events", json={
            "event_type": "auth.login.failed", "occurred_at": (T0 + timedelta(seconds=i)).isoformat(),
            "source": "test", "actor_id": actor, "outcome": "failure", "resource": "/login"})
    with SessionLocal() as session:
        found = {d.rule_code: d for d in session.scalars(select(Detection).where(Detection.actor_id == actor))}
    assert {"AUTH-001", "ML-001"} <= set(found)
    ml = found["ML-001"]
    assert ml.source_type == "ml" and ml.model_version == "iforest-v1"
    assert ml.anomaly_score is not None
    assert found["AUTH-001"].source_type == "rule" and found["AUTH-001"].anomaly_score is None
    # Both detections concern the same account at the same time: one incident.
    assert ml.incident_id == found["AUTH-001"].incident_id
