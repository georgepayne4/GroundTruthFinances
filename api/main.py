"""api/main.py — FastAPI application for the GroundTruth engine (v5.3-05).

Exposes the engine as a stateless REST API with:
  - Per-user API key authentication
  - User-scoped data isolation
  - Audit logging middleware
  - Rate limiting (simple in-memory token bucket)
  - Admin endpoints for user and assumption management
  - Report export (PDF, CSV, XLSX)

Run with:  uvicorn api.main:app --reload
"""

from __future__ import annotations

import io
import json
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

import yaml
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from api.database import crud
from api.database.models import User
from api.database.session import get_db, init_db
from api.dependencies import (
    generate_api_key,
    get_current_user,
    get_default_assumptions_path,
    hash_api_key,
    require_admin,
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


# ---------------------------------------------------------------------------
# Rate limiter (simple in-memory token bucket, per-user)
# ---------------------------------------------------------------------------

_RATE_LIMIT_RPM = int(__import__("os").environ.get("GROUNDTRUTH_RATE_LIMIT_RPM", "60"))
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(key: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    window = 60.0
    bucket = _rate_buckets[key]
    _rate_buckets[key] = [t for t in bucket if now - t < window]
    if len(_rate_buckets[key]) >= _RATE_LIMIT_RPM:
        return False
    _rate_buckets[key].append(now)
    return True


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup (dev/test mode)."""
    init_db()
    yield


app = FastAPI(
    title="GroundTruth Financial Planning API",
    version="6.0.0",
    description="Advisor-grade UK financial planning engine.",
    responses={401: {"model": ErrorResponse}},
    lifespan=lifespan,
)

_CORS_ORIGINS = [
    o.strip()
    for o in __import__("os").environ.get(
        "GROUNDTRUTH_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Banking router (v6.0-02)
from api.banking.router import router as banking_router
app.include_router(banking_router)

# WebSocket router (v6.0-03)
from api.websocket import router as ws_router
app.include_router(ws_router)

# What-If Explorer router (v6.0-04)
from api.whatif import router as whatif_router
app.include_router(whatif_router)


# ---------------------------------------------------------------------------
# Middleware: audit logging + rate limiting
# ---------------------------------------------------------------------------

@app.middleware("http")
async def audit_and_rate_limit(request: Request, call_next) -> Response:
    """Log every API call and enforce per-user rate limits."""
    # Skip docs/openapi
    path = request.url.path
    if path in ("/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    # Rate limit by API key (or IP if no key)
    api_key = request.headers.get("X-API-Key", "")
    rate_key = api_key or request.client.host if request.client else "unknown"

    if not _check_rate_limit(rate_key):
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded ({_RATE_LIMIT_RPM} requests/minute)"},
        )

    response = await call_next(request)

    # Audit log (best-effort, don't fail the request if DB is unavailable)
    try:
        from api.database.session import _get_session_factory
        factory = _get_session_factory()
        db = factory()
        try:
            user_id = None
            if api_key:
                user = crud.get_user_by_key_hash(db, hash_api_key(api_key))
                if user:
                    user_id = user.id
            crud.log_audit(db, user_id=user_id, endpoint=path, method=request.method, status_code=response.status_code)
        finally:
            db.close()
    except Exception:
        logger.debug("Audit log write failed (non-fatal)")

    return response


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/analyse",
    response_model=AnalyseResponse,
    summary="Run full analysis pipeline",
)
async def analyse(
    request: AnalyseRequest,
    user: User | None = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> AnalyseResponse:
    """Accept a JSON profile, run the full 15-stage pipeline, return the report."""
    from engine.pipeline import run_pipeline

    report, profile, _flags = run_pipeline(
        request.profile,
        assumptions_override=request.assumptions,
        assumptions_path=get_default_assumptions_path(),
    )
    run_id = None
    try:
        run_id = crud.record_run(db, report, profile=profile)
    except Exception:
        logger.warning("Could not record run in database")
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
    from engine.loader import load_assumptions, normalise_profile
    from engine.validator import validate_profile

    profile = normalise_profile(request.profile)
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
# Profile management (user-scoped in v5.3-04)
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/profiles",
    response_model=ProfileResponse,
    summary="Create or update a named profile",
)
async def create_profile(
    request: ProfileCreateRequest,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Store a profile in the database. In production, scoped to the authenticated user."""
    if user is not None:
        target_user = user
    else:
        # Dev mode: create/get user from request email
        target_user = crud.get_or_create_user(db, email=request.user_email, name=request.user_name)

    yaml_content = yaml.dump(request.profile, default_flow_style=False)
    profile = crud.create_profile(db, user_id=target_user.id, name=request.profile_name, yaml_content=yaml_content)
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
    summary="List profiles for the authenticated user",
)
async def list_profiles(
    user: User | None = Depends(get_current_user),
    user_email: str | None = Query(None, description="User email (dev mode only)"),
    db: Session = Depends(get_db),
) -> list[ProfileResponse]:
    """Return all profiles belonging to the authenticated user."""
    if user is not None:
        target_user = user
    elif user_email:
        target_user = crud.get_user_by_email(db, email=user_email)
        if target_user is None:
            return []
    else:
        return []

    profiles = crud.list_profiles(db, user_id=target_user.id)
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
# History (user-scoped in v5.3-04)
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
# Export endpoints (v5.3-05)
# ---------------------------------------------------------------------------

def _get_run_report(db: Session, run_id: int) -> dict[str, Any]:
    """Fetch a run and parse its stored JSON report. Raises 404 if missing."""
    run = crud.get_run(db, run_id)
    if run is None or not run.full_report_json:
        raise HTTPException(status_code=404, detail="Run not found")
    return json.loads(run.full_report_json)


@app.get(
    "/api/v1/export/{run_id}/csv",
    summary="Export run metrics as CSV",
    dependencies=[Depends(verify_api_key)],
)
async def export_csv(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Return key metrics from a run as a downloadable CSV file."""
    from api.exports import generate_csv

    report = _get_run_report(db, run_id)
    csv_content = generate_csv(report)
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{run_id}.csv"},
    )


@app.get(
    "/api/v1/export/{run_id}/xlsx",
    summary="Export run as Excel workbook",
    dependencies=[Depends(verify_api_key)],
)
async def export_xlsx(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Return a multi-sheet Excel workbook for a run."""
    from api.exports import generate_xlsx

    report = _get_run_report(db, run_id)
    xlsx_bytes = generate_xlsx(report)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=report_{run_id}.xlsx"},
    )


@app.get(
    "/api/v1/export/{run_id}/pdf",
    summary="Export run as PDF report",
    dependencies=[Depends(verify_api_key)],
)
async def export_pdf(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Return a formatted PDF of the narrative report.

    Requires weasyprint and markdown packages on the server.
    Returns 501 if PDF generation dependencies are not installed.
    """
    from api.exports import generate_pdf

    report = _get_run_report(db, run_id)
    try:
        pdf_bytes = generate_pdf(report)
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="PDF export requires 'weasyprint' and 'markdown' packages",
        ) from exc
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{run_id}.pdf"},
    )


# ---------------------------------------------------------------------------
# Admin endpoints (v5.3-04)
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/admin/users",
    summary="Register a new user and generate an API key (admin only)",
)
async def admin_create_user(
    email: str = Query(...),
    name: str | None = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a user and return their API key. The key is shown once."""
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    user = crud.get_or_create_user(db, email=email, name=name, api_key_hash=key_hash)
    if user.api_key_hash != key_hash:
        crud.set_user_api_key(db, user.id, key_hash)
    return {
        "user_id": user.id,
        "email": user.email,
        "api_key": raw_key,
        "warning": "Store this key securely. It cannot be retrieved later.",
    }


@app.get(
    "/api/v1/admin/audit",
    summary="View recent audit log entries (admin only)",
)
async def admin_audit_log(
    limit: int = Query(50, ge=1, le=500),
    user_id: int | None = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent audit log entries."""
    entries = crud.list_audit_log(db, limit=limit, user_id=user_id)
    return {"entries": entries, "count": len(entries)}


