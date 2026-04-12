"""engine/estate.py — Estate & IHT modelling with gift strategies (v8.5).

Projects estate value, calculates IHT with gift exemptions, PET taper
relief, RNRB tapering, charitable rate reduction, and generates an
IHT projection timeline with optimisation suggestions.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.types import (
    AssumptionsDict,
    CashflowResult,
    EstateResult,
    InvestmentsResult,
    MortgageResult,
    ProfileDict,
)

logger = logging.getLogger(__name__)


def analyse_estate(
    profile: ProfileDict,
    assumptions: AssumptionsDict,
    investment_analysis: InvestmentsResult,
    mortgage_analysis: MortgageResult,
    cashflow: CashflowResult | None = None,
) -> EstateResult:
    """Project estate value and calculate IHT with gift optimisation."""
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
    iht_rate = iht_cfg.get("rate", 0.40)

    years_to_death = max(1, life_expectancy - age)

    # Project asset values at life expectancy
    investment_return = assumptions.get("investment_returns", {}).get(
        personal.get("risk_profile", "moderate"), 0.06
    )
    total_liquid = sav.get("_total_liquid", 0)
    total_investments = sav.get("pension_balance", 0) + sav.get("other_investments", 0)

    projected_investments = total_investments * ((1 + investment_return) ** years_to_death)
    projected_liquid = total_liquid * ((1 + inflation) ** years_to_death)

    # Property value projection
    target_property = mortgage_analysis.get("target_property_value", 0) if mortgage_analysis.get("applicable") else 0
    property_value_at_death = target_property * ((1 + housing_growth) ** years_to_death) if target_property > 0 else 0

    total_estate = projected_investments + projected_liquid + property_value_at_death

    estate_breakdown = {
        "investments": round(projected_investments, 2),
        "liquid_savings": round(projected_liquid, 2),
        "property": round(property_value_at_death, 2),
    }

    # RNRB with taper
    has_direct_descendants = dependents > 0
    available_rnrb = _calculate_available_rnrb(
        property_value_at_death, has_direct_descendants, total_estate, iht_cfg,
    )
    available_nil_rate = nil_rate_band + available_rnrb

    # Gift analysis
    estate_planning_input = profile.get("estate_planning", {})
    gift_analysis = _classify_gifts(
        estate_planning_input.get("gifts_made", []),
        iht_cfg, age, life_expectancy, cashflow,
        estate_planning_input.get("regular_gifts_from_income", {}),
    )

    # IHT calculation with gifts
    charitable_intent = estate_planning_input.get("charitable_giving_intent", False)
    iht_result = _calculate_iht_with_gifts(
        total_estate, available_nil_rate,
        gift_analysis.get("total_pets_outstanding", 0),
        iht_cfg, charitable_intent,
    )

    # Spousal exemption overrides
    if has_partner and iht_cfg.get("spousal_exemption", True):
        iht_liability = 0.0
        iht_note = ("Estate passes to spouse/civil partner tax-free under spousal exemption. "
                     "IHT would apply on the second death.")
    else:
        iht_liability = iht_result["iht_liability"]
        iht_note = None

    exceeds_threshold = total_estate > available_nil_rate

    # IHT timeline
    timeline = _build_iht_timeline(
        age, life_expectancy, estate_breakdown, gift_analysis,
        iht_cfg, nil_rate_band, available_rnrb,
        investment_return, inflation, housing_growth, has_partner,
    )

    # Optimisation suggestions
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0) if cashflow else 0
    suggestions = _generate_optimisation_suggestions(
        total_estate, iht_liability, gift_analysis, iht_cfg,
        surplus_monthly, estate_planning_input, years_to_death, iht_rate,
    )
    estimated_savings = sum(s.get("estimated_lifetime_saving", 0) for s in suggestions)

    # Estate planning flags
    has_will = personal.get("has_will", False)
    has_lpa = personal.get("has_lpa", False)

    advisory_costs = assumptions.get("advisory_cost_estimates", {})
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
            "action": "Set up Lasting Power of Attorney (LPA) for health and financial decisions.",
            "estimated_cost": f"{lpa_cost} per LPA (health + finance = {lpa_cost * 2})",
            "cost_low": lpa_cost * 2,
            "cost_high": lpa_cost * 2,
            "one_off": True,
        })

    logger.info(
        "Estate analysis: projected %s, IHT %s, %d optimisation suggestions, %d gifts classified",
        f"£{total_estate:,.0f}", f"£{iht_liability:,.0f}",
        len(suggestions), len(gift_analysis.get("gifts", [])),
    )

    return {
        "projected_estate_value": round(total_estate, 2),
        "projection_age": life_expectancy,
        "estate_breakdown": estate_breakdown,
        "iht_threshold": {
            "nil_rate_band": nil_rate_band,
            "residence_nil_rate": available_rnrb,
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
        "iht_timeline": timeline,
        "gift_analysis": gift_analysis,
        "optimisation_suggestions": suggestions,
        "estimated_tax_savings": round(estimated_savings, 2),
    }


def _calculate_available_rnrb(
    property_value: float,
    has_direct_descendants: bool,
    estate_value: float,
    iht_cfg: dict[str, Any],
) -> int:
    """Calculate RNRB with taper for large estates."""
    residence_nil_rate = iht_cfg.get("residence_nil_rate", 175000)

    if property_value <= 0 or not has_direct_descendants:
        return 0

    taper_threshold = iht_cfg.get("rnrb_taper_threshold", 2000000)
    taper_rate = iht_cfg.get("rnrb_taper_rate", 0.50)

    if estate_value <= taper_threshold:
        return residence_nil_rate

    excess = estate_value - taper_threshold
    reduction = int(excess * taper_rate)
    return max(0, residence_nil_rate - reduction)


def _calculate_taper_relief(
    years_since_gift: float,
    taper_bands: list[dict[str, Any]],
) -> float:
    """Look up taper relief percentage for a failed PET."""
    if not taper_bands:
        # Default HMRC bands
        if years_since_gift < 3:
            return 0.0
        elif years_since_gift < 4:
            return 0.20
        elif years_since_gift < 5:
            return 0.40
        elif years_since_gift < 6:
            return 0.60
        elif years_since_gift < 7:
            return 0.80
        return 1.0

    # Bands: min_years is the threshold. Match highest band where years >= min_years
    sorted_bands = sorted(taper_bands, key=lambda b: b["min_years"], reverse=True)
    for band in sorted_bands:
        if years_since_gift >= band["min_years"]:
            return band["relief_pct"]
    return 0.0


def _classify_gifts(
    gifts_made: list[dict[str, Any]],
    iht_cfg: dict[str, Any],
    age: int,
    life_expectancy: int,
    cashflow: dict[str, Any] | None,
    regular_gifts_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Categorise gifts and calculate exemptions and PET status."""
    annual_exemption = iht_cfg.get("annual_gift_exemption", 3000)
    small_gift_limit = iht_cfg.get("small_gift_limit", 250)
    pet_years = iht_cfg.get("pet_full_exemption_years", 7)
    taper_bands = iht_cfg.get("taper_relief", [])

    classified = []
    annual_exemption_used = 0
    total_exempt = 0.0
    total_pets_outstanding = 0.0

    for gift in gifts_made:
        amount = gift.get("amount", 0)
        years_ago = gift.get("years_ago", 0)
        gift_type = gift.get("type", "pet")
        description = gift.get("description", "Gift")

        entry = {
            "description": description,
            "amount": amount,
            "type": gift_type,
            "years_ago": years_ago,
        }

        if gift_type == "annual_exemption":
            exempt_amount = min(amount, annual_exemption - annual_exemption_used)
            annual_exemption_used += exempt_amount
            entry["status"] = "exempt"
            entry["exempt_amount"] = exempt_amount
            total_exempt += exempt_amount
            if amount > exempt_amount:
                # Excess becomes a PET
                excess = amount - exempt_amount
                entry["pet_excess"] = excess
                if years_ago >= pet_years:
                    entry["status"] = "exempt"
                    total_exempt += excess
                else:
                    total_pets_outstanding += excess
                    entry["taper_relief_pct"] = _calculate_taper_relief(years_ago, taper_bands)

        elif gift_type == "small_gift":
            if amount <= small_gift_limit:
                entry["status"] = "exempt"
                total_exempt += amount
            else:
                entry["status"] = "potentially_exempt"
                total_pets_outstanding += amount

        elif gift_type == "regular_income":
            entry["status"] = "exempt"
            total_exempt += amount

        else:  # PET
            if years_ago >= pet_years:
                entry["status"] = "exempt"
                total_exempt += amount
            else:
                entry["status"] = "potentially_exempt"
                entry["taper_relief_pct"] = _calculate_taper_relief(years_ago, taper_bands)
                total_pets_outstanding += amount

        classified.append(entry)

    # Regular gifts from income
    regular_amount = 0.0
    regular_exempt = False
    if regular_gifts_cfg:
        regular_amount = regular_gifts_cfg.get("annual_amount", 0)
        if regular_amount > 0 and cashflow:
            surplus_annual = cashflow.get("surplus", {}).get("monthly", 0) * 12
            regular_exempt = regular_amount <= surplus_annual
            total_exempt += regular_amount if regular_exempt else 0

    annual_exemption_remaining = max(0, annual_exemption - annual_exemption_used)

    return {
        "gifts": classified,
        "total_exempt": round(total_exempt, 2),
        "total_pets_outstanding": round(total_pets_outstanding, 2),
        "annual_exemption_remaining": annual_exemption_remaining,
        "regular_income_gifts": {
            "annual_amount": regular_amount,
            "exempt": regular_exempt,
        },
    }


