import json
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

# 8 KB is plenty for an IP address, browser name and a few extra fields.
MAX_DETAILS_BYTES = 8 * 1024


class EventBase(BaseModel):
    """Fields shared by what clients send and what AEGIS returns."""

    event_type: str = Field(
        pattern=r"^[a-z]+(\.[a-z]+)+$",
        examples=["auth.login.failed"],
    )
    # AwareDatetime = the time MUST include a timezone ("Z" or "+05:30").
    # Without one, "10:00" is ambiguous and time-window rules would be wrong.
    occurred_at: AwareDatetime
    source: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    resource: Optional[str] = Field(default=None, max_length=200)
    outcome: Literal["success", "failure", "denied"]
    details: dict = Field(default_factory=dict)

    @field_validator("details")
    @classmethod
    def details_not_too_big(cls, value: dict) -> dict:
        # Without a limit, one client could send megabytes per event and fill the database.
        size = len(json.dumps(value).encode("utf-8"))
        if size > MAX_DETAILS_BYTES:
            raise ValueError(f"details is {size} bytes; the limit is {MAX_DETAILS_BYTES}")
        return value


class EventIn(EventBase):
    """What a client sends to AEGIS."""

    # Optional. If the client picks the ID itself, it can safely retry:
    # sending the same event_id twice stores the event only once.
    event_id: Optional[UUID] = None


class EventOut(EventBase):
    """What AEGIS sends back: the shared fields plus ones we add."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingested_at: datetime


class DetectionOut(BaseModel):
    """A detection in a list: the finding, without its evidence events."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rule_code: str
    severity: str
    actor_id: str
    window_start: datetime
    window_end: datetime
    event_count: int
    explanation: str
    created_at: datetime
    updated_at: datetime


class DetectionDetailOut(DetectionOut):
    """One detection with its evidence: the actual events that triggered it."""

    events: list[EventOut]


class RuleOut(BaseModel):
    """A rule from the catalogue, so users can see exactly what each code means."""

    code: str
    name: str
    description: str
    severity: str
    window_seconds: int
    threshold: int



# --- Incidents ---------------------------------------------------------------

IncidentStatus = Literal["open", "acknowledged", "investigating", "resolved", "closed"]
Resolution = Literal["true_positive", "false_positive", "benign", "duplicate"]
Severity = Literal["low", "medium", "high", "critical"]


class IncidentOut(BaseModel):
    """An incident in the queue (list view)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    actor_id: str
    severity: str
    status: str
    assigned_to: Optional[str]
    correlation_reason: str
    first_seen: datetime
    last_seen: datetime
    resolution: Optional[str]
    resolution_note: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author: str
    body: str
    created_at: datetime


class IncidentDetailOut(IncidentOut):
    """One incident with everything an analyst needs to investigate it."""

    detections: list[DetectionOut]
    timeline: list[EventOut]   # every evidence event from every detection, oldest first
    notes: list[NoteOut]


class IncidentUpdate(BaseModel):
    """Fields an analyst may change. Leave a field out to keep it as it is.

    Rules (checked by the API):
    * status must follow the allowed transitions (otherwise 409 Conflict);
    * moving to "resolved" requires a resolution;
    * a resolution may only be given together with status "resolved".
    """

    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = Field(default=None, max_length=100)
    resolution: Optional[Resolution] = None
    resolution_note: Optional[str] = Field(default=None, max_length=5000)
