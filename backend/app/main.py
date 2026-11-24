from fastapi import FastAPI

from app.api import health
from app.api.v1 import audit, auth, detections, events, incidents, users

app = FastAPI(title="AEGIS", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(detections.router)
app.include_router(detections.rules_router)
app.include_router(incidents.router)
app.include_router(audit.router)
app.include_router(users.router)
app.include_router(users.keys_router)


@app.get("/")
def home():
    return {"message": "Welcome to AEGIS", "docs": "/docs"}
