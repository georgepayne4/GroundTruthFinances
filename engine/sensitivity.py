"""
sensitivity.py — User-Choice Sensitivity Analysis (T1-4)

Tests "what-if" scenarios by re-running key calculations with modified
inputs and comparing outcomes to the baseline.  Built-in scenarios:
- Property price variations
- Retirement age changes
- Savings rate increases
- Pension contribution increases
- Mortgage term variations
"""

from __future__ import annotations

import copy
from typing import Any

from engine.cashflow import analyse_cashflow
from engine.investments import analyse_investments
from engine.mortgage import analyse_mortgage


def run_sensitivity(
    profile: dict,
    assumptions: dict,
    cashflow: dict,
    debt_analysis: dict,
    investment_analysis: dict,
    mortgage_analysis: dict,
) -> dict[str, Any]:
    """
    Run sensitivity analysis across multiple what-if dimensions.
    Returns baseline metrics plus delta for each scenario.
    """
    sens_cfg = assumptions.get("sensitivity", {})

    baseline = _extract_metrics(
        cashflow, investment_analysis, mortgage_analysis,
    )

    scenarios: dict[str, list[dict]] = {}

    # 1. Property price sensitivity
    if mortgage_analysis.get("applicable"):
        scenarios["property_price"] = _property_price_scenarios(
            profile, assumptions, cashflow, debt_analysis,
            mortgage_analysis, baseline,
            sens_cfg.get("property_price_deltas_pct", [-10, -20, 10]),
        )

    # 2. Retirement age sensitivity
    scenarios["retirement_age"] = _retirement_age_scenarios(
        profile, assumptions, cashflow, investment_analysis, baseline,
        sens_cfg.get("retirement_age_deltas", [-2, 2, 5]),
    )

    # 3. Savings rate / pension contribution sensitivity
    scenarios["pension_contribution"] = _pension_contribution_scenarios(
        profile, assumptions, cashflow, investment_analysis, baseline,
        sens_cfg.get("pension_contribution_increases_pct", [2, 5]),
    )

    # 4. Mortgage term sensitivity
    if mortgage_analysis.get("applicable"):
        scenarios["mortgage_term"] = _mortgage_term_scenarios(
            profile, assumptions, cashflow, debt_analysis,
            mortgage_analysis, baseline,
            sens_cfg.get("mortgage_terms", [25, 30, 35]),
        )

    return {
        "baseline": baseline,
        "scenarios": scenarios,
    }


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

def _extract_metrics(cashflow: dict, investment: dict, mortgage: dict) -> dict:
    """Pull key metrics from module outputs for comparison."""
    pension = investment.get("pension_analysis", {})
    return {
        "surplus_monthly": cashflow.get("surplus", {}).get("monthly", 0),
        "savings_rate_pct": cashflow.get("savings_rate", {}).get("basic_pct", 0),
        "pension_replacement_pct": pension.get("income_replacement_ratio_pct", 0),
        "pension_at_retirement_real": pension.get("projected_at_retirement_real", 0),
        "retirement_income_net": pension.get("total_retirement_income_net", 0),
        "mortgage_monthly": mortgage.get("repayment", {}).get("monthly_repayment", 0),
        "mortgage_total_interest": mortgage.get("repayment", {}).get("total_interest", 0),
        "mortgage_readiness": mortgage.get("readiness", "N/A"),
        "post_mortgage_surplus": mortgage.get("repayment", {}).get("post_mortgage_surplus", 0),
    }


# ---------------------------------------------------------------------------
# Property price scenarios
# ---------------------------------------------------------------------------

def _property_price_scenarios(
    profile, assumptions, cashflow, debt_analysis,
    mortgage_analysis, baseline, deltas_pct,
) -> list[dict]:
    results = []
    orig_value = profile.get("mortgage", {}).get("target_property_value", 0)

    for delta_pct in deltas_pct:
        p = copy.deepcopy(profile)
        new_value = orig_value * (1 + delta_pct / 100)
        p["mortgage"]["target_property_value"] = new_value

        m = analyse_mortgage(p, assumptions, cashflow, debt_analysis)
        metrics = {
            "mortgage_monthly": m.get("repayment", {}).get("monthly_repayment", 0),
            "mortgage_total_interest": m.get("repayment", {}).get("total_interest", 0),
            "mortgage_readiness": m.get("readiness", "N/A"),
            "post_mortgage_surplus": m.get("repayment", {}).get("post_mortgage_surplus", 0),
            "deposit_gap": m.get("deposit", {}).get("gap", 0),
            "can_borrow_enough": m.get("borrowing", {}).get("can_borrow_enough", False),
        }

        results.append({
            "label": f"Property at £{new_value:,.0f} ({delta_pct:+.0f}%)",
            "property_value": round(new_value, 0),
            "delta_pct": delta_pct,
            "metrics": {k: round(v, 2) if isinstance(v, float) else v for k, v in metrics.items()},
            "vs_baseline": {
                "mortgage_monthly_delta": round(metrics["mortgage_monthly"] - baseline["mortgage_monthly"], 2),
                "total_interest_delta": round(metrics["mortgage_total_interest"] - baseline["mortgage_total_interest"], 2),
            },
        })

    return results


# ---------------------------------------------------------------------------
# Retirement age scenarios
# ---------------------------------------------------------------------------

