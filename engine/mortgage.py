"""
mortgage.py — Mortgage Readiness Assessment

Estimates borrowing capacity using income multiples, assesses deposit
adequacy, runs affordability stress tests, and identifies blockers
preventing mortgage approval.
"""

from __future__ import annotations

import math
from typing import Any


def analyse_mortgage(profile: dict, assumptions: dict, cashflow: dict, debt_analysis: dict) -> dict[str, Any]:
    """
    Comprehensive mortgage readiness assessment:
    - Borrowing capacity from income multiples
    - Deposit analysis (current vs required)
    - Monthly repayment estimates at current and stress-test rates
    - Affordability check against net income
    - Blocker identification
    - Time to mortgage readiness
    """
    mort = profile.get("mortgage")
    if mort is None:
        return {"applicable": False, "reason": "No mortgage section in profile."}

    inc = profile.get("income", {})
    sav = profile.get("savings", {})
    personal = profile.get("personal", {})
    mort_cfg = assumptions.get("mortgage", {})

    target_value = mort.get("target_property_value", 0)
    preferred_dep_pct = mort.get("preferred_deposit_pct", mort_cfg.get("ideal_deposit_pct", 0.20))
    term_years = mort.get("preferred_term_years", mort_cfg.get("typical_term_years", 25))
    joint = mort.get("joint_application", False)

    primary_gross = inc.get("primary_gross_annual", 0)
    partner_gross = inc.get("partner_gross_annual", 0)
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)

    # ------------------------------------------------------------------
    # 1. Borrowing capacity
    # ------------------------------------------------------------------
    if joint and partner_gross > 0:
        combined_income = primary_gross + partner_gross
        income_multiple = mort_cfg.get("income_multiple_joint", 4.0)
    else:
        combined_income = primary_gross
        income_multiple = mort_cfg.get("income_multiple_single", 4.5)

    max_borrowing = combined_income * income_multiple

    # Reduce borrowing capacity for existing debt (conservative approach)
    total_debt_balance = debt_analysis.get("summary", {}).get("total_balance", 0)
    total_debt_payments = debt_analysis.get("summary", {}).get("total_minimum_monthly", 0)
    dti_adjustment = min(total_debt_payments * 12 * 3, max_borrowing * 0.20)  # cap deduction at 20%
    adjusted_borrowing = max(0, max_borrowing - dti_adjustment)

    # ------------------------------------------------------------------
    # 2. Deposit analysis
    # ------------------------------------------------------------------
    required_deposit = target_value * preferred_dep_pct
    min_deposit = target_value * mort_cfg.get("min_deposit_pct", 0.05)
    comfortable_deposit = target_value * mort_cfg.get("comfortable_deposit_pct", 0.10)
    ideal_deposit = target_value * mort_cfg.get("ideal_deposit_pct", 0.20)

    # Available deposit = liquid savings minus emergency fund buffer
    emergency_fund = sav.get("emergency_fund", 0)
    liquid = sav.get("_total_liquid", 0)
    available_for_deposit = max(0, liquid - emergency_fund)  # protect emergency fund

    deposit_gap = max(0, required_deposit - available_for_deposit)
    deposit_adequate = available_for_deposit >= required_deposit

    # Months to save deposit gap from surplus
    months_to_deposit = (
        math.ceil(deposit_gap / surplus_monthly) if surplus_monthly > 0 and deposit_gap > 0
        else (0 if deposit_gap <= 0 else float("inf"))
    )

    # ------------------------------------------------------------------
    # 3. LTV analysis and rate adjustment
    # ------------------------------------------------------------------
    mortgage_amount = target_value - required_deposit
    can_borrow_enough = adjusted_borrowing >= mortgage_amount

    current_ltv = mortgage_amount / target_value if target_value > 0 else 1.0
    ltv_pct = current_ltv * 100

    # Estimate rate based on LTV tier
    stress_rate = mort_cfg.get("stress_test_rate", 0.07)
    base_market_rate = stress_rate - 0.02
    ltv_tiers = assumptions.get("ltv_rate_tiers", [])
    ltv_adjustment = _get_ltv_rate_adjustment(current_ltv, ltv_tiers)
    estimated_market_rate = base_market_rate + ltv_adjustment

    # Find next better LTV band
    ltv_analysis = _analyse_ltv_bands(target_value, available_for_deposit, emergency_fund, ltv_tiers, base_market_rate, term_years)

    monthly_repayment_market = _monthly_repayment(mortgage_amount, estimated_market_rate, term_years)
    monthly_repayment_stress = _monthly_repayment(mortgage_amount, stress_rate, term_years)

    # Total cost of mortgage
    total_repayment = monthly_repayment_market * term_years * 12
    total_interest = total_repayment - mortgage_amount

    # ------------------------------------------------------------------
    # 4. Affordability assessment
    # ------------------------------------------------------------------
    net_monthly = cashflow.get("net_income", {}).get("monthly", 0)
    current_rent = profile.get("expenses", {}).get("housing", {}).get("rent_monthly", 0)

    # After mortgage: replace rent with mortgage payment
    net_change_monthly = monthly_repayment_market - current_rent
    post_mortgage_surplus = surplus_monthly - net_change_monthly

    affordability_ratio = (monthly_repayment_market / net_monthly * 100) if net_monthly > 0 else 100
    stress_affordability_ratio = (monthly_repayment_stress / net_monthly * 100) if net_monthly > 0 else 100

    affordable = affordability_ratio <= 35  # lender guideline
    stress_test_passes = stress_affordability_ratio <= 45

    # ------------------------------------------------------------------
    # 5. Acquisition costs (stamp duty + fees)
    # ------------------------------------------------------------------
    first_time_buyer = not profile.get("_owns_property", False)
    sdlt = _calculate_stamp_duty(target_value, first_time_buyer, assumptions)
    acquisition_costs = _estimate_acquisition_costs(target_value, mortgage_amount, sdlt, assumptions)

    # ------------------------------------------------------------------
    # 6. Blocker identification
    # ------------------------------------------------------------------
    blockers = []
    if not can_borrow_enough:
        blockers.append({
            "type": "borrowing_capacity",
            "message": f"Maximum borrowing ({adjusted_borrowing:,.0f}) is below required mortgage ({mortgage_amount:,.0f}).",
            "action": "Increase income, reduce debt, consider joint application, or target a lower-value property.",
        })
    if not deposit_adequate:
        blockers.append({
            "type": "deposit_shortfall",
            "message": f"Deposit gap of {deposit_gap:,.0f} (have {available_for_deposit:,.0f}, need {required_deposit:,.0f}).",
            "action": f"Save {deposit_gap:,.0f} more. At current surplus, this takes ~{months_to_deposit} months.",
        })
    if not affordable:
        blockers.append({
            "type": "affordability",
            "message": f"Mortgage payment ({monthly_repayment_market:,.0f}/mo) is {affordability_ratio:.0f}% of net income.",
            "action": "Reduce target property value, extend term, or increase deposit to lower the loan.",
        })
    if not stress_test_passes:
        blockers.append({
            "type": "stress_test",
            "message": f"Repayment at stress rate ({stress_rate*100:.1f}%) would be {monthly_repayment_stress:,.0f}/mo ({stress_affordability_ratio:.0f}% of net income).",
            "action": "Lenders may decline. Reduce loan amount or demonstrate additional income stability.",
        })

    high_interest_debts = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
    if high_interest_debts > 0:
        blockers.append({
            "type": "outstanding_high_interest_debt",
            "message": f"{high_interest_debts} high-interest debt(s) outstanding.",
            "action": "Clear high-interest debts before applying — lenders assess total debt burden.",
        })

    dti_pct = debt_analysis.get("summary", {}).get("debt_to_income_gross_pct", 0)
    max_dti = mort_cfg.get("max_dti_ratio", 0.45) * 100
    if dti_pct > max_dti:
        blockers.append({
            "type": "debt_to_income",
            "message": f"DTI ratio ({dti_pct:.1f}%) exceeds lender threshold ({max_dti:.0f}%).",
            "action": "Reduce monthly debt obligations before mortgage application.",
        })

    # ------------------------------------------------------------------
    # 7. Readiness classification
    # ------------------------------------------------------------------
    if not blockers:
        readiness = "ready"
    elif all(b["type"] in ("deposit_shortfall",) for b in blockers):
        readiness = "near_ready"
    elif len(blockers) <= 2:
        readiness = "needs_work"
    else:
        readiness = "not_ready"

    return {
        "applicable": True,
        "target_property_value": round(target_value, 2),
        "first_time_buyer": first_time_buyer,
        "borrowing": {
            "income_used": round(combined_income, 2),
            "income_multiple": income_multiple,
            "max_borrowing_gross": round(max_borrowing, 2),
            "debt_adjustment": round(dti_adjustment, 2),
            "max_borrowing_adjusted": round(adjusted_borrowing, 2),
            "required_mortgage": round(mortgage_amount, 2),
            "can_borrow_enough": can_borrow_enough,
        },
        "deposit": {
            "required_at_preferred_pct": round(required_deposit, 2),
            "minimum_5pct": round(min_deposit, 2),
            "comfortable_10pct": round(comfortable_deposit, 2),
            "ideal_20pct": round(ideal_deposit, 2),
            "available_for_deposit": round(available_for_deposit, 2),
            "gap": round(deposit_gap, 2),
            "adequate": deposit_adequate,
            "months_to_save_gap": months_to_deposit if months_to_deposit != float("inf") else None,
        },
        "repayment": {
            "mortgage_amount": round(mortgage_amount, 2),
            "term_years": term_years,
            "estimated_rate_pct": round(estimated_market_rate * 100, 2),
            "monthly_repayment": round(monthly_repayment_market, 2),
            "monthly_repayment_stress_test": round(monthly_repayment_stress, 2),
            "total_repayment": round(total_repayment, 2),
            "total_interest": round(total_interest, 2),
            "replaces_rent": round(current_rent, 2),
            "net_monthly_change": round(net_change_monthly, 2),
            "post_mortgage_surplus": round(post_mortgage_surplus, 2),
        },
        "affordability": {
            "repayment_to_income_pct": round(affordability_ratio, 1),
            "stress_test_to_income_pct": round(stress_affordability_ratio, 1),
            "affordable": affordable,
            "stress_test_passes": stress_test_passes,
        },
        "ltv_analysis": {
            "current_ltv_pct": round(ltv_pct, 1),
            "rate_adjustment_pct": round(ltv_adjustment * 100, 2),
            "bands": ltv_analysis,
        },
        "acquisition_costs": acquisition_costs,
        "blockers": blockers,
        "readiness": readiness,
    }


