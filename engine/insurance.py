"""
insurance.py — Insurance Gap Assessment

Evaluates adequacy of insurance coverage across three pillars:
- Life insurance (income replacement for dependents)
- Income protection (cover if unable to work)
- Critical illness (lump sum for serious diagnosis)

T1-1: Cross-references pension adequacy to adjust coverage recommendations.
      Uses configurable multipliers from assumptions.yaml.
"""

from __future__ import annotations

import logging

from engine.types import (
    AssumptionsDict,
    CashflowResult,
    InsuranceResult,
    InvestmentsResult,
    MortgageResult,
    ProfileDict,
)

logger = logging.getLogger(__name__)


def assess_insurance(
    profile: ProfileDict, assumptions: AssumptionsDict, cashflow: CashflowResult,
    mortgage_analysis: MortgageResult, investment_analysis: InvestmentsResult | None = None,
) -> InsuranceResult:
    """
    Assess insurance coverage adequacy and identify gaps.
    T1-1: Accepts investment_analysis to cross-reference pension adequacy.
    """
    personal = profile.get("personal", {})
    inc = profile.get("income", {})
    insurance = profile.get("insurance", {})
    age = personal.get("age", 30)
    dependents = personal.get("dependents", 0)
    primary_gross = inc.get("primary_gross_annual", 0)
    if primary_gross <= 0:
        logger.warning("primary_gross_annual is zero or missing — insurance recommendations will be £0")
    partner_gross = inc.get("partner_gross_annual", 0)
    net_monthly = cashflow.get("net_income", {}).get("monthly", 0)
    total_debt = profile.get("_debt_summary", {}).get("total_balance", 0)
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 0)

    # Insurance config from assumptions
    ins_cfg = assumptions.get("insurance", {})
    life_mult_dep = ins_cfg.get("life_multiplier_with_dependents", 10)
    life_mult_mort = ins_cfg.get("life_multiplier_mortgage_only", 5)
    ip_pct = ins_cfg.get("income_protection_pct", 0.60)
    ci_months = ins_cfg.get("critical_illness_expense_months", 24)
    pension_uplift = ins_cfg.get("pension_inadequacy_life_uplift", 1.5)

    # Mortgage context
    has_mortgage_plans = mortgage_analysis.get("applicable", False)
    mortgage_amount = mortgage_analysis.get("repayment", {}).get("mortgage_amount", 0) if has_mortgage_plans else 0

    # T1-1: Pension adequacy cross-reference
    pension_adequate = True
    pension_replacement_pct = 0
    if investment_analysis:
        pension = investment_analysis.get("pension_analysis", {})
        pension_adequate = pension.get("adequate", True)
        pension_replacement_pct = pension.get("income_replacement_ratio_pct", 0)

    life = _assess_life_insurance(
        insurance, primary_gross, dependents, total_debt, mortgage_amount, age,
        life_mult_dep, life_mult_mort, pension_adequate, pension_uplift,
    )
    income_prot = _assess_income_protection(
        insurance, net_monthly, primary_gross, partner_gross, dependents,
        ip_pct, pension_adequate,
    )
    critical = _assess_critical_illness(
        insurance, primary_gross, total_debt, monthly_expenses, ci_months,
    )

    # T2-3: Cost estimates for insurance gaps
    cost_estimates_cfg = assumptions.get("insurance_cost_estimates", {})
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)

    _add_cost_estimate(life, age, cost_estimates_cfg, surplus_monthly, "life")
    _add_cost_estimate(income_prot, age, cost_estimates_cfg, surplus_monthly, "income_protection")
    _add_cost_estimate(critical, age, cost_estimates_cfg, surplus_monthly, "critical_illness")

    gaps = []
    for assessment in [life, income_prot, critical]:
        if assessment.get("gap_identified"):
            gap_entry = {
                "type": assessment["type"],
                "severity": assessment["severity"],
                "message": assessment["message"],
                "recommended_action": assessment["recommended_action"],
            }
            if assessment.get("estimated_cost"):
                gap_entry["estimated_cost"] = assessment["estimated_cost"]
            gaps.append(gap_entry)

    # T2-1: Survivor security analysis when partner exists
    partner = profile.get("partner", {})
    survivor_analysis = None
    if partner and partner.get("gross_salary", 0) > 0:
        survivor_analysis = _survivor_security(
            primary_gross, partner.get("gross_salary", 0),
            monthly_expenses, cashflow, mortgage_analysis, dependents,
        )

    overall = "adequate" if not gaps else ("needs_attention" if len(gaps) <= 1 else "significant_gaps")

    return {
        "life_insurance": life,
        "income_protection": income_prot,
        "critical_illness": critical,
        "gaps": gaps,
        "gap_count": len(gaps),
        "overall_assessment": overall,
        "pension_cross_reference": {
            "pension_adequate": pension_adequate,
            "pension_replacement_pct": round(pension_replacement_pct, 1),
            "coverage_adjusted": not pension_adequate,
        },
        "survivor_analysis": survivor_analysis,
    }


