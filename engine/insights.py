"""
insights.py — Advisor-Style Insight Generation

Produces written insights in the tone of a professional financial advisor:
truthful, corrective where needed, supportive, and always paired with
actionable steps.  Highlights risks clearly and prioritises the most
impactful recommendations.
"""

from __future__ import annotations

from typing import Any


def generate_insights(
    profile: dict,
    assumptions: dict,
    cashflow: dict,
    debt_analysis: dict,
    goal_analysis: dict,
    investment_analysis: dict,
    mortgage_analysis: dict,
    scoring: dict,
    life_events: dict,
) -> dict[str, Any]:
    """
    Generate a structured set of advisor insights covering:
    - Executive summary
    - Top priorities (ordered)
    - Category-specific commentary
    - Risk warnings
    - Positive reinforcements
    - Next steps
    """
    personal = profile.get("personal", {})
    name = personal.get("name", "Client")

    insights: dict[str, Any] = {
        "executive_summary": _executive_summary(name, scoring, cashflow, profile),
        "top_priorities": _top_priorities(cashflow, debt_analysis, goal_analysis, mortgage_analysis, scoring),
        "cashflow_insights": _cashflow_insights(cashflow),
        "debt_insights": _debt_insights(debt_analysis),
        "goal_insights": _goal_insights(goal_analysis),
        "investment_insights": _investment_insights(investment_analysis, personal),
        "mortgage_insights": _mortgage_insights(mortgage_analysis),
        "life_event_insights": _life_event_insights(life_events),
        "risk_warnings": _risk_warnings(profile, cashflow, debt_analysis, scoring),
        "positive_reinforcements": _positive_reinforcements(cashflow, debt_analysis, scoring, profile),
        "recommended_next_steps": _next_steps(scoring, debt_analysis, goal_analysis, mortgage_analysis),
    }

    return insights


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

def _executive_summary(name: str, scoring: dict, cashflow: dict, profile: dict) -> str:
    score = scoring.get("overall_score", 0)
    grade = scoring.get("grade", "N/A")
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    nw = profile.get("_net_worth", 0)
    savings_rate = cashflow.get("savings_rate", {}).get("basic_pct", 0)

    lines = [
        f"{name}, your overall financial health score is {score:.0f}/100 (Grade: {grade}).",
    ]

    if surplus > 0:
        lines.append(
            f"You have a monthly surplus of {surplus:,.0f}, which gives you the capacity to "
            f"make meaningful progress on your goals."
        )
    else:
        lines.append(
            f"You are currently running a monthly deficit of {abs(surplus):,.0f}. "
            f"This must be addressed before any goal planning can be effective."
        )

    if nw >= 0:
        lines.append(f"Your net worth stands at {nw:,.0f}.")
    else:
        lines.append(
            f"Your net worth is currently negative ({nw:,.0f}), meaning liabilities exceed assets. "
            f"The priority should be shifting this trajectory."
        )

    if savings_rate >= 20:
        lines.append("Your savings rate is strong — well above the recommended minimum.")
    elif savings_rate >= 10:
        lines.append("Your savings rate is reasonable but has room for improvement toward the 20% benchmark.")
    elif savings_rate > 0:
        lines.append(f"A savings rate of {savings_rate:.1f}% is below where it should be. Review discretionary spending.")
    else:
        lines.append("You are not currently saving. This is the most critical issue to resolve.")

    return " ".join(lines)


# ---------------------------------------------------------------------------
# Top priorities
# ---------------------------------------------------------------------------

