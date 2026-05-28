"""Password hashing, JWT issuance, and input validation regexes.

All security primitives required across the auth use cases (UC-1, UC-3,
UC-4) live here so they can be replaced or audited in one location.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
import jwt

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Validation regexes (instructions.md §4 rule 3 — RegEx interceptors).
# ---------------------------------------------------------------------------

# A 16-digit ORCID identifier formatted as 0000-0000-0000-0000. The final
# character may be an uppercase ``X`` per the ORCID checksum specification.
ORCID_REGEX = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

# Institutional email — a permissive RFC-5322-style pattern. Final validation
# is delegated to ``email-validator`` inside the Pydantic schemas.
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_orcid(value: str) -> bool:
    """Return True when ``value`` matches the canonical ORCID layout."""
    return bool(ORCID_REGEX.match(value))


def is_valid_email(value: str) -> bool:
    """Cheap pre-check used by request validators before DB lookups."""
    return bool(EMAIL_REGEX.match(value))


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash for ``plain``."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verification."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT issuance
# ---------------------------------------------------------------------------

def create_access_token(subject: str, claims: Dict[str, Any] | None = None) -> str:
    """Sign and return a short-lived access JWT.

    ``subject`` is the user identifier (UUID string). Additional claims may
    carry role and portfolio information so the frontend can render the
    UC-6 sidebar without an extra round-trip.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_ttl_minutes)).timestamp()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT or raise ``jwt.PyJWTError``."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# Password reset tokens (UC-4)
# ---------------------------------------------------------------------------

def generate_reset_token() -> str:
    """Return a URL-safe 32-byte secret for password recovery."""
    return secrets.token_urlsafe(32)
