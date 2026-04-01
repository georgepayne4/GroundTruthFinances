"""
insurance.py — Insurance Gap Assessment

Evaluates adequacy of insurance coverage across three pillars:
- Life insurance (income replacement for dependents)
- Income protection (cover if unable to work)
- Critical illness (lump sum for serious diagnosis)

Flags gaps and quantifies recommended coverage levels.
"""

from __future__ import annotations

from typing import Any


def assess_insurance(
    profile: dict, assumptions: dict, cashflow: dict, mortgage_analysis: dict,
) -> dict[str, Any]:
    """
    Assess insurance coverage adequacy and identify gaps.
    """
    personal = profile.get("personal", {})
    inc = profile.get("income", {})
    insurance = profile.get("insurance", {})
    age = personal.get("age", 30)
    dependents = personal.get("dependents", 0)
    primary_gross = inc.get("primary_gross_annual", 0)
    partner_gross = inc.get("partner_gross_annual", 0)
    net_monthly = cashflow.get("net_income", {}).get("monthly", 0)
    total_debt = profile.get("_debt_summary", {}).get("total_balance", 0)
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 0)

    # Mortgage context
    has_mortgage_plans = mortgage_analysis.get("applicable", False)
    mortgage_amount = mortgage_analysis.get("repayment", {}).get("mortgage_amount", 0) if has_mortgage_plans else 0

    life = _assess_life_insurance(insurance, primary_gross, dependents, total_debt, mortgage_amount, age)
    income_prot = _assess_income_protection(insurance, net_monthly, primary_gross, partner_gross, dependents)
    critical = _assess_critical_illness(insurance, primary_gross, total_debt, monthly_expenses)

    gaps = []
    for assessment in [life, income_prot, critical]:
        if assessment.get("gap_identified"):
            gaps.append({
                "type": assessment["type"],
                "severity": assessment["severity"],
                "message": assessment["message"],
                "recommended_action": assessment["recommended_action"],
            })

    overall = "adequate" if not gaps else ("needs_attention" if len(gaps) <= 1 else "significant_gaps")

    return {
        "life_insurance": life,
        "income_protection": income_prot,
        "critical_illness": critical,
        "gaps": gaps,
        "gap_count": len(gaps),
        "overall_assessment": overall,
    }


def _assess_life_insurance(
    insurance: dict, gross_annual: float, dependents: int,
    total_debt: float, mortgage_amount: float, age: int,
) -> dict:
    """
    Life insurance: protects dependents by replacing income.
    Rule of thumb: 10-15x annual income if dependents, plus debt coverage.
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
        multiplier = 10 if dependents > 0 else 5
        income_cover = gross_annual * multiplier
        debt_cover = total_debt + mortgage_amount
        recommended = income_cover + debt_cover

        if not has_cover:
            gap = True
            severity = "high" if dependents > 0 else "moderate"
            message = (
                f"No life insurance in place. With {dependents} dependent(s), "
                f"recommended cover is £{recommended:,.0f} ({multiplier}x income + debts)."
                if dependents > 0
                else f"No life insurance. With a mortgage of £{mortgage_amount:,.0f}, "
                     f"cover of at least £{debt_cover:,.0f} is recommended."
            )
            action = "Obtain life insurance quotes. Term life is typically most cost-effective."
        elif cover_amount < recommended * 0.7:
            gap = True
            severity = "moderate"
            message = (
                f"Life insurance cover (£{cover_amount:,.0f}) is below recommended level (£{recommended:,.0f})."
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
) -> dict:
    """
    Income protection: replaces 50-70% of income if unable to work.
    Critical for sole earners and those without significant savings.
    """
    has_cover = insurance.get("income_protection", False)
    cover_monthly = insurance.get("income_protection_monthly", 0)
    recommended_monthly = net_monthly * 0.6  # 60% of take-home
    sole_earner = partner_gross == 0

    if not has_cover:
        severity = "high" if sole_earner else "moderate"
        gap = True
        message = (
            f"No income protection. As a sole earner, if you're unable to work, "
            f"you'd need £{recommended_monthly:,.0f}/month to maintain your lifestyle."
            if sole_earner
            else f"No income protection. Recommended cover: £{recommended_monthly:,.0f}/month (60% of take-home)."
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
        action = "Consider increasing cover to at least 60% of take-home pay."
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
    insurance: dict, gross_annual: float, total_debt: float, monthly_expenses: float,
) -> dict:
    """
    Critical illness: lump sum on diagnosis of specified conditions.
    Rule of thumb: cover debts + 2 years of living expenses.
    """
    has_cover = insurance.get("critical_illness", False)
    cover_amount = insurance.get("critical_illness_amount", 0)
    recommended = total_debt + (monthly_expenses * 24)

    if not has_cover:
        gap = True
        severity = "moderate"
        message = (
            f"No critical illness cover. A serious diagnosis could leave you unable to work "
            f"while facing ongoing expenses. Recommended lump sum: £{recommended:,.0f} "
            f"(debts + 2 years expenses)."
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
