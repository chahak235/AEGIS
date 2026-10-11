from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Event
from app.schemas import EventIn, EventOut

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
def create_event(event: EventIn, session: Session = Depends(get_session)):
    row = Event(**event.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)  # reload so ingested_at (set by the database) is filled in
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
