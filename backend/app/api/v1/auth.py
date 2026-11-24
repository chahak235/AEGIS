from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, config
from app.deps import get_current_user, get_session
from app.ingest import ingest_event
from app.models import User
from app.schemas import EventIn, TokenOut, UserOut
from app.security import (
    create_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# One message for every failure: never reveal whether the username exists.
LOGIN_FAILED = "Incorrect username or password"


def _record_login_event(session: Session, request: Request, username: str, ok: bool) -> None:
    """AEGIS watches itself: its own logins become events, so rules like
    AUTH-001 (repeated failed logins) also catch someone attacking AEGIS."""
    ingest_event(session, EventIn(
        event_type="auth.login.success" if ok else "auth.login.failed",
        occurred_at=datetime.now(timezone.utc),
        source="aegis",
        actor_id=username[:100] or "(empty)",
        resource="/api/v1/auth/login",
        outcome="success" if ok else "failure",
        details={"client_ip": request.client.host if request.client else None},
    ))


@router.post("/login", response_model=TokenOut)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Exchange username + password for an access token (JWT).

    On /docs, click **Authorize**, type a username and password, and every
    request you try afterwards is sent with the token automatically.
    """
    username = form.username.strip().lower()
    user = session.scalars(select(User).where(User.username == username)).first()

    # verify_password runs even for unknown users (against a dummy hash) so the
    # response time doesn't reveal which usernames exist.
    password_ok = verify_password(form.password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        audit.record(session, actor=username or "(empty)", action="auth.login_failed",
                     target_type="user", target_id=username or "(empty)",
                     details={"reason": "inactive" if user and password_ok else "bad_credentials"})
        session.commit()
        _record_login_event(session, request, username, ok=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=LOGIN_FAILED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(form.password)  # upgrade old hashes on the fly
    user.last_login_at = datetime.now(timezone.utc)
    audit.record(session, actor=user.username, action="auth.login_succeeded",
                 target_type="user", target_id=user.username)
    session.commit()
    _record_login_event(session, request, user.username, ok=True)

    token = create_access_token(user_id=str(user.id), username=user.username, role=user.role)
    return TokenOut(access_token=token, expires_in=config.ACCESS_TOKEN_MINUTES * 60)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Who am I logged in as?"""
    return user
