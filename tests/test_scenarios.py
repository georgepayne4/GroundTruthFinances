"""Tests for engine/scenarios.py — compound scenario trees (v8.6)."""

from __future__ import annotations

import copy

import pytest

from engine.scenarios import (
    _apply_expense_adjustment,
    _apply_income_adjustment,
    _build_decision_summary,
    _compute_expected_values,
    _extract_goal_feasibility,
    _npv_of_surplus,
    _resolve_discount_rate,
    _run_compound_scenarios,
    run_scenarios,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def compound_cfg():
    return {
        "discount_rate_override": None,
        "scenarios": [
            {
                "name": "recession",
                "description": "Job loss + crash",
                "probability": 0.10,
                "income_multiplier": 0.0,
                "income_loss_months": 6,
                "expense_multiplier": 1.0,
                "investment_return_override": -0.20,
                "interest_rate_bump_pct": 2.0,
                "inflation_override_pct": None,
                "recommended_actions": ["Build emergency fund"],
                "nudge_category": "defensive",
            },
            {
                "name": "boom",
                "description": "Pay rise + strong returns",
                "probability": 0.15,
                "income_multiplier": 1.15,
                "income_loss_months": 0,
                "expense_multiplier": 1.05,
                "investment_return_override": 0.12,
                "interest_rate_bump_pct": -0.5,
                "inflation_override_pct": None,
                "recommended_actions": ["Increase pension contributions"],
                "nudge_category": "offensive",
            },
            {
                "name": "stagflation",
                "description": "Flat income + high inflation",
                "probability": 0.15,
                "income_multiplier": 1.0,
                "income_loss_months": 0,
                "expense_multiplier": 1.10,
                "investment_return_override": 0.02,
                "interest_rate_bump_pct": 1.5,
                "inflation_override_pct": 0.08,
                "recommended_actions": ["Lock in fixed rate"],
                "nudge_category": "preservation",
            },
            {
                "name": "baseline",
                "description": "Current trajectory",
                "probability": 0.60,
                "income_multiplier": 1.0,
                "income_loss_months": 0,
                "expense_multiplier": 1.0,
                "investment_return_override": None,
                "interest_rate_bump_pct": 0.0,
                "inflation_override_pct": None,
                "recommended_actions": ["Continue current strategy"],
                "nudge_category": "steady",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Edge cases first
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_config_returns_empty(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, {},
        )
        assert result["branches"] == []

    def test_zero_income_recession(self, sample_profile, assumptions, compound_cfg):
        """Recession with income_multiplier=0 produces negative surplus."""
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)

        # Only recession scenario
        cfg = {"scenarios": [compound_cfg["scenarios"][0]]}
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, cfg,
        )
        branch = result["branches"][0]
        assert branch["results"]["surplus_monthly"] < 0

    def test_no_goals_feasibility_empty(self, minimal_profile, assumptions, compound_cfg):
        """Profile with no goals produces empty goal_feasibility list."""
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(minimal_profile, assumptions)
        debt = analyse_debt(minimal_profile, assumptions)
        inv = analyse_investments(minimal_profile, assumptions, cashflow)
        mort = analyse_mortgage(minimal_profile, assumptions, cashflow, debt)

        cfg = {"scenarios": [compound_cfg["scenarios"][3]]}  # baseline only
        result = _run_compound_scenarios(
            minimal_profile, assumptions, cashflow, debt, mort, inv, cfg,
        )
        assert result["branches"][0]["results"]["goal_feasibility"] == []

    def test_already_retired_npv_zero(self):
        """Age >= retirement_age means NPV is 0."""
        cashflow = {"surplus": {"annual": 10000}}
        profile = {"personal": {"age": 70, "retirement_age": 67}}
        assert _npv_of_surplus(cashflow, profile, 0.06) == 0.0

    def test_single_scenario_expected_equals_branch(self, sample_profile, assumptions, compound_cfg):
        """With one scenario at p=1.0, expected values equal that branch."""
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)

        single = copy.deepcopy(compound_cfg["scenarios"][3])  # baseline
        single["probability"] = 1.0
        cfg = {"scenarios": [single]}
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, cfg,
        )
        branch = result["branches"][0]
        expected = result["expected_values"]
        assert expected["expected_score"] == pytest.approx(branch["results"]["score"], abs=0.1)
        assert expected["expected_npv"] == pytest.approx(branch["results"]["npv_surplus"], abs=1)


# ---------------------------------------------------------------------------
# NPV calculation
# ---------------------------------------------------------------------------


