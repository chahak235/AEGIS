"""Seeing what the running app is doing: logs, request IDs and metrics.

* Request ID  - every request gets an ID (sent back in the X-Request-ID header
                and written on every log line), so all logs of one request can
                be found together. If a caller sends its own valid X-Request-ID,
                we keep it, so one ID can follow a request across services.
* JSON logs   - one JSON object per line. Machines (log tools such as Grafana
                Loki, Elasticsearch, Cloud Logging) can search fields instead of
                guessing from free text.
* Metrics     - numbers Prometheus collects from /metrics: request counts,
                durations, events ingested, detections, incidents.

Logs answer "what happened to THIS request?". Metrics answer "how is the
system doing overall?". Both are needed.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

# --- Metrics -------------------------------------------------------------------
# Labels must have FEW possible values. "route" is the template ("/api/v1/incidents/{incident_id}"),
# never the real path with IDs in it: one time series per incident would overload Prometheus.

HTTP_REQUESTS = Counter("aegis_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_DURATION = Histogram("aegis_http_request_duration_seconds", "HTTP request duration",
                          ["method", "route"])
EVENTS_INGESTED = Counter("aegis_events_ingested_total", "Events stored", ["new"])
DETECTIONS = Counter("aegis_detections_total", "Detections created or extended", ["rule_code", "kind"])
INCIDENTS_CREATED = Counter("aegis_incidents_created_total", "Incidents created", ["severity"])
RATE_LIMITED = Counter("aegis_rate_limited_total", "Requests refused by rate limiting", ["limit"])


# --- Logging -------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for field in ("method", "route", "path", "status", "duration_ms"):
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Our access log below replaces uvicorn's plain-text one.
    logging.getLogger("uvicorn.access").disabled = True


access_log = logging.getLogger("aegis.access")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def observe(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            duration = time.perf_counter() - start
            route = getattr(request.scope.get("route"), "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            HTTP_DURATION.labels(request.method, route).observe(duration)
            # Never log headers or bodies: they can contain passwords and tokens.
            access_log.info(
                "request",
                extra={"method": request.method, "route": route, "path": request.url.path,
                       "status": status, "duration_ms": round(duration * 1000, 1)},
            )
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        # Basic browser security headers (cheap, and expected by security scanners).
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        """Prometheus scrapes this page. In production, keep it on an internal network."""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
