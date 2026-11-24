"""Rate limiting, request IDs, security headers and metrics."""

import json
import logging

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app
from app.observability import JsonFormatter, request_id_var
from app.ratelimit import FailOpenLimiter, MemoryLimiter, RedisLimiter

anonymous = TestClient(app)


# --- The limiter itself (no database) ------------------------------------------

@pytest.mark.parametrize("make", [MemoryLimiter, lambda: RedisLimiter(fakeredis.FakeRedis())])
def test_limiter_allows_up_to_the_limit_then_refuses(make):
    limiter = make()
    results = [limiter.hit("k", limit=3, window=60).allowed for _ in range(4)]
    assert results == [True, True, True, False]


@pytest.mark.parametrize("make", [MemoryLimiter, lambda: RedisLimiter(fakeredis.FakeRedis())])
def test_limiter_tells_how_long_to_wait(make):
    limiter = make()
    for _ in range(2):
        limiter.hit("k", limit=2, window=60)
    decision = limiter.hit("k", limit=2, window=60)
    assert not decision.allowed and 1 <= decision.retry_after <= 61


@pytest.mark.parametrize("make", [MemoryLimiter, lambda: RedisLimiter(fakeredis.FakeRedis())])
def test_keys_are_counted_separately(make):
    limiter = make()
    limiter.hit("a", limit=1, window=60)
    assert limiter.hit("b", limit=1, window=60).allowed


def test_broken_redis_falls_back_instead_of_failing():
    class Broken:
        def hit(self, *args):
            raise ConnectionError("redis down")

    limiter = FailOpenLimiter(Broken(), MemoryLimiter())
    assert limiter.hit("k", limit=1, window=60).allowed


def test_login_is_rate_limited_per_username(monkeypatch):
    monkeypatch.setattr(ratelimit, "LOGIN_PER_USERNAME", (2, 300))
    calls = []
    original = ratelimit.limiter.hit

    def spy(key, limit, window):
        calls.append(key)
        return original(key, limit, window)

    monkeypatch.setattr(ratelimit.limiter, "hit", spy)
    for _ in range(2):
        ratelimit.enforce("login:user:bob", ratelimit.LOGIN_PER_USERNAME, "login_username")
    with pytest.raises(Exception) as refused:
        ratelimit.enforce("login:user:bob", ratelimit.LOGIN_PER_USERNAME, "login_username")
    assert refused.value.status_code == 429
    assert "Retry-After" in refused.value.headers


# --- Request IDs, headers, logs, metrics (no database) ----------------------------

def test_every_response_has_a_request_id_and_security_headers():
    r = anonymous.get("/health/live")
    assert len(r.headers["X-Request-ID"]) == 32
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_a_valid_incoming_request_id_is_kept():
    r = anonymous.get("/health/live", headers={"X-Request-ID": "trace-12345678"})
    assert r.headers["X-Request-ID"] == "trace-12345678"


def test_a_weird_incoming_request_id_is_replaced():
    r = anonymous.get("/health/live", headers={"X-Request-ID": "bad id with spaces\n"})
    assert r.headers["X-Request-ID"] != "bad id with spaces\n"


def test_log_lines_are_json_with_the_request_id():
    token = request_id_var.set("req-abcdefgh")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["message"] == "hello world"
    assert line["request_id"] == "req-abcdefgh"


def test_metrics_use_route_templates_not_raw_ids():
    anonymous.get("/api/v1/incidents/11111111-1111-1111-1111-111111111111")  # 401, but counted
    body = anonymous.get("/metrics").text
    assert 'route="/api/v1/incidents/{incident_id}"' in body
    assert "11111111-1111" not in body


def test_cors_allows_the_dashboard_origin_only():
    ok = anonymous.options("/api/v1/incidents", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    evil = anonymous.options("/api/v1/incidents", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in evil.headers
