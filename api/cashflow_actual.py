"""api/cashflow_actual.py — Planned vs Actual Cashflow (v6.0-07).

Combines declared expenses from the profile with actual bank transaction data
to show drift, suggest profile updates, and provide monthly breakdowns.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database.models import BankAccount, BankConnection, BankTransaction, User
from api.database.session import get_db
from api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cashflow", tags=["cashflow"])


# ---------------------------------------------------------------------------
# Category mapping: bank categories -> profile expense keys
# ---------------------------------------------------------------------------

_BANK_TO_PROFILE_MAP: dict[str, str] = {
    "food": "food_groceries",
    "groceries": "food_groceries",
    "dining": "dining_out",
    "eating out": "dining_out",
    "transport": "transport",
    "entertainment": "entertainment",
    "shopping": "shopping",
    "bills": "bills",
    "general": "general",
    "health": "health",
    "personal_care": "personal_care",
    "holidays": "holidays",
    "cash": "cash_withdrawals",
    "fees": "bank_fees",
    "uncategorised": "other",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CategoryDrift:
    """Planned vs actual comparison for one category."""
    category: str
    planned_monthly: float
    actual_monthly: float
    drift: float  # actual - planned
    drift_pct: float  # percentage over/under


@dataclass
class MonthBreakdown:
    """Spending breakdown for a single month."""
    month: str  # YYYY-MM
    total_planned: float
    total_actual: float
    categories: dict[str, float]  # category -> actual amount


@dataclass
class CashflowComparison:
    """Complete planned vs actual analysis."""
    period_months: int
    total_planned_monthly: float
    total_actual_monthly: float
    overall_drift: float
    overall_drift_pct: float
    category_drifts: list[CategoryDrift]
    monthly_breakdown: list[MonthBreakdown]
    suggested_updates: list[dict[str, Any]]


def _extract_planned_expenses(profile: dict[str, Any]) -> dict[str, float]:
    """Extract monthly planned expenses from profile, flattened to category keys."""
    expenses = profile.get("expenses", {})
    planned: dict[str, float] = {}

    for section_key in ("essential", "discretionary", "irregular"):
        section = expenses.get(section_key, {})
        if isinstance(section, dict):
            for key, value in section.items():
                if isinstance(value, (int, float)):
                    planned[key] = float(value)

    return planned


def _get_actual_spending(
    db: Session,
    user_id: int,
    months: int = 3,
) -> tuple[dict[str, float], list[MonthBreakdown]]:
    """Aggregate actual bank spending by category over the last N months.

    Returns (avg_monthly_by_category, monthly_breakdowns).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

    rows = (
        db.query(BankTransaction)
        .join(BankAccount, BankTransaction.account_id == BankAccount.id)
        .join(BankConnection, BankAccount.connection_id == BankConnection.id)
        .filter(BankConnection.user_id == user_id, BankConnection.status == "active")
        .filter(BankTransaction.amount < 0)
        .filter(BankTransaction.timestamp >= cutoff)
        .all()
    )

    # Group by month and category
    monthly_cats: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in rows:
        if t.timestamp is None:
            continue
        month_key = t.timestamp.strftime("%Y-%m")
        cat = _BANK_TO_PROFILE_MAP.get((t.category or "").lower(), "other")
        monthly_cats[month_key][cat] += abs(t.amount)

    # Build monthly breakdowns
    breakdowns = []
    for month_key in sorted(monthly_cats.keys()):
        cats = monthly_cats[month_key]
        breakdowns.append(MonthBreakdown(
            month=month_key,
            total_planned=0,  # filled by caller
            total_actual=sum(cats.values()),
            categories=dict(cats),
        ))

    # Average across months
    totals: dict[str, float] = defaultdict(float)
    for cats in monthly_cats.values():
        for cat, amount in cats.items():
            totals[cat] += amount

    actual_months = max(1, len(monthly_cats))
    avg = {cat: round(total / actual_months, 2) for cat, total in totals.items()}

    return avg, breakdowns


