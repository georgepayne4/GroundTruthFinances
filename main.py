"""
main.py — GroundTruth Financial Planning Engine v3.0

Entry point that orchestrates the full analysis pipeline:
1. Load profile and assumptions
2. Validate inputs
3. Run analysis modules in dependency order
4. Score financial health
5. Generate advisor insights
6. Run estate analysis
7. Assemble and save report

Usage:
    python main.py                                    # uses sample input by default
    python main.py --profile path/to/profile.yaml     # custom profile (config/<name>_input.yaml)
    python main.py --assumptions path/to/assumptions.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.loader import load_profile, load_assumptions
from engine.validator import validate_profile
from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.goals import analyse_goals
from engine.investments import analyse_investments
from engine.mortgage import analyse_mortgage
from engine.life_events import simulate_life_events
from engine.scoring import calculate_scores
from engine.insights import generate_insights
from engine.insurance import assess_insurance
from engine.scenarios import run_scenarios
from engine.estate import analyse_estate
from engine.report import assemble_report, save_report


def main() -> None:
    args = parse_args()

    project_root = Path(__file__).resolve().parent

    # ------------------------------------------------------------------
    # 1. Load inputs
    # ------------------------------------------------------------------
    profile_path = args.profile or project_root / "config" / "sample_input.yaml"
    assumptions_path = args.assumptions or project_root / "config" / "assumptions.yaml"

    print(f"Loading profile:     {profile_path}")
    print(f"Loading assumptions: {assumptions_path}")

    profile = load_profile(profile_path)
    assumptions = load_assumptions(assumptions_path)

    name = profile.get("personal", {}).get("name", "Unknown")
    print(f"\nAnalysing financial profile for: {name}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 2. Validate
    # ------------------------------------------------------------------
    print("Running advisor validation layer...")
    flags = validate_profile(profile, assumptions)
    flag_dicts = [f.to_dict() for f in flags]

    errors = [f for f in flags if f.severity.value == "error"]
    warnings = [f for f in flags if f.severity.value == "warning"]
    infos = [f for f in flags if f.severity.value == "info"]

    print(f"  Flags: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info(s)")

    if errors:
        print("\n  ERRORS (may affect analysis accuracy):")
        for e in errors:
            print(f"    - [{e.field}] {e.message}")

    # ------------------------------------------------------------------
    # 3. Cashflow analysis
    # ------------------------------------------------------------------
    print("\nRunning cashflow analysis...")
    cashflow = analyse_cashflow(profile, assumptions)
    surplus = cashflow.get("surplus", {}).get("monthly", 0)
    savings_rate = cashflow.get("savings_rate", {}).get("basic_pct", 0)
    print(f"  Net monthly income: {cashflow['net_income']['monthly']:,.2f}")
    print(f"  Monthly surplus:    {surplus:,.2f}")
    print(f"  Savings rate:       {savings_rate:.1f}%")

    if cashflow.get("spending_benchmarks"):
        total_saving = cashflow["spending_benchmarks"].get("total_potential_monthly_saving", 0)
        if total_saving > 0:
            print(f"  Benchmark savings:  {total_saving:,.2f}/mo potential")

    # ------------------------------------------------------------------
    # 4. Debt analysis
    # ------------------------------------------------------------------
    print("\nRunning debt analysis...")
    debt_result = analyse_debt(profile, assumptions)
    debt_summary = debt_result.get("summary", {})
    print(f"  Total debt:         {debt_summary.get('total_balance', 0):,.2f}")
    print(f"  Strategy:           {debt_result.get('recommended_strategy', 'N/A')}")
    if debt_result.get("avalanche_order"):
        print(f"  Priority order:     {' > '.join(debt_result['avalanche_order'])}")

    # ------------------------------------------------------------------
    # 5. Goal feasibility
    # ------------------------------------------------------------------
    print("\nRunning goal feasibility analysis...")
    goal_result = analyse_goals(profile, assumptions, cashflow)
    goal_summary = goal_result.get("summary", {})
    print(f"  Goals: {goal_summary.get('on_track', 0)} on track, "
          f"{goal_summary.get('at_risk', 0)} at risk, "
          f"{goal_summary.get('unreachable', 0)} unreachable")

    # ------------------------------------------------------------------
    # 6. Investment analysis
    # ------------------------------------------------------------------
    print("\nRunning investment analysis...")
    investment_result = analyse_investments(profile, assumptions, cashflow)
    pension = investment_result.get("pension_analysis", {})
    print(f"  Pension adequate:   {pension.get('adequate', False)}")
    print(f"  Replacement ratio:  {pension.get('income_replacement_ratio_pct', 0):.1f}% (net of tax)")
    if investment_result.get("pension_match_optimisation"):
        free = investment_result["pension_match_optimisation"]["free_money_left_on_table"]
        print(f"  Employer match gap: {free:,.0f}/year left on table")
    fees = investment_result.get("fee_analysis", {})
    if fees.get("fee_drag_over_term", 0) > 0:
        print(f"  Fee drag:           {fees['fee_drag_over_term']:,.0f} over term")

    # ------------------------------------------------------------------
    # 7. Mortgage readiness
    # ------------------------------------------------------------------
    print("\nRunning mortgage assessment...")
    mortgage_result = analyse_mortgage(profile, assumptions, cashflow, debt_result)
    if mortgage_result.get("applicable"):
        print(f"  Readiness:          {mortgage_result.get('readiness', 'N/A')}")
        blockers = mortgage_result.get("blockers", [])
        print(f"  Blockers:           {len(blockers)}")
        products = mortgage_result.get("product_comparison", [])
        if products:
            best = products[0]
            print(f"  Best product:       {best['product']} at {best['rate_pct']:.2f}%")
        so = mortgage_result.get("shared_ownership")
        if so:
            affordable = [s for s in so.get("shares", []) if s["affordable"]]
            if affordable:
                print(f"  Shared Ownership:   {affordable[0]['share_pct']:.0f}% share is affordable")
    else:
        print("  Not applicable")

    # ------------------------------------------------------------------
    # 8. Insurance gap assessment
    # ------------------------------------------------------------------
    print("\nAssessing insurance coverage...")
    insurance_result = assess_insurance(profile, assumptions, cashflow, mortgage_result)
    print(f"  Overall:            {insurance_result.get('overall_assessment', 'unknown')}")
    print(f"  Gaps identified:    {insurance_result.get('gap_count', 0)}")

    # ------------------------------------------------------------------
    # 9. Life event simulation
    # ------------------------------------------------------------------
    print("\nRunning life event simulation...")
    life_event_result = simulate_life_events(profile, assumptions, cashflow)
    le_summary = life_event_result.get("summary", {})
    print(f"  Projection years:   {life_event_result.get('projection_years', 0)}")
    print(f"  Starting net worth: {le_summary.get('starting_net_worth', 0):,.2f}")
    print(f"  Ending net worth:   {le_summary.get('ending_net_worth', 0):,.2f}")
    childcare = le_summary.get("total_childcare_tax_relief", 0)
    if childcare > 0:
        print(f"  Childcare relief:   {childcare:,.2f} total saved")

    # ------------------------------------------------------------------
    # 10. Financial health scoring
    # ------------------------------------------------------------------
    print("\nCalculating financial health score...")
    scoring_result = calculate_scores(
        profile, assumptions, cashflow, debt_result,
        goal_result, investment_result, mortgage_result,
    )
    print(f"  Overall score:      {scoring_result.get('overall_score', 0):.0f}/100")
    print(f"  Grade:              {scoring_result.get('grade', 'N/A')}")

    for cat_name, cat_data in scoring_result.get("categories", {}).items():
        score = cat_data.get("score", 0)
        bar = "#" * int(score / 5) + "-" * (20 - int(score / 5))
        print(f"    {cat_name:<25} [{bar}] {score:.0f}")

    # ------------------------------------------------------------------
    # 11. Stress scenarios
    # ------------------------------------------------------------------
    print("\nRunning stress scenarios...")
    scenario_result = run_scenarios(
        profile, assumptions, cashflow, debt_result,
        mortgage_result, investment_result,
    )
    job_loss = scenario_result.get("job_loss", {})
    print(f"  Job loss runway:    {job_loss.get('months_runway', 0):.1f} months ({job_loss.get('assessment', 'unknown')})")

    rate_shock = scenario_result.get("interest_rate_shock", {})
    if rate_shock.get("applicable"):
        worst = rate_shock.get("scenarios", {}).get("plus_3_pct", {})
        print(f"  Rate +3% payment:   {worst.get('monthly_payment', 0):,.0f}/mo ({('affordable' if worst.get('affordable') else 'unaffordable')})")

    # ------------------------------------------------------------------
    # 12. Estate analysis
    # ------------------------------------------------------------------
    print("\nRunning estate analysis...")
    estate_result = analyse_estate(profile, assumptions, investment_result, mortgage_result)
    print(f"  Projected estate:   {estate_result.get('projected_estate_value', 0):,.0f}")
    print(f"  IHT liability:      {estate_result.get('iht_liability', 0):,.0f}")
    planning = estate_result.get("estate_planning", {})
    if planning.get("actions"):
        print(f"  Planning actions:   {len(planning['actions'])}")

    # ------------------------------------------------------------------
    # 13. Advisor insights
    # ------------------------------------------------------------------
    print("\nGenerating advisor insights...")
    insights_result = generate_insights(
        profile, assumptions, cashflow, debt_result,
        goal_result, investment_result, mortgage_result,
        scoring_result, life_event_result,
    )

    # Print executive summary
    print(f"\n{'=' * 60}")
    print("EXECUTIVE SUMMARY")
    print(f"{'=' * 60}")
    print(insights_result.get("executive_summary", ""))

    # Print top priorities
    priorities = insights_result.get("top_priorities", [])
    if priorities:
        print(f"\n{'=' * 60}")
        print("TOP PRIORITIES")
        print(f"{'=' * 60}")
        for p in priorities:
            print(f"\n  {p['priority']}. [{p['category'].upper()}] {p['title']}")
            print(f"     {p['detail']}")

    # Print review schedule
    review = insights_result.get("review_schedule", {})
    if review:
        print(f"\n{'=' * 60}")
        print("REVIEW SCHEDULE")
        print(f"{'=' * 60}")
        print(f"  Next review: {review.get('next_review', 'N/A')}")

    # ------------------------------------------------------------------
    # 14. Assemble and save report
    # ------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    output_path = project_root / "outputs" / "report.json"

    report = assemble_report(
        profile=profile,
        validation_flags=flag_dicts,
        cashflow=cashflow,
        debt_analysis=debt_result,
        goal_analysis=goal_result,
        investment_analysis=investment_result,
        mortgage_analysis=mortgage_result,
        life_events=life_event_result,
        scoring=scoring_result,
        insights=insights_result,
        insurance=insurance_result,
        scenarios=scenario_result,
        estate=estate_result,
    )

    saved_path = save_report(report, output_path)
    print(f"\nReport saved to: {saved_path}")
    print("Done.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GroundTruth Financial Planning Engine",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Path to the financial profile YAML file (default: config/sample_input.yaml)",
    )
    parser.add_argument(
        "--assumptions",
        type=Path,
        default=None,
        help="Path to the assumptions YAML file (default: config/assumptions.yaml)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
