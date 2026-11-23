"""Writing audit records.

Call `record(...)` in the SAME database session (transaction) as the change it
describes. Then the change and its audit record are saved together, or not at
all: there can never be a change without a record, or a record of a change
that didn't happen.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog

SYSTEM = "system"  # actor name for things AEGIS does automatically


def record(
    session: Session,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: object,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        details=details or {},
    )
    session.add(entry)
    return entry