def _calculate_iht_with_gifts(
    estate_value: float,
    available_nil_rate: int,
    pets_outstanding: float,
    iht_cfg: dict[str, Any],
    charitable_intent: bool,
) -> dict[str, Any]:
    """Calculate IHT with PETs consuming NRB and charitable rate."""
    iht_rate = iht_cfg.get("rate", 0.40)
    charitable_rate = iht_cfg.get("charitable_rate", 0.36)
    charitable_threshold_pct = iht_cfg.get("charitable_threshold_pct", 0.10)

    # PETs consume NRB first
    nrb_used_by_pets = min(pets_outstanding, available_nil_rate)
    nrb_for_estate = available_nil_rate - nrb_used_by_pets

    # Tax on PETs exceeding NRB (with taper relief handled separately)
    pet_excess = max(0, pets_outstanding - available_nil_rate)

    # Taxable estate
    taxable_estate = max(0, estate_value - nrb_for_estate)

    # Determine effective rate
    effective_rate = iht_rate
    if charitable_intent and taxable_estate > 0:
        baseline = taxable_estate
        charity_threshold = baseline * charitable_threshold_pct
        if charity_threshold > 0:
            effective_rate = charitable_rate

    iht_on_estate = taxable_estate * effective_rate
    iht_on_pets = pet_excess * iht_rate
    total_iht = iht_on_estate + iht_on_pets

    return {
        "iht_liability": round(total_iht, 2),
        "effective_rate": effective_rate,
        "nrb_used_by_pets": round(nrb_used_by_pets, 2),
        "nrb_for_estate": round(nrb_for_estate, 2),
        "taxable_estate": round(taxable_estate, 2),
        "iht_on_estate": round(iht_on_estate, 2),
        "iht_on_pets": round(iht_on_pets, 2),
    }


