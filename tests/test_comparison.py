"""Tests for Multi-Profile Comparison (v6.0-06)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from api.comparison import (
    branch_profile,
    compare_profiles,
)


@pytest.fixture
def sample_profile() -> dict:
    path = Path(__file__).resolve().parent.parent / "config" / "sample_input.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def higher_income_profile(sample_profile) -> dict:
    p = copy.deepcopy(sample_profile)
    p["income"]["primary_gross_annual"] = 80000
    return p


# ---------------------------------------------------------------------------
# Comparison logic tests
# ---------------------------------------------------------------------------

class TestCompareProfiles:
    def test_two_profiles(self, sample_profile, higher_income_profile):
        report_a, report_b, report_merged, comparisons = compare_profiles(
            sample_profile, higher_income_profile
        )
        assert report_a["scoring"]["overall_score"] is not None
        assert report_b["scoring"]["overall_score"] is not None
        assert report_merged is None
        assert len(comparisons) > 0

        score_comp = next(c for c in comparisons if c.metric == "Overall Score")
        assert score_comp.delta is not None

    def test_with_merged_profile(self, sample_profile, higher_income_profile):
        merged = copy.deepcopy(sample_profile)
        merged["income"]["gross_salary"] = 125000  # combined household
        _, _, report_merged, comparisons = compare_profiles(
            sample_profile, higher_income_profile, merged_profile=merged
        )
        assert report_merged is not None
        score_comp = next(c for c in comparisons if c.metric == "Overall Score")
        assert score_comp.merged_value is not None

    def test_identical_profiles_zero_delta(self, sample_profile):
        _, _, _, comparisons = compare_profiles(sample_profile, sample_profile)
        for c in comparisons:
            if c.delta is not None:
                assert c.delta == 0.0


# ---------------------------------------------------------------------------
# Branch tests
# ---------------------------------------------------------------------------

class TestBranchProfile:
    def test_branch_applies_changes(self, sample_profile):
        changes = {"income.primary_gross_annual": 70000}
        branched, _, _ = branch_profile(sample_profile, changes)
        assert branched["income"]["primary_gross_annual"] == 70000
        assert sample_profile["income"]["primary_gross_annual"] != 70000  # original unchanged

    def test_branch_score_differs(self, sample_profile):
        changes = {"income.primary_gross_annual": 100000}
        _, base_report, branch_report = branch_profile(sample_profile, changes)
        base_score = base_report["scoring"]["overall_score"]
        branch_score = branch_report["scoring"]["overall_score"]
        assert branch_score >= base_score

    def test_empty_changes_same_result(self, sample_profile):
        _, base_report, branch_report = branch_profile(sample_profile, {})
        assert base_report["scoring"]["overall_score"] == branch_report["scoring"]["overall_score"]


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------

class TestCompareEndpoint:
    def test_post_compare(self, sample_profile, higher_income_profile):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/v1/compare",
            json={
                "profile_a": sample_profile,
                "profile_b": higher_income_profile,
                "label_a": "Current",
                "label_b": "Promotion",
            },
            headers={"X-API-Key": "dev-key-change-me"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["label_a"] == "Current"
        assert data["label_b"] == "Promotion"
        assert data["score_a"] is not None
        assert data["score_b"] is not None
        assert len(data["comparisons"]) > 0

    def test_post_branch(self, sample_profile):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/v1/compare/branch",
            json={
                "base_profile": sample_profile,
                "branch_name": "optimistic",
                "changes": {"income.primary_gross_annual": 75000},
            },
            headers={"X-API-Key": "dev-key-change-me"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["branch_name"] == "optimistic"
        assert data["score_delta"] is not None
