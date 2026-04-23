"""engine/lifetime_cashflow.py — Lifetime cashflow projection (v8.2).

Full year-by-year projection from current age to death, covering:
  - Accumulation: salary growth, pension/ISA contributions, debt payoff
  - Retirement transition: PCLS lump sum, employment cessation, state pension
  - Drawdown: pension/ISA drawdown, state pension, investment returns
  - Late life: reduced spending, care cost provision
"""

from __future__ import annotations

import logging
from typing import Any

from engine.types import (
    AssumptionsDict,
    CashflowResult,
    InvestmentsResult,
    MortgageResult,
    ProfileDict,
)

logger = logging.getLogger(__name__)


def project_lifetime_cashflow(
    profile: ProfileDict,
    assumptions: AssumptionsDict,
    cashflow: CashflowResult,
    investment_result: InvestmentsResult,
    mortgage_result: MortgageResult,
) -> dict[str, Any]:
    """Project year-by-year cashflow from current age to life expectancy."""
    personal = profile.get("personal", {})
    sav = profile.get("savings", {})
    inc = profile.get("income", {})

    age = personal.get("age", 30)
    retirement_age = personal.get("retirement_age",
                                  assumptions.get("life_events", {}).get("retirement_age", 67))
    life_expectancy = assumptions.get("life_events", {}).get("life_expectancy", 85)
    total_years = max(1, life_expectancy - age)

    # Config
    lcf_cfg = assumptions.get("lifetime_cashflow", {})
    retire_spending_pct = lcf_cfg.get("retirement_spending_pct_of_pre", 0.70)
    late_life_reduction = lcf_cfg.get("late_life_spending_reduction", 0.15)
    care_cost_home = lcf_cfg.get("care_cost_annual_home", 15000)
    care_start_age = lcf_cfg.get("care_provision_start_age", 85)

    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    risk_profile = personal.get("risk_profile", "moderate")
    investment_return = assumptions.get("investment_returns", {}).get(risk_profile, 0.06)
    salary_growth_key = personal.get("salary_growth_outlook", "average")
    salary_growth = assumptions.get("salary_growth", {}).get(salary_growth_key, 0.035)

    # Retirement config
    retire_cfg = assumptions.get("retirement", {})
    pcls_fraction = retire_cfg.get("tax_free_lump_sum_fraction", 0.25)
    isa_annual_limit = assumptions.get("isa", {}).get("annual_limit", 20000)

    # State pension
    sp_cfg = assumptions.get("state_pension", {})
    state_pension_annual = sp_cfg.get("full_annual_amount", 11502)
    state_pension_age = sp_cfg.get("age", 67)
    triple_lock = sp_cfg.get("triple_lock_growth", 0.035)

    # Initial balances
    gross_annual = inc.get("primary_gross_annual", 0) + inc.get("partner_gross_annual", 0)
    other_income = (inc.get("side_income_monthly", 0) * 12
                    + inc.get("rental_income_monthly", 0) * 12
                    + inc.get("investment_income_annual", 0))
    expenses_annual = cashflow.get("expenses", {}).get("total_annual", 0)
    pre_retirement_expenses = expenses_annual

    pension_bal = sav.get("pension_balance", 0)
    isa_bal = sav.get("isa_balance", 0) + sav.get("lisa_balance", 0)
    liquid = sav.get("_total_liquid", 0)
    total_debt = profile.get("_debt_summary", {}).get("total_balance", 0)
    debt_payments = cashflow.get("debt_servicing", {}).get("total_annual", 0)

    pension_personal_pct = sav.get("pension_personal_contribution_pct", 0)
    pension_employer_pct = sav.get("pension_employer_contribution_pct", 0)

    # Mortgage
    mortgage_bal = 0.0
    mortgage_payment_annual = 0.0
    if mortgage_result.get("applicable"):
        mortgage_bal = mortgage_result.get("current_balance", 0)
        mortgage_payment_annual = mortgage_result.get("monthly_payment", 0) * 12

    # Effective tax rate from cashflow
    gross_total = cashflow.get("income", {}).get("total_gross_annual", 0)
    deductions = cashflow.get("deductions", {}).get("total_deductions_annual", 0)
    tax_rate = min(0.60, deductions / gross_total) if gross_total > 0 else 0.25

    # State pension projection
    estimated_qualifying = min(35, max(0, age - 21))
    years_to_sp = max(0, state_pension_age - age)
    projected_qualifying = min(35, estimated_qualifying + years_to_sp)
    sp_fraction = projected_qualifying / 35 if projected_qualifying >= 10 else 0.0
    pcls_taken = False

    # Build timeline
    timeline: list[dict[str, Any]] = []
    phases: dict[str, dict[str, int]] = {}

    for yr in range(total_years + 1):
        current_age = age + yr
        is_retired = current_age >= retirement_age
        is_late_life = current_age >= 80
        receives_state_pension = current_age >= state_pension_age

        # Determine phase
        if not is_retired:
            phase = "accumulation"
        elif current_age == retirement_age:
            phase = "retirement_transition"
        elif is_late_life:
            phase = "late_life"
        else:
            phase = "drawdown"

        if phase not in phases:
            phases[phase] = {"start_age": current_age, "start_year": yr}
        phases[phase]["end_age"] = current_age
        phases[phase]["end_year"] = yr

        # --- Income ---
        employment_income = 0.0
        pension_income = 0.0
        state_pension_income = 0.0
        isa_drawdown = 0.0
        pcls_lump = 0.0

        if not is_retired:
            # Accumulation: salary income
            employment_income = gross_annual + other_income
            if yr > 0:
                gross_annual *= (1 + salary_growth)

            # Pension contributions
            primary_gross = inc.get("primary_gross_annual", 0) * ((1 + salary_growth) ** yr)
            annual_pension_contrib = primary_gross * (pension_personal_pct + pension_employer_pct)
            pension_bal += annual_pension_contrib

            # ISA contributions from surplus
            net_income = employment_income * (1 - tax_rate)
            year_expenses = expenses_annual + debt_payments + mortgage_payment_annual
            surplus = net_income - year_expenses
            if surplus > 0:
                isa_contrib = min(surplus * 0.3, isa_annual_limit)  # 30% of surplus to ISA, capped at allowance
                isa_bal += isa_contrib
                liquid += surplus - isa_contrib
            else:
                liquid += surplus  # negative surplus draws down liquid

        else:
            # Retirement transition: take PCLS
            if not pcls_taken:
                pcls_lump = pension_bal * pcls_fraction
                pension_bal -= pcls_lump
                liquid += pcls_lump
                pcls_taken = True

            # State pension (with triple lock growth from base year)
            if receives_state_pension:
                years_since_sp_start = current_age - state_pension_age
                state_pension_income = (
                    state_pension_annual * sp_fraction
                    * ((1 + triple_lock) ** max(0, years_to_sp + years_since_sp_start))
                )

            # Pension drawdown
            target_spending = _retirement_spending(
                pre_retirement_expenses, retire_spending_pct,
                late_life_reduction, current_age, inflation, yr, care_cost_home, care_start_age,
            )

            income_needed = max(0, target_spending - state_pension_income)

            # Draw from pension first (taxable)
            if pension_bal > 0 and income_needed > 0:
                pension_draw = min(income_needed / (1 - 0.20), pension_bal)  # gross up for basic rate
                pension_income = pension_draw
                pension_bal -= pension_draw
                income_needed -= pension_draw * 0.80  # net after approx tax

            # Draw from ISA (tax-free)
            if isa_bal > 0 and income_needed > 0:
                isa_drawdown = min(income_needed, isa_bal)
                isa_bal -= isa_drawdown
                income_needed -= isa_drawdown

            # Draw from liquid savings as last resort
            if income_needed > 0:
                liquid_draw = min(income_needed, max(0, liquid))
                liquid -= liquid_draw

        # Grow investments
        pension_bal *= (1 + investment_return)
        isa_bal *= (1 + investment_return)

        # Expenses inflation
        if yr > 0:
            expenses_annual *= (1 + inflation)

        # Debt reduction (accumulation only)
        if not is_retired and total_debt > 0:
            debt_reduction = min(debt_payments * 0.70, total_debt)
            total_debt = max(0, total_debt - debt_reduction)

        # Mortgage paydown
        if mortgage_bal > 0:
            # Simplified: assume interest-only portion is ~60% of payment
            principal_portion = mortgage_payment_annual * 0.40
            mortgage_bal = max(0, mortgage_bal - principal_portion)

        # Net worth
        net_worth = liquid + pension_bal + isa_bal - total_debt - mortgage_bal

        # Total income for this year
        total_income = employment_income + pension_income + state_pension_income + isa_drawdown + pcls_lump

        entry: dict[str, Any] = {
            "year": yr,
            "age": current_age,
            "phase": phase,
            "income": {
                "employment": round(employment_income, 2),
                "pension_drawdown": round(pension_income, 2),
                "state_pension": round(state_pension_income, 2),
                "isa_drawdown": round(isa_drawdown, 2),
                "pcls_lump_sum": round(pcls_lump, 2),
                "total": round(total_income, 2),
            },
            "expenses": round(expenses_annual, 2),
            "balances": {
                "pension": round(pension_bal, 2),
                "isa": round(isa_bal, 2),
                "liquid": round(max(0, liquid), 2),
                "debt": round(total_debt, 2),
                "mortgage": round(mortgage_bal, 2),
                "net_worth": round(net_worth, 2),
            },
        }

        if current_age >= care_start_age:
            entry["care_costs"] = round(care_cost_home * ((1 + inflation) ** yr), 2)

        timeline.append(entry)

    # Summary
    peak_nw = max(t["balances"]["net_worth"] for t in timeline)
    final_nw = timeline[-1]["balances"]["net_worth"]
    retirement_entry = next((t for t in timeline if t["age"] == retirement_age), None)

    # Find year when funds run out
    depletion_age = None
    for t in timeline:
        if t["age"] >= retirement_age:
            bals = t["balances"]
            if bals["pension"] + bals["isa"] + bals["liquid"] < 1000:
                depletion_age = t["age"]
                break

    summary = {
        "projection_years": total_years,
        "current_age": age,
        "retirement_age": retirement_age,
        "life_expectancy": life_expectancy,
        "peak_net_worth": round(peak_nw, 2),
        "net_worth_at_retirement": round(
            retirement_entry["balances"]["net_worth"], 2
        ) if retirement_entry else None,
        "pension_at_retirement": round(
            retirement_entry["balances"]["pension"], 2
        ) if retirement_entry else None,
        "pcls_lump_sum": round(
            retirement_entry["income"]["pcls_lump_sum"], 2
        ) if retirement_entry else 0,
        "final_net_worth": round(final_nw, 2),
        "fund_depletion_age": depletion_age,
        "funds_last_to_death": depletion_age is None,
        "phases": phases,
    }

    logger.info(
        "Lifetime cashflow: %d years, peak NW £%.0f, final NW £%.0f, depletion %s",
        total_years, peak_nw, final_nw,
        f"age {depletion_age}" if depletion_age else "none",
    )

    return {
        "timeline": timeline,
        "summary": summary,
    }


def _retirement_spending(
    pre_retirement_expenses: float,
    retire_pct: float,
    late_life_reduction: float,
    current_age: int,
    inflation: float,
    year: int,
    care_cost_home: float,
    care_start_age: int,
) -> float:
    """Calculate retirement spending for a given year, adjusted for age and care."""
    base = pre_retirement_expenses * retire_pct * ((1 + inflation) ** year)

    # Late life spending reduction after 80
    if current_age >= 80:
        base *= (1 - late_life_reduction)

    # Care costs after care_start_age
    if current_age >= care_start_age:
        base += care_cost_home * ((1 + inflation) ** year)

    return base