class TestNPVCalculation:
    def test_zero_surplus(self):
        cashflow = {"surplus": {"annual": 0}}
        profile = {"personal": {"age": 30, "retirement_age": 67}}
        assert _npv_of_surplus(cashflow, profile, 0.06) == 0.0

    def test_known_inputs(self):
        """Manual NPV check: 10000/year for 3 years at 5%."""
        cashflow = {"surplus": {"annual": 10000}}
        profile = {"personal": {"age": 64, "retirement_age": 67}}
        # NPV = 10000/1.05 + 10000/1.05^2 + 10000/1.05^3
        expected = 10000 / 1.05 + 10000 / 1.05**2 + 10000 / 1.05**3
        assert _npv_of_surplus(cashflow, profile, 0.05) == pytest.approx(expected, abs=0.01)

    def test_resolve_discount_rate_from_config(self):
        assumptions = {"investment_returns": {"moderate": 0.06}}
        profile = {"personal": {"risk_profile": "moderate"}}
        cfg = {"discount_rate_override": 0.04}
        assert _resolve_discount_rate(assumptions, profile, cfg) == 0.04

    def test_resolve_discount_rate_from_assumptions(self):
        assumptions = {"investment_returns": {"aggressive": 0.08}}
        profile = {"personal": {"risk_profile": "aggressive"}}
        cfg = {"discount_rate_override": None}
        assert _resolve_discount_rate(assumptions, profile, cfg) == 0.08


# ---------------------------------------------------------------------------
# Adjustment helpers
# ---------------------------------------------------------------------------


class TestAdjustments:
    def test_income_multiplier(self):
        profile = {
            "income": {
                "primary_gross_annual": 50000,
                "partner_gross_annual": 30000,
                "bonus_annual_expected": 5000,
                "side_income_monthly": 500,
                "_total_gross_monthly": 7500,
                "_total_gross_annual": 90000,
            },
        }
        _apply_income_adjustment(profile, 0.5, 0)
        inc = profile["income"]
        assert inc["primary_gross_annual"] == 25000
        assert inc["partner_gross_annual"] == 15000
        assert inc["bonus_annual_expected"] == 2500
        assert inc["side_income_monthly"] == 500  # passive unchanged
        # Totals recomputed
        expected_monthly = 25000 / 12 + 15000 / 12 + 500
        assert inc["_total_gross_monthly"] == pytest.approx(expected_monthly, abs=1)

    def test_income_loss_months(self):
        """6 months of zero income = 50% reduction for the year."""
        profile = {
            "income": {
                "primary_gross_annual": 60000,
                "side_income_monthly": 0,
                "_total_gross_monthly": 5000,
                "_total_gross_annual": 60000,
            },
        }
        _apply_income_adjustment(profile, 0.0, 6)
        # effective = 0.0 * (1 - 6/12) = 0.0
        assert profile["income"]["primary_gross_annual"] == 0.0

    def test_income_partial_loss(self):
        """50% income with 3 months loss: 0.5 * (1 - 3/12) = 0.375."""
        profile = {
            "income": {
                "primary_gross_annual": 100000,
                "_total_gross_monthly": 100000 / 12,
                "_total_gross_annual": 100000,
            },
        }
        _apply_income_adjustment(profile, 0.5, 3)
        assert profile["income"]["primary_gross_annual"] == pytest.approx(37500, abs=1)

    def test_expense_multiplier(self):
        profile = {
            "expenses": {
                "housing": {
                    "rent_monthly": 1000,
                    "utilities_monthly": 200,
                    "_category_monthly": 1200,
                },
                "living": {
                    "groceries_monthly": 400,
                    "holidays_annual": 2400,
                    "_category_monthly": 600,
                },
                "_total_monthly": 1800,
                "_total_annual": 21600,
            },
        }
        _apply_expense_adjustment(profile, 1.10)
        exp = profile["expenses"]
        assert exp["housing"]["rent_monthly"] == pytest.approx(1100, abs=1)
        assert exp["housing"]["utilities_monthly"] == pytest.approx(220, abs=1)
        assert exp["living"]["groceries_monthly"] == pytest.approx(440, abs=1)
        assert exp["living"]["holidays_annual"] == pytest.approx(2640, abs=1)
        # Totals recomputed
        assert exp["_total_monthly"] == pytest.approx(1800 * 1.10, abs=1)

    def test_expense_multiplier_one_noop(self):
        profile = {
            "expenses": {
                "housing": {"rent_monthly": 1000, "_category_monthly": 1000},
                "_total_monthly": 1000,
                "_total_annual": 12000,
            },
        }
        _apply_expense_adjustment(profile, 1.0)
        assert profile["expenses"]["housing"]["rent_monthly"] == 1000

    def test_null_overrides_preserve_defaults(self, sample_profile, assumptions, compound_cfg):
        """Baseline scenario (null overrides) preserves original assumptions."""
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)

        cfg = {"scenarios": [compound_cfg["scenarios"][3]]}  # baseline
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, cfg,
        )
        branch = result["branches"][0]
        # Baseline surplus should match original
        assert branch["results"]["surplus_monthly"] == pytest.approx(
            cashflow["surplus"]["monthly"], abs=5,
        )


# ---------------------------------------------------------------------------
# Goal feasibility extraction
# ---------------------------------------------------------------------------


