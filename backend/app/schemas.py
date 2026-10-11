from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    """What a client sends to AEGIS."""

    event_type: str = Field(
        pattern=r"^[a-z]+(\.[a-z]+)+$",
        examples=["auth.login.failed"],
    )
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    resource: Optional[str] = Field(default=None, max_length=200)
    outcome: Literal["success", "failure", "denied"]
    details: dict = Field(default_factory=dict)


class EventOut(EventIn):
    """What AEGIS sends back: the same fields plus ones we add."""

    id: UUID
    ingested_at: datetime
