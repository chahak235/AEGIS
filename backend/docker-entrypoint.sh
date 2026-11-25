#!/bin/sh
# Runs when the API container starts.
set -e  # stop immediately if any command fails

# 1. Bring the database schema up to date. Safe to run every time: already
#    applied migrations are skipped. (With several copies of the API starting
#    at once, a separate one-off "migrate" job is the safer pattern; see
#    docs/deployment.md.)
alembic upgrade head

# 2. Start the web server. 0.0.0.0 = accept connections from outside the
#    container (127.0.0.1 would only accept connections from inside it).
#    --proxy-headers: trust X-Forwarded-For from the load balancer, so logs
#    and rate limits see the real client IP.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
