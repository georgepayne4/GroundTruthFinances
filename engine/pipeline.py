"""engine/pipeline.py — Shared analysis pipeline (v6.0-00).

Single entry point for the full 15-stage analysis pipeline, used by both
the CLI (main.py) and the API (api/main.py). No DB or API dependencies.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.estate import analyse_estate
from engine.exceptions import AssumptionError
from engine.goals import analyse_goals
from engine.insights import generate_insights
from engine.insurance import assess_insurance
from engine.investments import analyse_investments
from engine.life_events import simulate_life_events
from engine.lifetime_cashflow import project_lifetime_cashflow
from engine.loader import load_assumptions, normalise_profile
from engine.mortgage import analyse_mortgage
from engine.report import assemble_report
from engine.risk_profiling import assess_risk_profiles
from engine.scenarios import run_scenarios
from engine.scoring import calculate_scores
from engine.sensitivity import run_sensitivity
from engine.validator import validate_profile
from engine.withdrawal import model_withdrawal_sequence

logger = logging.getLogger(__name__)


def _check_assumptions_staleness(assumptions: dict[str, Any]) -> None:
    """Block analysis if assumptions have expired (v7.6).

    Only enforced when GROUNDTRUTH_ENV=production. In development, logs a warning.
    """
    effective_to = assumptions.get("effective_to", "")
    if not effective_to:
        return
    try:
        end_date = date.fromisoformat(effective_to)
    except (ValueError, TypeError):
        return
    if date.today() <= end_date:
        return

    env = os.environ.get("GROUNDTRUTH_ENV", "development")
    tax_year = assumptions.get("tax_year", "unknown")
    msg = f"Assumptions expired (tax year {tax_year}, effective_to {effective_to})"
    if env == "production":
        raise AssumptionError(msg + " — update assumptions before running analysis")
    logger.warning("%s — running in dev mode, proceeding anyway", msg)


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

    _check_assumptions_staleness(assumptions)

    flags = validate_profile(profile, assumptions)
    flag_dicts = [f.to_dict() for f in flags]

    cashflow = analyse_cashflow(profile, assumptions)
    debt_result = analyse_debt(profile, assumptions)
    goal_result = analyse_goals(profile, assumptions, cashflow, debt_result)
    risk_profile_result = assess_risk_profiles(profile, assumptions, cashflow, goal_result)
    investment_result = analyse_investments(profile, assumptions, cashflow, goal_result, risk_profile_result)
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
    lifetime_cf = project_lifetime_cashflow(
        profile, assumptions, cashflow, investment_result, mortgage_result,
    )
    withdrawal_result = model_withdrawal_sequence(profile, assumptions, investment_result)
    sensitivity_result = run_sensitivity(
        profile, assumptions, cashflow, debt_result,
        investment_result, mortgage_result,
    )
    insights_result = generate_insights(
        profile, assumptions, cashflow, debt_result,
        goal_result, investment_result, mortgage_result,
        scoring_result, life_event_result,
        estate_analysis=estate_result,
        scenarios=scenario_result,
    )

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

    return report, profile, flags
