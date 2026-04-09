"""api/comparison.py — Multi-Profile Comparison (v6.0-06).

Side-by-side comparison of two profiles (e.g., couples merging finances)
and scenario branching (save a profile variant without overwriting the original).
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.database.models import User
from api.dependencies import verify_api_key
from engine.pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compare", tags=["comparison"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    """Two profiles to compare side by side."""
    profile_a: dict[str, Any] = Field(..., description="First profile (e.g., partner A)")
    profile_b: dict[str, Any] = Field(..., description="Second profile (e.g., partner B)")
    label_a: str = Field("Profile A", description="Display label for first profile")
    label_b: str = Field("Profile B", description="Display label for second profile")
    merged: dict[str, Any] | None = Field(None, description="Optional merged/combined profile")
    assumptions: dict[str, Any] | None = Field(None, description="Shared assumption overrides")


class MetricComparison(BaseModel):
    metric: str
    value_a: Any
    value_b: Any
    delta: float | None = None
    merged_value: Any = None


class CompareResponse(BaseModel):
    label_a: str
    label_b: str
    score_a: float | None
    score_b: float | None
    grade_a: str | None
    grade_b: str | None
    merged_score: float | None = None
    merged_grade: str | None = None
    comparisons: list[MetricComparison]
    report_a: dict[str, Any]
    report_b: dict[str, Any]
    report_merged: dict[str, Any] | None = None


class BranchRequest(BaseModel):
    """Create a named scenario branch from a base profile with modifications."""
    base_profile: dict[str, Any]
    branch_name: str
    changes: dict[str, Any] = Field(default_factory=dict, description="Flat dict of dot-path -> value overrides")


class BranchResponse(BaseModel):
    branch_name: str
    branched_profile: dict[str, Any]
    base_score: float | None
    branch_score: float | None
    score_delta: float | None


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

_COMPARISON_METRICS = [
    ("scoring.overall_score", "Overall Score"),
    ("cashflow.monthly_surplus", "Monthly Surplus"),
    ("cashflow.savings_rate_pct", "Savings Rate %"),
    ("debt.total_debt", "Total Debt"),
    ("debt.debt_to_income_pct", "Debt-to-Income %"),
    ("investments.total_portfolio", "Total Portfolio"),
    ("investments.pension.projected_pot", "Projected Pension Pot"),
    ("mortgage.ltv_pct", "LTV %"),
    ("estate.net_estate", "Net Estate"),
]


def _get_nested(data: dict[str, Any], path: str, default: Any = None) -> Any:
    keys = path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def compare_profiles(
    profile_a: dict[str, Any],
    profile_b: dict[str, Any],
    merged_profile: dict[str, Any] | None = None,
    assumptions: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, list[MetricComparison]]:
    """Run pipeline on both (and optionally merged) profiles, return reports and comparisons."""
    report_a, _, _ = run_pipeline(profile_a, assumptions_override=assumptions)
    report_b, _, _ = run_pipeline(profile_b, assumptions_override=assumptions)

    report_merged = None
    if merged_profile:
        report_merged, _, _ = run_pipeline(merged_profile, assumptions_override=assumptions)

    comparisons = []
    for path, label in _COMPARISON_METRICS:
        val_a = _get_nested(report_a, path)
        val_b = _get_nested(report_b, path)
        merged_val = _get_nested(report_merged, path) if report_merged else None

        if val_a is None and val_b is None:
            continue

        delta = None
        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            delta = round(val_b - val_a, 2)

        comparisons.append(MetricComparison(
            metric=label,
            value_a=val_a,
            value_b=val_b,
            delta=delta,
            merged_value=merged_val,
        ))

    return report_a, report_b, report_merged, comparisons


def branch_profile(
    base_profile: dict[str, Any],
    changes: dict[str, Any],
    assumptions: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Create a branched profile with changes applied. Returns (branched, base_report, branch_report)."""
    branched = copy.deepcopy(base_profile)
    for path, value in changes.items():
        _set_nested(branched, path, value)

    base_report, _, _ = run_pipeline(base_profile, assumptions_override=assumptions)
    branch_report, _, _ = run_pipeline(branched, assumptions_override=assumptions)

    return branched, base_report, branch_report


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CompareResponse,
    summary="Compare two profiles side by side",
)
async def compare(
    request: CompareRequest,
    user: User | None = Depends(verify_api_key),
) -> CompareResponse:
    """Run analysis on two profiles and return a side-by-side comparison."""
    report_a, report_b, report_merged, comparisons = compare_profiles(
        request.profile_a,
        request.profile_b,
        request.merged,
        request.assumptions,
    )

    score_a = _get_nested(report_a, "scoring.overall_score")
    score_b = _get_nested(report_b, "scoring.overall_score")

    return CompareResponse(
        label_a=request.label_a,
        label_b=request.label_b,
        score_a=score_a,
        score_b=score_b,
        grade_a=_get_nested(report_a, "scoring.grade"),
        grade_b=_get_nested(report_b, "scoring.grade"),
        merged_score=_get_nested(report_merged, "scoring.overall_score") if report_merged else None,
        merged_grade=_get_nested(report_merged, "scoring.grade") if report_merged else None,
        comparisons=comparisons,
        report_a=report_a,
        report_b=report_b,
        report_merged=report_merged,
    )


@router.post(
    "/branch",
    response_model=BranchResponse,
    summary="Create a scenario branch from a profile",
)
async def create_branch(
    request: BranchRequest,
    user: User | None = Depends(verify_api_key),
) -> BranchResponse:
    """Apply changes to a base profile and compare the outcomes."""
    branched, base_report, branch_report = branch_profile(
        request.base_profile,
        request.changes,
    )

    base_score = _get_nested(base_report, "scoring.overall_score")
    branch_score = _get_nested(branch_report, "scoring.overall_score")
    score_delta = None
    if isinstance(base_score, (int, float)) and isinstance(branch_score, (int, float)):
        score_delta = round(branch_score - base_score, 2)

    return BranchResponse(
        branch_name=request.branch_name,
        branched_profile=branched,
        base_score=base_score,
        branch_score=branch_score,
        score_delta=score_delta,
    )
