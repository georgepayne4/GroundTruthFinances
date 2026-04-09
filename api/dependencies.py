"""api/dependencies.py — Shared dependencies for the GroundTruth API (v5.3-04).

Authentication: per-user API keys hashed with SHA-256.
  - In dev mode (GROUNDTRUTH_DEV_MODE=1), accepts the dev key without DB lookup.
  - In production, resolves the API key to a User via the api_key_hash column.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from api.database.models import User
from api.database.session import get_db

# Dev mode: single shared key for local testing (no DB required)
_DEV_MODE = os.environ.get("GROUNDTRUTH_DEV_MODE", "1") == "1"
_DEV_KEY = os.environ.get("GROUNDTRUTH_API_KEY", "dev-key-change-me")


def hash_api_key(key: str) -> str:
    """SHA-256 hash of an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a cryptographically random API key."""
    return f"gt_{secrets.token_urlsafe(32)}"


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User | None:
    """Validate the X-API-Key header. Returns the User on success.

    In dev mode, accepts the dev key and returns None (no user context).
    In production mode, looks up the key hash in the users table.
    """
    if _DEV_MODE and x_api_key == _DEV_KEY:
        return None

    key_hash = hash_api_key(x_api_key)
    user = db.query(User).filter(User.api_key_hash == key_hash).first()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return user


async def require_admin(
    user: User | None = Depends(verify_api_key),
) -> User:
    """Dependency that requires the authenticated user to be an admin."""
    if user is None:
        raise HTTPException(status_code=403, detail="Admin access required (not available in dev mode)")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_current_user(
    user: User | None = Depends(verify_api_key),
) -> User | None:
    """Convenience dependency: returns the authenticated user or None in dev mode."""
    return user


def get_project_root() -> Path:
    """Return the project root directory (parent of api/)."""
    return Path(__file__).resolve().parent.parent


def get_default_assumptions_path() -> Path:
    return get_project_root() / "config" / "assumptions.yaml"


def get_default_history_db() -> Path:
    return get_project_root() / "outputs" / "history.db"