def analyse_drift(
    profile: dict[str, Any],
    db: Session,
    user_id: int,
    months: int = 3,
    drift_threshold_pct: float = 20.0,
) -> CashflowComparison:
    """Compare planned expenses with actual bank spending."""
    planned = _extract_planned_expenses(profile)
    actual_avg, breakdowns = _get_actual_spending(db, user_id, months)

    # Fill in planned totals for breakdowns
    total_planned_monthly = sum(planned.values())
    for b in breakdowns:
        b.total_planned = total_planned_monthly

    # Category-level drift
    all_categories = set(planned.keys()) | set(actual_avg.keys())
    drifts: list[CategoryDrift] = []

    for cat in sorted(all_categories):
        p = planned.get(cat, 0.0)
        a = actual_avg.get(cat, 0.0)
        drift = round(a - p, 2)
        drift_pct = round((drift / p) * 100, 1) if p > 0 else (100.0 if a > 0 else 0.0)

        drifts.append(CategoryDrift(
            category=cat,
            planned_monthly=p,
            actual_monthly=a,
            drift=drift,
            drift_pct=drift_pct,
        ))

    # Sort by absolute drift (biggest mismatches first)
    drifts.sort(key=lambda d: -abs(d.drift))

    total_actual_monthly = sum(actual_avg.values())
    overall_drift = round(total_actual_monthly - total_planned_monthly, 2)
    overall_drift_pct = round((overall_drift / total_planned_monthly) * 100, 1) if total_planned_monthly > 0 else 0.0

    # Generate suggested updates for significant drifts
    suggestions: list[dict[str, Any]] = []
    for d in drifts:
        if abs(d.drift_pct) >= drift_threshold_pct and abs(d.drift) >= 20:
            direction = "higher" if d.drift > 0 else "lower"
            suggestions.append({
                "category": d.category,
                "current_planned": d.planned_monthly,
                "suggested_value": d.actual_monthly,
                "drift_pct": d.drift_pct,
                "message": (
                    f"Your actual '{d.category}' spending (£{d.actual_monthly:,.0f}/mo) is "
                    f"{abs(d.drift_pct):.0f}% {direction} than planned (£{d.planned_monthly:,.0f}/mo). "
                    f"Consider updating your profile."
                ),
            })

    return CashflowComparison(
        period_months=months,
        total_planned_monthly=total_planned_monthly,
        total_actual_monthly=total_actual_monthly,
        overall_drift=overall_drift,
        overall_drift_pct=overall_drift_pct,
        category_drifts=drifts,
        monthly_breakdown=breakdowns,
        suggested_updates=suggestions,
    )


# ---------------------------------------------------------------------------
# REST endpoint
# ---------------------------------------------------------------------------

class DriftRequest(BaseModel):
    profile: dict[str, Any] = Field(..., description="Profile with planned expenses")
    months: int = Field(3, ge=1, le=12, description="Months of actual data to compare")
    drift_threshold_pct: float = Field(20.0, description="Minimum drift % to suggest update")


@router.post("/drift", summary="Planned vs actual spending comparison")
async def get_drift(
    request: DriftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Compare planned expenses from profile with actual bank transactions."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = analyse_drift(
        request.profile, db, user.id,
        months=request.months,
        drift_threshold_pct=request.drift_threshold_pct,
    )

    return {
        "period_months": result.period_months,
        "total_planned_monthly": result.total_planned_monthly,
        "total_actual_monthly": result.total_actual_monthly,
        "overall_drift": result.overall_drift,
        "overall_drift_pct": result.overall_drift_pct,
        "category_drifts": [
            {
                "category": d.category,
                "planned_monthly": d.planned_monthly,
                "actual_monthly": d.actual_monthly,
                "drift": d.drift,
                "drift_pct": d.drift_pct,
            }
            for d in result.category_drifts
        ],
        "monthly_breakdown": [
            {
                "month": m.month,
                "total_planned": m.total_planned,
                "total_actual": m.total_actual,
                "categories": m.categories,
            }
            for m in result.monthly_breakdown
        ],
        "suggested_updates": result.suggested_updates,
    }
