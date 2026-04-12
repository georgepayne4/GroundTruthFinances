"""
scenarios.py — Stress Testing & Scenario Analysis

Single-variable stress tests (v5.0):
- Job loss, interest rate shock, market downturn, inflation shock, income reduction

Compound multi-variable scenario trees (v8.6):
- Pre-built correlated scenarios (recession, boom, stagflation, baseline)
- Probability-weighted expected outcomes with NPV at each leaf
- Per-scenario recommended actions and nudge categories
"""

from __future__ import annotations

import copy
import logging

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.goals import analyse_goals
from engine.investments import analyse_investments
from engine.mortgage import analyse_mortgage
from engine.scoring import calculate_scores
from engine.types import (
    AssumptionsDict,
    CashflowResult,
    DebtResult,
    InvestmentsResult,
    MortgageResult,
    ProfileDict,
    ScenariosResult,
)
from engine.utils import monthly_repayment as _amortising_payment

logger = logging.getLogger(__name__)


def run_scenarios(
    profile: ProfileDict,
    assumptions: AssumptionsDict,
    cashflow: CashflowResult,
    debt_analysis: DebtResult,
    mortgage_analysis: MortgageResult,
    investment_analysis: InvestmentsResult,
) -> ScenariosResult:
    """Run all stress scenarios and return results."""
    scn_cfg = assumptions.get("scenarios", {})
    result: ScenariosResult = {
        "job_loss": _job_loss_scenario(profile, cashflow, scn_cfg),
        "interest_rate_shock": _rate_shock_scenario(profile, assumptions, cashflow, mortgage_analysis, scn_cfg),
        "market_downturn": _market_downturn_scenario(profile, investment_analysis, scn_cfg),
        "inflation_shock": _inflation_shock_scenario(profile, cashflow, scn_cfg),
        "income_reduction": _income_reduction_scenario(profile, cashflow, scn_cfg),
    }

    compound_cfg = assumptions.get("compound_scenarios", {})
    if compound_cfg.get("scenarios"):
        result["compound_scenarios"] = _run_compound_scenarios(
            profile, assumptions, cashflow, debt_analysis,
            mortgage_analysis, investment_analysis, compound_cfg,
        )

    return result


def _job_loss_scenario(profile: dict, cashflow: dict, scn_cfg: dict | None = None) -> dict:
    """
    How long can the user survive without income?
    """
    if scn_cfg is None:
        scn_cfg = {}
    sav = profile.get("savings", {})
    liquid = sav.get("_total_liquid", 0)
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 0)
    debt_monthly = cashflow.get("debt_servicing", {}).get("total_monthly", 0)
    monthly_burn = monthly_expenses + debt_monthly

    if monthly_burn <= 0:
        months_runway = 999
    else:
        months_runway = liquid / monthly_burn

    scenarios = {}
    for months in scn_cfg.get("job_loss_months", [3, 6, 12]):
        total_needed = monthly_burn * months
        shortfall = max(0, total_needed - liquid)
        survives = liquid >= total_needed
        scenarios[f"{months}_months"] = {
            "total_cost": round(total_needed, 2),
            "shortfall": round(shortfall, 2),
            "survives": survives,
        }

    return {
        "monthly_burn_rate": round(monthly_burn, 2),
        "liquid_savings": round(liquid, 2),
        "months_runway": round(months_runway, 1),
        "scenarios": scenarios,
        "assessment": (
            "comfortable" if months_runway >= 6
            else "tight" if months_runway >= 3
            else "critical"
        ),
        "recommendation": (
            "You have a comfortable runway. Maintain this buffer."
            if months_runway >= 6
            else f"Your savings would last {months_runway:.1f} months without income. "
                 f"Target at least 3 months (£{monthly_burn * 3:,.0f}) as a minimum safety net."
        ),
    }


