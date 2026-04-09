"""api/main.py — FastAPI application for the GroundTruth engine (v5.3-02).

Exposes the engine as a stateless REST API with optional database-backed
profile storage and run history.

Run with:  uvicorn api.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import yaml
from fastapi import Depends, FastAPI, Query
from sqlalchemy.orm import Session

from api.database import crud
from api.database.session import get_db, init_db
from api.dependencies import (
    get_default_assumptions_path,
    verify_api_key,
)
from api.models import (
    AnalyseRequest,
    AnalyseResponse,
    ErrorResponse,
    HistoryResponse,
    HistoryRun,
    ProfileCreateRequest,
    ProfileResponse,
    ValidateRequest,
    ValidateResponse,
    ValidationFlag,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup (dev/test mode)."""
    init_db()
    yield


app = FastAPI(
    title="GroundTruth Financial Planning API",
    version="5.3.2",
    description="Advisor-grade UK financial planning engine.",
    responses={401: {"model": ErrorResponse}},
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/analyse",
    response_model=AnalyseResponse,
    summary="Run full analysis pipeline",
    dependencies=[Depends(verify_api_key)],
)
async def analyse(
    request: AnalyseRequest,
    db: Session = Depends(get_db),
) -> AnalyseResponse:
    """Accept a JSON profile, run the full 15-stage pipeline, return the report."""
    report, _profile, run_id = _run_pipeline(request.profile, request.assumptions, db=db)
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


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/assumptions",
    summary="Return current server assumptions",
    dependencies=[Depends(verify_api_key)],
)
async def get_assumptions() -> dict[str, Any]:
    """Return the current assumptions YAML as a JSON dict."""
    from engine.loader import load_assumptions
    return load_assumptions(get_default_assumptions_path())


@app.post(
    "/api/v1/assumptions/update",
    summary="Fetch latest values from public data sources and update assumptions",
    dependencies=[Depends(verify_api_key)],
)
async def update_assumptions() -> dict[str, Any]:
    """Run the auto-update pipeline: fetch BoE base rate, ONS CPI, etc."""
    from engine.assumption_updater import run_update
    from engine.loader import load_assumptions

    assumptions = load_assumptions(get_default_assumptions_path())
    result = run_update(assumptions)

    return {
        "changes": [
            {
                "key": c.key_path,
                "old": c.old_value,
                "new": c.new_value,
                "source": c.source,
            }
            for c in result.changes
        ],
        "change_count": len(result.changes),
        "errors": result.errors,
        "source_date": result.source_date,
    }


# ---------------------------------------------------------------------------
# Profile management (new in v5.3-02)
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/profiles",
    response_model=ProfileResponse,
    summary="Create or update a named profile",
    dependencies=[Depends(verify_api_key)],
)
async def create_profile(
    request: ProfileCreateRequest,
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Store a profile in the database. Creates a default user if needed."""
    user = crud.get_or_create_user(db, email=request.user_email, name=request.user_name)
    yaml_content = yaml.dump(request.profile, default_flow_style=False)
    profile = crud.create_profile(db, user_id=user.id, name=request.profile_name, yaml_content=yaml_content)
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        name=profile.name,
        created_at=profile.created_at.isoformat() if profile.created_at else None,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
    )


@app.get(
    "/api/v1/profiles",
    response_model=list[ProfileResponse],
    summary="List profiles for a user",
    dependencies=[Depends(verify_api_key)],
)
async def list_profiles(
    user_email: str = Query(..., description="User email to list profiles for"),
    db: Session = Depends(get_db),
) -> list[ProfileResponse]:
    """Return all profiles belonging to a user."""
    user = crud.get_user_by_email(db, email=user_email)
    if user is None:
        return []
    profiles = crud.list_profiles(db, user_id=user.id)
    return [
        ProfileResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            created_at=p.created_at.isoformat() if p.created_at else None,
            updated_at=p.updated_at.isoformat() if p.updated_at else None,
        )
        for p in profiles
    ]


# ---------------------------------------------------------------------------
# History (now backed by SQLAlchemy)
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/history/{profile_name}",
    response_model=HistoryResponse,
    summary="List run history for a profile",
    dependencies=[Depends(verify_api_key)],
)
async def get_history(
    profile_name: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    """Return recent runs for the given profile name."""
    runs = crud.list_runs(db, limit=limit, profile_name=profile_name)
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
    db: Session = Depends(get_db),
) -> HistoryResponse:
    """Return recent runs across all profiles."""
    runs = crud.list_runs(db, limit=limit)
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
    db: Session | None = None,
) -> tuple[dict[str, Any], dict[str, Any], int | None]:
    """Run the full engine pipeline. Returns (report, profile, run_id)."""
    from engine.cashflow import analyse_cashflow
    from engine.debt import analyse_debt
    from engine.estate import analyse_estate
    from engine.goals import analyse_goals
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
    if db is not None:
        try:
            run_id = crud.record_run(db, report, profile=profile)
        except Exception:
            logger.warning("Could not record run in database")

    return report, profile, run_id
