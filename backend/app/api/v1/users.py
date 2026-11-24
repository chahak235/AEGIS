from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.deps import admin_only, get_session
from app.models import ApiKey, User
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreatedOut,
    ApiKeyOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import generate_api_key, hash_password

# Everything here is for admins only.
router = APIRouter(prefix="/api/v1/users", tags=["admin"], dependencies=[Depends(admin_only)])
keys_router = APIRouter(prefix="/api/v1/api-keys", tags=["admin"], dependencies=[Depends(admin_only)])


# --- Users -------------------------------------------------------------------

@router.get("", response_model=list[UserOut])
def list_users(session: Session = Depends(get_session)):
    return session.scalars(select(User).order_by(User.username)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(admin_only),
):
    if session.scalars(select(User).where(User.username == body.username)).first():
        raise HTTPException(status_code=409, detail="That username is taken.")
    user = User(username=body.username, password_hash=hash_password(body.password),
                role=body.role, is_active=True)
    session.add(user)
    audit.record(session, actor=admin.username, action="user.created",
                 target_type="user", target_id=body.username, details={"role": body.role})
    session.commit()
    session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    body: UserUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(admin_only),
):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Guard against locking yourself out (and leaving nobody who can fix it).
    if user.id == admin.id and (body.role == "analyst" or body.is_active is False):
        raise HTTPException(status_code=409, detail="You cannot demote or deactivate yourself.")

    changes = {}
    if body.role is not None and body.role != user.role:
        changes["role"] = {"from": user.role, "to": body.role}
        user.role = body.role
    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
    if body.password is not None:
        changes["password"] = "changed"  # never log the password itself
        user.password_hash = hash_password(body.password)
    if changes:
        audit.record(session, actor=admin.username, action="user.updated",
                     target_type="user", target_id=user.username, details=changes)
    session.commit()
    session.refresh(user)
    return user


# --- API keys ----------------------------------------------------------------

@keys_router.get("", response_model=list[ApiKeyOut])
def list_api_keys(session: Session = Depends(get_session)):
    return session.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())).all()


@keys_router.post("", response_model=ApiKeyCreatedOut, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(admin_only),
):
    """Create a key for a system that sends events. **Copy the key now**: it is never shown again."""
    full_key, prefix, key_hash = generate_api_key()
    key = ApiKey(name=body.name, prefix=prefix, key_hash=key_hash, created_by=admin.username)
    session.add(key)
    session.flush()
    audit.record(session, actor=admin.username, action="api_key.created",
                 target_type="api_key", target_id=key.id, details={"name": body.name, "prefix": prefix})
    session.commit()
    session.refresh(key)
    return ApiKeyCreatedOut(**ApiKeyOut.model_validate(key).model_dump(), key=full_key)


@keys_router.post("/{key_id}/revoke", response_model=ApiKeyOut)
def revoke_api_key(
    key_id: UUID,
    session: Session = Depends(get_session),
    admin: User = Depends(admin_only),
):
    """Switch a key off for good. It is kept (not deleted) so old audit records still make sense."""
    key = session.get(ApiKey, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.is_active:
        key.is_active = False
        audit.record(session, actor=admin.username, action="api_key.revoked",
                     target_type="api_key", target_id=key.id, details={"name": key.name})
        session.commit()
        session.refresh(key)
    return key