def _rate_shock_scenario(
    profile: dict, assumptions: dict, cashflow: dict, mortgage_analysis: dict,
    scn_cfg: dict | None = None,
) -> dict:
    """
    Test mortgage affordability at elevated interest rates.
    Scenarios: +1%, +2%, +3% above current estimated rate.
    """
    if not mortgage_analysis.get("applicable"):
        return {"applicable": False, "reason": "Mortgage not applicable."}

    repayment = mortgage_analysis.get("repayment", {})
    mortgage_amount = repayment.get("mortgage_amount", 0)
    term_years = repayment.get("term_years", 25)
    base_rate = repayment.get("estimated_rate_pct", 5.0) / 100
    net_monthly = cashflow.get("net_income", {}).get("monthly", 0)
    current_rent = profile.get("expenses", {}).get("housing", {}).get("rent_monthly", 0)
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)

    if scn_cfg is None:
        scn_cfg = {}

    scenarios = {}
    for bump in scn_cfg.get("rate_shock_bumps_pct", [1, 2, 3]):
        shocked_rate = base_rate + (bump / 100)
        payment = _amortising_payment(mortgage_amount, shocked_rate, term_years)
        ratio = (payment / net_monthly * 100) if net_monthly > 0 else 100
        post_mortgage_surplus = surplus_monthly - (payment - current_rent)
        scenarios[f"plus_{bump}_pct"] = {
            "rate_pct": round(shocked_rate * 100, 2),
            "monthly_payment": round(payment, 2),
            "affordability_pct": round(ratio, 1),
            "affordable": ratio <= 35,
            "post_mortgage_surplus": round(post_mortgage_surplus, 2),
            "in_deficit": post_mortgage_surplus < 0,
        }

    return {
        "applicable": True,
        "base_rate_pct": round(base_rate * 100, 2),
        "base_payment": round(repayment.get("monthly_repayment", 0), 2),
        "scenarios": scenarios,
    }


def _market_downturn_scenario(profile: dict, investment_analysis: dict, scn_cfg: dict | None = None) -> dict:
    """
    Impact of market corrections on investment portfolio.
    """
    if scn_cfg is None:
        scn_cfg = {}
    portfolio = investment_analysis.get("current_portfolio", {})
    total = portfolio.get("total_invested", 0)
    portfolio.get("pension_balance", 0)
    portfolio.get("isa_balance", 0)
    portfolio.get("lisa_balance", 0)

    pension_analysis = investment_analysis.get("pension_analysis", {})
    projected_retirement = pension_analysis.get("projected_balance_nominal", 0)

    scenarios = {}
    for drop in scn_cfg.get("market_drop_pcts", [10, 20, 30]):
        factor = 1 - (drop / 100)
        new_total = total * factor
        loss = total - new_total
        new_pension_projected = projected_retirement * factor
        scenarios[f"minus_{drop}_pct"] = {
            "portfolio_value": round(new_total, 2),
            "loss": round(loss, 2),
            "pension_at_retirement": round(new_pension_projected, 2),
        }

    return {
        "current_portfolio": round(total, 2),
        "scenarios": scenarios,
        "recommendation": (
            "Market downturns are normal. At your age, you have time to recover. "
            "Do not sell during a downturn — maintain contributions and buy at lower prices."
            if profile.get("personal", {}).get("age", 30) < 40
            else "Consider reviewing your risk profile to ensure you can tolerate volatility "
                 "this close to needing the money."
        ),
    }


def _inflation_shock_scenario(profile: dict, cashflow: dict, scn_cfg: dict | None = None) -> dict:
    """
    Test impact of higher inflation on expenses and surplus.
    """
    if scn_cfg is None:
        scn_cfg = {}
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 0)
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    annual_expenses = monthly_expenses * 12
    cashflow.get("net_income", {}).get("annual", 0)

    scenarios = {}
    for rate in scn_cfg.get("inflation_shock_pcts", [5, 8, 10]):
        inflated_annual = annual_expenses * (1 + rate / 100)
        inflated_monthly = inflated_annual / 12
        increase = inflated_monthly - monthly_expenses
        new_surplus = surplus - increase
        scenarios[f"{rate}_pct"] = {
            "inflated_monthly_expenses": round(inflated_monthly, 2),
            "monthly_increase": round(increase, 2),
            "new_surplus": round(new_surplus, 2),
            "in_deficit": new_surplus < 0,
        }

    return {
        "current_monthly_expenses": round(monthly_expenses, 2),
        "current_surplus": round(surplus, 2),
        "scenarios": scenarios,
    }


