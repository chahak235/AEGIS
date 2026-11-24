import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import any_user, get_event_sender, get_session
from app.ingest import ingest_event
from app.models import Event
from app.schemas import EventIn, EventOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
def create_event(
    event: EventIn,
    response: Response,
    session: Session = Depends(get_session),
    sender: str = Depends(get_event_sender),
):
    """Save an event. Needs an `X-API-Key` header (systems) or a login (people).

    Idempotency: if the client sends its own `event_id` and retries the same
    request (e.g. after a network timeout), we return the already-saved event
    with 200 instead of saving a duplicate. Duplicates would make
    "5 failed logins" rules fire on what was really 1 failed login sent 5 times.
    """
    row, created = ingest_event(session, event)
    if not created:
        response.status_code = 200
    logger.info("Event %s received from %s (new=%s)", row.id, sender, created)
    return row


@router.get("", response_model=list[EventOut], dependencies=[Depends(any_user)])
def list_events(
    actor_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """Newest events first. Optional filters by account and event type."""
    stmt = select(Event)
    if actor_id:
        stmt = stmt.where(Event.actor_id == actor_id)
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    stmt = stmt.order_by(Event.occurred_at.desc(), Event.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()


@router.get("/{event_id}", response_model=EventOut, dependencies=[Depends(any_user)])
def get_event(event_id: UUID, session: Session = Depends(get_session)):
    row = session.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return row