def _build_iht_timeline(
    age: int,
    life_expectancy: int,
    estate_breakdown: dict[str, float],
    gift_analysis: dict[str, Any],
    iht_cfg: dict[str, Any],
    nil_rate_band: int,
    available_rnrb: int,
    investment_return: float,
    inflation: float,
    housing_growth: float,
    has_partner: bool,
) -> list[dict[str, Any]]:
    """Build year-by-year IHT projection timeline."""
    years = max(1, life_expectancy - age)
    pet_years = iht_cfg.get("pet_full_exemption_years", 7)
    iht_rate = iht_cfg.get("rate", 0.40)

    investments = estate_breakdown.get("investments", 0)
    liquid = estate_breakdown.get("liquid_savings", 0)
    prop = estate_breakdown.get("property", 0)

    # These are already projected to death; we need to work backwards to current
    # and project forward year by year
    years_to_death = years
    if years_to_death > 0:
        investments_now = investments / ((1 + investment_return) ** years_to_death)
        liquid_now = liquid / ((1 + inflation) ** years_to_death)
        prop_now = prop / ((1 + housing_growth) ** years_to_death)
    else:
        investments_now = investments
        liquid_now = liquid
        prop_now = prop

    # Track PETs that expire over time
    pets = []
    for g in gift_analysis.get("gifts", []):
        if g.get("status") == "potentially_exempt":
            pets.append({
                "description": g.get("description", ""),
                "amount": g.get("amount", 0),
                "years_ago": g.get("years_ago", 0),
            })

    timeline = []
    for yr in range(years + 1):
        current_age = age + yr

        inv_val = investments_now * ((1 + investment_return) ** yr)
        liq_val = liquid_now * ((1 + inflation) ** yr)
        prop_val = prop_now * ((1 + housing_growth) ** yr)
        estate_val = inv_val + liq_val + prop_val

        # Calculate pets still outstanding
        pets_outstanding = 0.0
        gifts_becoming_exempt = []
        for p in pets:
            years_elapsed = p["years_ago"] + yr
            if years_elapsed >= pet_years:
                if yr > 0 and (p["years_ago"] + yr - 1) < pet_years:
                    gifts_becoming_exempt.append(p["description"])
            else:
                pets_outstanding += p["amount"]

        available_nrb = nil_rate_band + available_rnrb
        nrb_after_pets = max(0, available_nrb - pets_outstanding)
        taxable = max(0, estate_val - nrb_after_pets)
        iht = 0.0 if has_partner else taxable * iht_rate

        entry = {
            "age": current_age,
            "year": yr,
            "estate_value": round(estate_val, 2),
            "nil_rate_available": round(nrb_after_pets, 2),
            "pets_outstanding": round(pets_outstanding, 2),
            "iht_liability": round(iht, 2),
        }
        if gifts_becoming_exempt:
            entry["gifts_becoming_exempt"] = gifts_becoming_exempt

        timeline.append(entry)

    return timeline