def _income_reduction_scenario(profile: dict, cashflow: dict, scn_cfg: dict | None = None) -> dict:
    """
    Test impact of income reduction (pay cut, reduced hours).
    """
    if scn_cfg is None:
        scn_cfg = {}
    net_monthly = cashflow.get("net_income", {}).get("monthly", 0)
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 0)
    debt_monthly = cashflow.get("debt_servicing", {}).get("total_monthly", 0)
    total_outgoings = monthly_expenses + debt_monthly

    scenarios = {}
    for cut in scn_cfg.get("income_cut_pcts", [10, 20, 30]):
        factor = 1 - (cut / 100)
        new_net = net_monthly * factor
        new_surplus = new_net - total_outgoings
        scenarios[f"minus_{cut}_pct"] = {
            "new_net_monthly": round(new_net, 2),
            "new_surplus": round(new_surplus, 2),
            "in_deficit": new_surplus < 0,
        }

    return {
        "current_net_monthly": round(net_monthly, 2),
        "current_surplus": round(surplus, 2),
        "scenarios": scenarios,
    }


# ---------------------------------------------------------------------------
# Compound scenario trees (v8.6)
# ---------------------------------------------------------------------------


def _run_compound_scenarios(
    profile: dict, assumptions: dict, cashflow: dict,
    debt_analysis: dict, mortgage_analysis: dict,
    investment_analysis: dict, compound_cfg: dict,
) -> dict:
    """Run correlated multi-variable scenarios and build decision tree."""
    logger.info("Running compound scenario tree analysis")
    scenario_defs = compound_cfg.get("scenarios", [])

    baseline_metrics = _extract_baseline_metrics(cashflow, investment_analysis)
    discount_rate = _resolve_discount_rate(assumptions, profile, compound_cfg)
    baseline_npv = _npv_of_surplus(cashflow, profile, discount_rate)

    branches = []
    for scn_def in scenario_defs:
        branch = _evaluate_branch(
            scn_def, profile, assumptions, discount_rate,
        )
        branches.append(branch)

    # Compute deltas against baseline metrics
    for branch in branches:
        r = branch["results"]
        branch["vs_baseline"] = {
            "score_delta": round(r["score"] - baseline_metrics.get("surplus_monthly", 0), 1),
            "surplus_monthly_delta": round(r["surplus_monthly"] - baseline_metrics["surplus_monthly"], 2),
            "npv_delta": round(r["npv_surplus"] - baseline_npv, 2),
        }

    # Use the baseline branch's score for accurate score deltas
    baseline_branch = next(
        (b for b in branches if b["name"] == "baseline"), None,
    )
    if baseline_branch:
        base_score = baseline_branch["results"]["score"]
        for branch in branches:
            branch["vs_baseline"]["score_delta"] = round(
                branch["results"]["score"] - base_score, 1,
            )

    expected = _compute_expected_values(branches)
    summary = _build_decision_summary(branches)

    return {
        "branches": branches,
        "expected_values": expected,
        "decision_summary": summary,
        "baseline_metrics": baseline_metrics,
        "baseline_npv": round(baseline_npv, 2),
    }


def _extract_baseline_metrics(cashflow: dict, investment_analysis: dict) -> dict:
    """Extract key metrics from existing analysis for comparison."""
    portfolio = investment_analysis.get("current_portfolio", {})
    pension = investment_analysis.get("pension_analysis", {})
    return {
        "surplus_monthly": cashflow.get("surplus", {}).get("monthly", 0),
        "surplus_annual": cashflow.get("surplus", {}).get("annual", 0),
        "net_income_monthly": cashflow.get("net_income", {}).get("monthly", 0),
        "total_invested": portfolio.get("total_invested", 0),
        "pension_projected": pension.get("projected_balance_nominal", 0),
    }