# ---------------------------------------------------------------------------
# LTV-based rate analysis
# ---------------------------------------------------------------------------

def _get_ltv_rate_adjustment(ltv: float, tiers: list[dict]) -> float:
    """Get rate adjustment for a given LTV ratio."""
    for tier in sorted(tiers, key=lambda t: t["max_ltv"]):
        if ltv <= tier["max_ltv"]:
            return tier["rate_adjustment"]
    # Above all tiers — return worst tier adjustment
    return tiers[-1]["rate_adjustment"] if tiers else 0.0


def _analyse_ltv_bands(
    property_value: float, available_deposit: float, emergency_fund: float,
    tiers: list[dict], base_rate: float, term_years: int,
) -> list[dict]:
    """
    Show what each LTV band would cost and how much extra deposit is needed.
    """
    bands = []
    for tier in sorted(tiers, key=lambda t: t["max_ltv"]):
        max_ltv = tier["max_ltv"]
        deposit_needed = property_value * (1 - max_ltv)
        mortgage_at_band = property_value * max_ltv
        rate = base_rate + tier["rate_adjustment"]
        monthly_payment = _monthly_repayment(mortgage_at_band, rate, term_years)
        total_interest = (monthly_payment * term_years * 12) - mortgage_at_band
        extra_deposit_needed = max(0, deposit_needed - available_deposit)

        bands.append({
            "ltv_pct": round(max_ltv * 100, 0),
            "deposit_required": round(deposit_needed, 2),
            "extra_deposit_needed": round(extra_deposit_needed, 2),
            "mortgage_amount": round(mortgage_at_band, 2),
            "rate_pct": round(rate * 100, 2),
            "monthly_payment": round(monthly_payment, 2),
            "total_interest": round(total_interest, 2),
            "achievable": available_deposit >= deposit_needed,
        })

    return bands


