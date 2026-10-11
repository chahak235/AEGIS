from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI

from app.schemas import EventIn, EventOut

app = FastAPI(title="AEGIS", version="0.1.0")

# Temporary storage. Replaced by PostgreSQL in Stage 3.
EVENTS: list[EventOut] = []


@app.get("/")
def home():
    return {"message": "Welcome to AEGIS", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events", response_model=EventOut, status_code=201)
def create_event(event: EventIn):
    stored = EventOut(
        **event.model_dump(),
        id=uuid4(),
        ingested_at=datetime.now(timezone.utc),
    )
    EVENTS.append(stored)
    return stored


@app.get("/events", response_model=list[EventOut])
def list_events():
    return EVENTS
