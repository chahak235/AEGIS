# The AEGIS API as a container image.
# Build:  docker build -t aegis-api ./backend
# A Dockerfile is a recipe: each line adds a layer on top of the previous one.

# Small official Python image (Debian "slim" = without extra tools we don't need).
FROM python:3.12-slim

# Don't write .pyc files; print logs immediately (no buffering).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install libraries FIRST, before copying our code. Docker caches each step:
# if only our code changes, this slow step is reused instead of re-run.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Now our code: the app, the database migrations and their settings.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini docker-entrypoint.sh ./

# Never run as root inside the container: if someone broke into the app,
# they would get a powerless user, not administrator rights.
RUN useradd --create-home --uid 10001 aegis && chmod +x docker-entrypoint.sh
USER aegis

EXPOSE 8000

# Docker asks this every 30 s; after 3 failures the container is "unhealthy".
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=4).status == 200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
