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
    yield
