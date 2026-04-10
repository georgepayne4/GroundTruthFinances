"""api/database/crud.py — Database operations for the GroundTruth API (v5.3-04).

Pure functions that accept a SQLAlchemy Session and return model instances
or dicts. No business logic — just persistence.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.database.models import Assumption, AuditLog, Profile, Report, Run, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profile encryption at rest (v7.3)
# ---------------------------------------------------------------------------

def _encrypt_profile(plaintext: str) -> str:
    """Encrypt profile YAML if encryption key is configured. Returns plaintext otherwise."""
    try:
        from api.banking.encryption import encrypt_token
        return encrypt_token(plaintext)
    except (RuntimeError, ImportError):
        return plaintext


def _decrypt_profile(stored: str) -> str:
    """Decrypt profile YAML if it looks encrypted. Returns as-is if plaintext."""
    if not stored or stored.startswith(("personal:", "---", "#")):
        return stored  # Already plaintext YAML
    try:
        from api.banking.encryption import decrypt_token
        return decrypt_token(stored)
    except (RuntimeError, ImportError, Exception):
        return stored  # Assume plaintext if decryption fails


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_or_create_user(db: Session, email: str, name: str | None = None, api_key_hash: str | None = None) -> User:
    """Return existing user by email, or create a new one."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, name=name, api_key_hash=api_key_hash)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created user %d (%s)", user.id, email)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_key_hash(db: Session, key_hash: str) -> User | None:
    return db.query(User).filter(User.api_key_hash == key_hash).first()


def set_user_api_key(db: Session, user_id: int, api_key_hash: str) -> User | None:
    """Set the API key hash for a user. Returns the updated user or None."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None
    user.api_key_hash = api_key_hash
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def create_profile(db: Session, user_id: int, name: str, yaml_content: str) -> Profile:
    """Create or update a named profile for a user. Encrypts content at rest."""
    encrypted = _encrypt_profile(yaml_content)
    existing = (
        db.query(Profile)
        .filter(Profile.user_id == user_id, Profile.name == name)
        .first()
    )
    if existing:
        existing.yaml_content = encrypted
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    profile = Profile(user_id=user_id, name=name, yaml_content=encrypted)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_profile_content(profile: Profile) -> str:
    """Decrypt and return the YAML content from a profile."""
    return _decrypt_profile(profile.yaml_content)


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
    from engine.history import extract_metrics

    metrics = extract_metrics(report, profile)
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


def get_run(db: Session, run_id: int) -> Run | None:
    """Return a single run by ID, or None."""
    return db.query(Run).filter(Run.id == run_id).first()


def list_runs(
    db: Session, limit: int = 20, profile_name: str | None = None, cursor: int | None = None,
) -> list[dict[str, Any]]:
    """Return recent runs as dicts (newest first). Supports cursor-based pagination."""
    query = db.query(Run)
    if profile_name:
        query = query.filter(Run.profile_name == profile_name)
    if cursor is not None:
        query = query.filter(Run.id < cursor)
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


# ---------------------------------------------------------------------------
# Audit log (v5.3-04)
# ---------------------------------------------------------------------------

def log_audit(db: Session, user_id: int | None, endpoint: str, method: str, status_code: int | None = None) -> AuditLog:
    """Record an API call in the audit log."""
    entry = AuditLog(user_id=user_id, endpoint=endpoint, method=method, status_code=status_code)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_log(db: Session, limit: int = 50, user_id: int | None = None) -> list[dict[str, Any]]:
    """Return recent audit entries as dicts."""
    query = db.query(AuditLog)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    rows = query.order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "endpoint": r.endpoint,
            "method": r.method,
            "status_code": r.status_code,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]
