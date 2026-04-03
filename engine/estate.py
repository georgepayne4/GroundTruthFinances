"""
estate.py — Estate & Inheritance Tax Modelling (FA-7)

Projects estate value at life expectancy and calculates potential IHT
liability using nil-rate band, residence nil-rate band, and spousal
exemption rules.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def analyse_estate(
    profile: dict,
    assumptions: dict,
    investment_analysis: dict,
    mortgage_analysis: dict,
    cashflow: dict | None = None,
) -> dict[str, Any]:
    """
    Project estate value and calculate potential inheritance tax liability.
    """
    personal = profile.get("personal", {})
    sav = profile.get("savings", {})
    age = personal.get("age", 30)
    dependents = personal.get("dependents", 0)
    partner = profile.get("partner", {})
    has_partner = bool(partner) or profile.get("income", {}).get("partner_gross_annual", 0) > 0

    life_expectancy = assumptions.get("life_events", {}).get("life_expectancy", 85)
    iht_cfg = assumptions.get("inheritance_tax", {})
    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    housing_growth = assumptions.get("inflation", {}).get("housing", 0.04)

    nil_rate_band = iht_cfg.get("nil_rate_band", 325000)
    residence_nil_rate = iht_cfg.get("residence_nil_rate", 175000)
    iht_rate = iht_cfg.get("rate", 0.40)

    years_to_death = max(1, life_expectancy - age)

    # Project asset values at life expectancy
    pension = investment_analysis.get("pension_analysis", {})
    pension_at_retirement_nominal = pension.get("projected_at_retirement_nominal", 0)

    # Pension death benefits (pension pots pass outside estate if under 75 at death,
    # but included for conservative estimate)
    investment_return = assumptions.get("investment_returns", {}).get(
        personal.get("risk_profile", "moderate"), 0.06
    )
    total_liquid = sav.get("_total_liquid", 0)
    total_investments = sav.get("pension_balance", 0) + sav.get("other_investments", 0)

    projected_investments = total_investments * ((1 + investment_return) ** years_to_death)
    projected_liquid = total_liquid * ((1 + inflation) ** years_to_death)

    # Property value projection
    owns_property = profile.get("_owns_property", False)
    target_property = mortgage_analysis.get("target_property_value", 0) if mortgage_analysis.get("applicable") else 0
    property_value_at_death = target_property * ((1 + housing_growth) ** years_to_death) if target_property > 0 else 0

    total_estate = projected_investments + projected_liquid + property_value_at_death

    # Calculate thresholds
    has_property_for_rnrb = property_value_at_death > 0
    has_direct_descendants = dependents > 0

    available_nil_rate = nil_rate_band
    if has_property_for_rnrb and has_direct_descendants:
        available_nil_rate += residence_nil_rate

    # Spousal exemption
    if has_partner and iht_cfg.get("spousal_exemption", True):
        iht_liability = 0.0
        iht_note = ("Estate passes to spouse/civil partner tax-free under spousal exemption. "
                     "IHT would apply on the second death.")
    else:
        taxable_estate = max(0, total_estate - available_nil_rate)
        iht_liability = taxable_estate * iht_rate
        iht_note = None

    exceeds_threshold = total_estate > available_nil_rate

    # Estate planning flags
    has_will = personal.get("has_will", False)
    has_lpa = personal.get("has_lpa", False)

    # T2-3: Advisory cost estimates
    advisory_costs = assumptions.get("advisory_cost_estimates", {})
    surplus_monthly = 0
    if cashflow:
        surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)

    planning_actions = []
    if not has_will:
        will_cost = advisory_costs.get("will_simple", {})
        cost_low = will_cost.get("low", 150)
        cost_high = will_cost.get("high", 300)
        planning_actions.append({
            "action": "Write a will. Without one, intestacy rules apply and your assets may not "
                      "go where you intend.",
            "estimated_cost": f"{cost_low}-{cost_high}",
            "cost_low": cost_low,
            "cost_high": cost_high,
            "one_off": True,
        })
    if not has_lpa:
        lpa_cost = advisory_costs.get("lpa_per_type", 82)
        planning_actions.append({
            "action": "Set up Lasting Power of Attorney (LPA) for health and financial decisions. "
                      "This protects you if you lose mental capacity.",
            "estimated_cost": f"{lpa_cost} per LPA (health + finance = {lpa_cost * 2})",
            "cost_low": lpa_cost * 2,
            "cost_high": lpa_cost * 2,
            "one_off": True,
        })
    if exceeds_threshold and not has_partner:
        planning_actions.append({
            "action": "Consider inheritance tax planning: gifts (3k annual exemption, 7-year rule), "
                      "life insurance in trust to cover IHT liability, or charitable giving (40% -> 36% rate).",
            "estimated_cost": "Varies",
            "one_off": False,
        })

    return {
        "projected_estate_value": round(total_estate, 2),
        "projection_age": life_expectancy,
        "estate_breakdown": {
            "investments": round(projected_investments, 2),
            "liquid_savings": round(projected_liquid, 2),
            "property": round(property_value_at_death, 2),
        },
        "iht_threshold": {
            "nil_rate_band": nil_rate_band,
            "residence_nil_rate": residence_nil_rate if has_property_for_rnrb and has_direct_descendants else 0,
            "total_available": available_nil_rate,
        },
        "iht_liability": round(iht_liability, 2),
        "exceeds_threshold": exceeds_threshold,
        "iht_note": iht_note,
        "estate_planning": {
            "has_will": has_will,
            "has_lpa": has_lpa,
            "actions": planning_actions,
        },
    }
