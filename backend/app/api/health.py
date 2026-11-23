from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.deps import get_session

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live():
    """Is the process running? Never touches the database.

    If this fails, the app itself is stuck and should be restarted.
    """
    return {"status": "alive"}


@router.get("/health/ready")
def ready(response: Response, session: Session = Depends(get_session)):
    """Can the app do useful work right now? Checks the database.

    If the database is unreachable we answer 503 (Service Unavailable),
    so a load balancer stops sending traffic here until it recovers.
    We do NOT include the error text: it could leak the database address.
    """
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = 503
        return {"status": "not ready", "database": "unreachable"}
    return {"status": "ready", "database": "ok"}