def _top_priorities(cashflow, debt_analysis, goal_analysis, mortgage_analysis, scoring) -> list[dict]:
    """Generate an ordered list of the most important actions."""
    priorities = []

    # Check for deficit
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    if surplus < 0:
        priorities.append({
            "priority": 1,
            "category": "cashflow",
            "title": "Eliminate monthly deficit",
            "detail": (
                f"You are spending {abs(surplus):,.0f}/month more than you earn. "
                f"Review all discretionary expenses and consider increasing income. "
                f"No other financial goal can be sustainably pursued while running a deficit."
            ),
        })

    # High-interest debt
    high_debt = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
    high_balance = debt_analysis.get("summary", {}).get("high_interest_total_balance", 0)
    if high_debt > 0:
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "debt",
            "title": "Eliminate high-interest debt",
            "detail": (
                f"You have {high_debt} high-interest debt(s) totalling {high_balance:,.0f}. "
                f"The interest on these debts is actively working against your wealth. "
                f"Direct all available surplus toward the highest-rate debt first (avalanche method)."
            ),
        })

    # Emergency fund
    score_ef = scoring.get("categories", {}).get("emergency_fund", {}).get("score", 0)
    if score_ef < 50:
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "safety_net",
            "title": "Build emergency fund to 3 months of expenses",
            "detail": (
                "Your emergency fund is insufficient. Without adequate reserves, "
                "any unexpected expense — job loss, medical bill, car repair — could "
                "force you into high-interest debt. Build this before pursuing other goals."
            ),
        })

    # Goal shortfall
    shortfall = goal_analysis.get("summary", {}).get("shortfall_monthly", 0)
    unreachable = goal_analysis.get("summary", {}).get("unreachable", 0)
    if unreachable > 0:
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "goals",
            "title": "Re-evaluate unreachable goals",
            "detail": (
                f"{unreachable} of your goals are currently unreachable within their timeframes. "
                f"Either extend deadlines, reduce targets, or increase income/savings to close the gap."
            ),
        })

    # Mortgage blockers
    if mortgage_analysis.get("applicable") and mortgage_analysis.get("readiness") in ("needs_work", "not_ready"):
        blockers = mortgage_analysis.get("blockers", [])
        blocker_summary = "; ".join(b["message"] for b in blockers[:2])
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "mortgage",
            "title": "Address mortgage readiness blockers",
            "detail": f"Key issues: {blocker_summary}",
        })

    # Pension
    pension = scoring.get("categories", {}).get("investment_quality", {}).get("score", 0)
    if pension < 40:
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "retirement",
            "title": "Increase pension contributions",
            "detail": (
                "Your projected pension income is insufficient for a comfortable retirement. "
                "Even small increases in contributions now have a significant compounding effect. "
                "At minimum, ensure you are capturing any employer match."
            ),
        })

    # Re-number priorities
    for i, p in enumerate(priorities, 1):
        p["priority"] = i

    return priorities


# ---------------------------------------------------------------------------
# Category-specific insights
# ---------------------------------------------------------------------------

def _cashflow_insights(cashflow: dict) -> list[str]:
    insights = []
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    savings_rate = cashflow.get("savings_rate", {}).get("basic_pct", 0)
    effective_rate = cashflow.get("savings_rate", {}).get("effective_pct_incl_pension", 0)
    expenses = cashflow.get("expenses", {})
    breakdown = expenses.get("category_breakdown_monthly", {})

    if surplus > 0:
        insights.append(
            f"Your monthly surplus of {surplus:,.0f} is the engine for all goal progress. "
            f"Protect this by avoiding lifestyle inflation."
        )
    if effective_rate > savings_rate + 5:
        insights.append(
            f"Including pension, your effective savings rate is {effective_rate:.1f}% — "
            f"meaningfully higher than the {savings_rate:.1f}% visible in your bank account."
        )

    # Identify largest expense category
    if breakdown:
        largest = max(breakdown.items(), key=lambda x: x[1])
        insights.append(
            f"Your largest expense category is '{largest[0]}' at {largest[1]:,.0f}/month. "
            f"This is the first place to look for savings if you need to free up cash."
        )

    return insights


