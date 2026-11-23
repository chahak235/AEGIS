import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_session
from app.detection import engine as detection_engine
from app.models import Event
from app.schemas import EventIn, EventOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
def create_event(
    event: EventIn, response: Response, session: Session = Depends(get_session)
):
    """Save an event.

    Idempotency: if the client sends its own `event_id` and retries the same
    request (e.g. after a network timeout), we return the already-saved event
    with 200 instead of saving a duplicate. Duplicates would make
    "5 failed logins" rules fire on what was really 1 failed login sent 5 times.
    """
    if event.event_id is not None:
        existing = session.get(Event, event.event_id)
        if existing is not None:
            response.status_code = 200
            return existing

    row = Event(id=event.event_id or uuid4(), **event.model_dump(exclude={"event_id"}))
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        # Two identical retries arrived at the same moment; the other one won.
        session.rollback()
        response.status_code = 200
        return session.get(Event, row.id)
    session.refresh(row)  # reload so ingested_at (set by the database) is filled in

    # The event is now safely stored. Detection runs AFTER that, separately:
    # if a rule has a bug, we log it, but we never lose the event itself.
    # (A retried event returns early above, so its rules do not run twice.)
    try:
        detection_engine.run_detection(session, row)
    except Exception:
        session.rollback()
        logger.exception("Detection failed for event %s; the event itself is saved", row.id)
    return row


@router.get("", response_model=list[EventOut])
def list_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    stmt = select(Event).order_by(Event.occurred_at.desc()).limit(limit).offset(offset)
    return session.scalars(stmt).all()


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: UUID, session: Session = Depends(get_session)):
    row = session.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return row
