"""
investments.py — Investment Allocation and Projection

Suggests asset allocation based on risk profile, projects portfolio growth
over time, and evaluates whether current investment behaviour aligns with
stated goals and risk tolerance.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Model portfolios by risk profile
# ---------------------------------------------------------------------------
# Each sums to 100%.  These are simplified but realistic allocations.

MODEL_PORTFOLIOS = {
    "conservative": {
        "government_bonds": 40,
        "corporate_bonds": 20,
        "uk_equity": 15,
        "global_equity": 10,
        "property_funds": 5,
        "cash": 10,
    },
    "moderate": {
        "government_bonds": 15,
        "corporate_bonds": 15,
        "uk_equity": 25,
        "global_equity": 25,
        "property_funds": 10,
        "cash": 10,
    },
    "aggressive": {
        "government_bonds": 5,
        "corporate_bonds": 5,
        "uk_equity": 30,
        "global_equity": 40,
        "property_funds": 10,
        "cash": 10,
    },
    "very_aggressive": {
        "government_bonds": 0,
        "corporate_bonds": 0,
        "uk_equity": 30,
        "global_equity": 45,
        "emerging_markets": 10,
        "property_funds": 10,
        "cash": 5,
    },
}


def analyse_investments(profile: dict, assumptions: dict, cashflow: dict) -> dict[str, Any]:
    """
    Produce investment analysis:
    - Current portfolio snapshot
    - Suggested allocation based on risk profile
    - Projected growth at expected return rates
    - Pension adequacy estimate
    - ISA utilisation notes
    """
    sav = profile.get("savings", {})
    personal = profile.get("personal", {})
    inc = profile.get("income", {})
    surplus = cashflow.get("surplus", {}).get("monthly", 0)

    risk_profile = personal.get("risk_profile", "moderate").lower()
    if risk_profile not in MODEL_PORTFOLIOS:
        risk_profile = "moderate"

    returns_cfg = assumptions.get("investment_returns", {})
    expected_return = returns_cfg.get(risk_profile, 0.06)
    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    real_return = expected_return - inflation

    age = personal.get("age", 30)
    retirement_age = personal.get("retirement_age",
                                  assumptions.get("life_events", {}).get("retirement_age", 67))
    years_to_retirement = max(1, retirement_age - age)

    # ------------------------------------------------------------------
    # 1. Current portfolio snapshot
    # ------------------------------------------------------------------
    isa = sav.get("isa_balance", 0)
    lisa = sav.get("lisa_balance", 0)
    pension = sav.get("pension_balance", 0)
    other_inv = sav.get("other_investments", 0)
    total_invested = isa + lisa + pension + other_inv

    primary_gross = inc.get("primary_gross_annual", 0)
    pension_personal_pct = sav.get("pension_personal_contribution_pct", 0)
    pension_employer_pct = sav.get("pension_employer_contribution_pct", 0)
    annual_pension_contribution = primary_gross * (pension_personal_pct + pension_employer_pct)
    monthly_pension_contribution = annual_pension_contribution / 12

    # ------------------------------------------------------------------
    # 2. Model portfolio allocation
    # ------------------------------------------------------------------
    model = MODEL_PORTFOLIOS[risk_profile]

    # ------------------------------------------------------------------
    # 3. Portfolio growth projection (10, 20, 30 year horizons)
    # ------------------------------------------------------------------
    projections = _project_growth(
        current_invested=total_invested,
        monthly_contribution=monthly_pension_contribution,
        annual_return=expected_return,
        inflation=inflation,
        years_list=[5, 10, years_to_retirement],
    )

    # ------------------------------------------------------------------
    # 4. Pension adequacy
    # ------------------------------------------------------------------
    pension_at_retirement = _future_value(
        present_value=pension,
        monthly_contribution=monthly_pension_contribution,
        annual_return=expected_return,
        years=years_to_retirement,
    )
    pension_at_retirement_real = pension_at_retirement / ((1 + inflation) ** years_to_retirement)

    # Estimate annual pension income (4% safe withdrawal rate)
    safe_withdrawal_rate = 0.04
    estimated_annual_pension_income = pension_at_retirement_real * safe_withdrawal_rate
    pension_replacement_ratio = (
        estimated_annual_pension_income / primary_gross * 100
        if primary_gross > 0 else 0
    )

    life_expectancy = assumptions.get("life_events", {}).get("life_expectancy", 85)
    years_in_retirement = max(1, life_expectancy - retirement_age)
    pension_lasts_years = (
        pension_at_retirement_real / (estimated_annual_pension_income or 1)
    )

    pension_adequate = pension_replacement_ratio >= 50  # common benchmark

    # ------------------------------------------------------------------
    # 5. ISA analysis
    # ------------------------------------------------------------------
    isa_annual_limit = 20000  # current UK limit
    isa_utilisation = "not_tracked"
    # We can't know this year's contributions from a snapshot, but flag if balance is low
    isa_note = (
        "ISA balance is zero — consider using your annual ISA allowance for tax-free growth."
        if isa == 0 else
        "Ensure you are maximising your annual ISA allowance before using taxable accounts."
    )

    # ------------------------------------------------------------------
    # 6. Investable surplus
    # ------------------------------------------------------------------
    investable_monthly = max(0, surplus - monthly_pension_contribution)

    return {
        "current_portfolio": {
            "isa_balance": round(isa, 2),
            "lisa_balance": round(lisa, 2),
            "pension_balance": round(pension, 2),
            "other_investments": round(other_inv, 2),
            "total_invested": round(total_invested, 2),
        },
        "risk_profile": risk_profile,
        "expected_annual_return_pct": round(expected_return * 100, 1),
        "expected_real_return_pct": round(real_return * 100, 1),
        "suggested_allocation": model,
        "growth_projections": projections,
        "pension_analysis": {
            "current_balance": round(pension, 2),
            "monthly_contribution_total": round(monthly_pension_contribution, 2),
            "annual_contribution_total": round(annual_pension_contribution, 2),
            "projected_at_retirement_nominal": round(pension_at_retirement, 2),
            "projected_at_retirement_real": round(pension_at_retirement_real, 2),
            "estimated_annual_income_real": round(estimated_annual_pension_income, 2),
            "income_replacement_ratio_pct": round(pension_replacement_ratio, 1),
            "years_in_retirement": years_in_retirement,
            "fund_longevity_years": round(pension_lasts_years, 1),
            "adequate": pension_adequate,
        },
        "isa_note": isa_note,
        "investable_surplus_monthly": round(investable_monthly, 2),
    }


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------

def _future_value(
    present_value: float,
    monthly_contribution: float,
    annual_return: float,
    years: int,
) -> float:
    """
    Calculate future value with monthly compounding and contributions.
    FV = PV * (1 + r)^n + PMT * [((1 + r)^n - 1) / r]
    where r = monthly rate, n = total months.
    """
    if years <= 0:
        return present_value

    monthly_rate = annual_return / 12
    months = years * 12

    if monthly_rate == 0:
        return present_value + monthly_contribution * months

    compound = (1 + monthly_rate) ** months
    fv_lump = present_value * compound
    fv_annuity = monthly_contribution * ((compound - 1) / monthly_rate)
    return fv_lump + fv_annuity


def _project_growth(
    current_invested: float,
    monthly_contribution: float,
    annual_return: float,
    inflation: float,
    years_list: list[int],
) -> list[dict]:
    """Project portfolio value at multiple horizons, nominal and real."""
    results = []
    for y in years_list:
        nominal = _future_value(current_invested, monthly_contribution, annual_return, y)
        real = nominal / ((1 + inflation) ** y)
        total_contributions = current_invested + monthly_contribution * 12 * y
        growth = nominal - total_contributions
        results.append({
            "years": y,
            "nominal_value": round(nominal, 2),
            "real_value_today_terms": round(real, 2),
            "total_contributions": round(total_contributions, 2),
            "investment_growth": round(growth, 2),
        })
    return results
