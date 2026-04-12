"""
scoring.py — Financial Health Scoring System

Generates a composite financial health score (0–100) with weighted
category breakdowns. Includes IA-3 emergency fund placement penalty.
"""

from __future__ import annotations

import logging

from engine.types import (
    AssumptionsDict,
    CashflowResult,
    DebtResult,
    GoalsResult,
    InvestmentsResult,
    MortgageResult,
    ProfileDict,
    ScoringResult,
)

logger = logging.getLogger(__name__)


def calculate_scores(
    profile: ProfileDict,
    assumptions: AssumptionsDict,
    cashflow: CashflowResult,
    debt_analysis: DebtResult,
    goal_analysis: GoalsResult,
    investment_analysis: InvestmentsResult,
    mortgage_analysis: MortgageResult,
) -> ScoringResult:
    """
    Calculate financial health score with category breakdown.
    """
    weights = assumptions.get("scoring", {}).get("weights", {})

    categories = {}

    categories["savings_rate"] = _score_savings_rate(cashflow, weights.get("savings_rate", 0.20))
    age = profile.get("personal", {}).get("age", 30)
    categories["debt_health"] = _score_debt_health(debt_analysis, assumptions, weights.get("debt_health", 0.20), age)
    categories["emergency_fund"] = _score_emergency_fund(profile, assumptions, investment_analysis, weights.get("emergency_fund", 0.15))
    categories["net_worth_trend"] = _score_net_worth(profile, cashflow, weights.get("net_worth_trend", 0.10))
    categories["goal_progress"] = _score_goals(goal_analysis, weights.get("goal_progress", 0.15))
    categories["investment_quality"] = _score_investments(investment_analysis, weights.get("investment_diversification", 0.10))
    categories["mortgage_readiness"] = _score_mortgage(mortgage_analysis, weights.get("mortgage_readiness", 0.10))

    # Composite score
    total_weight = sum(c["weight"] for c in categories.values())
    if total_weight > 0:
        composite = sum(c["score"] * c["weight"] for c in categories.values()) / total_weight
    else:
        composite = 0

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
    rate = cashflow.get("savings_rate", {}).get("basic_pct", 0)
    if rate <= 0:
        score = 0
    elif rate < 5:
        score = rate * 6
    elif rate < 10:
        score = 30 + (rate - 5) * 4
    elif rate < 15:
        score = 50 + (rate - 10) * 3
    elif rate < 20:
        score = 65 + (rate - 15) * 3
    elif rate < 30:
        score = 80 + (rate - 20) * 2
    else:
        score = 100

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"Savings rate: {rate:.1f}%",
        "benchmark": "Target: 15-20% of net income",
    }


def _score_debt_health(debt_analysis: dict, assumptions: dict, weight: float, age: int = 30) -> dict:
    summary = debt_analysis.get("summary", {})
    total_balance = summary.get("total_balance", 0)

    if total_balance == 0:
        return {
            "score": 95,
            "weight": weight,
            "detail": "No outstanding debt",
            "benchmark": "Debt-free is excellent",
        }

    score = 100.0

    high_count = summary.get("high_interest_debt_count", 0)
    high_balance = summary.get("high_interest_total_balance", 0)
    if high_count > 0:
        score -= 25
        if high_balance > 5000:
            score -= 10

    dti = summary.get("debt_to_income_gross_pct", 0)
    if dti > 40:
        score -= 30
    elif dti > 30:
        score -= 20
    elif dti > 20:
        score -= 10
    elif dti > 10:
        score -= 5

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


def _score_emergency_fund(profile: dict, assumptions: dict, investment_analysis: dict, weight: float) -> dict:
    """
    Score emergency fund with IA-3 penalty for market-exposed funds.
    """
    sav = profile.get("savings", {})
    exp = profile.get("expenses", {})
    ef = sav.get("emergency_fund", 0)
    monthly_exp = exp.get("_total_monthly", 1)
    debt_monthly = profile.get("_debt_summary", {}).get("total_minimum_monthly", 0)
    total_monthly = monthly_exp + debt_monthly

    months_covered = ef / total_monthly if total_monthly > 0 else 0

    if months_covered <= 0:
        score = 0
    elif months_covered < 1:
        score = months_covered * 20
    elif months_covered < 3:
        score = 20 + (months_covered - 1) * 15
    elif months_covered < 6:
        score = 50 + (months_covered - 3) * 11.67
    elif months_covered < 12:
        score = 85 + (months_covered - 6) * 2.5
    else:
        score = 100

    # IA-3: Penalise if emergency fund is in stocks & shares
    ef_type = sav.get("emergency_fund_type", "cash")
    placement_note = ""
    if ef_type == "stocks_and_shares" and ef > 0:
        score = max(0, score - 10)
        placement_note = " (penalised: market-exposed)"

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"Emergency fund covers {months_covered:.1f} months of expenses+debt{placement_note}",
        "benchmark": "Target: 3-6 months of essential expenses in cash",
    }


