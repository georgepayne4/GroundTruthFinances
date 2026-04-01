"""
scoring.py — Financial Health Scoring System

Generates a composite financial health score (0–100) with weighted
category breakdowns.  Each category is scored independently using
domain-specific rubrics, then combined using configurable weights.
"""

from __future__ import annotations

from typing import Any


def calculate_scores(
    profile: dict,
    assumptions: dict,
    cashflow: dict,
    debt_analysis: dict,
    goal_analysis: dict,
    investment_analysis: dict,
    mortgage_analysis: dict,
) -> dict[str, Any]:
    """
    Calculate financial health score with category breakdown.

    Categories:
    1. Savings Rate         — how much of income is being saved
    2. Debt Health          — interest rates, DTI, payoff timeline
    3. Emergency Fund       — months of coverage
    4. Net Worth Trend      — direction and magnitude
    5. Goal Progress        — feasibility of stated goals
    6. Investment Quality   — diversification, pension adequacy
    7. Mortgage Readiness   — if applicable, how close to ready
    """
    weights = assumptions.get("scoring", {}).get("weights", {})

    categories = {}

    categories["savings_rate"] = _score_savings_rate(cashflow, weights.get("savings_rate", 0.20))
    age = profile.get("personal", {}).get("age", 30)
    categories["debt_health"] = _score_debt_health(debt_analysis, assumptions, weights.get("debt_health", 0.20), age)
    categories["emergency_fund"] = _score_emergency_fund(profile, assumptions, weights.get("emergency_fund", 0.15))
    categories["net_worth_trend"] = _score_net_worth(profile, cashflow, weights.get("net_worth_trend", 0.10))
    categories["goal_progress"] = _score_goals(goal_analysis, weights.get("goal_progress", 0.15))
    categories["investment_quality"] = _score_investments(investment_analysis, weights.get("investment_diversification", 0.10))
    categories["mortgage_readiness"] = _score_mortgage(mortgage_analysis, weights.get("mortgage_readiness", 0.10))

    # ------------------------------------------------------------------
    # Composite score
    # ------------------------------------------------------------------
    total_weight = sum(c["weight"] for c in categories.values())
    if total_weight > 0:
        composite = sum(c["score"] * c["weight"] for c in categories.values()) / total_weight
    else:
        composite = 0

    # Determine grade
    grade = _grade_from_score(composite)

    return {
        "overall_score": round(composite, 1),
        "grade": grade,
        "categories": categories,
        "interpretation": _interpret_score(composite),
    }


# ---------------------------------------------------------------------------
# Category scoring functions
# ---------------------------------------------------------------------------

def _score_savings_rate(cashflow: dict, weight: float) -> dict:
    """
    Score based on basic savings rate.
    0%  → 0
    5%  → 30
    10% → 50
    15% → 65
    20% → 80
    30%+→ 100
    """
    rate = cashflow.get("savings_rate", {}).get("basic_pct", 0)
    if rate <= 0:
        score = 0
    elif rate < 5:
        score = rate * 6  # 0-30
    elif rate < 10:
        score = 30 + (rate - 5) * 4  # 30-50
    elif rate < 15:
        score = 50 + (rate - 10) * 3  # 50-65
    elif rate < 20:
        score = 65 + (rate - 15) * 3  # 65-80
    elif rate < 30:
        score = 80 + (rate - 20) * 2  # 80-100
    else:
        score = 100

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"Savings rate: {rate:.1f}%",
        "benchmark": "Target: 15-20% of net income",
    }


def _score_debt_health(debt_analysis: dict, assumptions: dict, weight: float, age: int = 30) -> dict:
    """
    Score based on:
    - Presence of high-interest debt (heavy penalty)
    - DTI ratio
    - Total payoff timeline
    """
    summary = debt_analysis.get("summary", {})
    total_balance = summary.get("total_balance", 0)

    if total_balance == 0:
        return {
            "score": 95,  # not 100 because no debt history can mean limited credit
            "weight": weight,
            "detail": "No outstanding debt",
            "benchmark": "Debt-free is excellent",
        }

    score = 100.0

    # High-interest debt penalty
    high_count = summary.get("high_interest_debt_count", 0)
    high_balance = summary.get("high_interest_total_balance", 0)
    if high_count > 0:
        score -= 25  # significant penalty
        if high_balance > 5000:
            score -= 10  # additional penalty for large high-interest balances

    # DTI penalty
    dti = summary.get("debt_to_income_gross_pct", 0)
    if dti > 40:
        score -= 30
    elif dti > 30:
        score -= 20
    elif dti > 20:
        score -= 10
    elif dti > 10:
        score -= 5

    # Payoff timeline (less penalised for young people with student loans)
    months = summary.get("longest_payoff_months", 0)
    payoff_penalty_factor = 1.0 if age >= 40 else 0.5 if age >= 30 else 0.3
    if months > 120:
        score -= 15 * payoff_penalty_factor
    elif months > 60:
        score -= 10 * payoff_penalty_factor
    elif months > 36:
        score -= 5 * payoff_penalty_factor

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"DTI: {dti:.1f}%, high-interest debts: {high_count}, longest payoff: {months} months",
        "benchmark": "Target: DTI < 20%, no high-interest debt",
    }