def _debt_insights(debt_analysis: dict) -> list[str]:
    insights = []
    debts = debt_analysis.get("debts", [])
    summary = debt_analysis.get("summary", {})

    if not debts:
        insights.append("You are debt-free — an excellent position that gives you maximum financial flexibility.")
        return insights

    total_interest = summary.get("total_interest_if_minimum_only", 0)
    if total_interest > 1000:
        insights.append(
            f"At minimum payments, your total interest cost across all debts will be {total_interest:,.0f}. "
            f"Every extra pound directed at the highest-rate debt reduces this figure."
        )

    scenarios = debt_analysis.get("extra_payment_scenarios", [])
    for s in scenarios:
        if s["interest_saved"] > 500:
            insights.append(
                f"Paying an extra {s['extra_monthly']}/month would save you {s['interest_saved']:,.0f} in "
                f"interest and make you debt-free {s['months_saved']} months sooner."
            )
            break

    # Specific advice by debt type
    for d in debts:
        if d["type"] == "credit_card" and d["balance"] > 0:
            insights.append(
                f"Credit card '{d['name']}' at {d['interest_rate_pct']:.1f}% APR should be your "
                f"top repayment priority. Consider a 0% balance transfer card to freeze interest while repaying."
            )
        if d["type"] in ("student_loan", "student_loan_postgrad"):
            insights.append(
                f"Student loan '{d['name']}' repayment is income-contingent and relatively low-rate. "
                f"Do not prioritise overpaying this above higher-interest debts."
            )

    return insights


def _goal_insights(goal_analysis: dict) -> list[str]:
    insights = []
    goals = goal_analysis.get("goals", [])
    summary = goal_analysis.get("summary", {})

    if not goals:
        insights.append(
            "You have not defined any financial goals. Setting clear, time-bound targets "
            "significantly improves financial outcomes."
        )
        return insights

    for g in goals:
        name = g["name"]
        feasibility = g.get("feasibility_with_allocation", "pending")
        required = g.get("required_monthly", 0)
        allocated = g.get("allocated_monthly", 0)
        progress = g.get("progress_pct", 0)

        if feasibility == "on_track":
            insights.append(
                f"'{name}' is on track — maintain your current trajectory. "
                f"{progress:.0f}% of the inflation-adjusted target is already covered."
            )
        elif feasibility == "at_risk":
            gap = required - allocated
            insights.append(
                f"'{name}' is at risk. You can allocate {allocated:,.0f}/month but need {required:,.0f}. "
                f"Consider extending the deadline or increasing savings by {gap:,.0f}/month."
            )
        elif feasibility == "unreachable":
            insights.append(
                f"'{name}' is not achievable within the current timeframe and surplus. "
                f"Options: extend the deadline, reduce the target, or free up additional income."
            )

    if summary.get("surplus_covers_goals"):
        insights.append("Your surplus is sufficient to fund all goals — the challenge is execution and discipline.")
    elif summary.get("shortfall_monthly", 0) > 0:
        insights.append(
            f"You have a goal funding shortfall of {summary['shortfall_monthly']:,.0f}/month. "
            f"Prioritise high-priority goals and defer or resize lower-priority ones."
        )

    return insights


def _investment_insights(investment_analysis: dict, personal: dict) -> list[str]:
    insights = []
    pension = investment_analysis.get("pension_analysis", {})
    replacement = pension.get("income_replacement_ratio_pct", 0)
    adequate = pension.get("adequate", False)
    age = personal.get("age", 30)

    if not adequate:
        if age < 35:
            insights.append(
                f"Your projected pension replacement ratio is {replacement:.0f}% — below the 50% target. "
                f"However, you have time on your side. Even a 2-3% increase in contributions now "
                f"will compound significantly over your working life."
            )
        elif age < 50:
            insights.append(
                f"Pension replacement at {replacement:.0f}% is concerning at age {age}. "
                f"Consider maximising contributions and reviewing your investment strategy "
                f"for a higher expected return if your risk tolerance allows."
            )
        else:
            insights.append(
                f"At age {age} with a {replacement:.0f}% replacement ratio, pension adequacy is a serious risk. "
                f"Explore catch-up contributions, delayed retirement, or supplementary income strategies."
            )
    else:
        insights.append(
            f"Your pension is on track for a {replacement:.0f}% income replacement ratio — well done."
        )

    risk = investment_analysis.get("risk_profile", "moderate")
    expected_return = investment_analysis.get("expected_annual_return_pct", 0)
    insights.append(
        f"Based on your '{risk}' risk profile, we assume a {expected_return:.1f}% annual return. "
        f"Ensure your actual portfolio allocation matches the suggested model portfolio."
    )

    isa_note = investment_analysis.get("isa_note", "")
    if isa_note:
        insights.append(isa_note)

    return insights


