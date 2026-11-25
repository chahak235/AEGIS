"""Login, tokens, roles and API keys.

Security features need NEGATIVE tests most of all: proving that the wrong
person is kept out matters more than proving the right person gets in.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app import config
from app.db import SessionLocal
from app.main import app
from app.models import ApiKey, AuditLog, Detection, User
from app.security import create_access_token, hash_password, verify_password
from conftest import TEST_PASSWORD, TEST_USERS, auth_headers, delete_everything_for

T0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
anonymous = TestClient(app)
analyst = TestClient(app, headers=auth_headers("analyst"))
admin = TestClient(app, headers=auth_headers("admin"))


def login(username, password):
    return anonymous.post("/api/v1/auth/login", data={"username": username, "password": password})


# --- Pure security helpers (no database) -------------------------------------

def test_password_hash_is_not_the_password_and_is_salted():
    h1, h2 = hash_password("my secret password"), hash_password("my secret password")
    assert "my secret password" not in h1
    assert h1 != h2                       # random salt: same password, different hash
    assert h1.startswith("$argon2id$")
    assert verify_password("my secret password", h1)
    assert not verify_password("wrong password!!", h1)


def test_unknown_user_check_still_runs_and_fails():
    assert verify_password("anything", None) is False


def test_rules_catalogue_needs_login():
    assert anonymous.get("/api/v1/rules").status_code == 401


def test_health_and_home_are_public():
    assert anonymous.get("/health/live").status_code == 200
    assert anonymous.get("/").status_code == 200


def test_token_signed_with_another_secret_is_rejected():
    forged = jwt.encode({"sub": TEST_USERS["admin"][0], "role": "admin", "iss": "aegis",
                         "aud": "aegis-api", "iat": T0, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        "attacker-secret-attacker-secret-attacker!", algorithm="HS256")
    r = anonymous.get("/api/v1/rules", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_unsigned_alg_none_token_is_rejected():
    claims = {"sub": TEST_USERS["admin"][0], "role": "admin", "iss": "aegis", "aud": "aegis-api",
              "iat": T0, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    unsigned = jwt.encode(claims, key=None, algorithm="none")
    r = anonymous.get("/api/v1/rules", headers={"Authorization": f"Bearer {unsigned}"})
    assert r.status_code == 401


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_TOKEN_MINUTES", -1)  # token born already expired
    user_id, username = TEST_USERS["admin"]
    token = create_access_token(user_id=user_id, username=username, role="admin")
    r = anonymous.get("/api/v1/rules", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_garbage_token_is_rejected():
    r = anonymous.get("/api/v1/rules", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


# --- Login (database) ----------------------------------------------------------

@pytest.mark.db
def test_login_returns_a_working_token():
    r = login("test-analyst", TEST_PASSWORD)
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = anonymous.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["username"] == "test-analyst"
    assert "password_hash" not in me.json()


@pytest.mark.db
def test_wrong_password_and_unknown_user_get_the_same_answer():
    wrong_password = login("test-analyst", "not-the-password")
    unknown_user = login("nobody-" + uuid4().hex[:8], "whatever-password")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()  # no hint whether the user exists


@pytest.mark.db
def test_failed_logins_to_aegis_are_detected_by_aegis_itself():
    target = "victim-" + uuid4().hex[:8]
    try:
        for _ in range(5):
            login(target, "guessing-password")
        with SessionLocal() as session:
            codes = session.scalars(select(Detection.rule_code).where(Detection.actor_id == target)).all()
        assert "AUTH-001" in codes   # AEGIS caught a brute-force attempt against itself
    finally:
        _wipe_login_audit(target)
        delete_everything_for(target)


@pytest.mark.db
def test_failed_login_is_audited():
    target = "nobody-" + uuid4().hex[:8]
    try:
        login(target, "whatever-password")
        with SessionLocal() as session:
            actions = session.scalars(select(AuditLog.action).where(AuditLog.target_id == target)).all()
        assert actions == ["auth.login_failed"]
    finally:
        _wipe_login_audit(target)
        delete_everything_for(target)


def _wipe_login_audit(username):
    with SessionLocal() as session:
        session.execute(text("SET LOCAL aegis.allow_audit_delete = 'on'"))
        session.execute(delete(AuditLog).where(AuditLog.target_type == "user", AuditLog.target_id == username))
        session.commit()


# --- Roles ---------------------------------------------------------------------

@pytest.mark.db
def test_analyst_cannot_use_admin_endpoints():
    assert analyst.get("/api/v1/users").status_code == 403
    assert analyst.get("/api/v1/audit").status_code == 403
    assert analyst.post("/api/v1/api-keys", json={"name": "x"}).status_code == 403


@pytest.mark.db
def test_admin_can_use_admin_endpoints():
    assert admin.get("/api/v1/users").status_code == 200
    assert admin.get("/api/v1/audit").status_code == 200


@pytest.mark.db
def test_reading_incidents_needs_login():
    assert anonymous.get("/api/v1/incidents").status_code == 401
    assert analyst.get("/api/v1/incidents").status_code == 200


# --- User management -------------------------------------------------------------

@pytest.fixture
def new_username():
    username = "test-user-" + uuid4().hex[:8]
    yield username
    _wipe_login_audit(username)
    with SessionLocal() as session:
        session.execute(delete(User).where(User.username == username))
        session.commit()
    delete_everything_for(username)


@pytest.mark.db
def test_admin_creates_user_who_can_then_log_in(new_username):
    r = admin.post("/api/v1/users", json={"username": new_username, "password": "a-long-password-1", "role": "analyst"})
    assert r.status_code == 201
    assert login(new_username, "a-long-password-1").status_code == 200


@pytest.mark.db
def test_duplicate_username_is_409(new_username):
    body = {"username": new_username, "password": "a-long-password-1"}
    admin.post("/api/v1/users", json=body)
    assert admin.post("/api/v1/users", json=body).status_code == 409


@pytest.mark.db
def test_short_password_is_rejected(new_username):
    r = admin.post("/api/v1/users", json={"username": new_username, "password": "short"})
    assert r.status_code == 422


@pytest.mark.db
def test_deactivated_user_is_locked_out_immediately(new_username):
    created = admin.post("/api/v1/users", json={"username": new_username, "password": "a-long-password-1"}).json()
    token = login(new_username, "a-long-password-1").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert anonymous.get("/api/v1/auth/me", headers=headers).status_code == 200

    admin.patch(f"/api/v1/users/{created['id']}", json={"is_active": False})
    # Same token, not expired, but the user is switched off: refused.
    assert anonymous.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert login(new_username, "a-long-password-1").status_code == 401


@pytest.mark.db
def test_admin_cannot_demote_themselves():
    admin_id = TEST_USERS["admin"][0]
    assert admin.patch(f"/api/v1/users/{admin_id}", json={"role": "analyst"}).status_code == 409


# --- API keys --------------------------------------------------------------------

@pytest.fixture
def api_key():
    r = admin.post("/api/v1/api-keys", json={"name": "test-source-" + uuid4().hex[:6]})
    assert r.status_code == 201
    created = r.json()
    yield created
    with SessionLocal() as session:
        session.execute(text("SET LOCAL aegis.allow_audit_delete = 'on'"))
        session.execute(delete(AuditLog).where(AuditLog.target_id == created["id"]))
        session.execute(delete(ApiKey).where(ApiKey.id == created["id"]))
        session.commit()


def event_body(actor_id):
    return {"event_type": "auth.login.failed", "occurred_at": T0.isoformat(),
            "source": "test", "actor_id": actor_id, "outcome": "failure"}


@pytest.mark.db
def test_api_key_is_shown_once_and_stored_hashed(api_key):
    assert api_key["key"].startswith(api_key["prefix"] + "_")
    listed = admin.get("/api/v1/api-keys").json()
    assert all("key" not in k for k in listed)  # never shown again
    with SessionLocal() as session:
        stored = session.get(ApiKey, api_key["id"])
        assert stored.key_hash != api_key["key"]


@pytest.mark.db
def test_api_key_can_send_events_but_not_read_incidents(api_key, actor):
    source = TestClient(app, headers={"X-API-Key": api_key["key"]})
    assert source.post("/api/v1/events", json=event_body(actor)).status_code == 201
    assert source.get("/api/v1/incidents").status_code == 401  # keys are for sending only


@pytest.mark.db
def test_revoked_api_key_is_refused(api_key, actor):
    admin.post(f"/api/v1/api-keys/{api_key['id']}/revoke")
    source = TestClient(app, headers={"X-API-Key": api_key["key"]})
    assert source.post("/api/v1/events", json=event_body(actor)).status_code == 401


@pytest.mark.db
def test_sending_events_needs_a_key_or_login(actor):
    assert anonymous.post("/api/v1/events", json=event_body(actor)).status_code == 401
    wrong = TestClient(app, headers={"X-API-Key": "aeg_0000_made-up"})
    assert wrong.post("/api/v1/events", json=event_body(actor)).status_code == 401


@pytest.mark.db
def test_assigning_to_unknown_user_is_rejected(actor):
    for i in range(5):
        when = (T0 + timedelta(seconds=i)).isoformat()
        analyst.post("/api/v1/events", json={**event_body(actor), "occurred_at": when})
    [incident] = analyst.get(f"/api/v1/incidents?actor_id={actor}").json()
    r = analyst.patch(f"/api/v1/incidents/{incident['id']}", json={"assigned_to": "ghost"})
    assert r.status_code == 422


@pytest.mark.db
def test_notes_are_signed_with_the_logged_in_username(actor):
    for i in range(5):
        when = (T0 + timedelta(seconds=i)).isoformat()
        analyst.post("/api/v1/events", json={**event_body(actor), "occurred_at": when})
    [incident] = analyst.get(f"/api/v1/incidents?actor_id={actor}").json()
    note = analyst.post(f"/api/v1/incidents/{incident['id']}/notes", json={"body": "hi"}).json()
    assert note["author"] == "test-analyst"