class TestGoalFeasibility:
    def test_extract_goals(self):
        goals = {
            "goals": [
                {"name": "Emergency Fund", "status": "on_track"},
                {"name": "House Deposit", "status": "at_risk"},
            ],
        }
        result = _extract_goal_feasibility(goals)
        assert len(result) == 2
        assert result[0]["on_track"] is True
        assert result[1]["on_track"] is False


# ---------------------------------------------------------------------------
# Expected values and decision summary
# ---------------------------------------------------------------------------


class TestExpectedValues:
    def test_weighted_calculation(self):
        branches = [
            {"probability": 0.4, "results": {"score": 80, "npv_surplus": 100000, "surplus_monthly": 500}},
            {"probability": 0.6, "results": {"score": 40, "npv_surplus": 50000, "surplus_monthly": 200}},
        ]
        expected = _compute_expected_values(branches)
        assert expected["expected_score"] == pytest.approx(0.4 * 80 + 0.6 * 40, abs=0.1)
        assert expected["expected_npv"] == pytest.approx(0.4 * 100000 + 0.6 * 50000, abs=1)

    def test_empty_branches(self):
        expected = _compute_expected_values([])
        assert expected["expected_score"] == 0

    def test_decision_summary(self):
        branches = [
            {"name": "bad", "probability": 0.2, "results": {"npv_surplus": -100}},
            {"name": "ok", "probability": 0.5, "results": {"npv_surplus": 200}},
            {"name": "good", "probability": 0.3, "results": {"npv_surplus": 500}},
        ]
        summary = _build_decision_summary(branches)
        assert summary["worst_case"] == "bad"
        assert summary["best_case"] == "good"
        assert summary["most_likely"] == "ok"
        assert summary["risk_spread"] == pytest.approx(600, abs=1)


# ---------------------------------------------------------------------------
# Core scenario tests
# ---------------------------------------------------------------------------


class TestCompoundScenarios:
    def test_recession_reduces_score(self, sample_profile, assumptions, compound_cfg):
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, compound_cfg,
        )
        recession = next(b for b in result["branches"] if b["name"] == "recession")
        baseline = next(b for b in result["branches"] if b["name"] == "baseline")
        assert recession["results"]["score"] < baseline["results"]["score"]

    def test_boom_improves_or_maintains_score(self, sample_profile, assumptions, compound_cfg):
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, compound_cfg,
        )
        boom = next(b for b in result["branches"] if b["name"] == "boom")
        baseline = next(b for b in result["branches"] if b["name"] == "baseline")
        assert boom["results"]["score"] >= baseline["results"]["score"]

    def test_probabilities_sum_to_one(self, compound_cfg):
        total = sum(s["probability"] for s in compound_cfg["scenarios"])
        assert total == pytest.approx(1.0, abs=0.001)

    def test_vs_baseline_deltas(self, sample_profile, assumptions, compound_cfg):
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, compound_cfg,
        )
        baseline = next(b for b in result["branches"] if b["name"] == "baseline")
        assert baseline["vs_baseline"]["score_delta"] == pytest.approx(0, abs=0.1)
        assert baseline["vs_baseline"]["npv_delta"] == pytest.approx(0, abs=1)

    def test_branch_structure(self, sample_profile, assumptions, compound_cfg):
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
        result = _run_compound_scenarios(
            sample_profile, assumptions, cashflow, debt, mort, inv, compound_cfg,
        )
        assert len(result["branches"]) == 4
        branch = result["branches"][0]
        assert "name" in branch
        assert "probability" in branch
        assert "nudge_category" in branch
        assert "results" in branch
        assert "recommended_actions" in branch
        assert "vs_baseline" in branch
        r = branch["results"]
        assert "score" in r
        assert "npv_surplus" in r
        assert "goal_feasibility" in r
        assert "surplus_monthly" in r


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    def test_pipeline_has_compound_scenarios(self, sample_profile, assumptions):
        from engine.pipeline import run_pipeline

        report, _, _ = run_pipeline(sample_profile, assumptions_override=assumptions)
        scenarios = report["stress_scenarios"]
        assert "compound_scenarios" in scenarios
        compound = scenarios["compound_scenarios"]
        assert "branches" in compound
        assert "expected_values" in compound
        assert "decision_summary" in compound

    def test_insights_include_scenario_tree(self, sample_profile, assumptions):
        from engine.pipeline import run_pipeline

        report, _, _ = run_pipeline(sample_profile, assumptions_override=assumptions)
        insights = report.get("advisor_insights", {})
        assert "scenario_tree_insights" in insights

    def test_backward_compat(self, sample_profile, assumptions):
        """Existing stress scenario keys still present."""
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
        result = run_scenarios(sample_profile, assumptions, cashflow, debt, mort, inv)
        assert "job_loss" in result
        assert "interest_rate_shock" in result
        assert "market_downturn" in result
        assert "inflation_shock" in result
        assert "income_reduction" in result
        assert "compound_scenarios" in result
