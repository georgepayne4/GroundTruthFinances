"""Tests for the What-If Explorer (v6.0-04).

Covers parameter modification, delta computation, REST endpoint,
and WebSocket what-if messages.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from api.whatif import (
    ParameterChange,
    WhatIfResponse,
    apply_changes,
    compute_deltas,
    run_whatif,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_profile() -> dict:
    path = Path(__file__).resolve().parent.parent / "config" / "sample_input.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# apply_changes tests
# ---------------------------------------------------------------------------

class TestApplyChanges:
    def test_simple_path(self):
        profile = {"income": {"gross_salary": 50000}}
        changes = [ParameterChange(path="income.gross_salary", value=60000)]
        result = apply_changes(profile, changes)
        assert result["income"]["gross_salary"] == 60000
        # Original unchanged
        assert profile["income"]["gross_salary"] == 50000

    def test_nested_path(self):
        profile = {"pension": {"employer": {"contribution_pct": 5}}}
        changes = [ParameterChange(path="pension.employer.contribution_pct", value=8)]
        result = apply_changes(profile, changes)
        assert result["pension"]["employer"]["contribution_pct"] == 8

    def test_creates_missing_keys(self):
        profile = {"income": {}}
        changes = [ParameterChange(path="income.bonus", value=5000)]
        result = apply_changes(profile, changes)
        assert result["income"]["bonus"] == 5000

    def test_multiple_changes(self):
        profile = {"income": {"gross_salary": 50000}, "expenses": {"rent": 1200}}
        changes = [
            ParameterChange(path="income.gross_salary", value=55000),
            ParameterChange(path="expenses.rent", value=1000),
        ]
        result = apply_changes(profile, changes)
        assert result["income"]["gross_salary"] == 55000
        assert result["expenses"]["rent"] == 1000

    def test_deep_nested_creation(self):
        profile = {}
        changes = [ParameterChange(path="a.b.c.d", value="deep")]
        result = apply_changes(profile, changes)
        assert result["a"]["b"]["c"]["d"] == "deep"


# ---------------------------------------------------------------------------
# compute_deltas tests
# ---------------------------------------------------------------------------

class TestComputeDeltas:
    def test_numeric_delta(self):
        base = {"scoring": {"overall_score": 65.0}}
        modified = {"scoring": {"overall_score": 72.0}}
        deltas = compute_deltas(base, modified)
        score_delta = next(d for d in deltas if d.metric == "Overall Score")
        assert score_delta.delta == 7.0
        assert score_delta.base_value == 65.0
        assert score_delta.modified_value == 72.0

    def test_percentage_delta(self):
        base = {"scoring": {"overall_score": 50.0}}
        modified = {"scoring": {"overall_score": 60.0}}
        deltas = compute_deltas(base, modified)
        score_delta = next(d for d in deltas if d.metric == "Overall Score")
        assert score_delta.delta_pct == 20.0

    def test_missing_metric_skipped(self):
        deltas = compute_deltas({}, {})
        # All metrics are None in both, should be skipped
        assert len(deltas) == 0

    def test_zero_base_no_pct(self):
        base = {"debt": {"total_debt": 0}}
        modified = {"debt": {"total_debt": 5000}}
        deltas = compute_deltas(base, modified)
        debt_delta = next((d for d in deltas if d.metric == "Total Debt"), None)
        if debt_delta:
            assert debt_delta.delta_pct is None  # Can't compute % from zero


# ---------------------------------------------------------------------------
# Full what-if pipeline tests
# ---------------------------------------------------------------------------

class TestRunWhatIf:
    def test_salary_increase(self, sample_profile):
        changes = [ParameterChange(path="income.gross_salary", value=80000)]
        result = run_whatif(sample_profile, changes)

        assert isinstance(result, WhatIfResponse)
        assert result.base_score is not None
        assert result.modified_score is not None
        assert result.modified_score >= result.base_score  # Higher salary = better score
        assert len(result.deltas) > 0
        assert len(result.changes_applied) == 1

    def test_pension_contribution_increase(self, sample_profile):
        changes = [ParameterChange(path="pension.employee_contribution_pct", value=10)]
        result = run_whatif(sample_profile, changes)
        assert result.score_delta is not None

    def test_multiple_changes(self, sample_profile):
        changes = [
            ParameterChange(path="income.gross_salary", value=70000),
            ParameterChange(path="expenses.discretionary.holidays", value=0),
        ]
        result = run_whatif(sample_profile, changes)
        assert len(result.changes_applied) == 2

    def test_no_change_zero_delta(self, sample_profile):
        """Applying same value should produce zero score delta."""
        salary = sample_profile.get("income", {}).get("gross_salary", 45000)
        changes = [ParameterChange(path="income.gross_salary", value=salary)]
        result = run_whatif(sample_profile, changes)
        assert result.score_delta == 0.0


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------

class TestWhatIfEndpoint:
    def test_post_whatif(self, sample_profile):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/v1/whatif",
            json={
                "profile": sample_profile,
                "changes": [{"path": "income.gross_salary", "value": 80000}],
            },
            headers={"X-API-Key": "dev-key-change-me"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "base_score" in data
        assert "modified_score" in data
        assert "deltas" in data
        assert len(data["deltas"]) > 0

    def test_post_whatif_multiple_changes(self, sample_profile):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/v1/whatif",
            json={
                "profile": sample_profile,
                "changes": [
                    {"path": "income.gross_salary", "value": 60000},
                    {"path": "expenses.discretionary.holidays", "value": 500},
                ],
            },
            headers={"X-API-Key": "dev-key-change-me"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["changes_applied"]) == 2


# ---------------------------------------------------------------------------
# WebSocket what-if tests
# ---------------------------------------------------------------------------

class TestWebSocketWhatIf:
    def test_whatif_via_websocket(self, sample_profile):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({
                "type": "whatif",
                "profile": sample_profile,
                "changes": [{"path": "income.gross_salary", "value": 80000}],
            })

            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("type") == "whatif_result":
                    break

            result = messages[-1]
            assert result["type"] == "whatif_result"
            assert "base_score" in result
            assert "modified_score" in result
            assert "deltas" in result

    def test_whatif_missing_changes(self, sample_profile):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({"type": "whatif", "profile": sample_profile})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "changes" in msg["detail"].lower()

    def test_whatif_missing_profile(self):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({"type": "whatif", "changes": [{"path": "x", "value": 1}]})
            msg = ws.receive_json()
            assert msg["type"] == "error"