# ---------------------------------------------------------------------------
# Stamp Duty Land Tax (SDLT)
# ---------------------------------------------------------------------------

def _calculate_stamp_duty(property_value: float, first_time_buyer: bool, assumptions: dict) -> dict:
    """
    Calculate UK Stamp Duty Land Tax.

    First-time buyer rates (property up to £625k):
        £0 – £425,000:     0%
        £425,001 – £625,000: 5%
        Above £625,000: standard rates apply (FTB relief lost)

    Standard rates:
        £0 – £250,000:       0%
        £250,001 – £925,000:  5%
        £925,001 – £1,500,000: 10%
        Above £1,500,000:     12%
    """
    sdlt_cfg = assumptions.get("stamp_duty", {})

    if first_time_buyer and property_value <= 625000:
        bands = sdlt_cfg.get("first_time_buyer", [
            {"threshold": 425000, "rate": 0.00},
            {"threshold": 625000, "rate": 0.05},
        ])
        buyer_type = "first_time_buyer"
    else:
        bands = sdlt_cfg.get("standard", [
            {"threshold": 250000, "rate": 0.00},
            {"threshold": 925000, "rate": 0.05},
            {"threshold": 1500000, "rate": 0.10},
            {"threshold": float("inf"), "rate": 0.12},
        ])
        buyer_type = "standard"

    tax = 0.0
    breakdown = []
    prev_threshold = 0

    for band in bands:
        band_threshold = band["threshold"]
        rate = band["rate"]
        taxable_in_band = max(0, min(property_value, band_threshold) - prev_threshold)

        band_tax = taxable_in_band * rate
        tax += band_tax

        if taxable_in_band > 0:
            breakdown.append({
                "band": f"£{prev_threshold:,.0f} – £{band_threshold:,.0f}",
                "rate_pct": round(rate * 100, 1),
                "taxable_amount": round(taxable_in_band, 2),
                "tax": round(band_tax, 2),
            })

        prev_threshold = band_threshold
        if property_value <= band_threshold:
            break

    return {
        "buyer_type": buyer_type,
        "property_value": round(property_value, 2),
        "total_stamp_duty": round(tax, 2),
        "effective_rate_pct": round(tax / property_value * 100, 2) if property_value > 0 else 0,
        "breakdown": breakdown,
    }


