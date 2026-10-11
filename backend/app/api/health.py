from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live():
    """Is the process running?"""
    return {"status": "alive"}


@router.get("/health/ready")
def ready():
    """Is the app ready for traffic? Will check the database later."""
    return {"status": "ready"}
