"""
goals.py — Goal Feasibility Analysis

Evaluates each financial goal against available surplus, existing savings,
and time horizon.  Classifies goals as on-track, at-risk, or unreachable,
and suggests required monthly contributions.
"""

from __future__ import annotations

from typing import Any


# Priority ordering for allocation
PRIORITY_RANK = {"high": 1, "medium": 2, "low": 3}


def analyse_goals(profile: dict, assumptions: dict, cashflow: dict) -> dict[str, Any]:
    """
    For each goal:
    - Calculate the gap between current savings and target
    - Determine required monthly saving to hit deadline
    - Classify feasibility given available surplus
    - Factor in inflation where applicable
    - Suggest allocation of surplus across goals by priority
    """
    goals = profile.get("goals", [])
    sav = profile.get("savings", {})
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)
    inflation = assumptions.get("inflation", {}).get("general", 0.03)

    if not goals:
        return {"goals": [], "summary": _empty_summary()}

    # ------------------------------------------------------------------
    # 1. Analyse each goal independently
    # ------------------------------------------------------------------
    analyses = []
    for g in goals:
        a = _analyse_single_goal(g, sav, inflation)
        analyses.append(a)

    # ------------------------------------------------------------------
    # 2. Allocate surplus across goals by priority
    # ------------------------------------------------------------------
    allocation = _allocate_surplus(analyses, surplus_monthly)

    # ------------------------------------------------------------------
    # 3. Re-evaluate feasibility with allocated amounts
    # ------------------------------------------------------------------
    for a, alloc in zip(analyses, allocation):
        a["allocated_monthly"] = round(alloc, 2)
        a["feasibility_with_allocation"] = _assess_feasibility(
            a["remaining_gap"], alloc, a["deadline_months"]
        )

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    total_required = sum(a["required_monthly"] for a in analyses)
    on_track = sum(1 for a in analyses if a["feasibility_with_allocation"] == "on_track")
    at_risk = sum(1 for a in analyses if a["feasibility_with_allocation"] == "at_risk")
    unreachable = sum(1 for a in analyses if a["feasibility_with_allocation"] == "unreachable")

    return {
        "goals": analyses,
        "summary": {
            "total_goals": len(analyses),
            "on_track": on_track,
            "at_risk": at_risk,
            "unreachable": unreachable,
            "total_required_monthly": round(total_required, 2),
            "available_surplus_monthly": round(surplus_monthly, 2),
            "surplus_covers_goals": surplus_monthly >= total_required,
            "shortfall_monthly": round(max(0, total_required - surplus_monthly), 2),
        },
    }


# ---------------------------------------------------------------------------
# Single goal analysis
# ---------------------------------------------------------------------------

def _analyse_single_goal(goal: dict, savings: dict, inflation: float) -> dict:
    """Analyse feasibility of a single goal."""
    name = goal.get("name", "Unnamed")
    target = goal.get("target_amount", 0)
    deadline_years = goal.get("deadline_years", 0)
    priority = goal.get("priority", "medium")
    category = goal.get("category", "general")

    deadline_months = max(1, deadline_years * 12)

    # Adjust target for inflation if deadline > 1 year
    inflation_adjusted_target = target * ((1 + inflation) ** deadline_years)

    # Determine current progress toward this goal
    current_savings = _estimate_current_progress(goal, savings)

    remaining_gap = max(0, inflation_adjusted_target - current_savings)
    progress_pct = (current_savings / inflation_adjusted_target * 100) if inflation_adjusted_target > 0 else 0

    # Required monthly saving to close the gap
    required_monthly = remaining_gap / deadline_months if deadline_months > 0 else remaining_gap

    return {
        "name": name,
        "category": category,
        "priority": priority,
        "priority_rank": PRIORITY_RANK.get(priority, 2),
        "target_nominal": round(target, 2),
        "target_inflation_adjusted": round(inflation_adjusted_target, 2),
        "current_progress": round(current_savings, 2),
        "progress_pct": round(progress_pct, 1),
        "remaining_gap": round(remaining_gap, 2),
        "deadline_years": deadline_years,
        "deadline_months": deadline_months,
        "required_monthly": round(required_monthly, 2),
        "allocated_monthly": 0,
        "feasibility_with_allocation": "pending",
    }


def _estimate_current_progress(goal: dict, savings: dict) -> float:
    """
    Estimate how much of existing savings can be attributed to a goal.
    Uses category heuristics:
    - safety_net → emergency_fund
    - property → general_savings + isa (these are likely being saved for deposit)
    - For others, we don't assume existing savings apply
    """
    category = goal.get("category", "general")
    if category == "safety_net":
        return savings.get("emergency_fund", 0)
    elif category == "property":
        # Assume general savings + ISA are earmarked for deposit
        return savings.get("general_savings", 0) + savings.get("isa_balance", 0)
    else:
        # Conservative: don't assume savings are earmarked
        return 0


def _assess_feasibility(gap: float, monthly_contribution: float, months: int) -> str:
    """Classify goal feasibility based on whether contributions close the gap."""
    if gap <= 0:
        return "on_track"

    if monthly_contribution <= 0:
        return "unreachable"

    projected = monthly_contribution * months
    ratio = projected / gap

    if ratio >= 1.0:
        return "on_track"
    elif ratio >= 0.70:
        return "at_risk"
    else:
        return "unreachable"


# ---------------------------------------------------------------------------
# Surplus allocation
# ---------------------------------------------------------------------------

def _allocate_surplus(analyses: list[dict], surplus: float) -> list[float]:
    """
    Allocate available surplus across goals using a priority-weighted scheme.

    Strategy:
    1. High-priority goals get funded first (up to their required_monthly)
    2. Remaining surplus flows to medium, then low priority
    3. Within the same priority tier, allocate proportionally by required amount
    """
    allocations = [0.0] * len(analyses)
    remaining = max(0, surplus)

    # Sort indices by priority rank
    indexed = sorted(enumerate(analyses), key=lambda x: x[1]["priority_rank"])

    # Group by priority tier
    current_tier = None
    tier_indices = []

    for idx, a in indexed:
        if a["priority_rank"] != current_tier:
            # Allocate to previous tier
            if tier_indices and remaining > 0:
                remaining = _allocate_tier(analyses, allocations, tier_indices, remaining)
            tier_indices = []
            current_tier = a["priority_rank"]
        tier_indices.append(idx)

    # Final tier
    if tier_indices and remaining > 0:
        _allocate_tier(analyses, allocations, tier_indices, remaining)

    return allocations


def _allocate_tier(
    analyses: list[dict],
    allocations: list[float],
    indices: list[int],
    budget: float,
) -> float:
    """Allocate budget proportionally within a priority tier. Returns remaining budget."""
    total_needed = sum(analyses[i]["required_monthly"] for i in indices)
    if total_needed <= 0:
        return budget

    if budget >= total_needed:
        # Fully fund everything in this tier
        for i in indices:
            allocations[i] = analyses[i]["required_monthly"]
        return budget - total_needed
    else:
        # Pro-rata allocation
        for i in indices:
            share = analyses[i]["required_monthly"] / total_needed
            allocations[i] = budget * share
        return 0.0


def _empty_summary() -> dict:
    return {
        "total_goals": 0,
        "on_track": 0,
        "at_risk": 0,
        "unreachable": 0,
        "total_required_monthly": 0,
        "available_surplus_monthly": 0,
        "surplus_covers_goals": True,
        "shortfall_monthly": 0,
    }