def _estimate_acquisition_costs(
    property_value: float, mortgage_amount: float, sdlt: dict, assumptions: dict,
) -> dict:
    """
    Itemised estimate of total acquisition costs.
    """
    stamp_duty = sdlt["total_stamp_duty"]

    # Estimated professional fees
    solicitor = 1500
    survey = 500
    valuation = 350
    mortgage_arrangement_fee = 1000
    moving_costs = 1000

    total_fees = solicitor + survey + valuation + mortgage_arrangement_fee + moving_costs
    total_costs = stamp_duty + total_fees

    return {
        "stamp_duty": round(stamp_duty, 2),
        "stamp_duty_detail": sdlt,
        "solicitor_estimate": solicitor,
        "survey_estimate": survey,
        "valuation_fee": valuation,
        "mortgage_arrangement_fee": mortgage_arrangement_fee,
        "moving_costs": moving_costs,
        "total_fees_excl_stamp_duty": total_fees,
        "total_acquisition_costs": round(total_costs, 2),
    }


# ---------------------------------------------------------------------------
# Mortgage math
# ---------------------------------------------------------------------------

def _monthly_repayment(principal: float, annual_rate: float, term_years: int) -> float:
    """
    Standard amortising mortgage repayment formula.
    M = P * [r(1+r)^n] / [(1+r)^n - 1]
    """
    if principal <= 0 or term_years <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / (term_years * 12)

    r = annual_rate / 12
    n = term_years * 12
    compound = (1 + r) ** n
    payment = principal * (r * compound) / (compound - 1)
    return round(payment, 2)
