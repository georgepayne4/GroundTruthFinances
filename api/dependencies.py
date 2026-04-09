"""api/dependencies.py — Shared dependencies for the GroundTruth API (v5.3-01)."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header, HTTPException

# API key auth: read from environment, default to a dev key for local testing.
_API_KEY = os.environ.get("GROUNDTRUTH_API_KEY", "dev-key-change-me")


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Validate the X-API-Key header. Returns the key on success."""
    if x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


def get_project_root() -> Path:
    """Return the project root directory (parent of api/)."""
    return Path(__file__).resolve().parent.parent


def get_default_assumptions_path() -> Path:
    return get_project_root() / "config" / "assumptions.yaml"


def get_default_history_db() -> Path:
    return get_project_root() / "outputs" / "history.db"
