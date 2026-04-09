"""api/whatif.py — What-If Explorer endpoints (v6.0-04).

Supports interactive parameter exploration:
  1. REST endpoint for one-shot what-if comparison (base vs modified)
  2. WebSocket message type for streaming what-if analysis

The What-If flow:
  - Client sends a base profile + a list of parameter modifications
  - Server runs the pipeline on both base and modified profiles
  - Returns a delta comparison showing what changed
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

router = APIRouter(prefix="/api/v1/whatif", tags=["what-if"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ParameterChange(BaseModel):
    """A single parameter modification for what-if analysis."""
    path: str = Field(..., description="Dot-separated path to the parameter (e.g. 'income.gross_salary')")
    value: Any = Field(..., description="New value for the parameter")


class WhatIfRequest(BaseModel):
    """Request body for what-if analysis."""
    profile: dict[str, Any] = Field(..., description="Base profile to analyse")
    changes: list[ParameterChange] = Field(..., description="Parameter modifications to apply")
    assumptions: dict[str, Any] | None = Field(None, description="Optional assumption overrides")


class MetricDelta(BaseModel):
    """A single metric comparison between base and modified scenarios."""
    metric: str
    base_value: Any
    modified_value: Any
    delta: float | None = None
    delta_pct: float | None = None


class WhatIfResponse(BaseModel):
    """Response showing the impact of parameter changes."""
    changes_applied: list[dict[str, Any]]
    base_score: float | None
    modified_score: float | None
    score_delta: float | None
    base_grade: str | None
    modified_grade: str | None
    deltas: list[MetricDelta]
    base_report: dict[str, Any]
    modified_report: dict[str, Any]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def apply_changes(profile: dict[str, Any], changes: list[ParameterChange]) -> dict[str, Any]:
    """Apply parameter changes to a profile copy using dot-notation paths."""
    modified = copy.deepcopy(profile)
    for change in changes:
        _set_nested(modified, change.path, change.value)
    return modified


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    """Set a value in a nested dict using dot-separated path."""
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _get_nested(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a value from a nested dict using dot-separated path."""
    keys = path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def compute_deltas(base_report: dict[str, Any], modified_report: dict[str, Any]) -> list[MetricDelta]:
    """Compare key metrics between base and modified reports."""
    metrics = [
        ("scoring.overall_score", "Overall Score"),
        ("cashflow.monthly_surplus", "Monthly Surplus"),
        ("cashflow.annual_surplus", "Annual Surplus"),
        ("cashflow.savings_rate_pct", "Savings Rate %"),
        ("debt.total_debt", "Total Debt"),
        ("debt.debt_to_income_pct", "Debt-to-Income %"),
        ("investments.total_portfolio", "Total Portfolio"),
        ("investments.pension.projected_pot", "Projected Pension Pot"),
        ("mortgage.ltv_pct", "LTV %"),
        ("mortgage.deposit_gap", "Deposit Gap"),
        ("estate.net_estate", "Net Estate"),
        ("estate.iht_liability", "IHT Liability"),
    ]

    deltas = []
    for path, label in metrics:
        base_val = _get_nested(base_report, path)
        mod_val = _get_nested(modified_report, path)

        if base_val is None and mod_val is None:
            continue

        delta = None
        delta_pct = None
        if isinstance(base_val, (int, float)) and isinstance(mod_val, (int, float)):
            delta = round(mod_val - base_val, 2)
            if base_val != 0:
                delta_pct = round((delta / abs(base_val)) * 100, 2)

        deltas.append(MetricDelta(
            metric=label,
            base_value=base_val,
            modified_value=mod_val,
            delta=delta,
            delta_pct=delta_pct,
        ))

    return deltas


def run_whatif(
    profile: dict[str, Any],
    changes: list[ParameterChange],
    assumptions: dict[str, Any] | None = None,
) -> WhatIfResponse:
    """Run base and modified pipelines and return comparison."""
    base_report, _, _ = run_pipeline(profile, assumptions_override=assumptions)
    modified_profile = apply_changes(profile, changes)
    modified_report, _, _ = run_pipeline(modified_profile, assumptions_override=assumptions)

    base_scoring = base_report.get("scoring", {})
    mod_scoring = modified_report.get("scoring", {})
    base_score = base_scoring.get("overall_score")
    mod_score = mod_scoring.get("overall_score")

    score_delta = None
    if isinstance(base_score, (int, float)) and isinstance(mod_score, (int, float)):
        score_delta = round(mod_score - base_score, 2)

    deltas = compute_deltas(base_report, modified_report)

    return WhatIfResponse(
        changes_applied=[{"path": c.path, "value": c.value} for c in changes],
        base_score=base_score,
        modified_score=mod_score,
        score_delta=score_delta,
        base_grade=base_scoring.get("grade"),
        modified_grade=mod_scoring.get("grade"),
        deltas=deltas,
        base_report=base_report,
        modified_report=modified_report,
    )


# ---------------------------------------------------------------------------
# REST endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=WhatIfResponse,
    summary="Run what-if comparison",
)
async def whatif_analyse(
    request: WhatIfRequest,
    user: User | None = Depends(verify_api_key),
) -> WhatIfResponse:
    """Run the pipeline on base and modified profiles, return delta comparison."""
    return run_whatif(request.profile, request.changes, request.assumptions)
