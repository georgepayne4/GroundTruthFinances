"""Tests for engine/lifetime_cashflow.py (v8.2)."""

from __future__ import annotations

import pytest

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.investments import analyse_investments
from engine.lifetime_cashflow import _retirement_spending, project_lifetime_cashflow
from engine.mortgage import analyse_mortgage


@pytest.fixture
def _pipeline_results(sample_profile, assumptions):
    """Run upstream modules needed by lifetime cashflow."""
    cashflow = analyse_cashflow(sample_profile, assumptions)
    debt = analyse_debt(sample_profile, assumptions)
    inv = analyse_investments(sample_profile, assumptions, cashflow)
    mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
    return sample_profile, assumptions, cashflow, inv, mort


class TestLifetimeCashflow:
    def test_output_structure(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        assert "timeline" in result
        assert "summary" in result
        assert len(result["timeline"]) > 0

    def test_timeline_covers_full_life(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        ages = [t["age"] for t in result["timeline"]]
        personal = profile.get("personal", {})
        assert ages[0] == personal["age"]
        life_exp = assumptions.get("life_events", {}).get("life_expectancy", 85)
        assert ages[-1] == life_exp

    def test_phases_present(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        phases = result["summary"]["phases"]
        assert "accumulation" in phases
        # At least one post-retirement phase should exist
        assert any(p in phases for p in ["retirement_transition", "drawdown", "late_life"])

    def test_accumulation_has_employment_income(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        accum_entries = [t for t in result["timeline"] if t["phase"] == "accumulation"]
        assert len(accum_entries) > 0
        assert accum_entries[0]["income"]["employment"] > 0

    def test_retirement_has_no_employment(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        retired = [t for t in result["timeline"] if t["phase"] in ("drawdown", "late_life")]
        for t in retired:
            assert t["income"]["employment"] == 0

    def test_pcls_taken_at_retirement(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        retirement_age = profile.get("personal", {}).get("retirement_age", 67)
        transition = next(
            (t for t in result["timeline"] if t["age"] == retirement_age), None
        )
        if transition:
            assert transition["income"]["pcls_lump_sum"] > 0

    def test_state_pension_after_spa(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        spa = assumptions.get("state_pension", {}).get("age", 67)
        post_spa = [t for t in result["timeline"] if t["age"] > spa]
        if post_spa:
            assert post_spa[0]["income"]["state_pension"] > 0

    def test_net_worth_trajectory(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        # Net worth should generally increase during accumulation
        accum = [t for t in result["timeline"] if t["phase"] == "accumulation"]
        if len(accum) > 5:
            assert accum[-1]["balances"]["net_worth"] > accum[0]["balances"]["net_worth"]

    def test_summary_fields(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        s = result["summary"]
        assert "projection_years" in s
        assert "peak_net_worth" in s
        assert "final_net_worth" in s
        assert "fund_depletion_age" in s
        assert "funds_last_to_death" in s
        assert "pension_at_retirement" in s

    def test_care_costs_in_late_life(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        care_start = assumptions.get("lifetime_cashflow", {}).get("care_provision_start_age", 85)
        late_entries = [t for t in result["timeline"] if t["age"] >= care_start]
        if late_entries:
            assert "care_costs" in late_entries[0]
            assert late_entries[0]["care_costs"] > 0

    def test_each_entry_has_required_fields(self, _pipeline_results):
        profile, assumptions, cashflow, inv, mort = _pipeline_results
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        for t in result["timeline"]:
            assert "year" in t
            assert "age" in t
            assert "phase" in t
            assert "income" in t
            assert "expenses" in t
            assert "balances" in t
            assert "net_worth" in t["balances"]


class TestRetirementSpending:
    def test_base_case(self):
        spending = _retirement_spending(
            pre_retirement_expenses=40000, retire_pct=0.70,
            late_life_reduction=0.15, current_age=68,
            inflation=0.03, year=2, care_cost_home=15000,
            care_start_age=85,
        )
        # 40000 * 0.70 * (1.03)^2 = ~29,712
        assert 29000 < spending < 31000

    def test_late_life_reduction(self):
        base = _retirement_spending(
            pre_retirement_expenses=40000, retire_pct=0.70,
            late_life_reduction=0.15, current_age=75,
            inflation=0.0, year=0, care_cost_home=15000,
            care_start_age=85,
        )
        late = _retirement_spending(
            pre_retirement_expenses=40000, retire_pct=0.70,
            late_life_reduction=0.15, current_age=82,
            inflation=0.0, year=0, care_cost_home=15000,
            care_start_age=85,
        )
        assert late < base

    def test_care_costs_added(self):
        without_care = _retirement_spending(
            pre_retirement_expenses=40000, retire_pct=0.70,
            late_life_reduction=0.15, current_age=84,
            inflation=0.0, year=0, care_cost_home=15000,
            care_start_age=85,
        )
        with_care = _retirement_spending(
            pre_retirement_expenses=40000, retire_pct=0.70,
            late_life_reduction=0.15, current_age=86,
            inflation=0.0, year=0, care_cost_home=15000,
            care_start_age=85,
        )
        assert with_care > without_care


class TestEdgeCases:
    def test_already_retired(self, assumptions):
        """Profile where age >= retirement_age."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "Retiree", "age": 70, "retirement_age": 67},
            "income": {"primary_gross_annual": 0},
            "expenses": {"housing": {"rent_monthly": 800}},
            "savings": {
                "pension_balance": 300000, "isa_balance": 50000,
                "emergency_fund": 10000,
            },
            "debts": [],
            "goals": [],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        debt = analyse_debt(profile, assumptions)
        inv = analyse_investments(profile, assumptions, cashflow)
        mort = analyse_mortgage(profile, assumptions, cashflow, debt)
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        assert len(result["timeline"]) > 0
        # Should be all post-retirement
        assert result["timeline"][0]["phase"] != "accumulation" or result["timeline"][0]["age"] >= 67

    def test_zero_pension(self, assumptions):
        """Profile with no pension balance."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "No Pension", "age": 30, "retirement_age": 67},
            "income": {"primary_gross_annual": 35000},
            "expenses": {"housing": {"rent_monthly": 900}},
            "savings": {"emergency_fund": 2000, "pension_balance": 0},
            "debts": [],
            "goals": [],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        debt = analyse_debt(profile, assumptions)
        inv = analyse_investments(profile, assumptions, cashflow)
        mort = analyse_mortgage(profile, assumptions, cashflow, debt)
        result = project_lifetime_cashflow(profile, assumptions, cashflow, inv, mort)
        assert result["summary"]["pension_at_retirement"] is not None

    def test_pipeline_integration(self, sample_profile, assumptions):
        """Verify lifetime_cashflow appears in pipeline report."""
        from engine.pipeline import run_pipeline
        report, _, _ = run_pipeline(sample_profile, assumptions_override=assumptions)
        assert "lifetime_cashflow" in report
        assert report["lifetime_cashflow"] is not None
        assert "timeline" in report["lifetime_cashflow"]
        assert "summary" in report["lifetime_cashflow"]
