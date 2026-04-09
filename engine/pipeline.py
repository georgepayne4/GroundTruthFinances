"""engine/pipeline.py — Shared analysis pipeline (v6.0-00).

Single entry point for the full 15-stage analysis pipeline, used by both
the CLI (main.py) and the API (api/main.py). No DB or API dependencies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.estate import analyse_estate
from engine.goals import analyse_goals
from engine.insights import generate_insights
from engine.insurance import assess_insurance
from engine.investments import analyse_investments
from engine.life_events import simulate_life_events
from engine.loader import load_assumptions, normalise_profile
from engine.mortgage import analyse_mortgage
from engine.report import assemble_report
from engine.scenarios import run_scenarios
from engine.scoring import calculate_scores
from engine.sensitivity import run_sensitivity
from engine.validator import validate_profile

logger = logging.getLogger(__name__)


def run_pipeline(
    raw_profile: dict[str, Any],
    assumptions_override: dict[str, Any] | None = None,
    assumptions_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    """Run the full engine pipeline.

    Returns (report, normalised_profile, validation_flags).
    Callers handle persistence (DB recording, file saving) themselves.
    """
    profile = normalise_profile(raw_profile)

    if assumptions_override:
        from engine.schemas import validate_assumptions
        validate_assumptions(assumptions_override)
        assumptions = assumptions_override
    else:
        path = assumptions_path or (Path(__file__).resolve().parent.parent / "config" / "assumptions.yaml")
        assumptions = load_assumptions(path)

    flags = validate_profile(profile, assumptions)
    flag_dicts = [f.to_dict() for f in flags]

    cashflow = analyse_cashflow(profile, assumptions)
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
    )

    return report, profile, flags
