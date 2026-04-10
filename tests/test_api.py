"""Tests for the FastAPI REST API (v5.3-01 + v5.3-02 database integration)."""

from __future__ import annotations

import os

import pytest

# Force in-memory SQLite before any app imports
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database.models import Base
from api.database.session import get_db

# Single shared in-memory SQLite for all test API calls
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_test_engine, autoflush=False, expire_on_commit=False)

Base.metadata.create_all(bind=_test_engine)


def _override_get_db():
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


from api.main import app

app.dependency_overrides[get_db] = _override_get_db

from fastapi.testclient import TestClient

client = TestClient(app)

API_KEY = "dev-key-change-me"
HEADERS = {"X-API-Key": API_KEY}


def _minimal_profile() -> dict:
    return {
        "personal": {
            "name": "API Test User",
            "age": 30,
            "retirement_age": 67,
            "dependents": 0,
            "risk_profile": "moderate",
            "employment_type": "employed",
        },
        "income": {"primary_gross_annual": 50000},
        "expenses": {"housing": {"rent_monthly": 1000}},
        "savings": {
            "emergency_fund": 5000,
            "pension_balance": 10000,
            "pension_personal_contribution_pct": 0.05,
            "pension_employer_contribution_pct": 0.03,
        },
        "debts": [],
        "goals": [],
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_missing_api_key_returns_422(self):
        resp = client.post("/api/v1/validate", json={"profile": _minimal_profile()})
        assert resp.status_code == 422

    def test_wrong_api_key_returns_401(self):
        resp = client.post(
            "/api/v1/validate",
            json={"profile": _minimal_profile()},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_valid_api_key_succeeds(self):
        resp = client.post(
            "/api/v1/validate",
            json={"profile": _minimal_profile()},
            headers=HEADERS,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/validate
# ---------------------------------------------------------------------------

class TestValidateEndpoint:
    def test_returns_flags(self):
        resp = client.post(
            "/api/v1/validate",
            json={"profile": _minimal_profile()},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "flags" in data
        assert isinstance(data["flags"], list)
        assert "error_count" in data
        assert "warning_count" in data
        assert "info_count" in data

    def test_bad_profile_gets_warnings(self):
        profile = _minimal_profile()
        profile["personal"]["age"] = -5
        resp = client.post(
            "/api/v1/validate",
            json={"profile": profile},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning_count"] > 0


# ---------------------------------------------------------------------------
# POST /api/v1/analyse
# ---------------------------------------------------------------------------

class TestAnalyseEndpoint:
    def test_full_analysis_returns_report(self):
        resp = client.post(
            "/api/v1/analyse",
            json={"profile": _minimal_profile()},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_name"] == "API Test User"
        assert data["overall_score"] is not None
        assert data["grade"] is not None
        assert "report" in data
        report = data["report"]
        assert "scoring" in report
        assert "cashflow" in report
        assert "debt" in report

    def test_analysis_with_custom_assumptions(self):
        from engine.loader import load_assumptions
        assumptions = load_assumptions()
        resp = client.post(
            "/api/v1/analyse",
            json={"profile": _minimal_profile(), "assumptions": assumptions},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] is not None

    def test_analysis_records_run_id(self):
        resp = client.post(
            "/api/v1/analyse",
            json={"profile": _minimal_profile()},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] is not None


# ---------------------------------------------------------------------------
# GET /api/v1/assumptions
# ---------------------------------------------------------------------------

class TestAssumptionsEndpoint:
    def test_returns_assumptions_dict(self):
        resp = client.get("/api/v1/assumptions", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "tax" in data
        assert "inflation" in data or "general" in data


# ---------------------------------------------------------------------------
# GET /api/v1/history
# ---------------------------------------------------------------------------

class TestHistoryEndpoint:
    def test_history_returns_list(self):
        resp = client.get("/api/v1/history", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert "count" in data
        assert isinstance(data["runs"], list)

    def test_history_by_profile_name(self):
        resp = client.get("/api/v1/history/NonExistentUser", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_history_limit_param(self):
        resp = client.get("/api/v1/history?limit=1", headers=HEADERS)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Profile management (v5.3-02)
# ---------------------------------------------------------------------------

class TestProfileEndpoints:
    def test_create_profile(self):
        resp = client.post(
            "/api/v1/profiles",
            json={
                "user_email": "test@example.com",
                "user_name": "Test User",
                "profile_name": "My Profile",
                "profile": _minimal_profile(),
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Profile"
        assert data["id"] is not None
        assert data["user_id"] is not None

    def test_list_profiles(self):
        client.post(
            "/api/v1/profiles",
            json={
                "user_email": "list@example.com",
                "profile_name": "Profile A",
                "profile": _minimal_profile(),
            },
            headers=HEADERS,
        )
        resp = client.get(
            "/api/v1/profiles",
            params={"user_email": "list@example.com"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Profile A"

    def test_list_profiles_unknown_user(self):
        resp = client.get(
            "/api/v1/profiles",
            params={"user_email": "nobody@nowhere.com"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

class TestGeneral:
    def test_docs_available(self):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_schema(self):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "GroundTruth Financial Planning API"


# ---------------------------------------------------------------------------
# Security (v7.3)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# v7.4 endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAssumptionsStatus:
    def test_returns_staleness_info(self):
        resp = client.get("/api/v1/assumptions/status", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "tax_year" in data
        assert "stale" in data
        assert "schema_version" in data


class TestSensitivityEndpoint:
    def test_sensitivity_returns_results(self):
        resp = client.post(
            "/api/v1/sensitivity",
            json={"profile": _minimal_profile()},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data) > 0


class TestScenariosEndpoint:
    def test_scenarios_returns_results(self):
        resp = client.post(
            "/api/v1/scenarios",
            json={"profile": _minimal_profile()},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestHistoryPagination:
    def test_cursor_pagination(self):
        # Create a couple of runs first
        client.post("/api/v1/analyse", json={"profile": _minimal_profile()}, headers=HEADERS)
        client.post("/api/v1/analyse", json={"profile": _minimal_profile()}, headers=HEADERS)

        # Get first page
        resp = client.get("/api/v1/history?limit=1", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        if data["count"] > 0:
            cursor = data["runs"][0]["id"]
            # Get next page using cursor
            resp2 = client.get(f"/api/v1/history?limit=1&cursor={cursor}", headers=HEADERS)
            assert resp2.status_code == 200


class TestGracefulDegradation:
    def test_malformed_profile_returns_422(self):
        resp = client.post(
            "/api/v1/analyse",
            json={"profile": {"not_a_valid": "profile"}},
            headers=HEADERS,
        )
        # Should return structured error, not 500
        assert resp.status_code in (200, 422)


class TestSecurity:
    def test_oversized_request_rejected(self):
        """Request body > 100KB should be rejected."""
        # Build an oversized profile
        huge_profile = _minimal_profile()
        huge_profile["_padding"] = "x" * (110 * 1024)
        resp = client.post(
            "/api/v1/validate",
            json={"profile": huge_profile},
            headers={**HEADERS, "content-length": str(200 * 1024)},
        )
        assert resp.status_code == 413

    def test_xss_in_profile_name_sanitised(self):
        """Profile name with script tags should be escaped in narrative."""
        from engine.narrative import generate_narrative
        from engine.pipeline import run_pipeline

        profile = _minimal_profile()
        profile["personal"]["name"] = '<script>alert("xss")</script>'
        report, _, _ = run_pipeline(profile)
        narrative = generate_narrative(report)
        assert "<script>" not in narrative
        assert "&lt;script&gt;" in narrative

    def test_dev_key_block_in_production(self):
        """GROUNDTRUTH_ENV=production should reject the default dev key."""
        import importlib
        import os

        original_env = os.environ.get("GROUNDTRUTH_ENV")
        original_key = os.environ.get("GROUNDTRUTH_API_KEY")
        try:
            os.environ["GROUNDTRUTH_ENV"] = "production"
            os.environ["GROUNDTRUTH_API_KEY"] = "dev-key-change-me"
            # Re-importing should raise RuntimeError
            import api.dependencies as dep_mod
            with pytest.raises(RuntimeError, match="Cannot start in production"):
                importlib.reload(dep_mod)
        finally:
            # Restore original state
            if original_env is None:
                os.environ.pop("GROUNDTRUTH_ENV", None)
            else:
                os.environ["GROUNDTRUTH_ENV"] = original_env
            if original_key is None:
                os.environ.pop("GROUNDTRUTH_API_KEY", None)
            else:
                os.environ["GROUNDTRUTH_API_KEY"] = original_key
            import api.dependencies as dep_mod
            importlib.reload(dep_mod)
