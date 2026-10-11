from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db import SessionLocal


def get_session() -> Iterator[Session]:
    """Give each request its own database session, then close it."""
    with SessionLocal() as session:
        yield session
