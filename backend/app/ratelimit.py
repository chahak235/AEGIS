"""Rate limiting: "at most N requests per key in W seconds".

Why: without it, an attacker can try thousands of passwords per minute against
/api/v1/auth/login, or one broken sender can flood the event API.

Algorithm: SLIDING WINDOW LOG. For each key (e.g. "login:ip:1.2.3.4") we keep
the times of recent requests. A new request is allowed if fewer than N of them
are inside the last W seconds.

Two storage backends with the same interface:
* RedisLimiter  - used when REDIS_URL is set. All app copies (servers) share
                  one count, so the limit holds across the whole system.
* MemoryLimiter - fallback. Each app process counts on its own: with 3 copies
                  of the app, an attacker effectively gets 3x the limit.
                  Fine for one server and for development; documented as a
                  limitation, not hidden.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int  # seconds until a new request would be allowed (0 if allowed)


class MemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()  # FastAPI may run requests in parallel threads

    def hit(self, key: str, limit: int, window: int) -> Decision:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window:   # forget requests older than the window
                hits.popleft()
            if len(hits) >= limit:
                return Decision(False, max(1, int(hits[0] + window - now) + 1))
            hits.append(now)
            return Decision(True, 0)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisLimiter:
    """Same idea, stored in a Redis "sorted set" per key (member = request, score = time)."""

    def __init__(self, client) -> None:
        self._redis = client

    def hit(self, key: str, limit: int, window: int) -> Decision:
        now = time.time()
        redis_key = f"aegis:ratelimit:{key}"
        # MULTI/EXEC pipeline: these commands run together, in order.
        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(redis_key, 0, now - window)   # drop old requests
        pipe.zcard(redis_key)                               # count the rest
        pipe.zrange(redis_key, 0, 0, withscores=True)       # the oldest one
        _, count, oldest = pipe.execute()
        if count >= limit:
            oldest_time = oldest[0][1] if oldest else now
            return Decision(False, max(1, int(oldest_time + window - now) + 1))
        pipe = self._redis.pipeline(transaction=True)
        pipe.zadd(redis_key, {f"{now}:{uuid.uuid4().hex}": now})
        pipe.expire(redis_key, window)  # Redis deletes idle keys by itself
        pipe.execute()
        return Decision(True, 0)

    def reset(self) -> None:
        for key in self._redis.scan_iter("aegis:ratelimit:*"):
            self._redis.delete(key)


class FailOpenLimiter:
    """If Redis is down, don't take the whole API down with it: allow the
    request and log a warning. (Choosing availability over strictness here is
    a deliberate trade-off; a bank might choose the opposite.)"""

    def __init__(self, primary, fallback) -> None:
        self.primary, self.fallback = primary, fallback

    def hit(self, key: str, limit: int, window: int) -> Decision:
        try:
            return self.primary.hit(key, limit, window)
        except Exception:
            logger.warning("Rate limiter backend unavailable; using in-memory fallback")
            return self.fallback.hit(key, limit, window)

    def reset(self) -> None:
        self.fallback.reset()
        try:
            self.primary.reset()
        except Exception:
            pass


def _build() -> MemoryLimiter | FailOpenLimiter:
    url = os.environ.get("REDIS_URL")
    if not url:
        return MemoryLimiter()
    import redis

    client = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
    return FailOpenLimiter(RedisLimiter(client), MemoryLimiter())


limiter = _build()

# Limits (requests, seconds). Configurable so tests and deployments can tune them.
LOGIN_PER_IP = (int(os.environ.get("RATE_LOGIN_PER_IP", "20")), 300)
LOGIN_PER_USERNAME = (int(os.environ.get("RATE_LOGIN_PER_USERNAME", "10")), 300)
EVENTS_PER_SENDER = (int(os.environ.get("RATE_EVENTS_PER_SENDER", "1200")), 60)


def enforce(key: str, rule: tuple[int, int], name: str) -> None:
    """Count one request for `key`; refuse with 429 Too Many Requests if over the limit."""
    from fastapi import HTTPException

    from app.observability import RATE_LIMITED

    limit, window = rule
    decision = limiter.hit(key, limit, window)
    if not decision.allowed:
        RATE_LIMITED.labels(name).inc()
        logger.warning("Rate limit %s exceeded", name)
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Try again in {decision.retry_after} seconds.",
            headers={"Retry-After": str(decision.retry_after)},
        )
