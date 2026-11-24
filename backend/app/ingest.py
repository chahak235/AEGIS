"""Saving an event and running detection on it, in one place.

Used by the events API (events from other systems) AND by AEGIS's own login
endpoint (failed logins to AEGIS itself become events, so AEGIS can detect
attacks on itself).
"""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.detection import engine as detection_engine
from app.models import Event
from app.schemas import EventIn

logger = logging.getLogger(__name__)


def ingest_event(session: Session, event: EventIn) -> tuple[Event, bool]:
    """Save the event (once) and run detection. Returns (event, created).

    created=False means it was a retry of an event we already have
    (same event_id), so nothing new was saved and detection did not re-run.
    """
    if event.event_id is not None:
        existing = session.get(Event, event.event_id)
        if existing is not None:
            return existing, False

    row = Event(id=event.event_id or uuid4(), **event.model_dump(exclude={"event_id"}))
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        # Two identical retries arrived at the same moment; the other one won.
        session.rollback()
        return session.get(Event, row.id), False
    session.refresh(row)  # reload so ingested_at (set by the database) is filled in

    # The event is now safely stored. Detection runs AFTER that, separately:
    # if a rule has a bug, we log it, but we never lose the event itself.
    try:
        detection_engine.run_detection(session, row)
    except Exception:
        session.rollback()
        logger.exception("Detection failed for event %s; the event itself is saved", row.id)
    return row, True
