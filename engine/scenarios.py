"""
scenarios.py — Stress Testing & Scenario Analysis

Runs the financial profile through adverse scenarios to test resilience:
- Job loss (income gap)
- Interest rate shock (mortgage affordability)
- Market downturn (investment losses)
- Inflation shock (expense increases)
- Income reduction (pay cut)

Each scenario recalculates key metrics and reports the impact.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.utils import monthly_repayment as _amortising_payment

logger = logging.getLogger(__name__)


def run_scenarios(
    profile: dict,
    assumptions: dict,
    cashflow: dict,
    debt_analysis: dict,
    mortgage_analysis: dict,
    investment_analysis: dict,
) -> dict[str, Any]:
    """Run all stress scenarios and return results."""
    scn_cfg = assumptions.get("scenarios", {})
    return {
        "job_loss": _job_loss_scenario(profile, cashflow, scn_cfg),
        "interest_rate_shock": _rate_shock_scenario(profile, assumptions, cashflow, mortgage_analysis, scn_cfg),
        "market_downturn": _market_downturn_scenario(profile, investment_analysis, scn_cfg),
        "inflation_shock": _inflation_shock_scenario(profile, cashflow, scn_cfg),
        "income_reduction": _income_reduction_scenario(profile, cashflow, scn_cfg),
    }


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


