"""Settings read from environment variables (backend/.env on your PC).

Keeping settings out of the code means the same code runs on your laptop,
in tests and in the cloud. Only the environment changes.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# How long a login token stays valid. Short = a stolen token is useful for less time.
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "30"))

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "aegis"         # "who made this token": we only accept our own
JWT_AUDIENCE = "aegis-api"   # "who is it for": a token for another service is refused


def jwt_secret() -> str:
    """The key that signs login tokens. Anyone who knows it can forge tokens,
    so it lives only in .env / the cloud's secret store, never in Git."""
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET is missing or shorter than 32 characters. Add a long random "
            "value to backend/.env (see backend/.env.example)."
        )
    return secret