def _assess_life_insurance(
    insurance: dict, gross_annual: float, dependents: int,
    total_debt: float, mortgage_amount: float, age: int,
    mult_dependents: int, mult_mortgage: int,
    pension_adequate: bool, pension_uplift: float,
) -> dict:
    """
    Life insurance: protects dependents by replacing income.
    T1-1: If pension is inadequate, multiply cover by uplift factor.
    """
    has_cover = insurance.get("life_insurance", False)
    cover_amount = insurance.get("life_insurance_amount", 0)

    if dependents == 0 and mortgage_amount == 0:
        recommended = 0
        gap = False
        severity = "info"
        message = "No dependents and no mortgage — life insurance is not a priority."
        action = "Review if circumstances change (partner, children, property)."
    else:
        multiplier = mult_dependents if dependents > 0 else mult_mortgage
        income_cover = gross_annual * multiplier
        debt_cover = total_debt + mortgage_amount
        recommended = income_cover + debt_cover

        # T1-1: Uplift if pension inadequate
        if not pension_adequate and dependents > 0:
            recommended *= pension_uplift
            uplift_note = f" (uplifted ×{pension_uplift:.1f} due to inadequate pension)"
        else:
            uplift_note = ""

        if not has_cover:
            gap = True
            severity = "high" if dependents > 0 else "moderate"
            message = (
                f"No life insurance in place. With {dependents} dependent(s), "
                f"recommended cover is £{recommended:,.0f} ({multiplier}x income + debts{uplift_note})."
                if dependents > 0
                else f"No life insurance. With a mortgage of £{mortgage_amount:,.0f}, "
                     f"cover of at least £{debt_cover:,.0f} is recommended."
            )
            action = "Obtain life insurance quotes. Term life is typically most cost-effective."
        elif cover_amount < recommended * 0.7:
            gap = True
            severity = "moderate"
            message = (
                f"Life insurance cover (£{cover_amount:,.0f}) is below recommended level "
                f"(£{recommended:,.0f}{uplift_note})."
            )
            action = "Review and increase cover to match current income and debt levels."
        else:
            gap = False
            severity = "info"
            message = f"Life insurance cover (£{cover_amount:,.0f}) appears adequate."
            action = "Review annually or when circumstances change."

    return {
        "type": "life_insurance",
        "has_cover": has_cover,
        "cover_amount": cover_amount,
        "recommended_amount": round(recommended, 2),
        "gap_identified": gap,
        "severity": severity,
        "message": message,
        "recommended_action": action,
    }


