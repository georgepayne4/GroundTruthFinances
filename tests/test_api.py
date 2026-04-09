"""Tests for the FastAPI REST API (v5.3-01)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

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