def _generate_optimisation_suggestions(
    estate_value: float,
    iht_liability: float,
    gift_analysis: dict[str, Any],
    iht_cfg: dict[str, Any],
    surplus_monthly: float,
    estate_planning_input: dict[str, Any],
    years_to_death: int,
    iht_rate: float,
) -> list[dict[str, Any]]:
    """Generate ranked IHT optimisation suggestions."""
    suggestions = []
    annual_exemption = iht_cfg.get("annual_gift_exemption", 3000)
    nil_rate_band = iht_cfg.get("nil_rate_band", 325000)
    residence_nil_rate = iht_cfg.get("residence_nil_rate", 175000)
    available_nil_rate = nil_rate_band + residence_nil_rate

    if iht_liability <= 0:
        return suggestions

    excess = max(0, estate_value - available_nil_rate)

    # 1. Annual gift exemption
    remaining = gift_analysis.get("annual_exemption_remaining", annual_exemption)
    if remaining > 0:
        lifetime_gifts = remaining * min(years_to_death, 30)
        saving = lifetime_gifts * iht_rate
        suggestions.append({
            "strategy": "annual_gift_exemption",
            "description": (
                f"Use your {annual_exemption:,} annual gift exemption each year. "
                f"Over {min(years_to_death, 30)} years, this removes "
                f"{lifetime_gifts:,.0f} from your estate, saving up to "
                f"{saving:,.0f} in IHT."
            ),
            "estimated_annual_saving": round(remaining * iht_rate, 2),
            "estimated_lifetime_saving": round(saving, 2),
            "complexity": "low",
            "requires_professional_advice": False,
        })

    # 2. PET strategy (7-year rule)
    if excess > annual_exemption * 5:
        suggested_gift = min(excess * 0.5, 100000)
        pet_saving = suggested_gift * iht_rate
        suggestions.append({
            "strategy": "pet_7_year_rule",
            "description": (
                f"Consider a gift of {suggested_gift:,.0f} now. If you survive "
                f"7 years, it is fully exempt from IHT, saving "
                f"{pet_saving:,.0f}. Taper relief applies if death occurs "
                f"between 3-7 years."
            ),
            "estimated_annual_saving": 0,
            "estimated_lifetime_saving": round(pet_saving, 2),
            "complexity": "low",
            "requires_professional_advice": False,
        })

    # 3. Regular gifts from income
    regular = estate_planning_input.get("regular_gifts_from_income", {})
    if surplus_monthly > 0 and not regular.get("annual_amount", 0):
        annual_surplus = surplus_monthly * 12
        suggested_regular = min(annual_surplus * 0.3, 12000)
        if suggested_regular > 0:
            suggestions.append({
                "strategy": "regular_gifts_from_income",
                "description": (
                    f"Establish regular gifts from income ({suggested_regular:,.0f}/year). "
                    f"These are fully IHT exempt with no 7-year rule, provided they are "
                    f"from surplus income and don't affect your standard of living."
                ),
                "estimated_annual_saving": round(suggested_regular * iht_rate, 2),
                "estimated_lifetime_saving": round(
                    suggested_regular * min(years_to_death, 20) * iht_rate, 2,
                ),
                "complexity": "medium",
                "requires_professional_advice": False,
            })

    # 4. Charitable giving (36% rate)
    charitable_rate = iht_cfg.get("charitable_rate", 0.36)
    if not estate_planning_input.get("charitable_giving_intent", False) and excess > 0:
        rate_saving = excess * (iht_rate - charitable_rate)
        suggestions.append({
            "strategy": "charitable_giving",
            "description": (
                f"Leaving 10%+ of your net estate to charity reduces the IHT rate "
                f"from {iht_rate:.0%} to {charitable_rate:.0%}, saving {rate_saving:,.0f}."
            ),
            "estimated_annual_saving": 0,
            "estimated_lifetime_saving": round(rate_saving, 2),
            "complexity": "low",
            "requires_professional_advice": False,
        })

    # 5. Pension as IHT vehicle
    suggestions.append({
        "strategy": "pension_preservation",
        "description": (
            "Pensions typically pass outside the estate for IHT purposes. "
            "Draw from ISA/GIA before pension in retirement to keep wealth "
            "in the tax-sheltered wrapper."
        ),
        "estimated_annual_saving": 0,
        "estimated_lifetime_saving": 0,
        "complexity": "low",
        "requires_professional_advice": False,
    })

    # 6. Trust flagging
    if estate_value > available_nil_rate * 2 and not estate_planning_input.get("trusts_in_place", False):
        suggestions.append({
            "strategy": "trust_consideration",
            "description": (
                "With an estate significantly above the nil-rate band, consider "
                "professional advice on trust structures (bare trusts for "
                "grandchildren, discretionary trusts for asset protection)."
            ),
            "estimated_annual_saving": 0,
            "estimated_lifetime_saving": 0,
            "complexity": "high",
            "requires_professional_advice": True,
        })

    # 7. BPR/APR flagging
    if estate_planning_input.get("has_business_property", False):
        suggestions.append({
            "strategy": "business_property_relief",
            "description": (
                "Your business property may qualify for 50-100% Business Property "
                "Relief from IHT. Seek specialist valuation to confirm eligibility."
            ),
            "estimated_annual_saving": 0,
            "estimated_lifetime_saving": 0,
            "complexity": "high",
            "requires_professional_advice": True,
        })

    if estate_planning_input.get("has_agricultural_property", False):
        suggestions.append({
            "strategy": "agricultural_property_relief",
            "description": (
                "Your agricultural property may qualify for 50-100% Agricultural "
                "Property Relief from IHT. Seek specialist valuation."
            ),
            "estimated_annual_saving": 0,
            "estimated_lifetime_saving": 0,
            "complexity": "high",
            "requires_professional_advice": True,
        })

    # 8. Life insurance in trust
    if iht_liability > 50000:
        suggestions.append({
            "strategy": "life_insurance_in_trust",
            "description": (
                f"A whole-of-life policy written in trust could provide "
                f"{iht_liability:,.0f} to cover the IHT bill, keeping estate "
                f"assets intact for beneficiaries."
            ),
            "estimated_annual_saving": 0,
            "estimated_lifetime_saving": 0,
            "complexity": "medium",
            "requires_professional_advice": True,
        })

    return suggestions
