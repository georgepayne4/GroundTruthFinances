"""
insights.py — Advisor-Style Insight Generation

Produces written insights covering all 30 improvement areas including:
- FA-2:  "What would it take" goal guidance
- FA-3:  Childcare tax relief flagging
- FA-5:  Quarterly review triggers
- FA-6:  Employer pension match optimisation
- FA-9:  Bonus income guidance
- FA-10: Spending benchmark insights
- IA-3:  Emergency fund placement warning
- IA-6:  Rebalancing guidance
- IA-7:  Dividend reinvestment / pound-cost averaging
- IA-12: Tax-loss harvesting
- MA references to product comparison, overpayment, shared ownership
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
    """Generate a structured set of advisor insights."""
    personal = profile.get("personal", {})
    name = personal.get("name", "Client")
    conflicts = _detect_goal_event_conflicts(profile, cashflow, life_events)
    tax_opts = _tax_optimisation_insights(profile, assumptions, cashflow)

    # T1-3: Surplus deployment plan
    surplus_plan = _surplus_deployment_plan(
        profile, assumptions, cashflow, debt_analysis,
        investment_analysis, mortgage_analysis,
    )

    insights: dict[str, Any] = {
        "executive_summary": _executive_summary(name, scoring, cashflow, profile),
        "top_priorities": _top_priorities(cashflow, debt_analysis, goal_analysis, mortgage_analysis, scoring),
        "surplus_deployment_plan": surplus_plan,
        "cashflow_insights": _cashflow_insights(cashflow),
        "debt_insights": _debt_insights(debt_analysis),
        "goal_insights": _goal_insights(goal_analysis),
        "investment_insights": _investment_insights(investment_analysis, personal),
        "mortgage_insights": _mortgage_insights(mortgage_analysis),
        "life_event_insights": _life_event_insights(life_events),
        "goal_event_conflicts": conflicts,
        "tax_optimisation": tax_opts,
        "risk_warnings": _risk_warnings(profile, cashflow, debt_analysis, scoring),
        "positive_reinforcements": _positive_reinforcements(cashflow, debt_analysis, scoring, profile),
        "recommended_next_steps": _next_steps(scoring, debt_analysis, goal_analysis, mortgage_analysis),
        "review_schedule": _generate_review_triggers(profile, cashflow, debt_analysis, goal_analysis, scoring),
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
    priorities = []

    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    if surplus < 0:
        priorities.append({
            "priority": 1,
            "category": "cashflow",
            "title": "Eliminate monthly deficit",
            "detail": (
                f"You are spending {abs(surplus):,.0f}/month more than you earn. "
                f"Review all discretionary expenses and consider increasing income."
            ),
        })

    high_debt = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
    high_balance = debt_analysis.get("summary", {}).get("high_interest_total_balance", 0)
    if high_debt > 0:
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "debt",
            "title": "Eliminate high-interest debt",
            "detail": (
                f"You have {high_debt} high-interest debt(s) totalling {high_balance:,.0f}. "
                f"Direct all available surplus toward the highest-rate debt first (avalanche method)."
            ),
        })

    score_ef = scoring.get("categories", {}).get("emergency_fund", {}).get("score", 0)
    if score_ef < 50:
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "safety_net",
            "title": "Build emergency fund to 3 months of expenses",
            "detail": (
                "Your emergency fund is insufficient. Without adequate reserves, "
                "any unexpected expense could force you into high-interest debt."
            ),
        })

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

    if mortgage_analysis.get("applicable") and mortgage_analysis.get("readiness") in ("needs_work", "not_ready"):
        blockers = mortgage_analysis.get("blockers", [])
        blocker_summary = "; ".join(b["message"] for b in blockers[:2])
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "mortgage",
            "title": "Address mortgage readiness blockers",
            "detail": f"Key issues: {blocker_summary}",
        })

    pension = scoring.get("categories", {}).get("investment_quality", {}).get("score", 0)
    if pension < 40:
        priorities.append({
            "priority": len(priorities) + 1,
            "category": "retirement",
            "title": "Increase pension contributions",
            "detail": (
                "Your projected pension income is insufficient for a comfortable retirement. "
                "Even small increases in contributions now have a significant compounding effect."
            ),
        })

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

    if breakdown:
        largest = max(breakdown.items(), key=lambda x: x[1])
        insights.append(
            f"Your largest expense category is '{largest[0]}' at {largest[1]:,.0f}/month. "
            f"This is the first place to look for savings if you need to free up cash."
        )

    # FA-10: Spending benchmark insights
    benchmarks = cashflow.get("spending_benchmarks", {})
    if benchmarks:
        above = [c for c in benchmarks.get("comparisons", []) if c.get("above_benchmark")]
        total_saving = benchmarks.get("total_potential_monthly_saving", 0)
        if above:
            worst = max(above, key=lambda x: x["delta_monthly"])
            insights.append(
                f"Your '{worst['category']}' spending is {worst['actual_pct_of_net']:.0f}% of net income "
                f"vs {worst['benchmark_pct_of_net']:.0f}% average. Reducing to benchmark would save "
                f"£{worst['delta_monthly']:,.0f}/month."
            )
        if total_saving > 0:
            insights.append(
                f"If all above-benchmark categories were brought to average levels, "
                f"you could save an additional £{total_saving:,.0f}/month."
            )

    # FA-9: Bonus income guidance
    bonus = cashflow.get("bonus_scenarios", {})
    if bonus:
        expected = bonus.get("expected", {})
        if expected:
            insights.append(
                f"Your expected bonus adds £{expected.get('net', 0):,.0f}/year after tax. "
                f"Direct this to your highest-priority goal. Do not factor bonus into recurring commitments."
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

    for d in debts:
        if d["type"] == "credit_card" and d["balance"] > 0:
            insights.append(
                f"Credit card '{d['name']}' at {d['interest_rate_pct']:.1f}% APR should be your "
                f"top repayment priority. Consider a 0% balance transfer card to freeze interest while repaying."
            )
        if d["type"] in ("student_loan", "student_loan_postgrad"):
            # T1-5: Enhanced student loan insights with write-off intelligence
            woi = d.get("write_off_intelligence", {})
            written_off = d.get("will_be_written_off", False)
            monthly = d.get("minimum_payment_monthly", 0)
            threshold = d.get("repayment_threshold", 0)
            if written_off:
                total_repaid = woi.get("total_lifetime_repayment", 0)
                amount = d.get("amount_written_off", 0)
                write_off_age = d.get("write_off_age")
                break_even = woi.get("break_even_salary")
                insights.append(
                    f"'{d['name']}': At your salary trajectory, you'll repay £{total_repaid:,.0f} "
                    f"of £{d['balance']:,.0f} before write-off (age {write_off_age}). "
                    f"Do NOT overpay — every extra £1 is £1 less written off."
                )
                if break_even:
                    insights.append(
                        f"  Break-even salary: you'd need to earn over £{break_even:,.0f}/year "
                        f"consistently to clear this loan before write-off."
                    )
            else:
                insights.append(
                    f"'{d['name']}' will be repaid in full at £{monthly:,.0f}/month "
                    f"(income-contingent: deducted automatically above £{threshold:,.0f}/year)."
                )

    return insights


def _goal_insights(goal_analysis: dict) -> list[str]:
    insights = []
    goals = goal_analysis.get("goals", [])
    summary = goal_analysis.get("summary", {})

    # T1-1: Prerequisite warnings
    prereqs = goal_analysis.get("prerequisites", {})
    if prereqs and not prereqs.get("all_met", True):
        if not prereqs.get("emergency_fund_adequate"):
            insights.append(
                f"⚠ Emergency fund is only {prereqs['emergency_fund_months_current']:.1f} months "
                f"(target: {prereqs['emergency_fund_months_required']}). Discretionary goals are "
                f"blocked until this safety net is in place."
            )
        if not prereqs.get("high_interest_debt_cleared"):
            insights.append(
                f"⚠ {prereqs['high_interest_debt_count']} high-interest debt(s) totalling "
                f"£{prereqs['high_interest_debt_balance']:,.0f} must be cleared before surplus "
                f"flows to discretionary goals."
            )

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

        if feasibility == "blocked":
            blockers = g.get("blocked_by", [])
            insights.append(
                f"'{name}' is BLOCKED: {blockers[0] if blockers else 'prerequisites not met'}. "
                f"No surplus allocated until prerequisites are resolved."
            )
        elif feasibility == "on_track":
            insights.append(
                f"'{name}' is on track — maintain your current trajectory. "
                f"{progress:.0f}% of the inflation-adjusted target is already covered."
            )
        elif feasibility == "at_risk":
            gap = required - allocated
            # FA-2: Include "what would it take"
            wwit = g.get("what_would_it_take", {})
            if wwit:
                ext = wwit.get("option_extend_deadline_years")
                extra = wwit.get("shortfall_monthly", 0)
                insights.append(
                    f"'{name}' is at risk. Shortfall: £{extra:,.0f}/month. "
                    f"Options: earn £{extra:,.0f} more/month, cut expenses by the same, "
                    f"or extend deadline to {ext} years."
                    if ext else
                    f"'{name}' is at risk. You need an additional £{gap:,.0f}/month."
                )
            else:
                insights.append(
                    f"'{name}' is at risk. You can allocate {allocated:,.0f}/month but need {required:,.0f}."
                )
        elif feasibility == "unreachable":
            wwit = g.get("what_would_it_take", {})
            if wwit:
                ext = wwit.get("option_extend_deadline_years")
                extra = wwit.get("shortfall_monthly", 0)
                insights.append(
                    f"'{name}' is not achievable within the current timeframe. "
                    f"To make it work: earn £{extra:,.0f} more/month, cut expenses by £{extra:,.0f}/month, "
                    + (f"or extend deadline to ~{ext} years." if ext else "or reduce the target.")
                )
            else:
                insights.append(
                    f"'{name}' is not achievable. Extend the deadline, reduce the target, or increase income."
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

    # Pension adequacy (now using net income after FA-1 tax)
    retirement_tax = pension.get("retirement_tax", {})
    effective_rate = retirement_tax.get("effective_tax_rate_pct", 0)

    if not adequate:
        if age < 35:
            insights.append(
                f"Your projected net pension replacement ratio is {replacement:.0f}% (after {effective_rate:.0f}% effective tax). "
                f"You have time — even a 2-3% increase in contributions now compounds significantly."
            )
        else:
            insights.append(
                f"Pension replacement at {replacement:.0f}% (net of tax) is concerning at age {age}. "
                f"Consider maximising contributions."
            )
    else:
        insights.append(
            f"Your pension is on track for a {replacement:.0f}% net income replacement ratio."
        )

    # FA-6 + T1-2: Pension match optimisation with £-quantified ROI
    match = investment_analysis.get("pension_match_optimisation")
    if match:
        free_money = match["free_money_left_on_table"]
        net_cost = match["net_cost_monthly"]
        total_benefit = match.get("total_benefit_annual", 0)
        roi = match.get("roi_per_pound", 0)
        tax_relief = match.get("tax_relief_amount_annual", 0)
        insights.append(
            f"You're leaving £{free_money:,.0f}/year of employer contributions on the table. "
            f"Increasing to {match['match_cap_pct']:.0f}% costs £{net_cost:,.0f}/month after "
            f"tax relief (saving £{tax_relief:,.0f}/year) and gains £{free_money/12:,.0f}/month "
            f"in employer match. Total benefit: £{total_benefit:,.0f}/year. "
            f"ROI: every £1 of net cost returns £{roi:.2f}."
        )
        # Salary sacrifice option
        ss = match.get("salary_sacrifice_option", {})
        if ss:
            ss_cost = ss.get("net_cost_monthly", 0)
            ss_roi = ss.get("roi_per_pound", 0)
            ni_saving = ss.get("ni_saving_annual", 0)
            insights.append(
                f"  Via salary sacrifice: net cost drops to £{ss_cost:,.0f}/month "
                f"(additional £{ni_saving:,.0f}/year NI saving). ROI: £{ss_roi:.2f} per £1."
            )

    # IA-3: Emergency fund warning
    ef_warning = investment_analysis.get("emergency_fund_warning")
    if ef_warning:
        insights.append(ef_warning["risk"] + " " + ef_warning["action"])

    # Risk metrics
    risk_metrics = investment_analysis.get("risk_metrics", {})
    if risk_metrics:
        insights.append(risk_metrics.get("note", ""))

    # Fee impact
    fees = investment_analysis.get("fee_analysis", {})
    fee_drag = fees.get("fee_drag_over_term", 0)
    if fee_drag > 10000:
        cost_vs_low = fees.get("fee_comparison", {}).get("cost_vs_low_cost", 0)
        insights.append(
            f"Investment fees will cost you £{fee_drag:,.0f} over your working life. "
            + (f"Switching to a low-cost platform could save £{cost_vs_low:,.0f}." if cost_vs_low > 1000 else "")
        )

    # IA-6: Rebalancing guidance
    insights.append(
        "Review your portfolio allocation annually. Rebalance when any asset class drifts >5% "
        "from target. Within ISA/pension, rebalancing is tax-free."
    )

    # IA-7: Dividend reinvestment
    insights.append(
        "Ensure dividend reinvestment is enabled on all accounts. Regular monthly investing "
        "(pound-cost averaging) reduces the impact of market timing."
    )

    # IA-12: Tax-loss harvesting
    other_inv = investment_analysis.get("current_portfolio", {}).get("other_investments", 0)
    if other_inv > 0:
        insights.append(
            "Consider 'Bed and ISA': sell taxable holdings to crystallise gains within your CGT "
            "allowance, then rebuy inside an ISA for tax-free growth."
        )

    # ESG
    esg = investment_analysis.get("esg_note")
    if esg:
        insights.append(esg)

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
    deposit = mortgage_analysis.get("deposit", {})
    repayment = mortgage_analysis.get("repayment", {})
    blockers = mortgage_analysis.get("blockers", [])

    if readiness == "ready":
        insights.append(
            "You are mortgage-ready. All key criteria are met. "
            "Consider speaking to a mortgage broker to secure the best rate."
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
                f"your current rent ({current_rent:,.0f}/mo)."
            )
        else:
            insights.append(
                f"Mortgage payments ({mortgage_payment:,.0f}/mo) would be less than "
                f"your current rent ({current_rent:,.0f}/mo) — a positive cashflow shift."
            )

    # MA-1: Product comparison insight
    products = mortgage_analysis.get("product_comparison", [])
    if products and len(products) >= 2:
        cheapest = products[0]
        insights.append(
            f"Best value product: {cheapest['product']} at {cheapest['rate_pct']:.2f}% "
            f"(£{cheapest['monthly_payment']:,.0f}/mo). Compare against alternatives before choosing."
        )

    # MA-2: Overpayment insight
    overpayments = mortgage_analysis.get("overpayment_analysis", [])
    if overpayments:
        best = overpayments[0]  # £100/mo scenario
        if best.get("total_interest_saved", 0) > 1000:
            insights.append(
                f"Overpaying just £{best['extra_monthly']}/mo saves £{best['total_interest_saved']:,.0f} in "
                f"interest and clears your mortgage {best['years_saved']:.1f} years early."
            )

    # MA-3: Remortgage warning
    remortgage = mortgage_analysis.get("remortgage_analysis", {})
    if remortgage.get("cliff_edges"):
        insights.append(remortgage["advice"])

    # MA-5: Shared Ownership
    so = mortgage_analysis.get("shared_ownership")
    if so:
        affordable = [s for s in so.get("shares", []) if s["affordable"]]
        if affordable:
            best = affordable[0]
            insights.append(
                f"Shared Ownership alternative: buy a {best['share_pct']:.0f}% share for "
                f"£{best['total_monthly_cost']:,.0f}/month total (mortgage + rent + service charge)."
            )

    # MA-7: Credit warnings
    credit = mortgage_analysis.get("credit_warnings", [])
    for cw in credit:
        insights.append(f"Credit: {cw['message']}")

    return insights


def _life_event_insights(life_events: dict) -> list[str]:
    insights = []
    summary = life_events.get("summary", {})
    start_nw = summary.get("starting_net_worth", 0)
    end_nw = summary.get("ending_net_worth", 0)
    negative_year = summary.get("first_negative_year")

    if end_nw > start_nw:
        growth = end_nw - start_nw
        insights.append(
            f"Over the projection period, your net worth is expected to grow by {growth:,.0f} "
            f"(from {start_nw:,.0f} to {end_nw:,.0f})."
        )
    else:
        decline = start_nw - end_nw
        insights.append(
            f"Your net worth is projected to decline by {decline:,.0f} over the projection period."
        )

    if negative_year is not None:
        insights.append(
            f"Warning: Your net worth is projected to go negative in year {negative_year}. "
            f"Build additional reserves beforehand."
        )

    # FA-3: Childcare savings
    childcare_relief = summary.get("total_childcare_tax_relief", 0)
    if childcare_relief > 0:
        insights.append(
            f"Tax-Free Childcare will save you £{childcare_relief:,.0f} over the projection period. "
            f"Apply at childcarechoices.gov.uk — you pay in, the government tops up 20%."
        )

    goal_feasibility = life_events.get("goal_feasibility_at_deadline", [])
    for gf in goal_feasibility:
        if gf.get("likely_feasible") is False:
            insights.append(
                f"Goal '{gf['name']}' may not be feasible by year {gf['deadline_year']} — "
                f"projected liquid savings ({gf.get('projected_liquid_at_deadline', 0):,.0f}) "
                f"fall short of the {gf['target']:,.0f} target."
            )

    return insights


# ---------------------------------------------------------------------------
# Tax optimisation insights
# ---------------------------------------------------------------------------

def _tax_optimisation_insights(profile: dict, assumptions: dict, cashflow: dict) -> list[dict]:
    opportunities = []
    inc = profile.get("income", {})
    sav = profile.get("savings", {})
    personal = profile.get("personal", {})
    tax_cfg = assumptions.get("tax", {})

    primary_gross = inc.get("primary_gross_annual", 0)
    partner_gross = inc.get("partner_gross_annual", 0)
    personal_allowance = tax_cfg.get("personal_allowance", 12570)
    basic_threshold = tax_cfg.get("basic_threshold", 50270)
    higher_rate = tax_cfg.get("higher_rate", 0.40)
    basic_rate = tax_cfg.get("basic_rate", 0.20)
    age = personal.get("age", 30)
    dependents = personal.get("dependents", 0)

    # 1. Pension contribution tax relief
    personal_pct = sav.get("pension_personal_contribution_pct", 0)
    personal_contribution = primary_gross * personal_pct
    if primary_gross > basic_threshold:
        income_above_basic = primary_gross - basic_threshold
        if personal_contribution < income_above_basic:
            additional_possible = income_above_basic - personal_contribution
            tax_saving = additional_possible * (higher_rate - basic_rate)
            opportunities.append({
                "type": "pension_relief",
                "title": "Increase pension contributions for higher-rate tax relief",
                "detail": (
                    f"You earn £{income_above_basic:,.0f} above the basic rate threshold. "
                    f"Increasing pension contributions by up to £{additional_possible:,.0f}/year "
                    f"would save £{tax_saving:,.0f}/year in tax."
                ),
                "estimated_annual_saving": round(tax_saving, 2),
                "priority": "high",
            })

    # 2. Salary sacrifice
    if personal_pct > 0:
        ni_rate = tax_cfg.get("national_insurance_rate", 0.08)
        ni_saving = personal_contribution * ni_rate
        opportunities.append({
            "type": "salary_sacrifice",
            "title": "Consider salary sacrifice for pension contributions",
            "detail": (
                f"Converting your £{personal_contribution:,.0f}/year pension contribution to salary sacrifice "
                f"would save £{ni_saving:,.0f}/year in National Insurance."
            ),
            "estimated_annual_saving": round(ni_saving, 2),
            "priority": "medium",
        })

    # 3. ISA allowance
    isa_balance = sav.get("isa_balance", 0)
    lisa_balance = sav.get("lisa_balance", 0)
    opportunities.append({
        "type": "isa_allowance",
        "title": "Maximise annual ISA allowance",
        "detail": (
            f"You can shelter £20,000/year from tax in ISAs. Current ISA balance: £{isa_balance:,.0f}. "
            f"All growth within an ISA is completely tax-free."
        ),
        "estimated_annual_saving": None,
        "priority": "medium",
    })

    # 4. LISA bonus
    if lisa_balance > 0 and age < 40:
        opportunities.append({
            "type": "lisa_bonus",
            "title": "Maximise LISA contributions for 25% government bonus",
            "detail": (
                f"Contribute up to £4,000/year to your LISA for a £1,000 government bonus. "
                f"Current LISA balance: £{lisa_balance:,.0f}."
            ),
            "estimated_annual_saving": 1000,
            "priority": "high",
        })

    # 5. Marriage allowance
    if partner_gross > 0 and partner_gross <= personal_allowance and primary_gross <= basic_threshold:
        opportunities.append({
            "type": "marriage_allowance",
            "title": "Claim Marriage Allowance",
            "detail": (
                f"Your partner can transfer £1,260 of their allowance to you, saving £252/year in tax."
            ),
            "estimated_annual_saving": 252,
            "priority": "low",
        })

    # 6. CGT allowance
    other_investments = sav.get("other_investments", 0)
    if other_investments > 0 or isa_balance > 10000:
        opportunities.append({
            "type": "cgt_allowance",
            "title": "Use annual capital gains tax allowance",
            "detail": (
                "You have a £6,000 annual CGT exemption. Consider 'Bed and ISA' to crystallise "
                "gains tax-free and rebuy within an ISA wrapper."
            ),
            "estimated_annual_saving": None,
            "priority": "low",
        })

    # 7. FA-3: Tax-Free Childcare
    life_events = profile.get("life_events", [])
    has_childcare = any(e.get("type") == "childcare" for e in life_events)
    if dependents > 0 or has_childcare:
        opportunities.append({
            "type": "tax_free_childcare",
            "title": "Apply for Tax-Free Childcare",
            "detail": (
                "The government tops up childcare payments by 20%, up to £2,000/year per child. "
                "Apply at childcarechoices.gov.uk. Also check eligibility for 30 hours free childcare (3-4 year olds)."
            ),
            "estimated_annual_saving": 2000,
            "priority": "high" if has_childcare else "medium",
        })

    total_quantifiable = sum(
        o["estimated_annual_saving"] for o in opportunities
        if o["estimated_annual_saving"] is not None
    )

    return {
        "opportunities": opportunities,
        "total_estimated_annual_saving": round(total_quantifiable, 2),
    }


# ---------------------------------------------------------------------------
# Goal-event conflict detection
# ---------------------------------------------------------------------------

def _detect_goal_event_conflicts(profile: dict, cashflow: dict, life_events_result: dict) -> list[dict]:
    conflicts = []
    goals = profile.get("goals", [])
    events = profile.get("life_events", [])
    timeline = life_events_result.get("timeline", [])
    surplus_monthly = cashflow.get("surplus", {}).get("monthly", 0)
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 0)

    if not goals or not events:
        return conflicts

    event_outflows: dict[int, float] = {}
    event_descriptions: dict[int, list[str]] = {}
    event_inflows: dict[int, float] = {}
    for ev in events:
        yr = ev.get("year_offset", 0)
        one_off = ev.get("one_off_expense", 0)
        one_off_inc = ev.get("one_off_income", 0)
        if one_off > 0:
            event_outflows[yr] = event_outflows.get(yr, 0) + one_off
            event_descriptions.setdefault(yr, []).append(ev.get("description", "Unknown event"))
        if one_off_inc > 0:
            event_inflows[yr] = event_inflows.get(yr, 0) + one_off_inc

    # 1. Back-to-back large expenses
    sorted_years = sorted(event_outflows.keys())
    for i, yr in enumerate(sorted_years):
        if i + 1 < len(sorted_years):
            next_yr = sorted_years[i + 1]
            if next_yr - yr <= 1:
                combined = event_outflows[yr] + event_outflows[next_yr]
                annual_surplus = surplus_monthly * 12
                if combined > annual_surplus * 2:
                    conflicts.append({
                        "type": "back_to_back_expenses",
                        "severity": "high",
                        "years": [yr, next_yr],
                        "total_outflow": round(combined, 2),
                        "description": (
                            f"Large expenses in consecutive years: "
                            f"Year {yr} ({', '.join(event_descriptions.get(yr, []))}: £{event_outflows[yr]:,.0f}) "
                            f"and Year {next_yr} ({', '.join(event_descriptions.get(next_yr, []))}: £{event_outflows[next_yr]:,.0f})."
                        ),
                        "suggestion": "Consider spacing these events further apart or building a larger buffer beforehand.",
                    })

    # 2. Emergency fund depletion
    for t in timeline:
        yr = t["year"]
        if t.get("events") and t["liquid_savings"] < monthly_expenses * 3:
            conflicts.append({
                "type": "emergency_fund_depleted",
                "severity": "high",
                "year": yr,
                "liquid_savings": round(t["liquid_savings"], 2),
                "description": (
                    f"After Year {yr} events, projected liquid savings (£{t['liquid_savings']:,.0f}) "
                    f"fall below 3 months of expenses (£{monthly_expenses * 3:,.0f})."
                ),
                "suggestion": "Build additional reserves before this event.",
            })

    # 3. Goal sequencing
    safety_goals = [g for g in goals if g.get("category") == "safety_net"]
    discretionary_events = [e for e in events if e.get("one_off_expense", 0) > 5000]
    for sg in safety_goals:
        sg_deadline = sg.get("deadline_years", 0)
        for ev in discretionary_events:
            ev_year = ev.get("year_offset", 0)
            if ev_year <= sg_deadline:
                conflicts.append({
                    "type": "sequencing_risk",
                    "severity": "moderate",
                    "description": (
                        f"'{sg['name']}' should complete before '{ev.get('description', 'major expense')}' (Year {ev_year})."
                    ),
                    "suggestion": f"Prioritise completing '{sg['name']}' first.",
                })

    # 4. Aggregate feasibility (account for inflows from FA-4)
    total_planned_outflows = sum(event_outflows.values())
    total_planned_inflows = sum(event_inflows.values())
    goal_outflows = sum(g.get("target_amount", 0) for g in goals)
    years_covered = max(sorted_years) if sorted_years else 1
    total_savings_capacity = surplus_monthly * 12 * years_covered
    liquid_assets = profile.get("savings", {}).get("_total_liquid", 0)
    total_capacity = total_savings_capacity + liquid_assets + total_planned_inflows

    net_outflows = total_planned_outflows + goal_outflows
    if net_outflows > total_capacity * 1.1:
        shortfall = net_outflows - total_capacity
        conflicts.append({
            "type": "aggregate_infeasibility",
            "severity": "critical",
            "description": (
                f"Total planned outflows (£{net_outflows:,.0f}) exceed capacity "
                f"(savings + surplus + windfalls = £{total_capacity:,.0f}) by £{shortfall:,.0f}."
            ),
            "suggestion": "Reduce goal targets, extend timelines, increase income, or defer some events.",
        })

    return conflicts


# ---------------------------------------------------------------------------
# Risk warnings and positive reinforcements
# ---------------------------------------------------------------------------

def _risk_warnings(profile, cashflow, debt_analysis, scoring) -> list[dict]:
    warnings = []

    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    if surplus < 0:
        warnings.append({
            "severity": "critical",
            "area": "cashflow",
            "warning": "Monthly deficit — you are spending more than you earn.",
            "action": "Immediate expense review required.",
        })

    high = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
    if high > 0:
        warnings.append({
            "severity": "high",
            "area": "debt",
            "warning": f"{high} high-interest debt(s) are actively eroding your wealth.",
            "action": "Prioritise full repayment using the avalanche method.",
        })

    ef_score = scoring.get("categories", {}).get("emergency_fund", {}).get("score", 0)
    if ef_score < 30:
        warnings.append({
            "severity": "high",
            "area": "safety_net",
            "warning": "Emergency fund is critically low.",
            "action": "Build to at least 3 months of expenses before investing.",
        })

    overall = scoring.get("overall_score", 0)
    if overall < 40:
        warnings.append({
            "severity": "high",
            "area": "overall",
            "warning": "Overall financial health is in the danger zone.",
            "action": "Focus on fundamentals: cashflow, debt, emergency fund.",
        })

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
        positives.append(f"Your savings rate of {savings_rate:.1f}% exceeds the recommended 15% minimum.")

    nw = profile.get("_net_worth", 0)
    if nw > 0:
        positives.append("Your net worth is positive — you have more assets than liabilities.")

    overall = scoring.get("overall_score", 0)
    if overall >= 60:
        positives.append("Your overall financial health is above average.")

    total_debt = debt_analysis.get("summary", {}).get("total_balance", 0)
    if total_debt == 0:
        positives.append("Being debt-free gives you maximum flexibility to pursue your goals.")

    return positives


# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------

def _next_steps(scoring, debt_analysis, goal_analysis, mortgage_analysis) -> list[str]:
    steps = []

    categories = scoring.get("categories", {})
    if categories:
        weakest = min(categories.items(), key=lambda x: x[1].get("score", 100))
        steps.append(
            f"Focus area: '{weakest[0]}' scored {weakest[1]['score']:.0f}/100 — "
            f"this is your biggest opportunity for improvement."
        )

    high_debt = debt_analysis.get("summary", {}).get("high_interest_debt_count", 0)
    if high_debt > 0:
        top_debt = debt_analysis.get("avalanche_order", [""])[0]
        steps.append(f"Direct all extra repayment capacity toward '{top_debt}' first.")

    unreachable = goal_analysis.get("summary", {}).get("unreachable", 0)
    if unreachable > 0:
        steps.append(f"Review and adjust timelines for the {unreachable} unreachable goal(s).")

    if mortgage_analysis.get("applicable") and mortgage_analysis.get("readiness") != "ready":
        steps.append("Review mortgage blockers and create a timeline for resolution.")

    steps.append("Review this report quarterly and update your profile as circumstances change.")

    return steps


# ---------------------------------------------------------------------------
# FA-5: Quarterly review triggers
# ---------------------------------------------------------------------------

def _generate_review_triggers(
    profile: dict, cashflow: dict, debt_analysis: dict,
    goal_analysis: dict, scoring: dict,
) -> dict:
    """Generate quarterly review schedule with specific targets and triggers."""
    now = datetime.now()
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    ef = profile.get("savings", {}).get("emergency_fund", 0)
    monthly_exp = cashflow.get("expenses", {}).get("total_monthly", 0)

    # Quarterly dates
    quarters = []
    for q in range(1, 5):
        review_date = now + timedelta(days=90 * q)
        quarter_label = f"Q{q} ({review_date.strftime('%b %Y')})"

        targets = []
        triggers = []

        # Surplus target
        projected_savings = surplus * 3 * q
        targets.append(f"Cumulative savings from surplus: £{projected_savings:,.0f}")

        # Emergency fund milestone
        ef_months = ef / monthly_exp if monthly_exp > 0 else 0
        if ef_months < 3:
            target_ef = ef + surplus * 3 * q * 0.3  # assume 30% goes to EF
            targets.append(f"Emergency fund target: £{target_ef:,.0f}")

        # Debt milestones
        high_debt = debt_analysis.get("summary", {}).get("high_interest_total_balance", 0)
        if high_debt > 0 and q <= 2:
            targets.append(f"Credit card debt should be cleared by this point")
            triggers.append("If credit card debt not cleared, review spending and increase payments")

        # Trigger conditions
        triggers.append(f"If savings rate drops below 15%, investigate immediately")
        if surplus > 0:
            triggers.append(f"If monthly surplus drops below £{surplus * 0.7:,.0f}, review expenses")

        quarters.append({
            "quarter": quarter_label,
            "review_date": review_date.strftime("%Y-%m-%d"),
            "targets": targets,
            "trigger_conditions": triggers,
        })

    key_metrics_to_track = [
        "Monthly surplus",
        "Emergency fund balance (months of coverage)",
        "Outstanding debt balances",
        "Goal progress percentages",
        "Overall financial health score",
    ]

    return {
        "next_review": quarters[0]["review_date"],
        "schedule": quarters,
        "key_metrics": key_metrics_to_track,
    }


# ---------------------------------------------------------------------------
# T1-3: Surplus deployment plan (rank uses of surplus by effective return)
# ---------------------------------------------------------------------------

def _surplus_deployment_plan(
    profile: dict, assumptions: dict, cashflow: dict,
    debt_analysis: dict, investment_analysis: dict,
    mortgage_analysis: dict,
) -> dict:
    """
    Rank all competing uses of surplus by effective annual return,
    then allocate in priority order.
    """
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    if surplus <= 0:
        return {"applicable": False, "reason": "No surplus available to deploy."}

    sav = profile.get("savings", {})
    monthly_expenses = cashflow.get("expenses", {}).get("total_monthly", 1)
    ef = sav.get("emergency_fund", 0)
    ef_months = ef / monthly_expenses if monthly_expenses > 0 else 0

    uses: list[dict] = []

    # 1. High-interest debt payoff (guaranteed return = interest rate)
    for d in debt_analysis.get("debts", []):
        if d.get("risk_tier") == "high" and d.get("balance", 0) > 0:
            rate = d.get("interest_rate", 0)
            balance = d.get("balance", 0)
            monthly_to_clear = d.get("minimum_payment_monthly", 25)
            months_to_clear = max(1, int(balance / monthly_to_clear) + 1) if monthly_to_clear > 0 else 999
            uses.append({
                "action": f"Pay off {d['name']} (£{balance:,.0f} at {rate*100:.1f}% APR)",
                "effective_return_pct": round(rate * 100, 1),
                "type": "debt_payoff",
                "guaranteed": True,
                "monthly_amount": monthly_to_clear,
                "duration_months": months_to_clear,
                "rationale": f"Guaranteed {rate*100:.1f}% return — highest risk-adjusted return available.",
            })

    # 2. Emergency fund to 3 months (risk reduction, not return)
    if ef_months < 3:
        gap = max(0, (monthly_expenses * 3) - ef)
        months_needed = max(1, int(gap / (surplus * 0.3)) + 1) if surplus > 0 else 999
        uses.append({
            "action": f"Build emergency fund to 3 months (need £{gap:,.0f} more)",
            "effective_return_pct": 0,
            "type": "emergency_fund",
            "guaranteed": True,
            "monthly_amount": round(min(surplus * 0.5, gap), 2),
            "duration_months": months_needed,
            "rationale": "Not a return — but prevents forced borrowing at high rates. Top priority.",
            "priority_override": True,
        })

    # 3. Employer pension match (if available)
    match = investment_analysis.get("pension_match_optimisation")
    if match:
        net_cost = match.get("net_cost_monthly", 0)
        roi = match.get("roi_per_pound", 0)
        total_benefit = match.get("total_benefit_annual", 0)
        uses.append({
            "action": f"Max employer pension match (increase to {match['match_cap_pct']:.0f}%)",
            "effective_return_pct": round(roi * 100, 0),
            "type": "pension_match",
            "guaranteed": True,
            "monthly_amount": round(net_cost, 2),
            "duration_months": None,  # ongoing
            "rationale": f"Every £1 net cost returns £{roi:.2f} (employer match + tax relief).",
        })

    # 4. Moderate-interest debt
    for d in debt_analysis.get("debts", []):
        if d.get("risk_tier") == "moderate" and d.get("balance", 0) > 0:
            rate = d.get("interest_rate", 0)
            balance = d.get("balance", 0)
            uses.append({
                "action": f"Pay off {d['name']} (£{balance:,.0f} at {rate*100:.1f}%)",
                "effective_return_pct": round(rate * 100, 1),
                "type": "debt_payoff",
                "guaranteed": True,
                "monthly_amount": d.get("minimum_payment_monthly", 0),
                "duration_months": d.get("months_to_payoff", 0),
                "rationale": f"Guaranteed {rate*100:.1f}% return.",
            })

    # 5. Pension (beyond match) with tax relief
    tax_cfg = assumptions.get("tax", {})
    primary_gross = profile.get("income", {}).get("primary_gross_annual", 0)
    if primary_gross > tax_cfg.get("basic_threshold", 50270):
        effective_pension_return = 8 + 40  # ~8% market return + 40% tax relief on contributions
        uses.append({
            "action": "Additional pension contributions (higher-rate tax relief)",
            "effective_return_pct": round(effective_pension_return / 5, 1),  # annualised rough
            "type": "pension_extra",
            "guaranteed": False,
            "monthly_amount": None,
            "duration_months": None,
            "rationale": "40% tax relief on contributions + ~8% expected market return. Locked until age 57.",
        })

    # 6. ISA contributions
    isa_tracking = investment_analysis.get("isa_tracking", {})
    remaining_isa = isa_tracking.get("isa_remaining_allowance", 20000)
    if remaining_isa > 0:
        expected_return = investment_analysis.get("expected_annual_return_pct", 6)
        uses.append({
            "action": f"ISA contributions (£{remaining_isa:,.0f} allowance remaining)",
            "effective_return_pct": expected_return,
            "type": "isa",
            "guaranteed": False,
            "monthly_amount": None,
            "duration_months": None,
            "rationale": f"~{expected_return:.0f}% expected return, all growth tax-free. Flexible access.",
        })

    # 7. Mortgage overpayment (if applicable)
    if mortgage_analysis.get("applicable"):
        mort_rate = mortgage_analysis.get("repayment", {}).get("estimated_rate_pct", 0)
        if mort_rate > 0:
            uses.append({
                "action": f"Mortgage overpayment (saves {mort_rate:.2f}% guaranteed)",
                "effective_return_pct": mort_rate,
                "type": "mortgage_overpayment",
                "guaranteed": True,
                "monthly_amount": 100,
                "duration_months": None,
                "rationale": f"Guaranteed {mort_rate:.2f}% return. Check 10% annual overpayment limit.",
            })

    # 8. Student loans — explicitly mark as "do not overpay"
    for d in debt_analysis.get("debts", []):
        if d.get("type") in ("student_loan", "student_loan_postgrad"):
            woi = d.get("write_off_intelligence", {})
            if woi.get("will_be_written_off"):
                uses.append({
                    "action": f"DO NOT overpay {d['name']}",
                    "effective_return_pct": -100,
                    "type": "student_loan_do_not_overpay",
                    "guaranteed": True,
                    "monthly_amount": 0,
                    "duration_months": None,
                    "rationale": woi.get("reasoning", "Write-off makes overpayment counterproductive."),
                })

    # Sort: emergency fund first (priority override), then by effective return descending
    # Filter out student loan "do not overpay" entries from allocation (they're informational)
    actionable = [u for u in uses if u["type"] != "student_loan_do_not_overpay"]
    informational = [u for u in uses if u["type"] == "student_loan_do_not_overpay"]

    # Emergency fund always first, then sort by return
    ef_items = [u for u in actionable if u.get("priority_override")]
    other_items = sorted(
        [u for u in actionable if not u.get("priority_override")],
        key=lambda x: x["effective_return_pct"],
        reverse=True,
    )

    ordered = ef_items + other_items

    # Allocate surplus
    remaining = surplus
    for i, use in enumerate(ordered):
        monthly = use.get("monthly_amount")
        if monthly is not None and monthly > 0:
            allocated = min(remaining, monthly)
            ordered[i]["allocated_monthly"] = round(allocated, 2)
            remaining = max(0, remaining - allocated)
        else:
            ordered[i]["allocated_monthly"] = round(remaining, 2) if i == len(ordered) - 1 else 0

    return {
        "applicable": True,
        "monthly_surplus": round(surplus, 2),
        "deployment_order": ordered,
        "do_not_overpay": informational,
        "summary": (
            f"Deploy your £{surplus:,.0f}/month surplus in this order for maximum impact. "
            f"Higher-return, guaranteed items first."
        ),
    }
