"""Shared test setup. pytest loads this file automatically before any test file.

Two kinds of tests live in this folder:

* Unit tests (e.g. test_rules.py) check pure Python logic. They need no database
  and always run.
* Database tests are marked with `pytest.mark.db`. They create and delete rows,
  so they must NEVER touch the real database. They use a separate, throw-away
  database whose address is in TEST_DATABASE_URL (see backend/.env.example).
  If TEST_DATABASE_URL is missing, database tests are SKIPPED, and pytest
  prints the reason in its summary.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DATABASE_URL and TEST_DATABASE_URL == os.environ.get("DATABASE_URL"):
    pytest.exit(
        "TEST_DATABASE_URL is the same as DATABASE_URL. Tests would write into the real "
        "database. Point TEST_DATABASE_URL at a separate test database.",
        returncode=2,
    )

# app/db.py reads DATABASE_URL when it is first imported. Overwrite it now,
# before any test imports the app, so the whole app talks to the test database.
# With no test database we put in an address that cannot be reached: importing
# the app still works (unit tests need that), but nothing can touch real data.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "postgresql://no-test-db@localhost:1/none"

# Tests sign their own tokens with a fixed, test-only secret (never a real one).
os.environ["JWT_SECRET"] = "test-only-secret-not-used-anywhere-real-0123456789"

# Two fixed test users, created once per test run (see migrated_test_database).
# Fixed IDs let test files make tokens at import time.
TEST_USERS = {
    "admin": ("00000000-0000-0000-0000-00000000a001", "test-admin"),
    "analyst": ("00000000-0000-0000-0000-00000000a002", "test-analyst"),
}
TEST_PASSWORD = "correct-horse-battery-staple"


def auth_headers(role: str = "analyst") -> dict:
    """Headers that log a request in as the test admin or test analyst."""
    from app.security import create_access_token

    user_id, username = TEST_USERS[role]
    token = create_access_token(user_id=user_id, username=username, role=role)
    return {"Authorization": f"Bearer {token}"}

SKIP_REASON = (
    "TEST_DATABASE_URL is not set, so database tests were skipped. "
    "See docs/setup.md, step 4."
)


def pytest_collection_modifyitems(config, items):
    """Skip every test marked `db` when there is no test database."""
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason=SKIP_REASON)
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


def delete_everything_for(actor_id: str) -> None:
    """Remove all rows a test created for one account, in an order the foreign keys allow."""
    from sqlalchemy import delete, select, text

    from app.db import SessionLocal
    from app.models import AuditLog, Detection, Event, Incident

    with SessionLocal() as session:
        incident_ids = [str(i) for i in session.scalars(
            select(Incident.id).where(Incident.actor_id == actor_id))]
        if incident_ids:
            # The audit log is append-only. Deleting needs this explicit switch,
            # which only exists for clean-ups like this one (see the migration).
            session.execute(text("SET LOCAL aegis.allow_audit_delete = 'on'"))
            session.execute(delete(AuditLog).where(
                AuditLog.target_type == "incident", AuditLog.target_id.in_(incident_ids)))
        session.execute(delete(Incident).where(Incident.actor_id == actor_id))  # notes go too
        session.execute(delete(Detection).where(Detection.actor_id == actor_id))  # links go too
        session.execute(delete(Event).where(Event.actor_id == actor_id))
        session.commit()


@pytest.fixture
def actor():
    """A unique, made-up account name for one test. Everything created for it
    is deleted afterwards, so tests never see each other's data."""
    from uuid import uuid4

    actor_id = f"test-{uuid4()}"
    yield actor_id
    delete_everything_for(actor_id)


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database():
    """Bring the test database up to the latest schema once, before all tests.

    Uses the same Alembic migrations as production, so the tests also prove
    that the migrations work on an empty database.
    """
    if TEST_DATABASE_URL:
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
        _ensure_test_users()
    yield


def _ensure_test_users() -> None:
    from uuid import UUID

    from app.db import SessionLocal
    from app.models import User
    from app.security import hash_password

    with SessionLocal() as session:
        for role, (user_id, username) in TEST_USERS.items():
            user = session.get(User, UUID(user_id))
            if user is None:
                user = User(id=UUID(user_id), username=username)
                session.add(user)
            user.role, user.is_active = role, True
            user.password_hash = hash_password(TEST_PASSWORD)
        session.commit()
