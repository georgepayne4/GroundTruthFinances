"""engine/risk_profiling.py — Dynamic goal-specific risk profiling (v8.4).

Assesses appropriate risk levels per goal based on time horizon, capacity
for loss, and required return. Detects mismatches between the user's stated
risk profile and what each goal's timeline actually supports.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PROFILE_ORDER = ["conservative", "moderate", "aggressive", "very_aggressive"]


def assess_risk_profiles(
    profile: dict[str, Any],
    assumptions: dict[str, Any],
    cashflow: dict[str, Any],
    goal_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Produce per-goal risk assessments with capacity and need analysis."""
    personal = profile.get("personal", {})
    personal_risk = personal.get("risk_profile", "moderate").lower()
    if personal_risk not in _PROFILE_ORDER:
        personal_risk = "moderate"

    risk_cfg = assumptions.get("risk_profiling", {})
    returns_cfg = assumptions.get("investment_returns", {})
    inflation = assumptions.get("inflation", {}).get("general", 0.03)

    capacity = _calculate_capacity_for_loss(profile, cashflow, risk_cfg)

    goals = goal_analysis.get("goals", [])
    goal_profiles = []
    mismatches = []

    for goal in goals:
        goal_risk = _determine_goal_risk(goal, personal_risk, risk_cfg)

        current_savings = _estimate_goal_savings(goal, profile)
        need = _calculate_need_for_return(
            goal, current_savings, inflation, returns_cfg,
        )

        effective = _resolve_effective_profile(
            goal_risk["recommended_profile"],
            capacity["supports_profile"],
            need.get("minimum_profile", "conservative"),
        )

        mismatch = personal_risk != effective
        mismatch_detail = None
        severity = None
        if mismatch:
            personal_idx = _PROFILE_ORDER.index(personal_risk)
            effective_idx = _PROFILE_ORDER.index(effective)
            if personal_idx > effective_idx:
                severity = "warning"
                mismatch_detail = (
                    f"Your {goal['name']} goal is in {personal_risk} funds but due in "
                    f"{goal.get('deadline_years', 0)} years — {effective} recommended"
                )
            else:
                severity = "info"
                mismatch_detail = (
                    f"Your {goal['name']} goal could tolerate {effective} allocation "
                    f"but you're using {personal_risk}"
                )

        entry = {
            "goal_name": goal.get("name", "Unknown"),
            "deadline_years": goal.get("deadline_years", 0),
            "horizon_category": goal_risk["horizon_category"],
            "recommended_profile": goal_risk["recommended_profile"],
            "effective_profile": effective,
            "need_for_return": need,
            "mismatch": mismatch,
            "mismatch_detail": mismatch_detail,
        }
        goal_profiles.append(entry)

        if mismatch:
            mismatches.append({
                "goal_name": goal.get("name", "Unknown"),
                "current_profile": personal_risk,
                "recommended_profile": effective,
                "severity": severity,
                "message": mismatch_detail,
            })

    warning_count = sum(1 for m in mismatches if m.get("severity") == "warning")
    info_count = sum(1 for m in mismatches if m.get("severity") == "info")

    logger.info(
        "Risk profiling: %d goals assessed, %d mismatches (%d warnings, %d info)",
        len(goal_profiles), len(mismatches), warning_count, info_count,
    )

    return {
        "personal_risk_profile": personal_risk,
        "capacity_for_loss": capacity,
        "goal_risk_profiles": goal_profiles,
        "mismatches": mismatches,
        "summary": {
            "goals_assessed": len(goal_profiles),
            "mismatches_found": len(mismatches),
            "warning_count": warning_count,
            "info_count": info_count,
            "capacity_supports_profile": capacity["supports_profile"],
        },
    }


