"""
mortgage.py — Mortgage Readiness Assessment

Comprehensive mortgage analysis including:
- MA-1: Product comparison (fixed vs tracker)
- MA-2: Overpayment modelling
- MA-3: Remortgage cliff-edge modelling
- MA-4: Equity growth (tracked in life_events.py)
- MA-5: Shared Ownership modelling
- MA-6: Employment type impact
- MA-7: Credit score awareness
- MA-8: Deposit source documentation
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def analyse_mortgage(profile: dict, assumptions: dict, cashflow: dict, debt_analysis: dict) -> dict[str, Any]:
    """
    Comprehensive mortgage readiness assessment.
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

    partner = profile.get("partner", {})
    primary_gross = inc.get("primary_gross_annual", 0)
    partner_gross = partner.get("gross_salary", inc.get("partner_gross_annual", 0))
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)
    employment_type = personal.get("employment_type", "employed")
    mort_costs = assumptions.get("mortgage_costs", {})

    # ------------------------------------------------------------------
    # 1. Borrowing capacity (MA-6: employment type impact)
    # ------------------------------------------------------------------
    if joint and partner_gross > 0:
        combined_income = primary_gross + partner_gross
        income_multiple = mort_cfg.get("income_multiple_joint", 4.0)
    else:
        combined_income = primary_gross
        if employment_type in ("self_employed", "contractor"):
            income_multiple = mort_cfg.get("income_multiple_self_employed", 4.0)
        else:
            income_multiple = mort_cfg.get("income_multiple_single", 4.5)

    max_borrowing = combined_income * income_multiple

    # Reduce borrowing capacity for existing debt
    # T1-1: Weight student loan payments by proximity to write-off
    total_debt_payments = _weighted_debt_payments(debt_analysis, assumptions)
    dti_cap = mort_costs.get("dti_adjustment_cap_pct", 0.20)
    dti_adjustment = min(total_debt_payments * 12 * 3, max_borrowing * dti_cap)
    adjusted_borrowing = max(0, max_borrowing - dti_adjustment)

    # ------------------------------------------------------------------
    # 2. Deposit analysis
    # ------------------------------------------------------------------
    required_deposit = target_value * preferred_dep_pct
    min_deposit = target_value * mort_cfg.get("min_deposit_pct", 0.05)
    comfortable_deposit = target_value * mort_cfg.get("comfortable_deposit_pct", 0.10)
    ideal_deposit = target_value * mort_cfg.get("ideal_deposit_pct", 0.20)

    emergency_fund = sav.get("emergency_fund", 0)
    liquid = sav.get("_total_liquid", 0)
    available_for_deposit = max(0, liquid - emergency_fund)

    deposit_gap = max(0, required_deposit - available_for_deposit)
    deposit_adequate = available_for_deposit >= required_deposit

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

    stress_rate = mort_cfg.get("stress_test_rate", 0.07)
    rate_offset = mort_costs.get("rate_offset_from_stress", 0.02)
    base_market_rate = stress_rate - rate_offset
    ltv_tiers = assumptions.get("ltv_rate_tiers", [])
    ltv_adjustment = _get_ltv_rate_adjustment(current_ltv, ltv_tiers)
    estimated_market_rate = base_market_rate + ltv_adjustment

    ltv_analysis = _analyse_ltv_bands(target_value, available_for_deposit, emergency_fund, ltv_tiers, base_market_rate, term_years)

    monthly_repayment_market = _monthly_repayment(mortgage_amount, estimated_market_rate, term_years)
    monthly_repayment_stress = _monthly_repayment(mortgage_amount, stress_rate, term_years)

    total_repayment = monthly_repayment_market * term_years * 12
    total_interest = total_repayment - mortgage_amount

    # ------------------------------------------------------------------
    # 4. Affordability assessment
    # ------------------------------------------------------------------
    net_monthly = cashflow.get("net_income", {}).get("monthly", 0)
    current_rent = profile.get("expenses", {}).get("housing", {}).get("rent_monthly", 0)

    net_change_monthly = monthly_repayment_market - current_rent
    post_mortgage_surplus = surplus_monthly - net_change_monthly

    affordability_ratio = (monthly_repayment_market / net_monthly * 100) if net_monthly > 0 else 100
    stress_affordability_ratio = (monthly_repayment_stress / net_monthly * 100) if net_monthly > 0 else 100

    affordable = affordability_ratio <= 35
    stress_test_passes = stress_affordability_ratio <= 45

    # ------------------------------------------------------------------
    # 5. Acquisition costs
    # ------------------------------------------------------------------
    first_time_buyer = not profile.get("_owns_property", False)
    sdlt = _calculate_stamp_duty(target_value, first_time_buyer, assumptions, mort_costs)
    acquisition_costs = _estimate_acquisition_costs(target_value, mortgage_amount, sdlt, mort_costs)

    # ------------------------------------------------------------------
    # 6. MA-1: Product comparison
    # ------------------------------------------------------------------
    products_cfg = assumptions.get("mortgage_products", {})
    product_comparison = _compare_products(
        mortgage_amount, term_years, products_cfg, net_monthly,
    )

    # ------------------------------------------------------------------
    # 7. MA-2: Overpayment modelling
    # ------------------------------------------------------------------
    overpayment_analysis = _overpayment_analysis(
        mortgage_amount, estimated_market_rate, term_years, mort_costs,
    )

    # ------------------------------------------------------------------
    # 8. MA-3: Remortgage cliff-edge
    # ------------------------------------------------------------------
    remortgage_analysis = _remortgage_cliff_edge(
        mortgage_amount, term_years, products_cfg, net_monthly, current_rent, surplus_monthly,
    )

    # ------------------------------------------------------------------
    # 9. MA-5: Shared Ownership
    # ------------------------------------------------------------------
    shared_ownership = None
    if not can_borrow_enough:
        so_cfg = assumptions.get("shared_ownership", {})
        shared_ownership = _shared_ownership_analysis(
            target_value, adjusted_borrowing, available_for_deposit,
            term_years, estimated_market_rate, so_cfg,
        )

    # ------------------------------------------------------------------
    # 10. MA-7: Credit score awareness
    # ------------------------------------------------------------------
    credit_warnings = _credit_score_warnings(profile)

    # ------------------------------------------------------------------
    # 11. MA-8: Deposit source documentation
    # ------------------------------------------------------------------
    deposit_source = _deposit_source_check(sav, mort)

    # ------------------------------------------------------------------
    # 12. MA-6: Employment type notes
    # ------------------------------------------------------------------
    employment_notes = None
    if employment_type in ("self_employed", "contractor"):
        employment_notes = {
            "type": employment_type,
            "income_multiple_used": income_multiple,
            "warnings": [
                "Most lenders require 2-3 years of accounts/tax returns for self-employed applicants.",
                "Net profit (not turnover) is used for affordability calculations.",
                "Some specialist lenders may offer better terms for contractors with day rates.",
            ],
        }

    # ------------------------------------------------------------------
    # 13. Blockers
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

    if employment_type in ("self_employed", "contractor"):
        blockers.append({
            "type": "self_employed_documentation",
            "message": "Self-employed/contractor status requires additional documentation.",
            "action": "Prepare 2-3 years of accounts, SA302 tax calculations, and tax year overviews.",
        })

    # ------------------------------------------------------------------
    # 14. Readiness
    # ------------------------------------------------------------------
    non_doc_blockers = [b for b in blockers if b["type"] != "self_employed_documentation"]
    if not non_doc_blockers:
        readiness = "ready"
    elif all(b["type"] in ("deposit_shortfall",) for b in non_doc_blockers):
        readiness = "near_ready"
    elif len(non_doc_blockers) <= 2:
        readiness = "needs_work"
    else:
        readiness = "not_ready"

    result = {
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
        "product_comparison": product_comparison,
        "overpayment_analysis": overpayment_analysis,
        "remortgage_analysis": remortgage_analysis,
        "credit_warnings": credit_warnings,
        "deposit_source": deposit_source,
        "blockers": blockers,
        "readiness": readiness,
    }

    if shared_ownership:
        result["shared_ownership"] = shared_ownership
    if employment_notes:
        result["employment_impact"] = employment_notes

    return result


