"""
goals.py — Goal Feasibility Analysis

Evaluates each financial goal against available surplus, existing savings,
and time horizon.  Classifies goals as on-track, at-risk, or unreachable,
suggests required monthly contributions, and calculates "what would it take"
adjustments for off-track goals (FA-2).

T1-1: Prerequisite logic — emergency fund and high-interest debt must be
addressed before discretionary goals receive surplus allocation.
"""

from __future__ import annotations

from typing import Any


# Priority ordering for allocation
PRIORITY_RANK = {"high": 1, "medium": 2, "low": 3}


def analyse_goals(
    profile: dict, assumptions: dict, cashflow: dict,
    debt_analysis: dict | None = None,
) -> dict[str, Any]:
    """
    For each goal:
    - Check prerequisites (T1-1)
    - Calculate the gap between current savings and target
    - Determine required monthly saving to hit deadline
    - Classify feasibility given available surplus
    - Factor in inflation where applicable
    - Model LISA bonus for property goals
    - Suggest allocation of surplus across goals by priority
    - Calculate "what would it take" adjustments (FA-2)
    """
    goals = profile.get("goals", [])
    sav = profile.get("savings", {})
    personal = profile.get("personal", {})
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)
    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    age = personal.get("age", 30)

    # T1-1: Prerequisite config
    prereq_cfg = assumptions.get("goal_prerequisites", {})
    ef_months_required = prereq_cfg.get("emergency_fund_months_required", 3)
    clear_high_interest = prereq_cfg.get("clear_high_interest_debt_first", True)

    if not goals:
        return {"goals": [], "summary": _empty_summary(), "prerequisites": {}}

    # ------------------------------------------------------------------
    # T1-1: Check prerequisites
    # ------------------------------------------------------------------
    ef = sav.get("emergency_fund", 0)
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 1)
    ef_months_current = ef / monthly_expenses if monthly_expenses > 0 else 0
    ef_adequate = ef_months_current >= ef_months_required

    high_interest_count = 0
    high_interest_balance = 0
    if debt_analysis:
        high_interest_count = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
        high_interest_balance = debt_analysis.get("summary", {}).get("high_interest_total_balance", 0)
    has_high_interest_debt = clear_high_interest and high_interest_count > 0

    prerequisites = {
        "emergency_fund_adequate": ef_adequate,
        "emergency_fund_months_current": round(ef_months_current, 1),
        "emergency_fund_months_required": ef_months_required,
        "high_interest_debt_cleared": not has_high_interest_debt,
        "high_interest_debt_count": high_interest_count,
        "high_interest_debt_balance": round(high_interest_balance, 2),
        "all_met": ef_adequate and not has_high_interest_debt,
    }

    # LISA config
    lisa_cfg = assumptions.get("lisa", {})

    # ------------------------------------------------------------------
    # 1. Analyse each goal independently
    # ------------------------------------------------------------------
    analyses = []
    lisa_balance = sav.get("lisa_balance", 0)
    for g in goals:
        a = _analyse_single_goal(g, sav, inflation, lisa_balance, age, lisa_cfg)
        # T1-1: Mark blocked goals
        blocked_by = _check_goal_blocked(a, ef_adequate, has_high_interest_debt, ef_months_required)
        if blocked_by:
            a["blocked_by"] = blocked_by
        analyses.append(a)

    # ------------------------------------------------------------------
    # 2. Allocate surplus across goals by priority (respecting prerequisites)
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
        # Override to blocked if prerequisites not met
        if a.get("blocked_by"):
            a["feasibility_with_allocation"] = "blocked"
        # FA-2: Calculate "what would it take" for off-track goals
        if a["feasibility_with_allocation"] not in ("on_track",):
            a["what_would_it_take"] = _what_would_it_take(
                a["remaining_gap"], a["deadline_months"], surplus_monthly, alloc,
            )

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    total_required = sum(a["required_monthly"] for a in analyses)
    on_track = sum(1 for a in analyses if a["feasibility_with_allocation"] == "on_track")
    at_risk = sum(1 for a in analyses if a["feasibility_with_allocation"] == "at_risk")
    unreachable = sum(1 for a in analyses if a["feasibility_with_allocation"] == "unreachable")
    blocked = sum(1 for a in analyses if a["feasibility_with_allocation"] == "blocked")

    return {
        "goals": analyses,
        "prerequisites": prerequisites,
        "summary": {
            "total_goals": len(analyses),
            "on_track": on_track,
            "at_risk": at_risk,
            "unreachable": unreachable,
            "blocked": blocked,
            "total_required_monthly": round(total_required, 2),
            "available_surplus_monthly": round(surplus_monthly, 2),
            "surplus_covers_goals": surplus_monthly >= total_required,
            "shortfall_monthly": round(max(0, total_required - surplus_monthly), 2),
        },
    }