def _mortgage_insights(mortgage_analysis: dict) -> list[str]:
    insights = []

    if not mortgage_analysis.get("applicable", False):
        return ["No mortgage analysis applicable — no property purchase goal specified."]

    readiness = mortgage_analysis.get("readiness", "unknown")
    borrowing = mortgage_analysis.get("borrowing", {})
    deposit = mortgage_analysis.get("deposit", {})
    repayment = mortgage_analysis.get("repayment", {})
    blockers = mortgage_analysis.get("blockers", [])

    if readiness == "ready":
        insights.append(
            "You are mortgage-ready. All key criteria — borrowing capacity, deposit, "
            "and affordability — are met. Consider speaking to a mortgage broker to secure the best rate."
        )
    elif readiness == "near_ready":
        months = deposit.get("months_to_save_gap")
        if months:
            insights.append(
                f"You are close to mortgage-ready. The main gap is your deposit — "
                f"at your current savings rate, you need approximately {months} more months."
            )
    else:
        insights.append(
            f"Mortgage readiness: {readiness}. There are {len(blockers)} blocker(s) to resolve."
        )

    for b in blockers:
        insights.append(f"Blocker — {b['type']}: {b['message']} Action: {b['action']}")

    # Repayment comparison
    current_rent = repayment.get("replaces_rent", 0)
    mortgage_payment = repayment.get("monthly_repayment", 0)
    if current_rent > 0 and mortgage_payment > 0:
        delta = mortgage_payment - current_rent
        if delta > 0:
            insights.append(
                f"Mortgage payments ({mortgage_payment:,.0f}/mo) would be {delta:,.0f}/mo more than "
                f"your current rent ({current_rent:,.0f}/mo). Factor this into your budget planning."
            )
        else:
            insights.append(
                f"Mortgage payments ({mortgage_payment:,.0f}/mo) would actually be less than "
                f"your current rent ({current_rent:,.0f}/mo) — a positive cashflow shift."
            )

    return insights


def _life_event_insights(life_events: dict) -> list[str]:
    insights = []
    summary = life_events.get("summary", {})
    events = summary.get("cumulative_events", [])
    start_nw = summary.get("starting_net_worth", 0)
    end_nw = summary.get("ending_net_worth", 0)
    negative_year = summary.get("first_negative_year")

    if end_nw > start_nw:
        growth = end_nw - start_nw
        insights.append(
            f"Over the projection period, your net worth is expected to grow by {growth:,.0f} "
            f"(from {start_nw:,.0f} to {end_nw:,.0f}), assuming planned events proceed as modelled."
        )
    else:
        decline = start_nw - end_nw
        insights.append(
            f"Your net worth is projected to decline by {decline:,.0f} over the projection period. "
            f"This is driven by large planned expenses outpacing savings and investment growth."
        )

    if negative_year is not None:
        insights.append(
            f"Warning: Your net worth is projected to go negative in year {negative_year}. "
            f"Review the events planned for that period and consider building additional reserves beforehand."
        )

    # Comment on particularly impactful events
    goal_feasibility = life_events.get("goal_feasibility_at_deadline", [])
    for gf in goal_feasibility:
        if gf.get("likely_feasible") is False:
            insights.append(
                f"Goal '{gf['name']}' may not be feasible by year {gf['deadline_year']} — "
                f"projected liquid savings ({gf.get('projected_liquid_at_deadline', 0):,.0f}) "
                f"fall short of the {gf['target']:,.0f} target."
            )
        elif gf.get("likely_feasible") is True:
            insights.append(
                f"Goal '{gf['name']}' appears feasible by year {gf['deadline_year']} based on trajectory modelling."
            )

    return insights