# ---------------------------------------------------------------------------
# MA-1: Product comparison
# ---------------------------------------------------------------------------

def _compare_products(
    mortgage_amount: float, term_years: int,
    products_cfg: dict, net_monthly: float,
) -> list[dict]:
    """Compare mortgage product types."""
    comparisons = []
    svr_rate = products_cfg.get("svr", {}).get("rate", 0.075)

    for name, product in products_cfg.items():
        if name == "svr":
            continue
        rate = product.get("rate", 0.05)
        fee = product.get("fee", 0)
        product_term = product.get("term_years", 2)

        monthly = _monthly_repayment(mortgage_amount, rate, term_years)
        total_during_product = monthly * product_term * 12 + fee

        # Cost if switching to SVR after product ends
        svr_monthly = _monthly_repayment(mortgage_amount, svr_rate, term_years)
        remaining_years = term_years - product_term
        total_on_svr = svr_monthly * remaining_years * 12
        total_cost = total_during_product + total_on_svr

        affordability_pct = (monthly / net_monthly * 100) if net_monthly > 0 else 100

        comparisons.append({
            "product": name,
            "rate_pct": round(rate * 100, 2),
            "fee": fee,
            "product_term_years": product_term,
            "monthly_payment": round(monthly, 2),
            "affordability_pct": round(affordability_pct, 1),
            "total_cost_over_mortgage": round(total_cost, 2),
            "svr_monthly_after": round(svr_monthly, 2),
            "svr_payment_increase": round(svr_monthly - monthly, 2),
        })

    return sorted(comparisons, key=lambda x: x["total_cost_over_mortgage"])


