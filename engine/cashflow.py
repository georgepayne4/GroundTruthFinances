"""
cashflow.py — Cashflow Analysis Module

Computes net income after tax and national insurance, calculates surplus
or deficit, derives savings rate, and breaks down where money flows.
Uses UK-style tax bands from assumptions but the logic is adaptable.
"""

from __future__ import annotations

from typing import Any


def analyse_cashflow(profile: dict, assumptions: dict) -> dict[str, Any]:
    """
    Produce a complete cashflow analysis including:
    - Gross-to-net income breakdown (tax, NI)
    - Expense breakdown by category
    - Debt servicing costs
    - Pension contributions (deducted pre-surplus)
    - Monthly and annual surplus/deficit
    - Savings rate as a percentage of net income
    """
    inc = profile.get("income", {})
    exp = profile.get("expenses", {})
    debts = profile.get("debts", [])
    sav = profile.get("savings", {})

    # ------------------------------------------------------------------
    # 1. Tax and NI calculation on primary + partner income
    # ------------------------------------------------------------------
    tax_cfg = assumptions.get("tax", {})
    primary_gross = inc.get("primary_gross_annual", 0)
    partner_gross = inc.get("partner_gross_annual", 0)

    primary_tax = _calculate_income_tax(primary_gross, tax_cfg)
    primary_ni = _calculate_national_insurance(primary_gross, tax_cfg)
    partner_tax = _calculate_income_tax(partner_gross, tax_cfg)
    partner_ni = _calculate_national_insurance(partner_gross, tax_cfg)

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
    # Side income and rental are taxed more simply — apply basic rate
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
    # 7. Savings rate (proportion of net income saved/invested)
    # ------------------------------------------------------------------
    # Savings rate = surplus / net income (excluding pension which is pre-deducted)
    savings_rate = (surplus_monthly / net_monthly * 100) if net_monthly > 0 else 0

    # Effective savings rate includes pension contributions
    total_saving_monthly = surplus_monthly + pension_personal_annual / 12 + pension_employer_annual / 12
    effective_savings_rate = (total_saving_monthly / (net_monthly + pension_personal_annual / 12) * 100) if net_monthly > 0 else 0

    # ------------------------------------------------------------------
    # 8. Assemble result
    # ------------------------------------------------------------------
    return {
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


# ---------------------------------------------------------------------------
# Tax helpers (UK-style progressive bands)
# ---------------------------------------------------------------------------

def _calculate_income_tax(gross_annual: float, tax_cfg: dict) -> float:
    """Calculate income tax using progressive bands."""
    if gross_annual <= 0:
        return 0.0

    pa = tax_cfg.get("personal_allowance", 12570)
    basic_thresh = tax_cfg.get("basic_threshold", 50270)
    higher_thresh = tax_cfg.get("higher_threshold", 125140)
    basic_rate = tax_cfg.get("basic_rate", 0.20)
    higher_rate = tax_cfg.get("higher_rate", 0.40)
    additional_rate = tax_cfg.get("additional_rate", 0.45)

    # Personal allowance taper: reduced by 1 for every 2 over 100k
    effective_pa = pa
    if gross_annual > 100000:
        reduction = (gross_annual - 100000) / 2
        effective_pa = max(0, pa - reduction)

    taxable = max(0, gross_annual - effective_pa)

    tax = 0.0

    # Basic rate band (up to basic_threshold - personal_allowance worth of taxable income)
    basic_band = max(0, basic_thresh - effective_pa)
    basic_taxable = min(taxable, basic_band)
    tax += basic_taxable * basic_rate

    # Higher rate band
    higher_band = max(0, higher_thresh - basic_thresh)
    higher_taxable = min(max(0, taxable - basic_band), higher_band)
    tax += higher_taxable * higher_rate

    # Additional rate (everything above higher_threshold)
    additional_taxable = max(0, taxable - basic_band - higher_band)
    tax += additional_taxable * additional_rate

    return round(tax, 2)


def _calculate_national_insurance(gross_annual: float, tax_cfg: dict) -> float:
    """Simplified NI calculation — flat rate above primary threshold."""
    if gross_annual <= 0:
        return 0.0

    # NI primary threshold is roughly aligned with personal allowance
    threshold = tax_cfg.get("personal_allowance", 12570)
    rate = tax_cfg.get("national_insurance_rate", 0.08)

    ni_eligible = max(0, gross_annual - threshold)
    return round(ni_eligible * rate, 2)
