"""api/database/crud.py — Database operations for the GroundTruth API (v5.3-02).

Pure functions that accept a SQLAlchemy Session and return model instances
or dicts. No business logic — just persistence.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.database.models import Assumption, Profile, Report, Run, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_or_create_user(db: Session, email: str, name: str | None = None) -> User:
    """Return existing user by email, or create a new one."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created user %d (%s)", user.id, email)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def create_profile(db: Session, user_id: int, name: str, yaml_content: str) -> Profile:
    """Create or update a named profile for a user."""
    existing = (
        db.query(Profile)
        .filter(Profile.user_id == user_id, Profile.name == name)
        .first()
    )
    if existing:
        existing.yaml_content = yaml_content
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    profile = Profile(user_id=user_id, name=name, yaml_content=yaml_content)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_profile(db: Session, profile_id: int) -> Profile | None:
    return db.query(Profile).filter(Profile.id == profile_id).first()


def list_profiles(db: Session, user_id: int) -> list[Profile]:
    return db.query(Profile).filter(Profile.user_id == user_id).order_by(Profile.updated_at.desc()).all()


def delete_profile(db: Session, profile_id: int) -> bool:
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        return False
    db.delete(profile)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def store_report(
    db: Session,
    profile_id: int,
    report: dict[str, Any],
) -> Report:
    """Persist a full report JSON and extracted metadata."""
    scoring = report.get("scoring", {})
    row = Report(
        profile_id=profile_id,
        json_content=json.dumps(report, default=str),
        overall_score=scoring.get("overall_score"),
        grade=scoring.get("grade"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_report(db: Session, report_id: int) -> Report | None:
    return db.query(Report).filter(Report.id == report_id).first()


def list_reports(db: Session, profile_id: int, limit: int = 10) -> list[Report]:
    return (
        db.query(Report)
        .filter(Report.profile_id == profile_id)
        .order_by(Report.generated_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------

def store_assumptions(db: Session, tax_year: str, yaml_content: str, effective_from: str | None = None, effective_to: str | None = None) -> Assumption:
    """Upsert an assumption set for a given tax year."""
    existing = db.query(Assumption).filter(Assumption.tax_year == tax_year).first()
    if existing:
        existing.yaml_content = yaml_content
        existing.effective_from = effective_from
        existing.effective_to = effective_to
        db.commit()
        db.refresh(existing)
        return existing

    row = Assumption(tax_year=tax_year, yaml_content=yaml_content, effective_from=effective_from, effective_to=effective_to)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_assumptions(db: Session) -> Assumption | None:
    return db.query(Assumption).order_by(Assumption.created_at.desc()).first()


# ---------------------------------------------------------------------------
# Runs (migrated from v5.2-05 SQLite history)
# ---------------------------------------------------------------------------

def record_run(
    db: Session,
    report: dict[str, Any],
    profile: dict[str, Any] | None = None,
    profile_path: str | None = None,
) -> int:
    """Persist a run snapshot. Returns the new row id.

    Mirrors engine/history.py record_run() but uses SQLAlchemy.
    """
    from engine.history import _extract_metrics

    metrics = _extract_metrics(report, profile)
    row = Run(
        timestamp=metrics["timestamp"],
        profile_name=metrics["profile_name"],
        profile_path=profile_path,
        overall_score=metrics["overall_score"],
        grade=metrics["grade"],
        surplus_monthly=metrics["surplus_monthly"],
        net_worth=metrics["net_worth"],
        debt_total=metrics["debt_total"],
        savings_rate_pct=metrics["savings_rate_pct"],
        pension_replacement_pct=metrics["pension_replacement_pct"],
        emergency_fund_months=metrics["emergency_fund_months"],
        goals_on_track=metrics["goals_on_track"],
        goals_at_risk=metrics["goals_at_risk"],
        goals_unreachable=metrics["goals_unreachable"],
        high_interest_debt_count=metrics["high_interest_debt_count"],
        mortgage_readiness=metrics["mortgage_readiness"],
        full_report_json=json.dumps(report, default=str),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("Recorded run %d for profile %s", row.id, metrics["profile_name"])
    return row.id


def list_runs(db: Session, limit: int = 10, profile_name: str | None = None) -> list[dict[str, Any]]:
    """Return recent runs as dicts (newest first)."""
    query = db.query(Run)
    if profile_name:
        query = query.filter(Run.profile_name == profile_name)
    rows = query.order_by(Run.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "profile_name": r.profile_name,
            "overall_score": r.overall_score,
            "grade": r.grade,
            "surplus_monthly": r.surplus_monthly,
            "net_worth": r.net_worth,
            "debt_total": r.debt_total,
            "savings_rate_pct": r.savings_rate_pct,
            "pension_replacement_pct": r.pension_replacement_pct,
            "emergency_fund_months": r.emergency_fund_months,
            "goals_on_track": r.goals_on_track,
            "goals_at_risk": r.goals_at_risk,
        }
        for r in rows
    ]