# ---------------------------------------------------------------------------
# Risk warnings and positive reinforcements
# ---------------------------------------------------------------------------

def _risk_warnings(profile, cashflow, debt_analysis, scoring) -> list[dict]:
    warnings = []

    # Deficit
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    if surplus < 0:
        warnings.append({
            "severity": "critical",
            "area": "cashflow",
            "warning": "Monthly deficit — you are spending more than you earn.",
            "action": "Immediate expense review required. Consider a spending freeze on non-essentials.",
        })

    # High interest debt
    high = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
    if high > 0:
        warnings.append({
            "severity": "high",
            "area": "debt",
            "warning": f"{high} high-interest debt(s) are actively eroding your wealth.",
            "action": "Prioritise full repayment using the avalanche method. Consider balance transfers.",
        })

    # Inadequate emergency fund
    ef_score = scoring.get("categories", {}).get("emergency_fund", {}).get("score", 0)
    if ef_score < 30:
        warnings.append({
            "severity": "high",
            "area": "safety_net",
            "warning": "Emergency fund is critically low.",
            "action": "Build to at least 3 months of expenses before investing or pursuing goals.",
        })

    # Overall score
    overall = scoring.get("overall_score", 0)
    if overall < 40:
        warnings.append({
            "severity": "high",
            "area": "overall",
            "warning": "Overall financial health is in the danger zone.",
            "action": "Focus on fundamentals: cashflow, debt, emergency fund. All other goals are secondary.",
        })

    # Single income dependency
    inc = profile.get("income", {})
    if inc.get("partner_gross_annual", 0) == 0 and inc.get("side_income_monthly", 0) == 0:
        warnings.append({
            "severity": "moderate",
            "area": "income",
            "warning": "Entirely dependent on a single income source.",
            "action": "Consider building a secondary income stream or ensuring robust insurance coverage.",
        })

    return warnings


def _positive_reinforcements(cashflow, debt_analysis, scoring, profile) -> list[str]:
    positives = []

    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    if surplus > 0:
        positives.append(f"You have a positive monthly surplus of {surplus:,.0f} — this is the foundation for all financial progress.")

    savings_rate = cashflow.get("savings_rate", {}).get("basic_pct", 0)
    if savings_rate >= 15:
        positives.append(f"Your savings rate of {savings_rate:.1f}% exceeds the recommended 15% minimum — excellent discipline.")

    nw = profile.get("_net_worth", 0)
    if nw > 0:
        positives.append("Your net worth is positive — you have more assets than liabilities.")

    overall = scoring.get("overall_score", 0)
    if overall >= 60:
        positives.append("Your overall financial health is above average. Continue building on this foundation.")

    total_debt = debt_analysis.get("summary", {}).get("total_balance", 0)
    if total_debt == 0:
        positives.append("Being debt-free gives you maximum flexibility to pursue your goals.")

    return positives


# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------

def _next_steps(scoring, debt_analysis, goal_analysis, mortgage_analysis) -> list[str]:
    steps = []

    # Always recommend based on weakest category
    categories = scoring.get("categories", {})
    if categories:
        weakest = min(categories.items(), key=lambda x: x[1].get("score", 100))
        steps.append(
            f"Focus area: '{weakest[0]}' scored {weakest[1]['score']:.0f}/100 — "
            f"this is your biggest opportunity for improvement."
        )

    # Debt action
    high_debt = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
    if high_debt > 0:
        top_debt = debt_analysis.get("avalanche_order", [""])[0]
        steps.append(f"Direct all extra repayment capacity toward '{top_debt}' first.")

    # Goal action
    unreachable = goal_analysis.get("summary", {}).get("unreachable", 0)
    if unreachable > 0:
        steps.append(f"Review and adjust timelines for the {unreachable} unreachable goal(s).")

    # Mortgage action
    if mortgage_analysis.get("applicable") and mortgage_analysis.get("readiness") != "ready":
        steps.append("Review mortgage blockers and create a timeline for resolution.")

    steps.append("Review this report quarterly and update your profile as circumstances change.")

    return steps
