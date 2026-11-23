from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source: Mapped[str] = mapped_column(String(100))
    actor_id: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        Index("ix_events_actor_occurred", "actor_id", "occurred_at"),
        Index("ix_events_type_occurred", "event_type", "occurred_at"),
    )


# Link table: which events are the evidence for which detection.
# One detection has many events; one event can be evidence for several
# detections (e.g. a failed login counts for AUTH-001 and AUTH-002).
# This "many-to-many" relationship needs its own table.
detection_events = Table(
    "detection_events",
    Base.metadata,
    # Deleting a detection removes its links (CASCADE)...
    Column("detection_id", ForeignKey("detections.id", ondelete="CASCADE"), primary_key=True),
    # ...but an event that is evidence can NOT be deleted while a detection
    # points to it (the default, NO ACTION). Evidence must not vanish silently.
    Column("event_id", ForeignKey("events.id"), primary_key=True),
    # The primary key (detection_id, event_id) already finds "events of a detection"
    # fast. This index finds the reverse, "detections that use this event", fast.
    Index("ix_detection_events_event_id", "event_id"),
)


class Detection(Base):
    """A finding: a rule matched a group of events."""

    __tablename__ = "detections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rule_code: Mapped[str] = mapped_column(String(50))      # which rule, e.g. "AUTH-001"
    severity: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(100))      # which account it is about
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # first evidence event
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))    # last evidence event
    event_count: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)          # human sentence: why it fired
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list[Event]] = relationship(
        secondary=detection_events, order_by=Event.occurred_at
    )

    __table_args__ = (
        # The engine asks "is there already a detection for this rule and
        # account around this time?" on every event. This index answers fast.
        Index("ix_detections_rule_actor_window", "rule_code", "actor_id", "window_start"),
        # The dashboard lists newest detections first.
        Index("ix_detections_window_end", "window_end"),
    )
