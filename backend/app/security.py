"""Passwords, login tokens (JWT) and API keys.

Three different secrets, three different tools:

* Passwords (people)  -> Argon2id hash. Deliberately SLOW and memory-hungry, so
  an attacker who steals the database can only try a few guesses per second
  per password, not billions.
* Login tokens        -> JWT signed with HMAC-SHA256 (HS256). After logging in,
  the browser sends the token with each request instead of the password.
* API keys (systems)  -> long random strings. Already unguessable, so a fast
  SHA-256 hash is enough to store them safely.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app import config

_hasher = PasswordHasher()  # Argon2id with the library's recommended settings

# Used when the username doesn't exist, so a failed login takes the same time
# either way. Otherwise an attacker could tell "no such user" (fast) from
# "wrong password" (slow) and learn which usernames exist.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")

MIN_PASSWORD_LENGTH = 12


# --- Passwords ---------------------------------------------------------------

def hash_password(password: str) -> str:
    return _hasher.hash(password)  # includes a random salt: same password -> different hash


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the hash used weaker settings than today's defaults."""
    return _hasher.check_needs_rehash(password_hash)


# --- Login tokens (JWT) ------------------------------------------------------

def create_access_token(*, user_id: str, username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user_id,            # subject: WHO this token is about
        "username": username,
        "role": role,
        "iss": config.JWT_ISSUER,
        "aud": config.JWT_AUDIENCE,
        "iat": now,                # issued at
        "exp": now + timedelta(minutes=config.ACCESS_TOKEN_MINUTES),  # expires
    }
    return jwt.encode(claims, config.jwt_secret(), algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Check signature, expiry, issuer and audience. Raises jwt.InvalidTokenError if anything is off.

    `algorithms=[...]` is fixed on purpose: never let the token itself choose how
    it is checked (the classic "alg: none" attack).
    """
    return jwt.decode(
        token,
        config.jwt_secret(),
        algorithms=[config.JWT_ALGORITHM],
        audience=config.JWT_AUDIENCE,
        issuer=config.JWT_ISSUER,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
    )


# --- API keys ----------------------------------------------------------------

def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, key_hash). Show full_key once; store only prefix + hash."""
    prefix = "aeg_" + secrets.token_hex(4)
    full_key = f"{prefix}_{secrets.token_urlsafe(32)}"
    return full_key, prefix, hash_api_key(full_key)


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()