def _determine_goal_risk(
    goal: dict[str, Any], personal_risk: str, risk_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Map goal timeline to appropriate risk profile."""
    short_term = risk_cfg.get("short_term_years", 5)
    long_term = risk_cfg.get("long_term_years", 15)
    deadline = goal.get("deadline_years", 0)
    category = goal.get("category", "general")

    # Safety net goals are always conservative
    if category == "safety_net":
        return {
            "recommended_profile": "conservative",
            "horizon_category": "short",
        }

    if deadline <= 0 or deadline < short_term:
        return {
            "recommended_profile": "conservative",
            "horizon_category": "short",
        }
    elif deadline < long_term:
        return {
            "recommended_profile": "moderate",
            "horizon_category": "medium",
        }
    else:
        # Long-term: allow up to personal preference
        return {
            "recommended_profile": personal_risk,
            "horizon_category": "long",
        }


def _calculate_capacity_for_loss(
    profile: dict[str, Any],
    cashflow: dict[str, Any],
    risk_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Assess how much portfolio loss the user can absorb."""
    sav = profile.get("savings", {})
    emergency_fund = sav.get("emergency_fund", 0)

    monthly_expenses = cashflow.get("expenses", {}).get("monthly", 0)
    if monthly_expenses <= 0:
        monthly_expenses = cashflow.get("net_income", {}).get("monthly", 0) * 0.7

    emergency_months = (
        emergency_fund / monthly_expenses if monthly_expenses > 0 else 0
    )

    cfl_cfg = risk_cfg.get("capacity_for_loss", {})
    months_full = cfl_cfg.get("emergency_months_for_full", 6)
    months_moderate = cfl_cfg.get("emergency_months_for_moderate", 3)
    full_pct = cfl_cfg.get("full_drawdown_pct", 0.20)
    moderate_pct = cfl_cfg.get("moderate_drawdown_pct", 0.10)
    low_pct = cfl_cfg.get("low_drawdown_pct", 0.05)

    if emergency_months >= months_full:
        drawdown_pct = full_pct
        supports = "aggressive"
    elif emergency_months >= months_moderate:
        drawdown_pct = moderate_pct
        supports = "moderate"
    else:
        drawdown_pct = low_pct
        supports = "conservative"

    total_invested = (
        sav.get("pension_balance", 0)
        + sav.get("isa_balance", 0)
        + sav.get("lisa_balance", 0)
        + sav.get("gia_balance", 0)
    )
    affordable_loss = total_invested * drawdown_pct

    narrative = (
        f"You can afford a {drawdown_pct:.0%} portfolio drop — "
        f"emergency fund covers {emergency_months:.1f} months of expenses"
    )

    return {
        "affordable_drawdown_pct": round(drawdown_pct, 2),
        "affordable_loss_amount": round(affordable_loss, 2),
        "emergency_months": round(emergency_months, 1),
        "total_invested": round(total_invested, 2),
        "supports_profile": supports,
        "narrative": narrative,
    }


def _calculate_need_for_return(
    goal: dict[str, Any],
    current_savings: float,
    inflation: float,
    returns_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Compute required real return to reach goal target in timeline."""
    target = goal.get("target_amount", 0)
    deadline = goal.get("deadline_years", 0)
    allocated = goal.get("allocated_monthly", 0)

    if target <= 0 or deadline <= 0:
        return {
            "required_real_return_pct": 0.0,
            "minimum_profile": "conservative",
            "achievable": True,
        }

    target_real = target / ((1 + inflation) ** deadline)

    if current_savings > 0 and allocated <= 0:
        # Lump sum only: required_return = (target/pv)^(1/years) - 1
        ratio = target_real / current_savings
        if ratio <= 1:
            required = 0.0
        else:
            required = ratio ** (1 / deadline) - 1
    elif current_savings <= 0 and allocated > 0:
        # Contributions only: FV of annuity = C * ((1+r)^n - 1) / r
        # Solve numerically with bisection
        required = _solve_required_return_annuity(
            allocated * 12, deadline, target_real,
        )
    elif current_savings > 0 and allocated > 0:
        # Both: FV = PV*(1+r)^n + C*((1+r)^n - 1)/r
        required = _solve_required_return_combined(
            current_savings, allocated * 12, deadline, target_real,
        )
    else:
        return {
            "required_real_return_pct": 0.0,
            "minimum_profile": "conservative",
            "achievable": False,
        }

    # Map to minimum profile
    sorted_profiles = sorted(returns_cfg.items(), key=lambda x: x[1])
    minimum_profile = "very_aggressive"
    achievable = False
    for name, ret in sorted_profiles:
        real_ret = ret - inflation
        if real_ret >= required:
            minimum_profile = name
            achievable = True
            break

    if not achievable and required <= sorted_profiles[-1][1] - inflation:
        minimum_profile = sorted_profiles[-1][0]
        achievable = True

    return {
        "required_real_return_pct": round(required * 100, 1),
        "minimum_profile": minimum_profile,
        "achievable": achievable,
    }


def _solve_required_return_annuity(
    annual_contribution: float, years: int, target: float,
) -> float:
    """Bisection solver for required return on annuity."""
    if annual_contribution * years >= target:
        return 0.0

    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if mid == 0:
            fv = annual_contribution * years
        else:
            fv = annual_contribution * ((1 + mid) ** years - 1) / mid
        if fv < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _solve_required_return_combined(
    pv: float, annual_contribution: float, years: int, target: float,
) -> float:
    """Bisection solver for required return on lump sum + annuity."""
    lo, hi = -0.05, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        growth = pv * ((1 + mid) ** years)
        if mid == 0:
            annuity = annual_contribution * years
        else:
            annuity = annual_contribution * ((1 + mid) ** years - 1) / mid
        fv = growth + annuity
        if fv < target:
            lo = mid
        else:
            hi = mid
    return max(0.0, (lo + hi) / 2)


def _resolve_effective_profile(
    horizon_profile: str,
    capacity_profile: str,
    need_profile: str,
) -> str:
    """Resolve the effective risk profile from three factors.

    Horizon is the ceiling (time-based constraint).
    Capacity can lower (affordability constraint).
    Need can push up but never above horizon.
    """
    horizon_idx = _PROFILE_ORDER.index(horizon_profile)
    capacity_idx = _PROFILE_ORDER.index(capacity_profile)
    need_idx = _PROFILE_ORDER.index(need_profile)

    # Ceiling is the more conservative of horizon and capacity
    ceiling_idx = min(horizon_idx, capacity_idx)

    # Need can push up toward the ceiling, but never above it
    effective_idx = min(need_idx, ceiling_idx)

    return _PROFILE_ORDER[effective_idx]


def _estimate_goal_savings(
    goal: dict[str, Any], profile: dict[str, Any],
) -> float:
    """Estimate current savings allocated toward a goal."""
    category = goal.get("category", "general")
    sav = profile.get("savings", {})

    if category == "safety_net":
        return sav.get("emergency_fund", 0)
    elif category == "property":
        return sav.get("lisa_balance", 0) + sav.get("house_deposit_savings", 0)
    else:
        return sav.get("gia_balance", 0)
