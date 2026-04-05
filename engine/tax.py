"""
tax.py — Shared Tax Calculation Utilities

Extracted from cashflow.py for reuse across modules (pension withdrawal
tax in investments.py, retirement income modelling, etc.).

T2-2: Capital gains tax and dividend tax calculations.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


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


def calculate_marriage_allowance(
    earner_gross: float, partner_gross: float, tax_cfg: dict,
) -> dict:
    """Check eligibility and calculate Marriage Allowance tax saving.

    One partner (the transferor) must earn below the personal allowance.
    The other (the recipient) must be a basic-rate taxpayer (below basic_threshold).
    The transferor gives £1,260 of their PA to the recipient, saving £252/year.
    """
    pa = tax_cfg.get("personal_allowance", 12570)
    basic_thresh = tax_cfg.get("basic_threshold", 50270)
    transfer_amount = tax_cfg.get("marriage_allowance_transfer", 1260)
    basic_rate = tax_cfg.get("basic_rate", 0.20)

    # Determine who is the low earner and who is the higher earner
    if earner_gross <= pa and pa < partner_gross <= basic_thresh:
        transferor_gross = earner_gross
        recipient_gross = partner_gross
    elif partner_gross <= pa and pa < earner_gross <= basic_thresh:
        transferor_gross = partner_gross
        recipient_gross = earner_gross
    else:
        return {"eligible": False, "reason": "Neither partner qualifies (one must earn below PA, other must be basic-rate)."}

    tax_saving = transfer_amount * basic_rate

    return {
        "eligible": True,
        "transferor_income": round(transferor_gross, 2),
        "recipient_income": round(recipient_gross, 2),
        "transfer_amount": transfer_amount,
        "annual_tax_saving": round(tax_saving, 2),
    }


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
        se_cfg = tax_cfg.get("self_employment", {})
        class4_main_rate = se_cfg.get("class4_main_rate", 0.09)
        class4_additional_rate = se_cfg.get("class4_additional_rate", 0.02)
        class2_weekly = se_cfg.get("class2_weekly_rate", 3.45)

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


# ---------------------------------------------------------------------------
# T2-2: Capital Gains Tax
# ---------------------------------------------------------------------------

def calculate_capital_gains_tax(
    gain: float, gross_income: float,
    cgt_cfg: dict, tax_cfg: dict,
    is_property: bool = False,
) -> dict:
    """
    Calculate capital gains tax on a disposal.
    Rates depend on whether gain is from property and taxpayer's income level.
    """
    exemption = cgt_cfg.get("annual_exemption", 3000)
    taxable_gain = max(0, gain - exemption)

    if taxable_gain <= 0:
        return {
            "gain": round(gain, 2),
            "annual_exemption": exemption,
            "taxable_gain": 0,
            "tax": 0,
            "effective_rate_pct": 0,
        }

    basic_thresh = tax_cfg.get("basic_threshold", 50270)
    tax_cfg.get("personal_allowance", 12570)

    if is_property:
        basic_rate = cgt_cfg.get("basic_rate_property", 0.18)
        higher_rate = cgt_cfg.get("higher_rate_property", 0.24)
    else:
        basic_rate = cgt_cfg.get("basic_rate", 0.10)
        higher_rate = cgt_cfg.get("higher_rate", 0.20)

    # How much basic rate band remains after income
    basic_band_remaining = max(0, basic_thresh - gross_income)

    basic_gain = min(taxable_gain, basic_band_remaining)
    higher_gain = max(0, taxable_gain - basic_gain)

    tax = basic_gain * basic_rate + higher_gain * higher_rate
    effective_rate = (tax / gain * 100) if gain > 0 else 0

    return {
        "gain": round(gain, 2),
        "annual_exemption": exemption,
        "taxable_gain": round(taxable_gain, 2),
        "basic_rate_portion": round(basic_gain, 2),
        "higher_rate_portion": round(higher_gain, 2),
        "tax": round(tax, 2),
        "effective_rate_pct": round(effective_rate, 1),
    }


# ---------------------------------------------------------------------------
# T2-2: Dividend Tax
# ---------------------------------------------------------------------------

def calculate_dividend_tax(
    dividends: float, gross_income: float,
    div_cfg: dict, tax_cfg: dict,
) -> dict:
    """
    Calculate tax on dividend income.
    Dividend allowance shelters the first portion; remainder taxed at
    rates that depend on the taxpayer's income band.
    """
    allowance = div_cfg.get("allowance", 500)
    taxable_dividends = max(0, dividends - allowance)

    if taxable_dividends <= 0:
        return {
            "dividends": round(dividends, 2),
            "allowance": allowance,
            "taxable_dividends": 0,
            "tax": 0,
            "effective_rate_pct": 0,
        }

    basic_thresh = tax_cfg.get("basic_threshold", 50270)
    higher_thresh = tax_cfg.get("higher_threshold", 125140)

    basic_rate = div_cfg.get("basic_rate", 0.0875)
    higher_rate = div_cfg.get("higher_rate", 0.3375)
    additional_rate = div_cfg.get("additional_rate", 0.3935)

    # Total income including dividends determines band
    gross_income + dividends

    tax = 0.0
    remaining = taxable_dividends

    if gross_income < basic_thresh:
        basic_space = basic_thresh - gross_income - allowance
        basic_portion = min(remaining, max(0, basic_space))
        tax += basic_portion * basic_rate
        remaining -= basic_portion

    if remaining > 0 and gross_income < higher_thresh:
        higher_space = higher_thresh - max(gross_income, basic_thresh)
        higher_portion = min(remaining, max(0, higher_space))
        tax += higher_portion * higher_rate
        remaining -= higher_portion

    if remaining > 0:
        tax += remaining * additional_rate

    effective_rate = (tax / dividends * 100) if dividends > 0 else 0

    return {
        "dividends": round(dividends, 2),
        "allowance": allowance,
        "taxable_dividends": round(taxable_dividends, 2),
        "tax": round(tax, 2),
        "effective_rate_pct": round(effective_rate, 1),
    }
