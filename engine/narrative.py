"""
narrative.py — Narrative Report Generator (T3-1)

Transforms the JSON report data into a structured, readable text report
suitable for client delivery. Produces Markdown output with:
- Executive summary
- Financial snapshot
- Priority actions with cost/benefit
- Detailed analysis sections
- Timeline and milestones
- Decision points
- Review schedule
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _sanitise(value: str) -> str:
    """Escape HTML entities in user-provided strings to prevent XSS."""
    return html.escape(str(value), quote=True)


def generate_narrative(report: dict) -> str:
    """Generate a full narrative report from the assembled JSON report."""
    sections = [
        _header(report),
        _disclaimer_banner(report),
        _executive_summary(report),
        _financial_snapshot(report),
        _priority_actions(report),
        _surplus_deployment(report),
        _detailed_analysis(report),
        _timeline_and_milestones(report),
        _decision_points(report),
        _compound_scenarios(report),
        _review_schedule(report),
        _appendix(report),
    ]
    return "\n\n".join(s for s in sections if s)


def _get_legal(report: dict) -> dict:
    """Extract the legal config from the report (falls back to safe defaults)."""
    legal = report.get("meta", {}).get("legal") or {}
    return {
        "disclaimer_short": legal.get(
            "disclaimer_short", "Not financial advice. Educational information only."
        ),
        "disclaimer_long": legal.get(
            "disclaimer_long",
            "This report is for informational purposes only and does not constitute "
            "financial advice. Consult a qualified financial adviser before making "
            "significant financial decisions. Past performance is not indicative of "
            "future results. All projections are estimates based on the stated assumptions.",
        ),
        "regulatory_classification": legal.get(
            "regulatory_classification", "information service"
        ),
        "provider_name": legal.get("provider_name", "GroundTruth"),
    }


def _disclaimer_banner(report: dict) -> str:
    """Prominent disclaimer banner at the top of the report."""
    legal = _get_legal(report)
    return (
        f"> **⚠ {legal['disclaimer_short']}** "
        f"{legal['provider_name']} is an {legal['regulatory_classification']}, "
        "not a regulated financial adviser. See the full disclaimer at the end of this report."
    )


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

def _header(report: dict) -> str:
    meta = report.get("meta", {})
    name = _sanitise(meta.get("profile_name", "Unknown"))
    age = meta.get("profile_age", "")
    date = meta.get("generated_at", datetime.now(timezone.utc).isoformat())[:10]
    scoring = report.get("scoring", {})

    lines = [
        "# GroundTruth Financial Health Report",
        f"**Prepared for:** {name} (age {age})",
        f"**Date:** {date}",
        f"**Overall Score:** {scoring.get('overall_score', 0):.0f}/100 (Grade: {scoring.get('grade', 'N/A')})",
        "",
        "---",
    ]
    return "\n".join(lines)


def _executive_summary(report: dict) -> str:
    insights = report.get("advisor_insights", {})
    summary = insights.get("executive_summary", "")
    if not summary:
        return ""

    lines = [
        "## Executive Summary",
        "",
        summary,
    ]
    return "\n".join(lines)


def _financial_snapshot(report: dict) -> str:
    cashflow = report.get("cashflow", {})
    scoring = report.get("scoring", {})
    debt = report.get("debt", {})

    net_monthly = cashflow.get("net_income", {}).get("monthly", 0)
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    savings_rate = cashflow.get("savings_rate", {}).get("basic_pct", 0)
    total_debt = debt.get("summary", {}).get("total_balance", 0)

    lines = [
        "## Financial Snapshot",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Net monthly income | {net_monthly:,.0f} |",
        f"| Monthly surplus | {surplus:,.0f} |",
        f"| Savings rate | {savings_rate:.1f}% |",
        f"| Total debt | {total_debt:,.0f} |",
    ]

    # Category scores
    cats = scoring.get("categories", {})
    if cats:
        lines.append("")
        lines.append("### Health Score Breakdown")
        lines.append("")
        lines.append("| Category | Score | Benchmark |")
        lines.append("|----------|-------|-----------|")
        for name, data in cats.items():
            score = data.get("score", 0)
            benchmark = data.get("benchmark", "")
            lines.append(f"| {name.replace('_', ' ').title()} | {score:.0f}/100 | {benchmark} |")

    return "\n".join(lines)


def _priority_actions(report: dict) -> str:
    insights = report.get("advisor_insights", {})
    priorities = insights.get("top_priorities", [])
    if not priorities:
        return ""

    lines = [
        "## Priority Actions",
        "",
    ]

    for p in priorities:
        lines.append(f"### {p['priority']}. [{p['category'].upper()}] {p['title']}")
        lines.append("")
        lines.append(f"**What:** {p['detail']}")
        if p.get("estimated_monthly_cost"):
            lines.append(f"**Cost:** {p['estimated_monthly_cost']:,.0f}/month")
        if p.get("estimated_benefit"):
            lines.append(f"**Benefit:** {p['estimated_benefit']}")
        lines.append("")

    return "\n".join(lines)


def _surplus_deployment(report: dict) -> str:
    insights = report.get("advisor_insights", {})
    plan = insights.get("surplus_deployment_plan", {})
    if not plan.get("applicable"):
        return ""

    lines = [
        "## Surplus Deployment Plan",
        "",
        "Deploy your monthly surplus in this order for maximum impact:",
        "",
        "| Priority | Action | Return | Monthly |",
        "|----------|--------|--------|---------|",
    ]

    for i, use in enumerate(plan.get("deployment_order", []), 1):
        ret = use.get("effective_return_pct", 0)
        guaranteed = " (g)" if use.get("guaranteed") else ""
        alloc = use.get("allocated_monthly", 0)
        lines.append(f"| {i} | {use['action']} | {ret:.1f}%{guaranteed} | {alloc:,.0f} |")

    do_nots = plan.get("do_not_overpay", [])
    if do_nots:
        lines.append("")
        lines.append("**Do NOT overpay:**")
        for d in do_nots:
            lines.append(f"- {d['action']}: {d.get('reasoning', '')}")

    return "\n".join(lines)


def _detailed_analysis(report: dict) -> str:
    sections = []

    # Debt analysis
    debt = report.get("debt", {})
    if debt.get("debts"):
        lines = ["## Debt Analysis", ""]
        strategy = debt.get("recommended_strategy", "N/A")
        lines.append(f"**Recommended strategy:** {strategy}")
        order = debt.get("avalanche_order", [])
        if order:
            lines.append(f"**Priority order:** {' > '.join(order)}")
        lines.append("")

        for d in debt.get("debts", []):
            woi = d.get("write_off_intelligence", {})
            if woi and woi.get("will_be_written_off"):
                lines.append(f"- **{d['name']}:** Will be written off. {woi.get('reasoning', '')}")
            elif d.get("risk_tier") == "high":
                lines.append(f"- **{d['name']}:** HIGH PRIORITY - {d['balance']:,.0f} at {d['interest_rate_pct']:.1f}%")

        sections.append("\n".join(lines))

    # Mortgage analysis
    mortgage = report.get("mortgage", {})
    if mortgage.get("applicable"):
        lines = ["## Mortgage Assessment", ""]
        lines.append(f"**Readiness:** {mortgage.get('readiness', 'N/A')}")
        blockers = mortgage.get("blockers", [])
        if blockers:
            lines.append(f"**Blockers:** {len(blockers)}")
            for b in blockers:
                lines.append(f"- {b['message']}")
                lines.append(f"  *Action:* {b['action']}")
        products = mortgage.get("product_comparison", [])
        if products:
            lines.append("")
            lines.append("**Product comparison:**")
            for p in products[:3]:
                lines.append(f"- {p['product']}: {p['rate_pct']:.2f}% ({p['monthly_payment']:,.0f}/month)")
        sections.append("\n".join(lines))

    # Insurance
    insurance = report.get("insurance", {})
    gaps = insurance.get("gaps", [])
    if gaps:
        lines = ["## Insurance Gaps", ""]
        for g in gaps:
            lines.append(f"- **{g['type'].replace('_', ' ').title()}** [{g['severity'].upper()}]")
            lines.append(f"  {g['message']}")
            cost = g.get("estimated_cost", {})
            if cost:
                note = cost.get("note", "")
                pct = cost.get("pct_of_surplus", 0)
                lines.append(f"  *Estimated cost:* {note} ({pct:.1f}% of surplus)")
        sections.append("\n".join(lines))

    # Estate
    estate = report.get("estate", {})
    if estate:
        lines = ["## Estate Planning", ""]
        lines.append(f"**Projected estate value:** {estate.get('projected_estate_value', 0):,.0f}")
        lines.append(f"**IHT liability:** {estate.get('iht_liability', 0):,.0f}")
        iht_note = estate.get("iht_note")
        if iht_note:
            lines.append(f"*{iht_note}*")
        actions = estate.get("estate_planning", {}).get("actions", [])
        if actions:
            lines.append("")
            for a in actions:
                if isinstance(a, dict):
                    lines.append(f"- {a['action']} (Cost: {a.get('estimated_cost', 'N/A')})")
                else:
                    lines.append(f"- {a}")
        suggestions = estate.get("optimisation_suggestions", [])
        actionable = [s for s in suggestions if s.get("estimated_lifetime_saving", 0) > 0]
        if actionable:
            lines.append("\n### IHT Optimisation Strategies")
            for s in actionable:
                lines.append(f"- {s['description']}")
        savings = estate.get("estimated_tax_savings", 0)
        if savings > 0:
            lines.append(f"\n**Total potential IHT savings:** {savings:,.0f}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def _timeline_and_milestones(report: dict) -> str:
    le = report.get("life_events", {})
    milestones = le.get("milestones", [])
    timeline = le.get("timeline", [])
    summary = le.get("summary", {})

    if not timeline:
        return ""

    lines = [
        "## Financial Timeline",
        "",
        f"**Projection:** {le.get('projection_years', 0)} years",
        f"**Starting net worth:** {summary.get('starting_net_worth', 0):,.0f}",
        f"**Ending net worth:** {summary.get('ending_net_worth', 0):,.0f}",
        "",
    ]

    if milestones:
        lines.append("### Key Milestones")
        lines.append("")
        for ms in milestones:
            severity = f" [{ms['severity'].upper()}]" if ms.get("severity") else ""
            lines.append(f"- **Year {ms['year']} (age {ms['age']}):** {ms['message']}{severity}")
        lines.append("")

    # Condensed timeline table
    lines.append("### Year-by-Year Summary")
    lines.append("")
    lines.append("| Year | Age | Net Income | Surplus | Net Worth | Events |")
    lines.append("|------|-----|-----------|---------|-----------|--------|")
    for t in timeline:
        events = ", ".join(t["events"]) if t.get("events") else "-"
        if len(events) > 40:
            events = events[:37] + "..."
        lines.append(
            f"| {t['year']} | {t['age']} | {t['net_income_annual']:,.0f} | "
            f"{t['annual_surplus']:,.0f} | {t['net_worth']:,.0f} | {events} |"
        )

    return "\n".join(lines)


def _decision_points(report: dict) -> str:
    """Generate forward-looking decision points from the analysis."""
    points = []

    # Remortgage decision points
    mortgage = report.get("mortgage", {})
    remortgage = mortgage.get("remortgage_analysis", {})
    for edge in remortgage.get("cliff_edges", []):
        years = edge.get("ends_after_years", 0)
        shock = edge.get("payment_shock", 0)
        if shock > 0:
            points.append(
                f"**Year {years} — Remortgage cliff:** Your {edge['product']} fix ends. "
                f"Payment jumps by {shock:,.0f}/month if you fall to SVR. "
                f"Start comparing products 3 months before."
            )

    # Pension allocation decision
    le = report.get("life_events", {})
    for ms in le.get("milestones", []):
        if ms.get("type") == "negative_surplus":
            points.append(
                f"**Year {ms['year']} (age {ms['age']}) — Budget pressure:** {ms['message']}. "
                f"Review expenses and consider deferring discretionary goals."
            )

    # Debt clearance redirect
    debt = report.get("debt", {})
    for d in debt.get("debts", []):
        if d.get("risk_tier") == "high" and d.get("months_to_payoff", 0) < 24:
            months = d["months_to_payoff"]
            payment = d["minimum_payment_monthly"]
            points.append(
                f"**Month ~{months} — {d['name']} cleared:** Redirect {payment:,.0f}/month "
                f"to next priority (check surplus deployment plan)."
            )

    # Sensitivity triggers
    sensitivity = report.get("sensitivity_analysis", {})
    for _cat, scenarios in sensitivity.get("scenarios", {}).items():
        for s in scenarios:
            if s.get("delta_score", 0) < -10:
                points.append(f"**If {s['label']}:** Score drops significantly. Monitor this risk.")

    if not points:
        return ""

    lines = ["## Decision Points", ""]
    for p in points:
        lines.append(f"- {p}")

    return "\n".join(lines)


def _compound_scenarios(report: dict) -> str:
    """v8.6: Compound scenario tree summary."""
    scenarios = report.get("stress_scenarios", {})
    compound = scenarios.get("compound_scenarios") if scenarios else None
    if not compound:
        return ""

    branches = compound.get("branches", [])
    if not branches:
        return ""

    lines = ["## Scenario Tree Analysis", ""]
    lines.append("| Scenario | Probability | Score | Monthly Surplus | NPV |")
    lines.append("|----------|------------|-------|-----------------|-----|")

    for b in branches:
        r = b["results"]
        prob = f"{b['probability']:.0%}"
        score = f"{r['score']:.0f}/100"
        surplus = f"{r['surplus_monthly']:,.0f}"
        npv = f"{r['npv_surplus']:,.0f}"
        lines.append(f"| {b['name'].title()} | {prob} | {score} | {surplus} | {npv} |")

    expected = compound.get("expected_values", {})
    lines.append("")
    lines.append(
        f"**Expected outcome (probability-weighted):** "
        f"Score {expected.get('expected_score', 0):.0f}/100, "
        f"NPV {expected.get('expected_npv', 0):,.0f}"
    )

    summary = compound.get("decision_summary", {})
    worst = summary.get("worst_case", "")
    if worst:
        worst_branch = next((b for b in branches if b["name"] == worst), None)
        if worst_branch and worst_branch["recommended_actions"]:
            lines.append("")
            lines.append(f"**If {worst} occurs:**")
            for action in worst_branch["recommended_actions"]:
                lines.append(f"- {action}")

    return "\n".join(lines)


def _review_schedule(report: dict) -> str:
    review = report.get("review_schedule", {})
    if not review:
        return ""

    lines = [
        "## Review Schedule",
        "",
        f"**Next review:** {review.get('next_review', 'N/A')}",
        f"**Frequency:** {review.get('frequency', 'Quarterly')}",
    ]

    targets = review.get("targets", [])
    if targets:
        lines.append("")
        lines.append("### Targets to Check")
        for t in targets:
            lines.append(f"- {t}")

    triggers = review.get("triggers", [])
    if triggers:
        lines.append("")
        lines.append("### Triggers for Immediate Review")
        for t in triggers:
            lines.append(f"- {t}")

    return "\n".join(lines)


def _appendix(report: dict) -> str:
    lines = [
        "## Appendix",
        "",
        "### Assumptions",
        "",
        "This report uses the following key assumptions:",
        "",
    ]

    # Pull key assumptions from validation/meta
    meta = report.get("meta", {})
    lines.append(f"- Engine version: {meta.get('engine_version', 'N/A')}")

    validation = report.get("validation", {})
    errors = validation.get("error_count", 0)
    warnings = validation.get("warning_count", 0)
    lines.append(f"- Validation: {errors} errors, {warnings} warnings")

    lines.append("")
    lines.append("### Disclaimer")
    lines.append("")
    legal = _get_legal(report)
    lines.append(legal["disclaimer_long"])

    return "\n".join(lines)
