"""Integration test — run the full pipeline with sample_input.yaml."""

from __future__ import annotations

from pathlib import Path

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.estate import analyse_estate
from engine.goals import analyse_goals
from engine.insights import generate_insights
from engine.insurance import assess_insurance
from engine.investments import analyse_investments
from engine.life_events import simulate_life_events
from engine.loader import load_assumptions, load_profile
from engine.mortgage import analyse_mortgage
from engine.narrative import generate_narrative
from engine.report import assemble_report
from engine.scenarios import run_scenarios
from engine.scoring import calculate_scores
from engine.sensitivity import run_sensitivity
from engine.validator import Severity, validate_profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_full_pipeline():
    """Run the entire analysis pipeline end-to-end with sample data."""
    profile = load_profile(PROJECT_ROOT / "config" / "sample_input.yaml")
    assumptions = load_assumptions(PROJECT_ROOT / "config" / "assumptions.yaml")

    flags = validate_profile(profile, assumptions)
    errors = [f for f in flags if f.severity == Severity.ERROR]
    assert len(errors) == 0, f"Validation errors: {[e.message for e in errors]}"

    cashflow = analyse_cashflow(profile, assumptions)
    assert cashflow["net_income"]["monthly"] > 0

    debt_result = analyse_debt(profile, assumptions)
    goal_result = analyse_goals(profile, assumptions, cashflow, debt_result)
    investment_result = analyse_investments(profile, assumptions, cashflow)
    mortgage_result = analyse_mortgage(profile, assumptions, cashflow, debt_result)
    insurance_result = assess_insurance(profile, assumptions, cashflow, mortgage_result, investment_result)
    life_event_result = simulate_life_events(profile, assumptions, cashflow)
    scoring_result = calculate_scores(
        profile, assumptions, cashflow, debt_result,
        goal_result, investment_result, mortgage_result,
    )
    scenario_result = run_scenarios(
        profile, assumptions, cashflow, debt_result,
        mortgage_result, investment_result,
    )
    estate_result = analyse_estate(profile, assumptions, investment_result, mortgage_result, cashflow)
    sensitivity_result = run_sensitivity(
        profile, assumptions, cashflow, debt_result,
        investment_result, mortgage_result,
    )
    insights_result = generate_insights(
        profile, assumptions, cashflow, debt_result,
        goal_result, investment_result, mortgage_result,
        scoring_result, life_event_result,
    )

    report = assemble_report(
        profile=profile,
        validation_flags=[f.to_dict() for f in flags],
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
    )

    assert report["meta"]["engine_version"] is not None
    assert 0 <= report["scoring"]["overall_score"] <= 100

    narrative = generate_narrative(report)
    assert len(narrative) > 100
    assert "Financial Health" in narrative