# ---------------------------------------------------------------------------
# MA-2: Overpayment modelling
# ---------------------------------------------------------------------------

def _overpayment_analysis(
    principal: float, annual_rate: float, term_years: int,
    mort_costs: dict = None,
) -> list[dict]:
    """Model impact of monthly overpayments."""
    if mort_costs is None:
        mort_costs = {}
    base_monthly = _monthly_repayment(principal, annual_rate, term_years)
    base_total_interest = base_monthly * term_years * 12 - principal
    overpay_limit_pct = mort_costs.get("overpayment_annual_limit_pct", 0.10)
    annual_overpayment_limit = principal * overpay_limit_pct

    scenarios = []
    for extra in mort_costs.get("overpayment_scenarios", [100, 200, 500]):
        # Check against overpayment limit
        annual_extra = extra * 12
        exceeds_limit = annual_extra > annual_overpayment_limit

        # Simulate payoff
        months, total_interest = _simulate_overpayment(principal, annual_rate, base_monthly, extra)
        years_to_payoff = months / 12
        interest_saved = base_total_interest - total_interest
        months_saved = (term_years * 12) - months

        scenarios.append({
            "extra_monthly": extra,
            "new_payoff_years": round(years_to_payoff, 1),
            "months_saved": months_saved,
            "years_saved": round(months_saved / 12, 1),
            "total_interest_saved": round(interest_saved, 2),
            "exceeds_10pct_limit": exceeds_limit,
        })

    return scenarios


def _simulate_overpayment(
    principal: float, annual_rate: float,
    base_monthly: float, extra: float,
) -> tuple[int, float]:
    """Simulate month-by-month payoff with overpayment."""
    monthly_rate = annual_rate / 12
    remaining = principal
    total_interest = 0.0
    months = 0

    while remaining > 0 and months < 600:
        interest = remaining * monthly_rate
        total_interest += interest
        payment = min(base_monthly + extra, remaining + interest)
        principal_paid = payment - interest
        remaining = max(0, remaining - principal_paid)
        months += 1

    return months, total_interest


# ---------------------------------------------------------------------------
# MA-3: Remortgage cliff-edge
# ---------------------------------------------------------------------------

