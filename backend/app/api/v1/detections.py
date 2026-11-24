from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import any_user, get_session
from app.detection.rules import RULES
from app.models import Detection
from app.schemas import DetectionDetailOut, DetectionOut, RuleOut

router = APIRouter(prefix="/api/v1/detections", tags=["detections"], dependencies=[Depends(any_user)])
rules_router = APIRouter(prefix="/api/v1/rules", tags=["detections"], dependencies=[Depends(any_user)])


@router.get("", response_model=list[DetectionOut])
def list_detections(
    rule_code: Optional[str] = None,
    actor_id: Optional[str] = None,
    severity: Optional[Literal["low", "medium", "high"]] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """Newest detections first. Every filter is optional; filters combine with AND."""
    stmt = select(Detection)
    if rule_code:
        stmt = stmt.where(Detection.rule_code == rule_code)
    if actor_id:
        stmt = stmt.where(Detection.actor_id == actor_id)
    if severity:
        stmt = stmt.where(Detection.severity == severity)
    stmt = stmt.order_by(Detection.window_end.desc(), Detection.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()


@router.get("/{detection_id}", response_model=DetectionDetailOut)
def get_detection(detection_id: UUID, session: Session = Depends(get_session)):
    """One detection plus the events that are its evidence, oldest first."""
    # selectinload = fetch the evidence events in one extra query, instead of
    # one query per event (the "N+1 queries" problem).
    detection = session.scalars(
        select(Detection)
        .where(Detection.id == detection_id)
        .options(selectinload(Detection.events))
    ).first()
    if detection is None:
        raise HTTPException(status_code=404, detail="Detection not found")
    return detection


@rules_router.get("", response_model=list[RuleOut])
def list_rules():
    """The rule catalogue: what every rule code means, its window and threshold."""
    return [
        RuleOut(
            code=r.code,
            name=r.name,
            description=r.description,
            severity=r.severity,
            window_seconds=int(r.window.total_seconds()),
            threshold=r.threshold,
        )
        for r in RULES
    ]