def _score_emergency_fund(profile: dict, assumptions: dict, weight: float) -> dict:
    """
    Score based on months of expense coverage.
    0 months   → 0
    1 month    → 20
    3 months   → 50
    6 months   → 85
    12+ months → 100
    """
    sav = profile.get("savings", {})
    exp = profile.get("expenses", {})
    ef = sav.get("emergency_fund", 0)
    monthly_exp = exp.get("_total_monthly", 1)  # avoid div/0
    debt_monthly = profile.get("_debt_summary", {}).get("total_minimum_monthly", 0)
    total_monthly = monthly_exp + debt_monthly

    months_covered = ef / total_monthly if total_monthly > 0 else 0

    if months_covered <= 0:
        score = 0
    elif months_covered < 1:
        score = months_covered * 20
    elif months_covered < 3:
        score = 20 + (months_covered - 1) * 15  # 20-50
    elif months_covered < 6:
        score = 50 + (months_covered - 3) * 11.67  # 50-85
    elif months_covered < 12:
        score = 85 + (months_covered - 6) * 2.5  # 85-100
    else:
        score = 100

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"Emergency fund covers {months_covered:.1f} months of expenses+debt",
        "benchmark": "Target: 3-6 months of essential expenses",
    }


def _score_net_worth(profile: dict, cashflow: dict, weight: float) -> dict:
    """
    Score based on net worth relative to income, direction, AND age.

    Age-adjusted benchmarks (multiples of gross income):
      Under 30: 0x is normal, 0.5x is good
      30-35: 0.5x target, 1x is good
      35-40: 1x target, 2x is good
      40-45: 2x target, 3x is good
      45-50: 3x target, 5x is good
      50-55: 5x target, 7x is good
      55+:   7x target, 10x is good
    """
    nw = profile.get("_net_worth", 0)
    age = profile.get("personal", {}).get("age", 30)
    gross_annual = cashflow.get("income", {}).get("total_gross_annual", 1)
    surplus = cashflow.get("surplus", {}).get("annual", 0)

    nw_ratio = nw / gross_annual if gross_annual > 0 else 0
    direction = "growing" if surplus > 0 else "shrinking"

    # Age-adjusted target (expected net worth multiple of income)
    if age < 30:
        target_ratio = 0.0
        good_ratio = 0.5
    elif age < 35:
        target_ratio = 0.5
        good_ratio = 1.0
    elif age < 40:
        target_ratio = 1.0
        good_ratio = 2.0
    elif age < 45:
        target_ratio = 2.0
        good_ratio = 3.0
    elif age < 50:
        target_ratio = 3.0
        good_ratio = 5.0
    elif age < 55:
        target_ratio = 5.0
        good_ratio = 7.0
    else:
        target_ratio = 7.0
        good_ratio = 10.0

    if nw < 0:
        # Negative net worth — less concerning for under-30s (student loans)
        if age < 30:
            score = max(10, 40 + nw_ratio * 20)
        else:
            score = max(0, 30 + nw_ratio * 30)
    elif nw_ratio >= good_ratio:
        score = 90
    elif nw_ratio >= target_ratio:
        progress = (nw_ratio - target_ratio) / max(0.01, good_ratio - target_ratio)
        score = 65 + progress * 25  # 65-90
    elif target_ratio > 0:
        progress = nw_ratio / target_ratio
        score = 30 + progress * 35  # 30-65
    else:
        # Under 30, any positive net worth is good
        score = min(80, 50 + nw_ratio * 30)

    # Bonus/penalty for direction
    if surplus > 0:
        score = min(100, score + 5)
    elif surplus < 0:
        score = max(0, score - 10)

    benchmark_text = f"Age {age} target: {target_ratio:.1f}x income, good: {good_ratio:.1f}x income"

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"Net worth: {nw:,.0f} ({nw_ratio:.1f}x income), trend: {direction}",
        "benchmark": benchmark_text,
    }


