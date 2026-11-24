"""The AEGIS web application: creates the FastAPI app and plugs everything in."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import observability
from app.api import health
from app.api.v1 import audit, auth, detections, events, incidents, users

observability.configure_logging(os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="AEGIS",
    version="0.1.0",
    description="Security event ingestion, detection, correlation and incident management.",
)

observability.install(app)  # request IDs, JSON access logs, /metrics, security headers

# CORS: browsers block a web page from calling an API on a different address
# unless the API says that page is allowed. The dashboard runs on another
# address (e.g. http://localhost:5173), so we list it here. Never use "*"
# together with logins: that would let any website call the API as the user.
# (Added last so it runs first, answering browser "preflight" checks directly.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)

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
