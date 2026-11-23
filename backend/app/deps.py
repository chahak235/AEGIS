from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db import SessionLocal


def get_session() -> Iterator[Session]:
    """Give each request its own database session, then close it."""
    with SessionLocal() as session:
        yield session


def current_username() -> str:
    """Who is making this request.

    Placeholder until login (JWT) is added: everyone is "anonymous".
    Endpoints already ask for this dependency, so adding real login later
    only changes this one function, not every endpoint.
    """
    return "anonymous"
