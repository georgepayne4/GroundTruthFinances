"""
cashflow.py — Cashflow Analysis Module

Computes net income after tax and national insurance, calculates surplus
or deficit, derives savings rate, and breaks down where money flows.
Supports employed, self-employed, and mixed employment types (FA-8).
Models bonus/variable income scenarios (FA-9).
Includes spending benchmark comparison (FA-10).
"""

from __future__ import annotations

from typing import Any

from engine.tax import calculate_income_tax, calculate_national_insurance


def analyse_cashflow(profile: dict, assumptions: dict) -> dict[str, Any]:
    """
    Produce a complete cashflow analysis including:
    - Gross-to-net income breakdown (tax, NI)
    - Expense breakdown by category
    - Debt servicing costs
    - Pension contributions (deducted pre-surplus)
    - Monthly and annual surplus/deficit
    - Savings rate as a percentage of net income
    - Bonus income scenarios (FA-9)
    - Spending benchmark analysis (FA-10)
    """
    inc = profile.get("income", {})
    exp = profile.get("expenses", {})
    debts = profile.get("debts", [])
    sav = profile.get("savings", {})
    personal = profile.get("personal", {})

    employment_type = personal.get("employment_type", "employed")
    is_self_employed = employment_type in ("self_employed", "contractor")

    # ------------------------------------------------------------------
    # 1. Tax and NI calculation on primary + partner income
    # ------------------------------------------------------------------
    tax_cfg = assumptions.get("tax", {})
    primary_gross = inc.get("primary_gross_annual", 0)
    partner_gross = inc.get("partner_gross_annual", 0)

    # For self-employed, deduct business expenses before tax
    business_expenses = inc.get("business_expenses_annual", 0)
    taxable_primary = max(0, primary_gross - business_expenses) if is_self_employed else primary_gross

    primary_tax = calculate_income_tax(taxable_primary, tax_cfg)
    primary_ni = calculate_national_insurance(taxable_primary, tax_cfg, self_employed=is_self_employed)
    partner_tax = calculate_income_tax(partner_gross, tax_cfg)
    partner_ni = calculate_national_insurance(partner_gross, tax_cfg)

    total_tax = primary_tax + partner_tax
    total_ni = primary_ni + partner_ni

    # ------------------------------------------------------------------
    # 2. Pension contributions (reduce take-home pay)
    # ------------------------------------------------------------------
    personal_pct = sav.get("pension_personal_contribution_pct", 0)
    employer_pct = sav.get("pension_employer_contribution_pct", 0)
    pension_personal_annual = primary_gross * personal_pct
    pension_employer_annual = primary_gross * employer_pct

    # ------------------------------------------------------------------
    # 3. Net (take-home) income
    # ------------------------------------------------------------------
    basic_rate = tax_cfg.get("basic_rate", 0.20)
    side_annual = inc.get("side_income_monthly", 0) * 12
    rental_annual = inc.get("rental_income_monthly", 0) * 12
    investment_annual = inc.get("investment_income_annual", 0)
    other_gross = side_annual + rental_annual + investment_annual
    other_tax = other_gross * basic_rate

    total_gross_annual = primary_gross + partner_gross + other_gross
    total_deductions = total_tax + total_ni + other_tax + pension_personal_annual
    net_annual = total_gross_annual - total_deductions
    net_monthly = net_annual / 12

    # ------------------------------------------------------------------
    # 4. Expense totals by category
    # ------------------------------------------------------------------
    category_breakdown = {}
    for cat_name, items in exp.items():
        if cat_name.startswith("_") or not isinstance(items, dict):
            continue
        category_breakdown[cat_name] = round(items.get("_category_monthly", 0), 2)

    total_expenses_monthly = exp.get("_total_monthly", 0)

    # ------------------------------------------------------------------
    # 5. Debt servicing
    # ------------------------------------------------------------------
    total_debt_payments_monthly = sum(d.get("minimum_payment_monthly", 0) for d in debts)

    # ------------------------------------------------------------------
    # 6. Surplus / deficit
    # ------------------------------------------------------------------
    total_outgoings_monthly = total_expenses_monthly + total_debt_payments_monthly
    surplus_monthly = net_monthly - total_outgoings_monthly
    surplus_annual = surplus_monthly * 12

    # ------------------------------------------------------------------
    # 7. Savings rate
    # ------------------------------------------------------------------
    savings_rate = (surplus_monthly / net_monthly * 100) if net_monthly > 0 else 0
    total_saving_monthly = surplus_monthly + pension_personal_annual / 12 + pension_employer_annual / 12
    effective_savings_rate = (total_saving_monthly / (net_monthly + pension_personal_annual / 12) * 100) if net_monthly > 0 else 0

    # ------------------------------------------------------------------
    # 8. Bonus income scenarios (FA-9)
    # ------------------------------------------------------------------
    bonus_low = inc.get("bonus_annual_low", 0)
    bonus_expected = inc.get("bonus_annual_expected", 0)
    bonus_high = inc.get("bonus_annual_high", 0)

    bonus_scenarios = None
    if bonus_expected > 0 or bonus_low > 0 or bonus_high > 0:
        bonus_scenarios = {}
        for label, bonus in [("low", bonus_low), ("expected", bonus_expected), ("high", bonus_high)]:
            if bonus > 0:
                bonus_tax = bonus * (tax_cfg.get("higher_rate", 0.40)
                                     if primary_gross > tax_cfg.get("basic_threshold", 50270)
                                     else tax_cfg.get("basic_rate", 0.20))
                bonus_net = bonus - bonus_tax
                bonus_scenarios[label] = {
                    "gross": round(bonus, 2),
                    "tax": round(bonus_tax, 2),
                    "net": round(bonus_net, 2),
                    "surplus_with_bonus_monthly": round(surplus_monthly + bonus_net / 12, 2),
                }

    # ------------------------------------------------------------------
    # 9. Spending benchmark analysis (FA-10)
    # ------------------------------------------------------------------
    benchmarks_cfg = assumptions.get("expense_benchmarks", {})
    spending_benchmarks = None
    if benchmarks_cfg and net_monthly > 0:
        spending_benchmarks = _spending_benchmark_analysis(
            category_breakdown, net_monthly, benchmarks_cfg,
        )

    # ------------------------------------------------------------------
    # 10. Self-employment notes (FA-8)
    # ------------------------------------------------------------------
    self_employment_info = None
    if is_self_employed:
        quarterly_tax = (primary_tax + primary_ni) / 4
        self_employment_info = {
            "employment_type": employment_type,
            "business_expenses_deducted": round(business_expenses, 2),
            "taxable_profit": round(taxable_primary, 2),
            "quarterly_tax_payment": round(quarterly_tax, 2),
            "annual_class2_ni": round(3.45 * 52, 2) if taxable_primary > tax_cfg.get("personal_allowance", 12570) else 0,
            "note": "Set aside quarterly tax payments. Keep 6 months of tax in a separate account.",
        }

    # ------------------------------------------------------------------
    # 11. Assemble result
    # ------------------------------------------------------------------
    result = {
        "income": {
            "primary_gross_annual": round(primary_gross, 2),
            "partner_gross_annual": round(partner_gross, 2),
            "other_income_annual": round(other_gross, 2),
            "total_gross_annual": round(total_gross_annual, 2),
            "total_gross_monthly": round(total_gross_annual / 12, 2),
        },
        "deductions": {
            "income_tax_annual": round(total_tax, 2),
            "national_insurance_annual": round(total_ni, 2),
            "other_income_tax_annual": round(other_tax, 2),
            "pension_personal_annual": round(pension_personal_annual, 2),
            "pension_employer_annual": round(pension_employer_annual, 2),
            "total_deductions_annual": round(total_deductions, 2),
        },
        "net_income": {
            "annual": round(net_annual, 2),
            "monthly": round(net_monthly, 2),
        },
        "expenses": {
            "category_breakdown_monthly": category_breakdown,
            "total_monthly": round(total_expenses_monthly, 2),
            "total_annual": round(total_expenses_monthly * 12, 2),
        },
        "debt_servicing": {
            "total_monthly": round(total_debt_payments_monthly, 2),
            "total_annual": round(total_debt_payments_monthly * 12, 2),
        },
        "surplus": {
            "monthly": round(surplus_monthly, 2),
            "annual": round(surplus_annual, 2),
        },
        "savings_rate": {
            "basic_pct": round(savings_rate, 1),
            "effective_pct_incl_pension": round(effective_savings_rate, 1),
        },
        "total_outgoings_monthly": round(total_outgoings_monthly, 2),
    }

    if bonus_scenarios:
        result["bonus_scenarios"] = bonus_scenarios
    if spending_benchmarks:
        result["spending_benchmarks"] = spending_benchmarks
    if self_employment_info:
        result["self_employment"] = self_employment_info

    return result


