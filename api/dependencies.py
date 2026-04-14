"""api/dependencies.py — Shared dependencies for the GroundTruth API (v9.3).

Dual authentication: Clerk session JWT (primary) or API key (fallback).
  - Clerk: Authorization: Bearer <jwt> — verified via JWKS, creates/looks up User by clerk_user_id.
  - API key: X-API-Key header — dev mode accepts hardcoded key, production resolves via hash.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.clerk_auth import get_clerk_user_email, verify_clerk_token
from api.database.crud import get_or_create_user_by_clerk_id
from api.database.models import User
from api.database.session import get_db

logger = logging.getLogger(__name__)

_DEV_MODE = os.environ.get("GROUNDTRUTH_DEV_MODE", "1") == "1"
_DEV_KEY = os.environ.get("GROUNDTRUTH_API_KEY", "dev-key-change-me")
_ENV = os.environ.get("GROUNDTRUTH_ENV", "development")

if _ENV == "production" and _DEV_KEY == "dev-key-change-me":
    raise RuntimeError(
        "Cannot start in production with default dev API key. "
        "Set GROUNDTRUTH_API_KEY to a secure value."
    )


def hash_api_key(key: str) -> str:
    """SHA-256 hash of an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a cryptographically random API key."""
    return f"gt_{secrets.token_urlsafe(32)}"


async def authenticate(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Dual auth: try Clerk JWT first, fall back to API key.

    Returns User on successful auth, None in dev mode with dev key.
    Raises 401 if neither auth method succeeds.
    """
    # 1. Check Authorization header for Bearer token (Clerk)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            claims = verify_clerk_token(token)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e
        clerk_user_id = claims.get("sub")
        if not clerk_user_id:
            raise HTTPException(status_code=401, detail="Missing sub claim")
        email = get_clerk_user_email(clerk_user_id)
        return get_or_create_user_by_clerk_id(db, clerk_user_id, email=email)

    # 2. Fall back to X-API-Key
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        if _DEV_MODE:
            return None
        raise HTTPException(status_code=401, detail="Missing authentication")

    if _DEV_MODE and api_key == _DEV_KEY:
        return None

    key_hash = hash_api_key(api_key)
    user = db.query(User).filter(User.api_key_hash == key_hash).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


# Backward-compatible alias — existing Depends(verify_api_key) references keep working.
verify_api_key = authenticate


async def require_admin(
    user: User | None = Depends(authenticate),
) -> User:
    """Dependency that requires the authenticated user to be an admin."""
    if user is None:
        raise HTTPException(status_code=403, detail="Admin access required (not available in dev mode)")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_current_user(
    user: User | None = Depends(authenticate),
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
