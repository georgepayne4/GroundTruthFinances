"""Tests for the SQLAlchemy database layer (v5.3-04)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database.models import Base

# Force in-memory SQLite for all tests
_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_TestSession = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def db():
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


def _sample_report() -> dict:
    return {
        "meta": {"profile_name": "Test User", "generated_at": "2026-04-09T10:00:00"},
        "scoring": {"overall_score": 72.5, "grade": "B"},
        "cashflow": {"surplus": {"monthly": 800}, "savings_rate": {"basic_pct": 15.0}},
        "debt": {"summary": {"total_balance": 5000, "high_interest_debt_count": 1}},
        "goals": {"summary": {"on_track": 2, "at_risk": 1, "unreachable": 0}},
        "investments": {"pension_analysis": {"income_replacement_ratio_pct": 45.0}},
        "mortgage": {"readiness": "ready"},
    }


def _sample_profile() -> dict:
    return {
        "personal": {"name": "Test User", "age": 30, "retirement_age": 67},
        "income": {"primary_gross_annual": 50000},
        "expenses": {"housing": {"rent_monthly": 1000}, "_total_monthly": 2000},
        "savings": {"emergency_fund": 6000, "pension_balance": 10000},
        "debts": [],
        "goals": [],
        "_net_worth": 16000,
    }


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

class TestUserCrud:
    def test_create_user(self, db: Session):
        from api.database.crud import get_or_create_user

        user = get_or_create_user(db, email="test@example.com", name="Test")
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.name == "Test"

    def test_get_or_create_returns_existing(self, db: Session):
        from api.database.crud import get_or_create_user

        u1 = get_or_create_user(db, email="test@example.com")
        u2 = get_or_create_user(db, email="test@example.com")
        assert u1.id == u2.id

    def test_get_user_by_email(self, db: Session):
        from api.database.crud import get_or_create_user, get_user_by_email

        get_or_create_user(db, email="find@me.com")
        found = get_user_by_email(db, email="find@me.com")
        assert found is not None
        assert found.email == "find@me.com"

    def test_get_user_by_email_missing(self, db: Session):
        from api.database.crud import get_user_by_email

        assert get_user_by_email(db, email="nope@nope.com") is None

    def test_get_user_by_id(self, db: Session):
        from api.database.crud import get_or_create_user, get_user_by_id

        user = get_or_create_user(db, email="id@test.com")
        found = get_user_by_id(db, user.id)
        assert found is not None
        assert found.email == "id@test.com"


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

class TestProfileCrud:
    def test_create_profile(self, db: Session):
        from api.database.crud import create_profile, get_or_create_user

        user = get_or_create_user(db, email="p@test.com")
        profile = create_profile(db, user_id=user.id, name="My Profile", yaml_content="income: 50000")
        assert profile.id is not None
        assert profile.name == "My Profile"
        assert profile.yaml_content == "income: 50000"

    def test_create_profile_upserts_on_same_name(self, db: Session):
        from api.database.crud import create_profile, get_or_create_user

        user = get_or_create_user(db, email="p@test.com")
        p1 = create_profile(db, user_id=user.id, name="Same", yaml_content="v1")
        p2 = create_profile(db, user_id=user.id, name="Same", yaml_content="v2")
        assert p1.id == p2.id
        assert p2.yaml_content == "v2"

    def test_list_profiles(self, db: Session):
        from api.database.crud import create_profile, get_or_create_user, list_profiles

        user = get_or_create_user(db, email="p@test.com")
        create_profile(db, user_id=user.id, name="A", yaml_content="a")
        create_profile(db, user_id=user.id, name="B", yaml_content="b")
        profiles = list_profiles(db, user_id=user.id)
        assert len(profiles) == 2

    def test_delete_profile(self, db: Session):
        from api.database.crud import create_profile, delete_profile, get_or_create_user, list_profiles

        user = get_or_create_user(db, email="p@test.com")
        p = create_profile(db, user_id=user.id, name="Del", yaml_content="x")
        assert delete_profile(db, p.id) is True
        assert list_profiles(db, user_id=user.id) == []

    def test_delete_nonexistent_returns_false(self, db: Session):
        from api.database.crud import delete_profile

        assert delete_profile(db, 9999) is False


# ---------------------------------------------------------------------------
# Report CRUD
# ---------------------------------------------------------------------------

class TestReportCrud:
    def test_store_and_retrieve_report(self, db: Session):
        from api.database.crud import create_profile, get_or_create_user, get_report, store_report

        user = get_or_create_user(db, email="r@test.com")
        profile = create_profile(db, user_id=user.id, name="Rpt", yaml_content="x")
        report_data = _sample_report()
        row = store_report(db, profile_id=profile.id, report=report_data)
        assert row.id is not None
        assert row.overall_score == 72.5
        assert row.grade == "B"

        fetched = get_report(db, row.id)
        assert fetched is not None
        content = json.loads(fetched.json_content)
        assert content["scoring"]["overall_score"] == 72.5

    def test_list_reports(self, db: Session):
        from api.database.crud import create_profile, get_or_create_user, list_reports, store_report

        user = get_or_create_user(db, email="r@test.com")
        profile = create_profile(db, user_id=user.id, name="Rpt", yaml_content="x")
        store_report(db, profile_id=profile.id, report=_sample_report())
        store_report(db, profile_id=profile.id, report=_sample_report())
        reports = list_reports(db, profile_id=profile.id)
        assert len(reports) == 2


# ---------------------------------------------------------------------------
# Assumptions CRUD
# ---------------------------------------------------------------------------

class TestAssumptionsCrud:
    def test_store_assumptions(self, db: Session):
        from api.database.crud import get_latest_assumptions, store_assumptions

        row = store_assumptions(db, tax_year="2025/26", yaml_content="tax: {}", effective_from="2025-04-06", effective_to="2026-04-05")
        assert row.id is not None
        assert row.tax_year == "2025/26"

        latest = get_latest_assumptions(db)
        assert latest is not None
        assert latest.tax_year == "2025/26"

    def test_store_assumptions_upserts(self, db: Session):
        from api.database.crud import store_assumptions

        a1 = store_assumptions(db, tax_year="2025/26", yaml_content="v1")
        a2 = store_assumptions(db, tax_year="2025/26", yaml_content="v2")
        assert a1.id == a2.id
        assert a2.yaml_content == "v2"


# ---------------------------------------------------------------------------
# Run CRUD (migrated from SQLite history)
# ---------------------------------------------------------------------------

class TestRunCrud:
    def test_record_run(self, db: Session):
        from api.database.crud import record_run

        run_id = record_run(db, report=_sample_report(), profile=_sample_profile())
        assert run_id is not None
        assert run_id > 0

    def test_list_runs(self, db: Session):
        from api.database.crud import list_runs, record_run

        record_run(db, report=_sample_report(), profile=_sample_profile())
        record_run(db, report=_sample_report(), profile=_sample_profile())
        runs = list_runs(db, limit=10)
        assert len(runs) == 2
        assert runs[0]["profile_name"] == "Test User"

    def test_list_runs_by_profile_name(self, db: Session):
        from api.database.crud import list_runs, record_run

        record_run(db, report=_sample_report(), profile=_sample_profile())
        runs = list_runs(db, profile_name="Test User")
        assert len(runs) == 1

    def test_list_runs_filters_by_name(self, db: Session):
        from api.database.crud import list_runs, record_run

        record_run(db, report=_sample_report(), profile=_sample_profile())
        runs = list_runs(db, profile_name="Nobody")
        assert len(runs) == 0

    def test_list_runs_respects_limit(self, db: Session):
        from api.database.crud import list_runs, record_run

        for _ in range(5):
            record_run(db, report=_sample_report(), profile=_sample_profile())
        runs = list_runs(db, limit=2)
        assert len(runs) == 2


# ---------------------------------------------------------------------------
# User API key management (v5.3-04)
# ---------------------------------------------------------------------------

class TestUserApiKeys:
    def test_set_user_api_key(self, db: Session):
        from api.database.crud import get_or_create_user, set_user_api_key
        from api.dependencies import hash_api_key

        user = get_or_create_user(db, email="key@test.com")
        key_hash = hash_api_key("test-key-123")
        updated = set_user_api_key(db, user.id, key_hash)
        assert updated is not None
        assert updated.api_key_hash == key_hash

    def test_get_user_by_key_hash(self, db: Session):
        from api.database.crud import get_or_create_user, get_user_by_key_hash
        from api.dependencies import hash_api_key

        key_hash = hash_api_key("lookup-key")
        user = get_or_create_user(db, email="lookup@test.com", api_key_hash=key_hash)
        found = get_user_by_key_hash(db, key_hash)
        assert found is not None
        assert found.id == user.id

    def test_get_user_by_key_hash_missing(self, db: Session):
        from api.database.crud import get_user_by_key_hash
        from api.dependencies import hash_api_key

        assert get_user_by_key_hash(db, hash_api_key("nonexistent")) is None

    def test_set_user_api_key_nonexistent(self, db: Session):
        from api.database.crud import set_user_api_key

        assert set_user_api_key(db, 9999, "somehash") is None


# ---------------------------------------------------------------------------
# Audit log (v5.3-04)
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_log_audit(self, db: Session):
        from api.database.crud import get_or_create_user, log_audit

        user = get_or_create_user(db, email="audit@test.com")
        entry = log_audit(db, user_id=user.id, endpoint="/api/v1/analyse", method="POST", status_code=200)
        assert entry.id is not None
        assert entry.endpoint == "/api/v1/analyse"
        assert entry.status_code == 200

    def test_log_audit_no_user(self, db: Session):
        from api.database.crud import log_audit

        entry = log_audit(db, user_id=None, endpoint="/api/v1/validate", method="POST")
        assert entry.id is not None
        assert entry.user_id is None

    def test_list_audit_log(self, db: Session):
        from api.database.crud import get_or_create_user, list_audit_log, log_audit

        user = get_or_create_user(db, email="audit@test.com")
        log_audit(db, user_id=user.id, endpoint="/api/v1/analyse", method="POST", status_code=200)
        log_audit(db, user_id=user.id, endpoint="/api/v1/validate", method="POST", status_code=200)
        log_audit(db, user_id=None, endpoint="/api/v1/assumptions", method="GET", status_code=200)

        all_entries = list_audit_log(db, limit=10)
        assert len(all_entries) == 3

        user_entries = list_audit_log(db, limit=10, user_id=user.id)
        assert len(user_entries) == 2