def _retirement_age_scenarios(
    profile, assumptions, cashflow, investment_analysis, baseline, deltas,
) -> list[dict]:
    results = []
    orig_age = profile.get("personal", {}).get("retirement_age",
                assumptions.get("life_events", {}).get("retirement_age", 67))

    for delta in deltas:
        p = copy.deepcopy(profile)
        new_age = orig_age + delta
        p["personal"]["retirement_age"] = new_age

        inv = analyse_investments(p, assumptions, cashflow)
        pension = inv.get("pension_analysis", {})

        metrics = {
            "retirement_age": new_age,
            "pension_at_retirement_real": pension.get("projected_at_retirement_real", 0),
            "retirement_income_net": pension.get("total_retirement_income_net", 0),
            "pension_replacement_pct": pension.get("income_replacement_ratio_pct", 0),
            "pension_adequate": pension.get("adequate", False),
        }

        results.append({
            "label": f"Retire at {new_age} ({delta:+d} years)",
            "retirement_age": new_age,
            "delta_years": delta,
            "metrics": {k: round(v, 2) if isinstance(v, float) else v for k, v in metrics.items()},
            "vs_baseline": {
                "pension_real_delta": round(metrics["pension_at_retirement_real"] - baseline["pension_at_retirement_real"], 2),
                "replacement_pct_delta": round(metrics["pension_replacement_pct"] - baseline["pension_replacement_pct"], 1),
                "income_net_delta": round(metrics["retirement_income_net"] - baseline["retirement_income_net"], 2),
            },
        })

    return results


# ---------------------------------------------------------------------------
# Pension contribution scenarios
# ---------------------------------------------------------------------------

def _pension_contribution_scenarios(
    profile, assumptions, cashflow, investment_analysis, baseline, increases_pct,
) -> list[dict]:
    results = []
    orig_pct = profile.get("savings", {}).get("pension_personal_contribution_pct", 0)

    for inc_pct in increases_pct:
        p = copy.deepcopy(profile)
        new_pct = orig_pct + inc_pct / 100
        p["savings"]["pension_personal_contribution_pct"] = new_pct

        cf = analyse_cashflow(p, assumptions)
        inv = analyse_investments(p, assumptions, cf)
        pension = inv.get("pension_analysis", {})

        gross_salary = profile.get("income", {}).get("primary_gross_annual", 0)
        additional_annual = gross_salary * (inc_pct / 100)
        # Tax relief: basic or higher rate
        tax_cfg = assumptions.get("tax", {})
        if gross_salary > tax_cfg.get("basic_threshold", 50270):
            tax_relief_rate = tax_cfg.get("higher_rate", 0.40)
        else:
            tax_relief_rate = tax_cfg.get("basic_rate", 0.20)
        net_cost_annual = additional_annual * (1 - tax_relief_rate)

        metrics = {
            "personal_contribution_pct": round(new_pct * 100, 1),
            "additional_annual_gross": round(additional_annual, 2),
            "net_cost_annual": round(net_cost_annual, 2),
            "net_cost_monthly": round(net_cost_annual / 12, 2),
            "new_surplus_monthly": cf.get("surplus", {}).get("monthly", 0),
            "pension_at_retirement_real": pension.get("projected_at_retirement_real", 0),
            "retirement_income_net": pension.get("total_retirement_income_net", 0),
            "pension_replacement_pct": pension.get("income_replacement_ratio_pct", 0),
            "pension_adequate": pension.get("adequate", False),
        }

        results.append({
            "label": f"Pension +{inc_pct}% (to {new_pct*100:.0f}%)",
            "increase_pct": inc_pct,
            "metrics": {k: round(v, 2) if isinstance(v, float) else v for k, v in metrics.items()},
            "vs_baseline": {
                "surplus_monthly_delta": round(metrics["new_surplus_monthly"] - baseline["surplus_monthly"], 2),
                "pension_real_delta": round(metrics["pension_at_retirement_real"] - baseline["pension_at_retirement_real"], 2),
                "replacement_pct_delta": round(metrics["pension_replacement_pct"] - baseline["pension_replacement_pct"], 1),
            },
        })

    return results


# ---------------------------------------------------------------------------
# Mortgage term scenarios
# ---------------------------------------------------------------------------

def _mortgage_term_scenarios(
    profile, assumptions, cashflow, debt_analysis,
    mortgage_analysis, baseline, terms,
) -> list[dict]:
    results = []
    orig_term = profile.get("mortgage", {}).get("preferred_term_years", 25)

    for term in terms:
        if term == orig_term:
            continue
        p = copy.deepcopy(profile)
        p["mortgage"]["preferred_term_years"] = term

        m = analyse_mortgage(p, assumptions, cashflow, debt_analysis)
        metrics = {
            "term_years": term,
            "mortgage_monthly": m.get("repayment", {}).get("monthly_repayment", 0),
            "mortgage_total_interest": m.get("repayment", {}).get("total_interest", 0),
            "post_mortgage_surplus": m.get("repayment", {}).get("post_mortgage_surplus", 0),
            "stress_test_passes": m.get("affordability", {}).get("stress_test_passes", False),
        }

        results.append({
            "label": f"{term}-year mortgage",
            "term_years": term,
            "metrics": {k: round(v, 2) if isinstance(v, float) else v for k, v in metrics.items()},
            "vs_baseline": {
                "monthly_delta": round(metrics["mortgage_monthly"] - baseline["mortgage_monthly"], 2),
                "total_interest_delta": round(metrics["mortgage_total_interest"] - baseline["mortgage_total_interest"], 2),
                "surplus_delta": round(metrics["post_mortgage_surplus"] - baseline["post_mortgage_surplus"], 2),
            },
        })

    return results