def _resolve_discount_rate(
    assumptions: dict, profile: dict, compound_cfg: dict,
) -> float:
    """Resolve discount rate from config or investment returns."""
    rate = compound_cfg.get("discount_rate_override")
    if rate is not None:
        return rate
    risk_profile = profile.get("personal", {}).get("risk_profile", "moderate")
    return assumptions.get("investment_returns", {}).get(risk_profile, 0.06)


def _npv_of_surplus(cashflow: dict, profile: dict, discount_rate: float) -> float:
    """Present value of annual surplus over remaining working years."""
    annual_surplus = cashflow.get("surplus", {}).get("annual", 0)
    personal = profile.get("personal", {})
    age = personal.get("age", 30)
    retirement_age = personal.get("retirement_age", 67)
    years = max(0, retirement_age - age)
    if years == 0 or annual_surplus == 0:
        return 0.0

    npv = 0.0
    for t in range(1, years + 1):
        npv += annual_surplus / (1 + discount_rate) ** t
    return npv


def _evaluate_branch(
    scn_def: dict, profile: dict, assumptions: dict,
    discount_rate: float,
) -> dict:
    """Evaluate a single compound scenario branch by re-running core modules."""
    p = copy.deepcopy(profile)
    a = copy.deepcopy(assumptions)

    income_mult = scn_def.get("income_multiplier", 1.0)
    loss_months = scn_def.get("income_loss_months", 0)
    expense_mult = scn_def.get("expense_multiplier", 1.0)
    inv_return = scn_def.get("investment_return_override")
    rate_bump = scn_def.get("interest_rate_bump_pct", 0.0)
    inflation = scn_def.get("inflation_override_pct")

    _apply_income_adjustment(p, income_mult, loss_months)
    _apply_expense_adjustment(p, expense_mult)

    if inv_return is not None:
        for key in ("conservative", "moderate", "aggressive", "very_aggressive"):
            if key in a.get("investment_returns", {}):
                a["investment_returns"][key] = inv_return

    if rate_bump and p.get("mortgage", {}).get("target_property_value", 0) > 0:
        current_rate = a.get("mortgage", {}).get("base_rate_pct", 5.0)
        a["mortgage"]["base_rate_pct"] = current_rate + rate_bump

    if inflation is not None:
        a["inflation"]["general"] = inflation

    cf = analyse_cashflow(p, a)
    debt = analyse_debt(p, a)
    goals = analyse_goals(p, a, cf, debt)
    inv = analyse_investments(p, a, cf)
    mort = analyse_mortgage(p, a, cf, debt)
    score = calculate_scores(p, a, cf, debt, goals, inv, mort)

    branch_npv = _npv_of_surplus(cf, p, discount_rate)
    goal_feasibility = _extract_goal_feasibility(goals)
    surplus_monthly = cf.get("surplus", {}).get("monthly", 0)
    surplus_annual = cf.get("surplus", {}).get("annual", 0)

    mort_applicable = mort.get("applicable", False)
    mort_affordable = None
    if mort_applicable:
        mort_affordable = mort.get("affordability", {}).get("stress_test_passes", False)

    overall_score = score.get("overall_score", 0)
    grade = score.get("grade", "N/A")

    return {
        "name": scn_def.get("name", "unknown"),
        "description": scn_def.get("description", ""),
        "probability": scn_def.get("probability", 0),
        "nudge_category": scn_def.get("nudge_category", "steady"),
        "adjustments": {
            "income_multiplier": income_mult,
            "income_loss_months": loss_months,
            "expense_multiplier": expense_mult,
            "investment_return_override": inv_return,
            "interest_rate_bump_pct": rate_bump,
            "inflation_override_pct": inflation,
        },
        "results": {
            "score": round(overall_score, 1),
            "grade": grade,
            "surplus_monthly": round(surplus_monthly, 2),
            "surplus_annual": round(surplus_annual, 2),
            "npv_surplus": round(branch_npv, 2),
            "goal_feasibility": goal_feasibility,
            "mortgage_affordable": mort_affordable,
        },
        "recommended_actions": scn_def.get("recommended_actions", []),
    }


