"""Things FastAPI hands to endpoints: database sessions and "who is calling".

Two kinds of callers:
* People (analysts, admins) log in and send   Authorization: Bearer <JWT>
* Systems that send events use                X-API-Key: <key>

401 Unauthorized = "I don't know who you are" (missing / invalid / expired credentials).
403 Forbidden    = "I know who you are, but you're not allowed to do this."
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ApiKey, User
from app.security import decode_access_token, hash_api_key

ROLES = ("analyst", "admin")

# tokenUrl makes the "Authorize" button on /docs show a username/password form.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_session() -> Iterator[Session]:
    """Give each request its own database session, then close it."""
    with SessionLocal() as session:
        yield session


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _user_from_token(token: str | None, session: Session) -> User | None:
    if not token:
        return None
    try:
        claims = decode_access_token(token)
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise _unauthorized("Invalid or expired token")
    user = session.get(User, user_id)
    # Checked on EVERY request: a deactivated user is locked out immediately,
    # even though their token has not expired yet.
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    user = _user_from_token(token, session)
    if user is None:
        raise _unauthorized()
    return user


def require_roles(*allowed: str):
    """Build a dependency that only lets users with one of these roles through."""

    def check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action needs role: {' or '.join(allowed)}",
            )
        return user

    return check


any_user = require_roles("analyst", "admin")
admin_only = require_roles("admin")


def get_event_sender(
    api_key: str | None = Depends(api_key_header),
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> str:
    """Who is sending an event: an active API key, or a logged-in user.

    Returns a label for the logs, e.g. "apikey:web-app" or "user:alice".
    """
    if api_key:
        key = session.scalars(
            select(ApiKey).where(ApiKey.key_hash == hash_api_key(api_key), ApiKey.is_active)
        ).first()
        if key is None:
            raise _unauthorized("Invalid API key")
        key.last_used_at = datetime.now(timezone.utc)
        session.commit()
        return f"apikey:{key.name}"
    user = _user_from_token(token, session)
    if user is None:
        raise _unauthorized("Send an X-API-Key header or log in")
    return f"user:{user.username}"