# ---------------------------------------------------------------------------
# T1-1: Prerequisite check
# ---------------------------------------------------------------------------

def _check_goal_blocked(
    goal: dict, ef_adequate: bool, has_high_interest_debt: bool,
    ef_months_required: int,
) -> list[str] | None:
    """Check if a goal is blocked by unmet prerequisites."""
    category = goal.get("category", "general")

    # Safety net goals are never blocked — they ARE the prerequisite
    if category == "safety_net":
        return None

    blockers = []
    if not ef_adequate:
        blockers.append(
            f"Emergency fund below {ef_months_required} months — build safety net before pursuing this goal"
        )
    if has_high_interest_debt:
        blockers.append(
            "High-interest debt outstanding — clear this before allocating to discretionary goals"
        )

    return blockers if blockers else None


# ---------------------------------------------------------------------------
# Single goal analysis
# ---------------------------------------------------------------------------

def _analyse_single_goal(
    goal: dict, savings: dict, inflation: float,
    lisa_balance: float = 0, age: int = 30,
    lisa_cfg: dict | None = None,
) -> dict:
    """Analyse feasibility of a single goal, including LISA bonus for property."""
    if lisa_cfg is None:
        lisa_cfg = {}

    name = goal.get("name", "Unnamed")
    target = goal.get("target_amount", 0)
    deadline_years = goal.get("deadline_years", 0)
    priority = goal.get("priority", "medium")
    category = goal.get("category", "general")
    property_price = goal.get("property_target_price", 0)

    deadline_months = max(1, deadline_years * 12)

    inflation_adjusted_target = target * ((1 + inflation) ** deadline_years)

    current_savings = _estimate_current_progress(goal, savings)

    # LISA bonus projection for property goals
    lisa_annual_max = lisa_cfg.get("annual_limit", 4000)
    lisa_bonus_rate = lisa_cfg.get("bonus_rate", 0.25)
    lisa_property_limit = lisa_cfg.get("property_price_limit", 450000)
    lisa_age_limit = lisa_cfg.get("age_limit", 40)

    lisa_info = None
    if category == "property" and lisa_balance > 0 and age < lisa_age_limit:
        years_can_contribute = min(deadline_years, lisa_age_limit - age)
        projected_bonuses = years_can_contribute * (lisa_annual_max * lisa_bonus_rate)
        projected_lisa_contributions = years_can_contribute * lisa_annual_max
        projected_lisa_total = lisa_balance + projected_lisa_contributions + projected_bonuses

        current_savings += projected_bonuses

        lisa_eligible = property_price <= lisa_property_limit if property_price > 0 else True

        lisa_info = {
            "current_balance": round(lisa_balance, 2),
            "projected_bonuses": round(projected_bonuses, 2),
            "projected_contributions": round(projected_lisa_contributions, 2),
            "projected_total_at_deadline": round(projected_lisa_total, 2),
            "property_eligible": lisa_eligible,
            "property_limit": lisa_property_limit,
            "warning": (
                f"Property target (£{property_price:,.0f}) is at the LISA limit of £{lisa_property_limit:,.0f}. "
                f"If the price exceeds this, LISA funds cannot be used penalty-free."
                if property_price >= lisa_property_limit * 0.95 and lisa_eligible
                else f"Property target (£{property_price:,.0f}) exceeds the LISA limit of £{lisa_property_limit:,.0f}. "
                     f"LISA withdrawal would incur a 25% penalty, losing the bonus and 6.25% of your contributions."
                if not lisa_eligible
                else None
            ),
        }

    remaining_gap = max(0, inflation_adjusted_target - current_savings)
    progress_pct = (current_savings / inflation_adjusted_target * 100) if inflation_adjusted_target > 0 else 0

    required_monthly = remaining_gap / deadline_months if deadline_months > 0 else remaining_gap

    result = {
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

    if lisa_info:
        result["lisa_projection"] = lisa_info

    return result


def _estimate_current_progress(goal: dict, savings: dict) -> float:
    """Estimate how much of existing savings can be attributed to a goal."""
    category = goal.get("category", "general")
    if category == "safety_net":
        return savings.get("emergency_fund", 0)
    elif category == "property":
        return (savings.get("general_savings", 0)
                + savings.get("isa_balance", 0)
                + savings.get("lisa_balance", 0))
    else:
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
# "What would it take" calculator (FA-2)
# ---------------------------------------------------------------------------

def _what_would_it_take(
    gap: float, deadline_months: int, total_surplus: float, allocated: float,
) -> dict:
    """
    For off-track goals, calculate what adjustments would make them achievable.
    """
    if deadline_months <= 0 or gap <= 0:
        return {}

    required_monthly = gap / deadline_months
    shortfall_monthly = max(0, required_monthly - allocated)

    income_increase_needed = shortfall_monthly
    expense_reduction_needed = shortfall_monthly

    if allocated > 0:
        extended_months = int(gap / allocated) + 1
        extended_years = round(extended_months / 12, 1)
    else:
        extended_months = None
        extended_years = None

    combined_each = shortfall_monthly / 2

    return {
        "shortfall_monthly": round(shortfall_monthly, 2),
        "option_increase_income_monthly": round(income_increase_needed, 2),
        "option_reduce_expenses_monthly": round(expense_reduction_needed, 2),
        "option_extend_deadline_months": extended_months,
        "option_extend_deadline_years": extended_years,
        "option_combined_income_and_expense": round(combined_each, 2),
    }


# ---------------------------------------------------------------------------
# Surplus allocation (T1-1: respects prerequisite ordering)
# ---------------------------------------------------------------------------

def _allocate_surplus(analyses: list[dict], surplus: float) -> list[float]:
    """
    Allocate available surplus across goals using a priority-weighted scheme.
    Safety net goals always get first allocation (prerequisite logic).
    """
    allocations = [0.0] * len(analyses)
    remaining = max(0, surplus)

    # Phase 1: Allocate to safety_net goals first (prerequisites)
    safety_indices = [i for i, a in enumerate(analyses) if a.get("category") == "safety_net"]
    other_indices = [i for i, a in enumerate(analyses) if a.get("category") != "safety_net"]

    if safety_indices and remaining > 0:
        remaining = _allocate_to_indices(analyses, allocations, safety_indices, remaining)

    # Phase 2: Allocate remaining to non-blocked goals by priority
    unblocked = [i for i in other_indices if not analyses[i].get("blocked_by")]
    if unblocked and remaining > 0:
        indexed = sorted(unblocked, key=lambda i: analyses[i]["priority_rank"])

        current_tier = None
        tier_indices = []
        for idx in indexed:
            if analyses[idx]["priority_rank"] != current_tier:
                if tier_indices and remaining > 0:
                    remaining = _allocate_to_indices(analyses, allocations, tier_indices, remaining)
                tier_indices = []
                current_tier = analyses[idx]["priority_rank"]
            tier_indices.append(idx)

        if tier_indices and remaining > 0:
            _allocate_to_indices(analyses, allocations, tier_indices, remaining)

    return allocations


def _allocate_to_indices(
    analyses: list[dict], allocations: list[float],
    indices: list[int], budget: float,
) -> float:
    """Allocate budget proportionally within a set of goal indices. Returns remaining."""
    total_needed = sum(analyses[i]["required_monthly"] for i in indices)
    if total_needed <= 0:
        return budget

    if budget >= total_needed:
        for i in indices:
            allocations[i] = analyses[i]["required_monthly"]
        return budget - total_needed
    else:
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
        "blocked": 0,
        "total_required_monthly": 0,
        "available_surplus_monthly": 0,
        "surplus_covers_goals": True,
        "shortfall_monthly": 0,
    }