def _apply_income_adjustment(profile: dict, multiplier: float, loss_months: int) -> None:
    """Apply income multiplier and job loss duration, then recompute totals."""
    income = profile.get("income", {})
    effective = multiplier
    if loss_months > 0:
        effective = multiplier * (1 - loss_months / 12)

    for key in ("primary_gross_annual", "partner_gross_annual", "bonus_annual_expected",
                "bonus_annual_low", "bonus_annual_high"):
        if key in income:
            income[key] = income[key] * effective

    # Recompute pre-calculated totals (set by loader.normalise_profile)
    primary_monthly = income.get("primary_gross_annual", 0) / 12
    partner_monthly = income.get("partner_gross_annual", 0) / 12
    side = income.get("side_income_monthly", 0)
    rental = income.get("rental_income_monthly", 0)
    invest_monthly = income.get("investment_income_annual", 0) / 12
    income["_total_gross_monthly"] = primary_monthly + partner_monthly + side + rental + invest_monthly
    income["_total_gross_annual"] = income["_total_gross_monthly"] * 12


def _apply_expense_adjustment(profile: dict, multiplier: float) -> None:
    """Apply expense multiplier to all expense fields and recompute totals."""
    if multiplier == 1.0:
        return
    expenses = profile.get("expenses", {})
    total_monthly = 0.0
    for cat_name, category in expenses.items():
        if cat_name.startswith("_") or not isinstance(category, dict):
            continue
        cat_monthly = 0.0
        for key, val in category.items():
            if key.startswith("_"):
                continue
            if isinstance(val, (int, float)):
                category[key] = val * multiplier
                if "monthly" in key:
                    cat_monthly += category[key]
                elif "annual" in key:
                    cat_monthly += category[key] / 12
        category["_category_monthly"] = round(cat_monthly, 2)
        total_monthly += cat_monthly
    expenses["_total_monthly"] = round(total_monthly, 2)
    expenses["_total_annual"] = round(total_monthly * 12, 2)


def _extract_goal_feasibility(goal_analysis: dict) -> list[dict]:
    """Extract goal feasibility summary from goal analysis."""
    goals = goal_analysis.get("goals", [])
    return [
        {
            "name": g.get("name", "Unknown"),
            "status": g.get("status", "unknown"),
            "on_track": g.get("status") == "on_track",
        }
        for g in goals
    ]


def _compute_expected_values(branches: list[dict]) -> dict:
    """Compute probability-weighted expected outcomes across branches."""
    if not branches:
        return {"expected_score": 0, "expected_npv": 0, "expected_surplus_monthly": 0}

    expected_score = sum(
        b["probability"] * b["results"]["score"] for b in branches
    )
    expected_npv = sum(
        b["probability"] * b["results"]["npv_surplus"] for b in branches
    )
    expected_surplus = sum(
        b["probability"] * b["results"]["surplus_monthly"] for b in branches
    )
    return {
        "expected_score": round(expected_score, 1),
        "expected_npv": round(expected_npv, 2),
        "expected_surplus_monthly": round(expected_surplus, 2),
    }


def _build_decision_summary(branches: list[dict]) -> dict:
    """Identify best/worst/most likely scenarios."""
    if not branches:
        return {}

    by_npv = sorted(branches, key=lambda b: b["results"]["npv_surplus"])
    by_prob = sorted(branches, key=lambda b: b["probability"], reverse=True)

    return {
        "best_case": by_npv[-1]["name"],
        "worst_case": by_npv[0]["name"],
        "most_likely": by_prob[0]["name"],
        "risk_spread": round(
            by_npv[-1]["results"]["npv_surplus"] - by_npv[0]["results"]["npv_surplus"], 2,
        ),
    }