def _assess_income_protection(
    insurance: dict, net_monthly: float, gross_annual: float,
    partner_gross: float, dependents: int,
    ip_pct: float, pension_adequate: bool,
) -> dict:
    """
    Income protection: replaces income if unable to work.
    T1-1: Escalate severity if pension is also inadequate.
    """
    has_cover = insurance.get("income_protection", False)
    cover_monthly = insurance.get("income_protection_monthly", 0)
    recommended_monthly = net_monthly * ip_pct
    sole_earner = partner_gross == 0

    # T1-1: If pension inadequate AND no income protection, this is critical
    severity_base = "high" if sole_earner else "moderate"
    if not pension_adequate and not has_cover:
        severity_base = "critical"

    if not has_cover:
        gap = True
        severity = severity_base
        pension_note = (
            " Your pension is also inadequate — without income protection, "
            "a period of illness could permanently damage your retirement prospects."
            if not pension_adequate else ""
        )
        message = (
            f"No income protection. As a sole earner, if you're unable to work, "
            f"you'd need £{recommended_monthly:,.0f}/month to maintain your lifestyle.{pension_note}"
            if sole_earner
            else f"No income protection. Recommended cover: £{recommended_monthly:,.0f}/month "
                 f"({ip_pct*100:.0f}% of take-home).{pension_note}"
        )
        action = (
            "Income protection is arguably the most important insurance for working-age adults. "
            "Obtain quotes for long-term income protection (not short-term accident-only policies)."
        )
    elif cover_monthly < recommended_monthly * 0.7:
        gap = True
        severity = "moderate"
        message = (
            f"Income protection cover (£{cover_monthly:,.0f}/mo) is below "
            f"recommended level (£{recommended_monthly:,.0f}/mo)."
        )
        action = f"Consider increasing cover to at least {ip_pct*100:.0f}% of take-home pay."
    else:
        gap = False
        severity = "info"
        message = f"Income protection cover (£{cover_monthly:,.0f}/mo) appears adequate."
        action = "Ensure policy covers your actual occupation and has a suitable deferred period."

    return {
        "type": "income_protection",
        "has_cover": has_cover,
        "cover_monthly": cover_monthly,
        "recommended_monthly": round(recommended_monthly, 2),
        "gap_identified": gap,
        "severity": severity,
        "message": message,
        "recommended_action": action,
    }


def _assess_critical_illness(
    insurance: dict, gross_annual: float, total_debt: float,
    monthly_expenses: float, expense_months: int,
) -> dict:
    """
    Critical illness: lump sum on diagnosis of specified conditions.
    """
    has_cover = insurance.get("critical_illness", False)
    cover_amount = insurance.get("critical_illness_amount", 0)
    recommended = total_debt + (monthly_expenses * expense_months)

    if not has_cover:
        gap = True
        severity = "moderate"
        message = (
            f"No critical illness cover. A serious diagnosis could leave you unable to work "
            f"while facing ongoing expenses. Recommended lump sum: £{recommended:,.0f} "
            f"(debts + {expense_months} months expenses)."
        )
        action = "Consider critical illness cover, especially if you have dependents or a mortgage."
    elif cover_amount < recommended * 0.5:
        gap = True
        severity = "moderate"
        message = (
            f"Critical illness cover (£{cover_amount:,.0f}) is well below "
            f"recommended level (£{recommended:,.0f})."
        )
        action = "Review and consider increasing cover."
    else:
        gap = False
        severity = "info"
        message = f"Critical illness cover (£{cover_amount:,.0f}) appears adequate."
        action = "Review policy terms to ensure key conditions are covered."

    return {
        "type": "critical_illness",
        "has_cover": has_cover,
        "cover_amount": cover_amount,
        "recommended_amount": round(recommended, 2),
        "gap_identified": gap,
        "severity": severity,
        "message": message,
        "recommended_action": action,
    }


# ---------------------------------------------------------------------------
# T2-3: Cost estimation for insurance gaps
# ---------------------------------------------------------------------------

def _add_cost_estimate(
    assessment: dict, age: int, cost_cfg: dict,
    surplus_monthly: float, insurance_type: str,
) -> None:
    """Add estimated monthly cost to an insurance gap assessment."""
    if not assessment.get("gap_identified"):
        return

    recommended = assessment.get("recommended_amount", 0) or assessment.get("recommended_monthly", 0)
    if recommended <= 0:
        return

    age_band = _get_age_band(age)
    if not age_band:
        return

    if insurance_type == "life":
        rates = cost_cfg.get("term_life_per_100k", {}).get(age_band)
        if rates and recommended > 0:
            units = recommended / 100000
            low = round(rates["monthly_low"] * units, 0)
            high = round(rates["monthly_high"] * units, 0)
            pct = round(((low + high) / 2) / surplus_monthly * 100, 1) if surplus_monthly > 0 else 0
            assessment["estimated_cost"] = {
                "monthly_low": low,
                "monthly_high": high,
                "cover_amount": round(recommended, 0),
                "pct_of_surplus": pct,
                "note": f"Term life cover of {recommended:,.0f}: approx {low:,.0f}-{high:,.0f}/month",
            }

    elif insurance_type == "income_protection":
        pct_of_benefit = cost_cfg.get("income_protection_pct_of_benefit", 0.04)
        annual_benefit = recommended * 12
        annual_cost = annual_benefit * pct_of_benefit
        monthly_cost = round(annual_cost / 12, 0)
        pct = round(monthly_cost / surplus_monthly * 100, 1) if surplus_monthly > 0 else 0
        assessment["estimated_cost"] = {
            "monthly_estimate": monthly_cost,
            "annual_benefit": round(annual_benefit, 0),
            "pct_of_surplus": pct,
            "note": f"Income protection of {recommended:,.0f}/month: approx {monthly_cost:,.0f}/month premium",
        }

    elif insurance_type == "critical_illness":
        rates = cost_cfg.get("critical_illness_per_100k", {}).get(age_band)
        if rates and recommended > 0:
            units = recommended / 100000
            low = round(rates["monthly_low"] * units, 0)
            high = round(rates["monthly_high"] * units, 0)
            pct = round(((low + high) / 2) / surplus_monthly * 100, 1) if surplus_monthly > 0 else 0
            assessment["estimated_cost"] = {
                "monthly_low": low,
                "monthly_high": high,
                "cover_amount": round(recommended, 0),
                "pct_of_surplus": pct,
                "note": f"Critical illness cover of {recommended:,.0f}: approx {low:,.0f}-{high:,.0f}/month",
            }


