from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import audit
from app.deps import current_username, get_session
from app.incidents.lifecycle import InvalidTransition, check_transition
from app.models import AuditLog, Detection, Incident, IncidentNote
from app.schemas import (
    AuditOut,
    IncidentDetailOut,
    IncidentOut,
    IncidentStatus,
    IncidentUpdate,
    NoteIn,
    NoteOut,
    Severity,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


def _load_incident(session: Session, incident_id: UUID) -> Incident:
    incident = session.scalars(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.detections).selectinload(Detection.events),
            selectinload(Incident.notes),
        )
    ).first()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def _detail(incident: Incident) -> IncidentDetailOut:
    # The timeline = every evidence event of every detection, each event once, oldest first.
    events = {e.id: e for d in incident.detections for e in d.events}
    timeline = sorted(events.values(), key=lambda e: (e.occurred_at, str(e.id)))
    return IncidentDetailOut.model_validate(
        {
            **IncidentOut.model_validate(incident).model_dump(),
            "detections": incident.detections,
            "timeline": timeline,
            "notes": incident.notes,
        }
    )


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status: Optional[IncidentStatus] = None,
    severity: Optional[Severity] = None,
    actor_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """The incident queue: most recent activity first. Filters combine with AND."""
    stmt = select(Incident)
    if status:
        stmt = stmt.where(Incident.status == status)
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if actor_id:
        stmt = stmt.where(Incident.actor_id == actor_id)
    if assigned_to:
        stmt = stmt.where(Incident.assigned_to == assigned_to)
    stmt = stmt.order_by(Incident.last_seen.desc(), Incident.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: UUID, session: Session = Depends(get_session)):
    """Everything about one incident: detections, evidence timeline and notes."""
    return _detail(_load_incident(session, incident_id))


@router.patch("/{incident_id}", response_model=IncidentDetailOut)
def update_incident(
    incident_id: UUID,
    changes: IncidentUpdate,
    session: Session = Depends(get_session),
    username: str = Depends(current_username),
):
    """Change status, assignee or resolution. Only the fields you send are changed."""
    incident = _load_incident(session, incident_id)
    sent = changes.model_fields_set  # which fields the client actually included

    if "resolution" in sent and changes.status != "resolved":
        raise HTTPException(422, "A resolution can only be set together with status 'resolved'.")

    if changes.status is not None and changes.status != incident.status:
        try:
            check_transition(incident.status, changes.status)
        except InvalidTransition as error:
            # 409 Conflict: the request is valid, but not allowed in the incident's current state.
            raise HTTPException(status_code=409, detail=str(error))

        details = {"from": incident.status, "to": changes.status}
        if changes.status == "resolved":
            if changes.resolution is None:
                raise HTTPException(422, "Resolving an incident requires a resolution.")
            incident.resolution = changes.resolution
            incident.resolution_note = changes.resolution_note
            incident.resolved_at = datetime.now(timezone.utc)
            details["resolution"] = changes.resolution
        elif incident.status == "resolved" and changes.status == "investigating":
            # Reopened: the old conclusion no longer applies (but the audit log keeps it).
            details["previous_resolution"] = incident.resolution
            incident.resolution = None
            incident.resolution_note = None
            incident.resolved_at = None
        incident.status = changes.status
        audit.record(session, actor=username, action="incident.status_changed",
                     target_type="incident", target_id=incident.id, details=details)

    if "assigned_to" in sent and changes.assigned_to != incident.assigned_to:
        audit.record(session, actor=username, action="incident.assigned",
                     target_type="incident", target_id=incident.id,
                     details={"from": incident.assigned_to, "to": changes.assigned_to})
        incident.assigned_to = changes.assigned_to  # null = unassign

    session.commit()  # the changes AND their audit records, together
    return _detail(_load_incident(session, incident_id))


@router.post("/{incident_id}/notes", response_model=NoteOut, status_code=201)
def add_note(
    incident_id: UUID,
    note: NoteIn,
    session: Session = Depends(get_session),
    username: str = Depends(current_username),
):
    """Add an investigation note. Notes cannot be edited or deleted afterwards."""
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status == "closed":
        raise HTTPException(status_code=409, detail="Incident is closed; no more notes.")
    row = IncidentNote(id=uuid4(), incident_id=incident.id, author=username, body=note.body)
    session.add(row)
    audit.record(session, actor=username, action="incident.note_added",
                 target_type="incident", target_id=incident.id, details={"note_id": str(row.id)})
    session.commit()
    session.refresh(row)
    return row


@router.get("/{incident_id}/audit", response_model=list[AuditOut])
def incident_audit(incident_id: UUID, session: Session = Depends(get_session)):
    """The full history of one incident: who changed what, oldest first."""
    if session.get(Incident, incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return session.scalars(
        select(AuditLog)
        .where(AuditLog.target_type == "incident", AuditLog.target_id == str(incident_id))
        .order_by(AuditLog.seq)
    ).all()