# ---------------------------------------------------------------------------
# Spending benchmark analysis (FA-10)
# ---------------------------------------------------------------------------

def _spending_benchmark_analysis(
    breakdown: dict, net_monthly: float, benchmarks: dict,
) -> dict:
    """Compare each expense category to UK average benchmarks."""
    comparisons = []
    total_potential_saving = 0.0

    category_map = {
        "housing": "housing_pct_of_net",
        "transport": "transport_pct_of_net",
        "living": "food_pct_of_net",
        "other": "discretionary_pct_of_net",
    }

    for cat_name, amount in breakdown.items():
        benchmark_key = category_map.get(cat_name)
        if not benchmark_key or benchmark_key not in benchmarks:
            continue

        benchmark_pct = benchmarks[benchmark_key]
        benchmark_amount = net_monthly * benchmark_pct
        actual_pct = amount / net_monthly if net_monthly > 0 else 0
        delta = amount - benchmark_amount
        saving_if_at_benchmark = max(0, delta)
        total_potential_saving += saving_if_at_benchmark

        comparisons.append({
            "category": cat_name,
            "actual_monthly": round(amount, 2),
            "actual_pct_of_net": round(actual_pct * 100, 1),
            "benchmark_pct_of_net": round(benchmark_pct * 100, 1),
            "benchmark_monthly": round(benchmark_amount, 2),
            "delta_monthly": round(delta, 2),
            "above_benchmark": delta > 0,
        })

    return {
        "comparisons": comparisons,
        "total_potential_monthly_saving": round(total_potential_saving, 2),
    }