def _remortgage_cliff_edge(
    mortgage_amount: float, term_years: int,
    products_cfg: dict, net_monthly: float,
    current_rent: float, surplus_monthly: float,
) -> dict:
    """Model what happens when a fixed rate ends."""
    svr_rate = products_cfg.get("svr", {}).get("rate", 0.075)
    svr_monthly = _monthly_repayment(mortgage_amount, svr_rate, term_years)

    cliff_edges = []
    for name, product in products_cfg.items():
        if name == "svr":
            continue
        rate = product.get("rate", 0.05)
        product_term = product.get("term_years", 2)
        fixed_monthly = _monthly_repayment(mortgage_amount, rate, term_years)
        payment_shock = svr_monthly - fixed_monthly

        cliff_edges.append({
            "product": name,
            "fixed_rate_pct": round(rate * 100, 2),
            "fixed_monthly": round(fixed_monthly, 2),
            "svr_monthly": round(svr_monthly, 2),
            "payment_shock": round(payment_shock, 2),
            "ends_after_years": product_term,
            "remortgage_fee_estimate": products_cfg.get("_remortgage_fee", 1500),
        })

    return {
        "cliff_edges": cliff_edges,
        "advice": "Set a calendar reminder 3 months before your fix ends. Budget for remortgage fees every 2-5 years.",
    }


# ---------------------------------------------------------------------------
# MA-5: Shared Ownership
# ---------------------------------------------------------------------------

def _shared_ownership_analysis(
    property_value: float, max_borrowing: float, available_deposit: float,
    term_years: int, market_rate: float, so_cfg: dict,
) -> dict:
    """Analyse Shared Ownership as alternative when full purchase isn't affordable."""
    rent_pct = so_cfg.get("rent_on_unowned_pct", 0.0275)
    service_charge = so_cfg.get("service_charge_monthly", 150)
    min_share = so_cfg.get("min_share_pct", 0.25)

    # Find affordable share
    shares = []
    for share_pct in [0.25, 0.50, 0.75]:
        share_value = property_value * share_pct
        so_deposit_pct = so_cfg.get("deposit_pct", 0.10)
        share_deposit = share_value * so_deposit_pct
        share_mortgage = share_value - share_deposit
        unowned_value = property_value * (1 - share_pct)
        monthly_rent_on_unowned = unowned_value * rent_pct / 12

        mortgage_payment = _monthly_repayment(share_mortgage, market_rate, term_years)
        total_monthly = mortgage_payment + monthly_rent_on_unowned + service_charge

        affordable = share_mortgage <= max_borrowing and share_deposit <= available_deposit

        shares.append({
            "share_pct": round(share_pct * 100, 0),
            "share_value": round(share_value, 2),
            "deposit_needed": round(share_deposit, 2),
            "mortgage_on_share": round(share_mortgage, 2),
            "mortgage_payment_monthly": round(mortgage_payment, 2),
            "rent_on_unowned_monthly": round(monthly_rent_on_unowned, 2),
            "service_charge_monthly": service_charge,
            "total_monthly_cost": round(total_monthly, 2),
            "affordable": affordable,
        })

    return {
        "alternative": "Shared Ownership",
        "shares": shares,
        "note": "Shared Ownership lets you buy a share (25-75%) and rent the rest. You can 'staircase' to full ownership over time.",
    }


# ---------------------------------------------------------------------------
# MA-7: Credit score warnings
# ---------------------------------------------------------------------------

def _credit_score_warnings(profile: dict) -> list[dict]:
    """Flag credit score risk factors for mortgage applications."""
    warnings = []
    debts = profile.get("debts", [])

    for d in debts:
        if d.get("type") == "credit_card" and d.get("balance", 0) > 0:
            limit = d.get("credit_limit", 0)
            balance = d.get("balance", 0)
            if limit > 0:
                utilisation = balance / limit
                if utilisation > 0.30:
                    warnings.append({
                        "type": "high_utilisation",
                        "debt": d.get("name", "Credit card"),
                        "message": f"Credit utilisation at {utilisation*100:.0f}% (balance £{balance:,.0f} / limit £{limit:,.0f}). Keep below 30%.",
                    })
            else:
                warnings.append({
                    "type": "outstanding_balance",
                    "debt": d.get("name", "Credit card"),
                    "message": f"Outstanding balance of £{balance:,.0f}. Pay to zero before mortgage application.",
                })

    if not warnings:
        warnings.append({
            "type": "general",
            "message": "Pay credit card balances to zero before applying. Avoid new credit applications 6 months before.",
        })

    return warnings


# ---------------------------------------------------------------------------
# MA-8: Deposit source check
# ---------------------------------------------------------------------------

