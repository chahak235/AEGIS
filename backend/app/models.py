from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
