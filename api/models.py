"""api/models.py — Pydantic request/response models for the GroundTruth API (v5.3-01)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    """Full analysis request: profile + optional assumptions override."""
    profile: dict[str, Any] = Field(..., description="Financial profile (same schema as YAML input)")
    assumptions: dict[str, Any] | None = Field(
        None, description="Optional assumptions override. Uses server defaults if omitted.",
    )


class ValidateRequest(BaseModel):
    """Validate a profile without running the full pipeline."""
    profile: dict[str, Any] = Field(..., description="Financial profile to validate")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ValidationFlag(BaseModel):
    field: str
    message: str
    severity: str


class ValidateResponse(BaseModel):
    flags: list[ValidationFlag]
    error_count: int
    warning_count: int
    info_count: int


class AnalyseResponse(BaseModel):
    """Wraps the full report dict with top-level metadata."""
    profile_name: str | None = None
    overall_score: float | None = None
    grade: str | None = None
    report: dict[str, Any]
    run_id: int | None = None


class HistoryRun(BaseModel):
    id: int
    timestamp: str | None = None
    profile_name: str | None = None
    overall_score: float | None = None
    grade: str | None = None
    surplus_monthly: float | None = None
    net_worth: float | None = None
    debt_total: float | None = None
    savings_rate_pct: float | None = None
    pension_replacement_pct: float | None = None
    emergency_fund_months: float | None = None
    goals_on_track: int | None = None
    goals_at_risk: int | None = None


class HistoryResponse(BaseModel):
    runs: list[HistoryRun]
    count: int


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Profile management (v5.3-02)
# ---------------------------------------------------------------------------

class ProfileCreateRequest(BaseModel):
    """Store a named profile in the database."""
    user_email: str = Field(..., description="Email address identifying the user")
    user_name: str | None = Field(None, description="Display name (optional, used on first creation)")
    profile_name: str = Field(..., description="Name for this profile (unique per user)")
    profile: dict[str, Any] = Field(..., description="Financial profile data")


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str
    created_at: str | None = None
    updated_at: str | None = None
