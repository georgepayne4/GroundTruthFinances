"""
main.py — GroundTruth Financial Planning Engine v4.0

Entry point that orchestrates the full analysis pipeline:
1. Load profile and assumptions
2. Validate inputs
3. Run analysis modules in dependency order
4. Score financial health
5. Generate advisor insights
6. Run estate analysis
7. Run sensitivity analysis
8. Assemble and save report

Usage:
    python main.py                                    # uses sample input
    python main.py --profile path/to/profile.yaml     # custom profile
    python main.py --assumptions path/to/assumptions.yaml
    python main.py --import-csv path/to/statement.csv # preview bank CSV import
    python main.py --bank-csv path/to/statement.csv   # merge bank CSV into profile, run full pipeline
    python main.py --history                          # list recent runs from the history DB
    python main.py --diff                             # diff the two most recent runs
    python main.py --diff 3 7                         # diff specific run ids
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

import engine
from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.estate import analyse_estate
from engine.goals import analyse_goals
from engine.history import (
    HistoryError,
    diff_runs,
    latest_two_runs,
    list_runs,
    record_run,
)
from engine.import_csv import import_bank_csv
from engine.insights import generate_insights
from engine.insurance import assess_insurance
from engine.investments import analyse_investments
from engine.life_events import simulate_life_events
from engine.loader import load_assumptions, load_profile, merge_bank_data
from engine.mortgage import analyse_mortgage
from engine.narrative import generate_narrative
from engine.report import assemble_report, save_report
from engine.risk_profiling import assess_risk_profiles
from engine.scenarios import run_scenarios
from engine.scoring import calculate_scores
from engine.sensitivity import run_sensitivity
from engine.validator import validate_profile

logger = logging.getLogger(__name__)


def main() -> None:
    args = parse_args()

    # Configure logging: file always gets DEBUG, console gets WARNING (engine prints are the UI)
    log_dir = Path(__file__).resolve().parent / "outputs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_dir / "engine.log", encoding="utf-8")]
    if args.verbose:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    logger.info("GroundTruth engine v%s starting", engine.__version__)

    # v5.3-03: Assumption auto-update — short-circuits the main pipeline
    if args.update_assumptions:
        _run_assumption_update(args.assumptions)
        return

    # v5.2-01: CSV import preview mode — short-circuits the main pipeline
    if args.import_csv:
        _run_csv_preview(args.import_csv)
        return

    project_root = Path(__file__).resolve().parent
    history_db_path = args.history_db or project_root / "outputs" / "history.db"

    # v5.2-05: history short-circuits — list past runs or diff two runs without
    # touching the analysis pipeline.
    if args.history:
        _show_history(history_db_path, limit=args.history_limit, profile_name=args.history_profile)
        return
    if args.diff is not None:
        _show_diff(history_db_path, args.diff, profile_name=args.history_profile)
        return

    # ------------------------------------------------------------------
    # 1. Load inputs
    # ------------------------------------------------------------------
    profile_path = args.profile or project_root / "config" / "sample_input.yaml"
    assumptions_path = args.assumptions or project_root / "config" / "assumptions.yaml"

    print(f"Loading profile:     {profile_path}")
    print(f"Loading assumptions: {assumptions_path}")

    profile = load_profile(profile_path)
    assumptions = load_assumptions(assumptions_path)

    # v7.6: check assumptions staleness
    from engine.pipeline import _check_assumptions_staleness
    _check_assumptions_staleness(assumptions)

    # v5.2-02: optional bank CSV merge — runs before any analysis so the
    # whole pipeline sees the bank-derived expenses and inferred income.
    if args.bank_csv:
        print(f"Merging bank CSV:    {args.bank_csv}")
        bank_result = import_bank_csv(args.bank_csv)
        profile = merge_bank_data(profile, bank_result, override=args.bank_csv_override)
        bi = profile.get("_bank_import", {})
        bsum = bi.get("summary", {})
        print(
            f"  Bank merge:         "
            f"{len(bi.get('expense_fields_overridden', []))} overridden, "
            f"{len(bi.get('expense_fields_supplemented', []))} supplemented, "
            f"avg confidence {bsum.get('average_confidence', 0):.2f}",
        )
        if bi.get("income_inferred"):
            inf = bi["income_inferred"]
            print(f"  Income inferred:    £{inf['annual_estimate']:,.0f}/yr from '{inf['source_description']}'")
        if bi.get("recurring_transactions"):
            print(f"  Recurring detected: {len(bi['recurring_transactions'])} groups")
        if bi.get("subscriptions"):
            sub_total = bsum.get("subscription_monthly_total", 0)
            print(f"  Subscriptions:      {len(bi['subscriptions'])} active, {sub_total:,.2f}/mo total")
        if bi.get("committed_outflows"):
            co_total = bsum.get("committed_outflow_monthly_total", 0)
            print(f"  DD/SO committed:    {len(bi['committed_outflows'])} payees, {co_total:,.2f}/mo total")
        iv = bi.get("income_verification", {})
        if iv.get("match_status") and iv["match_status"] != "unverifiable":
            status = iv["match_status"]
            obs = iv.get("observed_annual") or 0
            print(f"  Income verified:    {status} (observed net {obs:,.0f}/yr, {iv.get('income_regularity', '?')})")

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

    # T1-5: Student loan write-off intelligence
    for d in debt_result.get("debts", []):
        woi = d.get("write_off_intelligence", {})
        if woi and woi.get("will_be_written_off"):
            be = woi.get("break_even_salary")
            if be:
                print(f"  {d['name']}: WRITE-OFF (break-even: £{be:,.0f}/yr)")
            else:
                print(f"  {d['name']}: WRITE-OFF recommended")

    # ------------------------------------------------------------------
    # 5. Goal feasibility (T1-1: with prerequisites and debt context)
    # ------------------------------------------------------------------
    print("\nRunning goal feasibility analysis...")
    goal_result = analyse_goals(profile, assumptions, cashflow, debt_result)
    goal_summary = goal_result.get("summary", {})
    prereqs = goal_result.get("prerequisites", {})
    print(f"  Goals: {goal_summary.get('on_track', 0)} on track, "
          f"{goal_summary.get('at_risk', 0)} at risk, "
          f"{goal_summary.get('unreachable', 0)} unreachable, "
          f"{goal_summary.get('blocked', 0)} blocked")
    if not prereqs.get("all_met", True):
        print(f"  Prerequisites: NOT MET (EF: {prereqs.get('emergency_fund_months_current', 0):.1f}mo, "
              f"high-interest debt: {prereqs.get('high_interest_debt_count', 0)})")

    # ------------------------------------------------------------------
    # 5b. Risk profiling (v8.4)
    # ------------------------------------------------------------------
    print("\nRunning risk profiling...")
    risk_profile_result = assess_risk_profiles(profile, assumptions, cashflow, goal_result)
    rp_summary = risk_profile_result.get("summary", {})
    capacity = risk_profile_result.get("capacity_for_loss", {})
    print(f"  Goals assessed:     {rp_summary.get('goals_assessed', 0)}")
    print(f"  Mismatches:         {rp_summary.get('warning_count', 0)} warnings, "
          f"{rp_summary.get('info_count', 0)} info")
    print(f"  Capacity for loss:  {capacity.get('affordable_drawdown_pct', 0):.0%} "
          f"({capacity.get('emergency_months', 0):.1f}mo emergency fund)")
    for m in risk_profile_result.get("mismatches", []):
        if m.get("severity") == "warning":
            print(f"  WARNING: {m['message']}")

    # ------------------------------------------------------------------
    # 6. Investment analysis
    # ------------------------------------------------------------------
    print("\nRunning investment analysis...")
    investment_result = analyse_investments(profile, assumptions, cashflow, goal_result, risk_profile_result)
    pension = investment_result.get("pension_analysis", {})
    print(f"  Pension adequate:   {pension.get('adequate', False)}")
    print(f"  Replacement ratio:  {pension.get('income_replacement_ratio_pct', 0):.1f}% (net of tax)")
    if investment_result.get("pension_match_optimisation"):
        match = investment_result["pension_match_optimisation"]
        free = match["free_money_left_on_table"]
        roi = match.get("roi_per_pound", 0)
        print(f"  Employer match gap: £{free:,.0f}/year (ROI: £{roi:.2f} per £1)")
    fees = investment_result.get("fee_analysis", {})
    if fees.get("fee_drag_over_term", 0) > 0:
        print(f"  Fee drag:           {fees['fee_drag_over_term']:,.0f} over term")

    # ------------------------------------------------------------------
    # 7. Mortgage readiness (T1-1: student loan DTI weighting)
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
    # 8. Insurance gap assessment (T1-1: pension cross-reference)
    # ------------------------------------------------------------------
    print("\nAssessing insurance coverage...")
    insurance_result = assess_insurance(profile, assumptions, cashflow, mortgage_result, investment_result)
    print(f"  Overall:            {insurance_result.get('overall_assessment', 'unknown')}")
    print(f"  Gaps identified:    {insurance_result.get('gap_count', 0)}")
    pcr = insurance_result.get("pension_cross_reference", {})
    if pcr.get("coverage_adjusted"):
        print(f"  Pension-adjusted:   Yes (pension replacement only {pcr.get('pension_replacement_pct', 0):.0f}%)")

    # ------------------------------------------------------------------
    # 9. Life event simulation (T1-1: milestones)
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
    milestones = life_event_result.get("milestones", [])
    if milestones:
        print(f"  Milestones:         {len(milestones)} detected")
        for ms in milestones[:3]:
            print(f"    Year {ms['year']}: {ms['message']}")

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
    estate_result = analyse_estate(profile, assumptions, investment_result, mortgage_result, cashflow)
    print(f"  Projected estate:   {estate_result.get('projected_estate_value', 0):,.0f}")
    print(f"  IHT liability:      {estate_result.get('iht_liability', 0):,.0f}")
    planning = estate_result.get("estate_planning", {})
    if planning.get("actions"):
        print(f"  Planning actions:   {len(planning['actions'])}")
    suggestions = estate_result.get("optimisation_suggestions", [])
    if suggestions:
        print(f"  IHT optimisations:  {len(suggestions)}")
        savings = estate_result.get("estimated_tax_savings", 0)
        if savings > 0:
            print(f"  Potential savings:  {savings:,.0f}")
    gift = estate_result.get("gift_analysis", {})
    pets = gift.get("total_pets_outstanding", 0)
    if pets > 0:
        print(f"  PETs outstanding:   {pets:,.0f}")

    # ------------------------------------------------------------------
    # 13. Sensitivity analysis (T1-4)
    # ------------------------------------------------------------------
    print("\nRunning sensitivity analysis...")
    sensitivity_result = run_sensitivity(
        profile, assumptions, cashflow, debt_result,
        investment_result, mortgage_result,
    )
    for category, scenarios in sensitivity_result.get("scenarios", {}).items():
        if scenarios:
            print(f"  {category}:")
            for s in scenarios[:2]:
                print(f"    {s['label']}")

    # ------------------------------------------------------------------
    # 13b. Lifetime cashflow projection (v8.2)
    # ------------------------------------------------------------------
    from engine.lifetime_cashflow import project_lifetime_cashflow
    lifetime_cf = project_lifetime_cashflow(
        profile, assumptions, cashflow, investment_result, mortgage_result,
    )
    lcf_summary = lifetime_cf.get("summary", {})
    if lcf_summary.get("fund_depletion_age"):
        print(f"\nLifetime cashflow: funds deplete at age {lcf_summary['fund_depletion_age']}")
    else:
        print(f"\nLifetime cashflow: funds last to age {lcf_summary.get('life_expectancy', '?')}")

    # ------------------------------------------------------------------
    # 13c. Withdrawal sequencing (v8.3)
    # ------------------------------------------------------------------
    from engine.withdrawal import model_withdrawal_sequence
    withdrawal_result = model_withdrawal_sequence(profile, assumptions, investment_result)
    ws = withdrawal_result
    print(f"\nWithdrawal sequencing: lifetime tax saving £{ws.get('lifetime_tax_saving', 0):,.0f}")

    # ------------------------------------------------------------------
    # 14. Advisor insights (T1-2, T1-3)
    # ------------------------------------------------------------------
    print("\nGenerating advisor insights...")
    insights_result = generate_insights(
        profile, assumptions, cashflow, debt_result,
        goal_result, investment_result, mortgage_result,
        scoring_result, life_event_result,
        estate_analysis=estate_result,
    )

    # Print executive summary
    print(f"\n{'=' * 60}")
    print("EXECUTIVE SUMMARY")
    print(f"{'=' * 60}")
    print(insights_result.get("executive_summary", ""))

    # T1-3: Print surplus deployment plan
    surplus_plan = insights_result.get("surplus_deployment_plan", {})
    if surplus_plan.get("applicable"):
        print(f"\n{'=' * 60}")
        print("SURPLUS DEPLOYMENT PLAN")
        print(f"{'=' * 60}")
        for i, use in enumerate(surplus_plan.get("deployment_order", []), 1):
            alloc = use.get("allocated_monthly", 0)
            ret = use.get("effective_return_pct", 0)
            guaranteed = " (guaranteed)" if use.get("guaranteed") else ""
            print(f"  {i}. {use['action']}")
            print(f"     Return: {ret:.1f}%{guaranteed} | Allocated: £{alloc:,.0f}/mo")
        for do_not in surplus_plan.get("do_not_overpay", []):
            print(f"  x {do_not['action']}")

    # v5.2-06: Print subscription insight (only when bank CSV merge ran)
    sub_insight = insights_result.get("subscription_insights", {})
    if sub_insight.get("applicable"):
        print(f"\n{'=' * 60}")
        print("SUBSCRIPTIONS")
        print(f"{'=' * 60}")
        for msg in sub_insight.get("messages", []):
            print(f"  {msg}")

    # v5.2-09: Print expense micro-insights
    micro = insights_result.get("expense_micro_insights", {})
    if micro.get("applicable") and micro.get("messages"):
        print(f"\n{'=' * 60}")
        print("EXPENSE INSIGHTS")
        print(f"{'=' * 60}")
        for msg in micro["messages"]:
            print(f"  - {msg}")
        trends = micro.get("trends", {})
        if trends:
            for cat, direction in trends.items():
                if direction != "rising":
                    print(f"  - '{cat}' spending is {direction}")

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
    # 15. Assemble and save report
    # ------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    output_path = project_root / "outputs" / "report.json"

    assumptions_meta = {
        "schema_version": assumptions.get("schema_version", 0),
        "tax_year": assumptions.get("tax_year", "unknown"),
        "effective_from": assumptions.get("effective_from", ""),
        "effective_to": assumptions.get("effective_to", ""),
    }

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
        sensitivity=sensitivity_result,
        assumptions_meta=assumptions_meta,
        lifetime_cashflow=lifetime_cf,
        withdrawal_sequence=withdrawal_result,
        risk_profiling=risk_profile_result,
    )

    saved_path = save_report(report, output_path)
    logger.info("Report saved to %s", saved_path)
    print(f"\nReport saved to: {saved_path}")

    # v5.2-05: persist this run to the history DB unless suppressed
    if not args.no_history:
        try:
            run_id = record_run(
                report,
                history_db_path,
                profile=profile,
                profile_path=profile_path,
            )
            print(f"Run recorded in history: id={run_id} (db: {history_db_path})")
            previous = latest_two_runs(history_db_path, profile_name=name)
            if previous and previous[0] != run_id and previous[1] == run_id:
                diff = diff_runs(history_db_path, previous[0], previous[1])
                _print_diff_summary(diff)
        except HistoryError as e:
            logger.warning("Could not record run history: %s", e)
            print(f"Warning: history not recorded ({e})")

    # T3-1: Generate narrative report
    narrative_path = project_root / "outputs" / "report.md"
    narrative = generate_narrative(report)
    narrative_path.parent.mkdir(parents=True, exist_ok=True)
    narrative_path.write_text(narrative, encoding="utf-8")
    logger.info("Narrative report saved to %s", narrative_path)
    logger.info("Engine run complete — score: %s", scoring_result.get("overall_score", "N/A"))
    print(f"Narrative report: {narrative_path}")
    print("Done.")


def _show_history(db_path: Path, limit: int, profile_name: str | None) -> None:
    """List recent runs from the history DB to stdout."""
    print(f"History DB: {db_path}")
    print("=" * 60)
    try:
        runs = list_runs(db_path, limit=limit, profile_name=profile_name)
    except HistoryError as e:
        print(f"Error: {e}")
        return
    if not runs:
        print("No runs recorded yet. Run the engine to create the first entry.")
        return
    header = f"{'ID':>4}  {'Timestamp':<25}  {'Profile':<20}  {'Score':>6}  {'Grade':<5}  {'Surplus/mo':>12}"
    print(header)
    print("-" * len(header))
    for r in runs:
        score = r.get("overall_score") or 0
        surplus = r.get("surplus_monthly") or 0
        ts = (r.get("timestamp") or "")[:25]
        name = (r.get("profile_name") or "-")[:20]
        grade = r.get("grade") or "-"
        print(f"{r['id']:>4}  {ts:<25}  {name:<20}  {score:>6.0f}  {grade:<5}  {surplus:>12,.0f}")


def _show_diff(db_path: Path, diff_args: list[int], profile_name: str | None) -> None:
    """Render a structured diff between two runs to stdout."""
    print(f"History DB: {db_path}")
    print("=" * 60)
    try:
        if not diff_args:
            pair = latest_two_runs(db_path, profile_name=profile_name)
            if pair is None:
                print("Need at least two recorded runs to diff.")
                return
            old_id, new_id = pair
        elif len(diff_args) == 2:
            old_id, new_id = diff_args
        else:
            print("Usage: --diff [OLD_ID NEW_ID]  (omit ids for the latest pair)")
            return
        diff = diff_runs(db_path, old_id, new_id)
    except HistoryError as e:
        print(f"Error: {e}")
        return

    print(f"From: run {diff['from']['id']} at {diff['from']['timestamp']}")
    print(f"To:   run {diff['to']['id']} at {diff['to']['timestamp']}")
    print()
    _print_diff_summary(diff)
    print()
    print("Numeric changes:")
    for field, vals in diff["numeric"].items():
        old, new, delta = vals.get("old"), vals.get("new"), vals.get("delta")
        pct = vals.get("delta_pct")
        pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
        if delta is None:
            print(f"  {field:<28} {old} -> {new}")
        else:
            print(f"  {field:<28} {old} -> {new}  delta {delta:+}{pct_str}")
    cat_changes = [(f, v) for f, v in diff["categorical"].items() if v.get("changed")]
    if cat_changes:
        print("\nCategorical changes:")
        for field, vals in cat_changes:
            print(f"  {field:<28} {vals['old']} -> {vals['new']}")


def _print_diff_summary(diff: dict) -> None:
    """One-line headline diff summary used by --diff and post-run reporting."""
    summary = diff.get("summary", {})
    direction = summary.get("direction", "unchanged")
    score_delta = summary.get("score_delta")
    parts = [f"Direction: {direction}"]
    if score_delta is not None:
        parts.append(f"score delta {score_delta:+}")
    if summary.get("surplus_delta") is not None:
        parts.append(f"surplus delta {summary['surplus_delta']:+,.0f}")
    if summary.get("net_worth_delta") is not None:
        parts.append(f"net worth delta {summary['net_worth_delta']:+,.0f}")
    if summary.get("debt_delta") is not None:
        parts.append(f"debt delta {summary['debt_delta']:+,.0f}")
    if summary.get("grade_changed"):
        parts.append("grade changed")
    print("  " + " | ".join(parts))


def _run_assumption_update(assumptions_path_arg: Path | None) -> None:
    """Fetch latest data from public sources, apply updates, report changes."""
    from engine.assumption_updater import run_update, save_assumptions_yaml
    from engine.loader import load_assumptions

    project_root = Path(__file__).resolve().parent
    assumptions_path = assumptions_path_arg or project_root / "config" / "assumptions.yaml"

    print(f"Loading assumptions: {assumptions_path}")
    assumptions = load_assumptions(assumptions_path)

    print("Fetching latest data from public sources...")
    result = run_update(assumptions)

    if result.errors:
        print(f"\n  Fetch errors ({len(result.errors)}):")
        for err in result.errors:
            print(f"    - {err}")

    if result.changes:
        print(f"\n  Changes applied ({len(result.changes)}):")
        for c in result.changes:
            print(f"    {c.key_path}: {c.old_value} -> {c.new_value}  (source: {c.source})")
        save_assumptions_yaml(assumptions, str(assumptions_path))
        print(f"\n  Updated assumptions written to {assumptions_path}")
    else:
        print("\n  No changes needed -- assumptions are up to date.")


def _run_csv_preview(csv_path: Path) -> None:
    """Parse a bank CSV and print a YAML-formatted expenses preview to stdout."""
    print(f"Importing bank CSV: {csv_path}")
    print("=" * 60)
    result = import_bank_csv(csv_path)
    summary = result["summary"]
    print(f"  Bank format:        {summary.get('bank', 'unknown')}")
    print(f"  Transactions:       {summary['transactions_parsed']}")
    print(f"  Outflows:           {summary['outflow_count']}")
    print(f"  Inflows:            {summary['inflow_count']}")
    print(f"  Uncategorised:      {summary['uncategorised_count']}")
    if summary.get("subscription_count"):
        print(f"  Subscriptions:      {summary['subscription_count']} ({summary.get('subscription_monthly_total', 0):,.2f}/mo)")
    if summary.get("committed_outflow_count"):
        print(f"  DD/SO committed:    {summary['committed_outflow_count']} ({summary.get('committed_outflow_monthly_total', 0):,.2f}/mo)")
    if summary.get("date_range"):
        dr = summary["date_range"]
        print(f"  Date range:         {dr['start']} to {dr['end']}")
    print(f"  Months covered:     {summary.get('months_covered', 1)}")
    print(f"\n{'=' * 60}")
    print("Generated expenses block (paste into your profile YAML):")
    print(f"{'=' * 60}\n")
    print(yaml.safe_dump({"expenses": result["expenses"]}, sort_keys=False, default_flow_style=False))


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
    parser.add_argument(
        "--import-csv",
        type=Path,
        default=None,
        help="Parse a bank statement CSV and print a profile-compatible expenses preview",
    )
    parser.add_argument(
        "--bank-csv",
        type=Path,
        default=None,
        help="Bank statement CSV to merge into the profile before running the full pipeline",
    )
    parser.add_argument(
        "--bank-csv-override",
        action="store_true",
        default=False,
        help="When merging bank CSV, replace profile expense values instead of taking the maximum",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        default=False,
        help="List recent runs from the history database and exit",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=10,
        help="Maximum runs to show with --history (default: 10)",
    )
    parser.add_argument(
        "--history-profile",
        type=str,
        default=None,
        help="Filter --history and --diff by profile name",
    )
    parser.add_argument(
        "--history-db",
        type=Path,
        default=None,
        help="Path to the history SQLite DB (default: outputs/history.db)",
    )
    parser.add_argument(
        "--diff",
        nargs="*",
        type=int,
        default=None,
        help="Diff two history runs by id (e.g. --diff 3 7); with no ids, diffs the latest pair",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        default=False,
        help="Do not record this run in the history database",
    )
    parser.add_argument(
        "--update-assumptions",
        action="store_true",
        default=False,
        help="Fetch latest BoE base rate and ONS CPI, update assumptions, and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose console logging (DEBUG level)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
