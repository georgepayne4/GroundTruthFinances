"""api/main.py — FastAPI application for the GroundTruth engine (v5.3-01).

Exposes the engine as a stateless REST API. All financial analysis modules
are pure functions, so the API is trivially parallel.

Run with:  uvicorn api.main:app --reload
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, Query

from api.dependencies import (
    get_default_assumptions_path,
    get_default_history_db,
    verify_api_key,
)
from api.models import (
    AnalyseRequest,
    AnalyseResponse,
    ErrorResponse,
    HistoryResponse,
    HistoryRun,
    ValidateRequest,
    ValidateResponse,
    ValidationFlag,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="GroundTruth Financial Planning API",
    version="5.3.0",
    description="Advisor-grade UK financial planning engine.",
    responses={401: {"model": ErrorResponse}},
)


@app.post(
    "/api/v1/analyse",
    response_model=AnalyseResponse,
    summary="Run full analysis pipeline",
    dependencies=[Depends(verify_api_key)],
)
async def analyse(request: AnalyseRequest) -> AnalyseResponse:
    """Accept a JSON profile, run the full 15-stage pipeline, return the report."""
    report, _profile, run_id = _run_pipeline(request.profile, request.assumptions)
    scoring = report.get("scoring", {})
    meta = report.get("meta", {})
    return AnalyseResponse(
        profile_name=meta.get("profile_name"),
        overall_score=scoring.get("overall_score"),
        grade=scoring.get("grade"),
        report=report,
        run_id=run_id,
    )


@app.post(
    "/api/v1/validate",
    response_model=ValidateResponse,
    summary="Validate a profile without running the pipeline",
    dependencies=[Depends(verify_api_key)],
)
async def validate(request: ValidateRequest) -> ValidateResponse:
    """Validate a profile and return severity-graded flags."""
    from engine.loader import _normalise_profile, load_assumptions
    from engine.validator import validate_profile

    profile = _normalise_profile(request.profile)
    assumptions = load_assumptions(get_default_assumptions_path())
    flags = validate_profile(profile, assumptions)

    flag_dicts = [
        ValidationFlag(field=f.field, message=f.message, severity=f.severity.value)
        for f in flags
    ]
    errors = sum(1 for f in flags if f.severity.value == "error")
    warnings = sum(1 for f in flags if f.severity.value == "warning")
    infos = sum(1 for f in flags if f.severity.value == "info")

    return ValidateResponse(
        flags=flag_dicts,
        error_count=errors,
        warning_count=warnings,
        info_count=infos,
    )


@app.get(
    "/api/v1/assumptions",
    summary="Return current server assumptions",
    dependencies=[Depends(verify_api_key)],
)
async def get_assumptions() -> dict[str, Any]:
    """Return the current assumptions YAML as a JSON dict."""
    from engine.loader import load_assumptions
    return load_assumptions(get_default_assumptions_path())


@app.get(
    "/api/v1/history/{profile_name}",
    response_model=HistoryResponse,
    summary="List run history for a profile",
    dependencies=[Depends(verify_api_key)],
)
async def get_history(
    profile_name: str,
    limit: int = Query(10, ge=1, le=100),
) -> HistoryResponse:
    """Return recent runs for the given profile name."""
    from engine.history import HistoryError, list_runs

    db_path = get_default_history_db()
    try:
        runs = list_runs(db_path, limit=limit, profile_name=profile_name)
    except HistoryError:
        return HistoryResponse(runs=[], count=0)

    return HistoryResponse(
        runs=[HistoryRun(**r) for r in runs],
        count=len(runs),
    )


@app.get(
    "/api/v1/history",
    response_model=HistoryResponse,
    summary="List all recent runs",
    dependencies=[Depends(verify_api_key)],
)
async def get_all_history(
    limit: int = Query(10, ge=1, le=100),
) -> HistoryResponse:
    """Return recent runs across all profiles."""
    from engine.history import HistoryError, list_runs

    db_path = get_default_history_db()
    try:
        runs = list_runs(db_path, limit=limit)
    except HistoryError:
        return HistoryResponse(runs=[], count=0)

    return HistoryResponse(
        runs=[HistoryRun(**r) for r in runs],
        count=len(runs),
    )


# ---------------------------------------------------------------------------
# Pipeline runner — mirrors the logic in main.py without CLI print statements
# ---------------------------------------------------------------------------

def _run_pipeline(
    raw_profile: dict[str, Any],
    assumptions_override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], int | None]:
    """Run the full engine pipeline. Returns (report, profile, run_id)."""
    from engine.cashflow import analyse_cashflow
    from engine.debt import analyse_debt
    from engine.estate import analyse_estate
    from engine.goals import analyse_goals
    from engine.history import HistoryError, record_run
    from engine.insights import generate_insights
    from engine.insurance import assess_insurance
    from engine.investments import analyse_investments
    from engine.life_events import simulate_life_events
    from engine.loader import _normalise_profile, load_assumptions
    from engine.mortgage import analyse_mortgage
    from engine.report import assemble_report
    from engine.scenarios import run_scenarios
    from engine.scoring import calculate_scores
    from engine.sensitivity import run_sensitivity
    from engine.validator import validate_profile

    profile = _normalise_profile(raw_profile)

    if assumptions_override:
        from engine.schemas import validate_assumptions
        validate_assumptions(assumptions_override)
        assumptions = assumptions_override
    else:
        assumptions = load_assumptions(get_default_assumptions_path())

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

    run_id = None
    try:
        db_path = get_default_history_db()
        run_id = record_run(report, db_path, profile=profile)
    except HistoryError:
        logger.warning("Could not record run in history DB")

    return report, profile, run_id