def _get_age_band(age: int) -> str | None:
    """Map age to cost estimate band."""
    if 25 <= age < 30:
        return "age_25_30"
    elif 30 <= age < 40:
        return "age_30_40"
    elif 40 <= age < 50:
        return "age_40_50"
    elif 50 <= age < 60:
        return "age_50_60"
    return None


# ---------------------------------------------------------------------------
# T2-1: Survivor security analysis
# ---------------------------------------------------------------------------

def _survivor_security(
    primary_gross: float, partner_gross: float,
    monthly_expenses: float, cashflow: dict,
    mortgage_analysis: dict, dependents: int,
) -> dict:
    """
    Model whether the surviving partner can maintain the household
    on a single income if the primary earner dies.
    """
    # Derive net-to-gross ratio from cashflow (replaces hardcoded 0.70)
    total_gross = cashflow.get("income", {}).get("total_gross_annual", 0)
    net_annual = cashflow.get("net_income", {}).get("annual", 0)
    net_to_gross = (net_annual / total_gross) if total_gross > 0 else 0.70
    primary_net_monthly = primary_gross * net_to_gross / 12
    partner_net_monthly = partner_gross * net_to_gross / 12

    mortgage_payment = 0
    if mortgage_analysis.get("applicable"):
        mortgage_payment = mortgage_analysis.get("repayment", {}).get("monthly_repayment", 0)

    # If primary dies, partner must cover all expenses
    survivor_income = partner_net_monthly
    survivor_shortfall = monthly_expenses + mortgage_payment - survivor_income

    # If partner dies, primary must cover all expenses
    primary_survivor_income = primary_net_monthly
    primary_survivor_shortfall = monthly_expenses + mortgage_payment - primary_survivor_income

    scenarios = []
    if survivor_shortfall > 0:
        scenarios.append({
            "scenario": "Primary earner dies",
            "survivor_income_monthly": round(survivor_income, 2),
            "total_outgoings_monthly": round(monthly_expenses + mortgage_payment, 2),
            "shortfall_monthly": round(survivor_shortfall, 2),
            "life_cover_needed": round(survivor_shortfall * 12 * 20, 0),  # 20 years cover
            "assessment": "critical" if dependents > 0 else "concerning",
        })

    if primary_survivor_shortfall > 0:
        scenarios.append({
            "scenario": "Partner dies",
            "survivor_income_monthly": round(primary_survivor_income, 2),
            "total_outgoings_monthly": round(monthly_expenses + mortgage_payment, 2),
            "shortfall_monthly": round(primary_survivor_shortfall, 2),
            "life_cover_needed": round(primary_survivor_shortfall * 12 * 20, 0),
            "assessment": "critical" if dependents > 0 else "concerning",
        })

    return {
        "applicable": True,
        "scenarios": scenarios,
        "both_adequately_covered": len(scenarios) == 0,
        "note": (
            "Both partners can independently cover household costs."
            if not scenarios
            else "One or both partners cannot cover household costs alone. "
                 "Life insurance should bridge the gap."
        ),
    }
