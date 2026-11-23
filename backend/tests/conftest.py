"""Shared test setup. pytest loads this file automatically before any test file.

Its one job: make sure tests NEVER touch the real database.

Tests create and delete rows. If they ran against the real database, a bug in
a test's cleanup could delete real data. So tests use a separate, throw-away
database whose address is in TEST_DATABASE_URL (see backend/.env.example).
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

test_url = os.environ.get("TEST_DATABASE_URL")
if not test_url:
    pytest.exit(
        "TEST_DATABASE_URL is not set, so tests will not run (they must never use the "
        "real database). Add it to backend/.env; see backend/.env.example and docs/setup.md.",
        returncode=2,
    )
if test_url == os.environ.get("DATABASE_URL"):
    pytest.exit(
        "TEST_DATABASE_URL is the same as DATABASE_URL. Tests would write into the real "
        "database. Point TEST_DATABASE_URL at a separate test database.",
        returncode=2,
    )

# app/db.py reads DATABASE_URL when it is first imported. Overwrite it now,
# before any test imports the app, so the whole app talks to the test database.
os.environ["DATABASE_URL"] = test_url


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database():
    """Bring the test database up to the latest schema once, before all tests.

    Uses the same Alembic migrations as production, so the tests also prove
    that the migrations work on an empty database.
    """
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    yield
