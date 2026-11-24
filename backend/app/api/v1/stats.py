from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import any_user, get_session
from app.incidents.lifecycle import ACTIVE_STATUSES
from app.models import Detection, Event, Incident

router = APIRouter(prefix="/api/v1/stats", tags=["stats"], dependencies=[Depends(any_user)])


@router.get("")
def overview(session: Session = Depends(get_session)) -> dict:
    """Numbers for the dashboard's Overview page.

    The counting happens INSIDE PostgreSQL (GROUP BY), not by loading every
    row into Python: the database is built for exactly this and only sends
    back a few small numbers.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    def grouped(column, *where):
        stmt = select(column, func.count()).group_by(column)
        for condition in where:
            stmt = stmt.where(condition)
        return {key: count for key, count in session.execute(stmt)}

    return {
        "incidents_by_status": grouped(Incident.status),
        "active_incidents_by_severity": grouped(Incident.severity, Incident.status.in_(ACTIVE_STATUSES)),
        "detections_last_24h_by_rule": grouped(Detection.rule_code, Detection.created_at >= since),
        "events_last_24h": session.scalar(
            select(func.count()).select_from(Event).where(Event.ingested_at >= since)),
        "unassigned_active_incidents": session.scalar(
            select(func.count()).select_from(Incident).where(
                Incident.status.in_(ACTIVE_STATUSES), Incident.assigned_to.is_(None))),
    }
