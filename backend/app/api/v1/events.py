from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException

from app.schemas import EventIn, EventOut

router = APIRouter(prefix="/api/v1/events", tags=["events"])

# Temporary storage. Replaced by PostgreSQL in the next stage.
EVENTS: list[EventOut] = []


@router.post("", response_model=EventOut, status_code=201)
def create_event(event: EventIn):
    stored = EventOut(
        **event.model_dump(),
        id=uuid4(),
        ingested_at=datetime.now(timezone.utc),
    )
    EVENTS.append(stored)
    return stored


@router.get("", response_model=list[EventOut])
def list_events():
    return EVENTS


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: UUID):
    for event in EVENTS:
        if event.id == event_id:
            return event
    raise HTTPException(status_code=404, detail="Event not found")