def _deposit_source_check(sav: dict, mort: dict) -> dict:
    """Check deposit source documentation requirements."""
    sources = mort.get("deposit_sources", {})
    gifted = sources.get("gifted", 0)
    inherited = sources.get("inherited", 0)

    notes = [
        "Ensure you have 3-6 months of bank statements showing savings buildup.",
        "Lenders will ask for source of deposit documentation.",
    ]
    if gifted > 0:
        notes.append(
            f"Gifted deposit of £{gifted:,.0f} requires a gifted deposit letter from the donor. "
            "Some lenders don't accept gifted deposits."
        )
    if inherited > 0:
        notes.append(
            f"Inherited funds of £{inherited:,.0f} — keep probate documentation as evidence."
        )

    return {
        "sources": sources if sources else {"saved": round(sav.get("_total_liquid", 0), 2)},
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# LTV-based rate analysis
# ---------------------------------------------------------------------------

def _get_ltv_rate_adjustment(ltv: float, tiers: list[dict]) -> float:
    """Get rate adjustment for a given LTV ratio."""
    for tier in sorted(tiers, key=lambda t: t["max_ltv"]):
        if ltv <= tier["max_ltv"]:
            return tier["rate_adjustment"]
    return tiers[-1]["rate_adjustment"] if tiers else 0.0


def _analyse_ltv_bands(
    property_value: float, available_deposit: float, emergency_fund: float,
    tiers: list[dict], base_rate: float, term_years: int,
) -> list[dict]:
    """Show what each LTV band would cost."""
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

def _calculate_stamp_duty(property_value: float, first_time_buyer: bool, assumptions: dict, mort_costs: dict = None) -> dict:
    """Calculate UK Stamp Duty Land Tax."""
    if mort_costs is None:
        mort_costs = {}
    sdlt_cfg = assumptions.get("stamp_duty", {})
    ftb_threshold = mort_costs.get("first_time_buyer_threshold", 625000)

    if first_time_buyer and property_value <= ftb_threshold:
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
    property_value: float, mortgage_amount: float, sdlt: dict, mort_costs: dict = None,
) -> dict:
    """Itemised estimate of total acquisition costs."""
    if mort_costs is None:
        mort_costs = {}
    stamp_duty = sdlt["total_stamp_duty"]

    solicitor = mort_costs.get("solicitor", 1500)
    survey = mort_costs.get("survey", 500)
    valuation = mort_costs.get("valuation", 350)
    mortgage_arrangement_fee = mort_costs.get("arrangement_fee", 1000)
    moving_costs = mort_costs.get("moving_costs", 1000)

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

def _weighted_debt_payments(debt_analysis: dict, assumptions: dict) -> float:
    """
    T1-1: Calculate DTI-weighted monthly debt payments.
    Student loans near write-off get reduced weight since they won't
    affect long-term affordability.
    """
    sl_dti_cfg = assumptions.get("student_loan_dti", {})
    thresh_50 = sl_dti_cfg.get("years_to_writeoff_50pct_weight", 10)
    thresh_25 = sl_dti_cfg.get("years_to_writeoff_25pct_weight", 5)

    total = 0.0
    for d in debt_analysis.get("debts", []):
        monthly = d.get("minimum_payment_monthly", 0)
        dtype = d.get("type", "")

        if dtype in ("student_loan", "student_loan_postgrad") and d.get("will_be_written_off"):
            years_to_wo = d.get("years_to_write_off")
            if years_to_wo is not None:
                if years_to_wo <= thresh_25:
                    weight = 0.25
                elif years_to_wo <= thresh_50:
                    weight = 0.50
                else:
                    weight = 1.0
            else:
                weight = 0.50  # default reduced weight for write-off loans
            total += monthly * weight
        else:
            total += monthly

    return total


def _monthly_repayment(principal: float, annual_rate: float, term_years: int) -> float:
    """Standard amortising mortgage repayment formula."""
    if principal <= 0 or term_years <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / (term_years * 12)

    r = annual_rate / 12
    n = term_years * 12
    compound = (1 + r) ** n
    payment = principal * (r * compound) / (compound - 1)
    return round(payment, 2)