def _score_net_worth(profile: dict, cashflow: dict, weight: float) -> dict:
    nw = profile.get("_net_worth", 0)
    age = profile.get("personal", {}).get("age", 30)
    gross_annual = cashflow.get("income", {}).get("total_gross_annual", 1)
    surplus = cashflow.get("surplus", {}).get("annual", 0)

    nw_ratio = nw / gross_annual if gross_annual > 0 else 0
    direction = "growing" if surplus > 0 else "shrinking"

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
        if age < 30:
            score = max(10, 40 + nw_ratio * 20)
        else:
            score = max(0, 30 + nw_ratio * 30)
    elif nw_ratio >= good_ratio:
        score = 90
    elif nw_ratio >= target_ratio:
        progress = (nw_ratio - target_ratio) / max(0.01, good_ratio - target_ratio)
        score = 65 + progress * 25
    elif target_ratio > 0:
        progress = nw_ratio / target_ratio
        score = 30 + progress * 35
    else:
        score = min(80, 50 + nw_ratio * 30)

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
    summary = goal_analysis.get("summary", {})
    total = summary.get("total_goals", 0)
    if total == 0:
        return {
            "score": 50,
            "weight": weight,
            "detail": "No financial goals defined",
            "benchmark": "Define goals to enable progress tracking",
        }

    on_track = summary.get("on_track", 0)
    at_risk = summary.get("at_risk", 0)

    feasibility_score = (on_track * 1.0 + at_risk * 0.5) / total * 100

    if summary.get("surplus_covers_goals", False):
        feasibility_score = min(100, feasibility_score + 10)

    return {
        "score": round(min(100, max(0, feasibility_score)), 1),
        "weight": weight,
        "detail": f"{on_track} on track, {at_risk} at risk, {summary.get('unreachable', 0)} unreachable out of {total}",
        "benchmark": "All goals should be on track or at risk (with a plan)",
    }


def _score_investments(investment_analysis: dict, weight: float) -> dict:
    pension = investment_analysis.get("pension_analysis", {})
    replacement = pension.get("income_replacement_ratio_pct", 0)
    adequate = pension.get("adequate", False)
    total_invested = investment_analysis.get("current_portfolio", {}).get("total_invested", 0)

    score = 0.0

    if adequate:
        score += 50
    elif replacement >= 30:
        score += 35
    elif replacement >= 15:
        score += 20
    else:
        score += 5

    if total_invested > 0:
        score += 30
    else:
        score += 5

    monthly_contrib = pension.get("monthly_contribution_total", 0)
    if monthly_contrib > 0:
        score += 20

    # v8.1: MC probability bonus/penalty
    mc = pension.get("monte_carlo")
    if mc:
        prob = mc.get("probability_of_target_pct", 50)
        if prob >= 80:
            score += 5
        elif prob < 40:
            score -= 5

    # v8.4: Risk alignment bonus/penalty
    goal_rp = investment_analysis.get("goal_risk_profiles")
    if goal_rp:
        warnings = [m for m in goal_rp.get("mismatches", []) if m.get("severity") == "warning"]
        if not warnings:
            score += 5
        else:
            score -= 3 * min(len(warnings), 3)

    return {
        "score": round(min(100, max(0, score)), 1),
        "weight": weight,
        "detail": f"Pension replacement: {replacement:.0f}%, total invested: {total_invested:,.0f}",
        "benchmark": "Target: pension replacing 50%+ of income, diversified portfolio",
    }


def _score_mortgage(mortgage_analysis: dict, weight: float) -> dict:
    if not mortgage_analysis.get("applicable", False):
        return {
            "score": 70,
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