def _score_goals(goal_analysis: dict, weight: float) -> dict:
    """Score based on proportion of goals that are on track."""
    summary = goal_analysis.get("summary", {})
    total = summary.get("total_goals", 0)
    if total == 0:
        return {
            "score": 50,  # neutral — no goals isn't bad but isn't great
            "weight": weight,
            "detail": "No financial goals defined",
            "benchmark": "Define goals to enable progress tracking",
        }

    on_track = summary.get("on_track", 0)
    at_risk = summary.get("at_risk", 0)
    unreachable = summary.get("unreachable", 0)

    # Weighted: on_track=1.0, at_risk=0.5, unreachable=0.0
    feasibility_score = (on_track * 1.0 + at_risk * 0.5) / total * 100

    # Bonus if surplus covers all goals
    if summary.get("surplus_covers_goals", False):
        feasibility_score = min(100, feasibility_score + 10)

    return {
        "score": round(min(100, max(0, feasibility_score)), 1),
        "weight": weight,
        "detail": f"{on_track} on track, {at_risk} at risk, {unreachable} unreachable out of {total}",
        "benchmark": "All goals should be on track or at risk (with a plan)",
    }


def _score_investments(investment_analysis: dict, weight: float) -> dict:
    """Score based on pension adequacy and investment engagement."""
    pension = investment_analysis.get("pension_analysis", {})
    replacement = pension.get("income_replacement_ratio_pct", 0)
    adequate = pension.get("adequate", False)
    total_invested = investment_analysis.get("current_portfolio", {}).get("total_invested", 0)

    score = 0.0

    # Pension adequacy (50% of this category)
    if adequate:
        score += 50
    elif replacement >= 30:
        score += 35
    elif replacement >= 15:
        score += 20
    else:
        score += 5

    # Investment engagement (30% of this category)
    if total_invested > 0:
        score += 30
    else:
        score += 5  # at least they're being assessed

    # Contribution rate (20%)
    monthly_contrib = pension.get("monthly_contribution_total", 0)
    if monthly_contrib > 0:
        score += 20
    else:
        score += 0

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"Pension replacement: {replacement:.0f}%, total invested: {total_invested:,.0f}",
        "benchmark": "Target: pension replacing 50%+ of income, diversified portfolio",
    }


def _score_mortgage(mortgage_analysis: dict, weight: float) -> dict:
    """Score mortgage readiness if applicable."""
    if not mortgage_analysis.get("applicable", False):
        # Not applicable — score neutrally and redistribute weight implicitly
        return {
            "score": 70,  # neutral-positive
            "weight": weight,
            "detail": "No mortgage goal specified",
            "benchmark": "N/A",
        }

    readiness = mortgage_analysis.get("readiness", "not_ready")
    blockers = mortgage_analysis.get("blockers", [])

    readiness_scores = {
        "ready": 95,
        "near_ready": 70,
        "needs_work": 40,
        "not_ready": 15,
    }
    score = readiness_scores.get(readiness, 30)

    return {
        "score": round(score, 1),
        "weight": weight,
        "detail": f"Readiness: {readiness}, blockers: {len(blockers)}",
        "benchmark": "Target: ready or near-ready with clear path to resolution",
    }


# ---------------------------------------------------------------------------
# Interpretation helpers
# ---------------------------------------------------------------------------

def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B+"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C+"
    elif score >= 40:
        return "C"
    elif score >= 30:
        return "D"
    else:
        return "F"


def _interpret_score(score: float) -> str:
    if score >= 85:
        return "Excellent financial health. You are well-positioned across all major categories."
    elif score >= 70:
        return "Good financial health with some areas for improvement. Focus on the lower-scoring categories."
    elif score >= 55:
        return "Fair financial health. Several areas need attention — prioritise high-interest debt and emergency savings."
    elif score >= 40:
        return "Below average. Immediate action needed on debt management and building safety nets before pursuing other goals."
    else:
        return "Critical. Financial stability is at risk. Focus exclusively on reducing high-interest debt and building a minimal emergency fund."
