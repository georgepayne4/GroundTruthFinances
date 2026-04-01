"""
tax.py — Shared Tax Calculation Utilities

Extracted from cashflow.py for reuse across modules (pension withdrawal
tax in investments.py, retirement income modelling, etc.).
"""

from __future__ import annotations


def calculate_income_tax(gross_annual: float, tax_cfg: dict) -> float:
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

    # Basic rate band
    basic_band = max(0, basic_thresh - effective_pa)
    basic_taxable = min(taxable, basic_band)
    tax += basic_taxable * basic_rate

    # Higher rate band
    higher_band = max(0, higher_thresh - basic_thresh)
    higher_taxable = min(max(0, taxable - basic_band), higher_band)
    tax += higher_taxable * higher_rate

    # Additional rate
    additional_taxable = max(0, taxable - basic_band - higher_band)
    tax += additional_taxable * additional_rate

    return round(tax, 2)


def calculate_national_insurance(
    gross_annual: float, tax_cfg: dict, self_employed: bool = False,
) -> float:
    """
    NI calculation.
    Employed: Class 1 — flat rate above primary threshold.
    Self-employed: Class 4 — 9% on profits £12,570–£50,270, 2% above;
                   Class 2 — £3.45/week if profits > £12,570.
    """
    if gross_annual <= 0:
        return 0.0

    threshold = tax_cfg.get("personal_allowance", 12570)

    if self_employed:
        upper_profits_limit = tax_cfg.get("basic_threshold", 50270)
        class4_main_rate = 0.09
        class4_additional_rate = 0.02
        class2_weekly = 3.45

        profits_above_threshold = max(0, gross_annual - threshold)
        main_band = min(profits_above_threshold, upper_profits_limit - threshold)
        additional_band = max(0, profits_above_threshold - main_band)

        class4 = main_band * class4_main_rate + additional_band * class4_additional_rate
        class2 = class2_weekly * 52 if gross_annual > threshold else 0
        return round(class4 + class2, 2)
    else:
        rate = tax_cfg.get("national_insurance_rate", 0.08)
        ni_eligible = max(0, gross_annual - threshold)
        return round(ni_eligible * rate, 2)


def calculate_tax_on_pension_withdrawal(
    annual_drawdown: float, state_pension_annual: float, tax_cfg: dict,
) -> dict:
    """
    Calculate tax on pension income in retirement.
    - 25% of pension drawdown is tax-free
    - Remaining 75% is taxable as income
    - State pension is fully taxable
    """
    tax_free_portion = annual_drawdown * 0.25
    taxable_drawdown = annual_drawdown * 0.75
    total_taxable = taxable_drawdown + state_pension_annual

    tax = calculate_income_tax(total_taxable, tax_cfg)
    net_income = annual_drawdown + state_pension_annual - tax

    effective_rate = (tax / (annual_drawdown + state_pension_annual) * 100
                      if (annual_drawdown + state_pension_annual) > 0 else 0)

    return {
        "gross_income": round(annual_drawdown + state_pension_annual, 2),
        "tax_free_drawdown": round(tax_free_portion, 2),
        "taxable_income": round(total_taxable, 2),
        "income_tax": round(tax, 2),
        "net_income": round(net_income, 2),
        "effective_tax_rate_pct": round(effective_rate, 1),
    }
