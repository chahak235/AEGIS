from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventIn(BaseModel):
    """What a client sends to AEGIS."""

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


class EventOut(EventIn):
    """What AEGIS sends back: the same fields plus ones we add."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingested_at: datetime

