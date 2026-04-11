"""Tests for engine/withdrawal.py — tax-optimal withdrawal sequencing (v8.3)."""

from __future__ import annotations

import pytest

from engine.cashflow import analyse_cashflow
from engine.investments import analyse_investments
from engine.withdrawal import (
    _analyse_pcls_timing,
    _analyse_sp_deferral,
    model_withdrawal_sequence,
)


class TestWithdrawalSequence:
    def test_output_structure(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        result = model_withdrawal_sequence(sample_profile, assumptions, inv)
        assert "optimised_schedule" in result
        assert "naive_total_tax" in result
        assert "optimised_total_tax" in result
        assert "lifetime_tax_saving" in result
        assert "draw_order" in result
        assert "pcls_timing" in result
        assert "state_pension_deferral" in result

    def test_optimised_beats_naive(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        result = model_withdrawal_sequence(sample_profile, assumptions, inv)
        assert result["lifetime_tax_saving"] >= 0

    def test_schedule_has_entries(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        result = model_withdrawal_sequence(sample_profile, assumptions, inv)
        retirement_age = sample_profile.get("personal", {}).get("retirement_age", 67)
        life_exp = assumptions.get("life_events", {}).get("life_expectancy", 85)
        expected_years = life_exp - retirement_age
        assert len(result["optimised_schedule"]) == expected_years

    def test_schedule_entry_fields(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        result = model_withdrawal_sequence(sample_profile, assumptions, inv)
        entry = result["optimised_schedule"][0]
        assert "pension_drawdown" in entry
        assert "isa_drawdown" in entry
        assert "state_pension" in entry
        assert "tax_paid" in entry
        assert "total_net" in entry
        assert "pension_remaining" in entry

    def test_pcls_in_first_year(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        result = model_withdrawal_sequence(sample_profile, assumptions, inv)
        first = result["optimised_schedule"][0]
        assert "pcls_lump_sum" in first
        assert first["pcls_lump_sum"] > 0

    def test_no_pcls_after_first_year(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        result = model_withdrawal_sequence(sample_profile, assumptions, inv)
        for entry in result["optimised_schedule"][1:]:
            assert entry.get("pcls_lump_sum", 0) == 0

    def test_pension_remaining_decreases(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        result = model_withdrawal_sequence(sample_profile, assumptions, inv)
        schedule = result["optimised_schedule"]
        # Generally pension should decrease over time (drawdown exceeds growth)
        if len(schedule) > 5:
            assert schedule[-1]["pension_remaining"] < schedule[0].get("pension_remaining", float("inf"))

    def test_pipeline_integration(self, sample_profile, assumptions):
        from engine.pipeline import run_pipeline
        report, _, _ = run_pipeline(sample_profile, assumptions_override=assumptions)
        assert "withdrawal_sequence" in report
        assert report["withdrawal_sequence"] is not None
        assert "lifetime_tax_saving" in report["withdrawal_sequence"]


class TestPclsTiming:
    def test_returns_both_options(self):
        result = _analyse_pcls_timing(
            pension_real=500000, pcls_fraction=0.25,
            real_return=0.03, retirement_age=67, life_expectancy=85,
        )
        assert "early_pcls_amount" in result
        assert "late_pcls_amount" in result
        assert result["early_pcls_amount"] == 125000
        assert result["recommendation"] in ("early", "late")

    def test_late_pcls_larger(self):
        result = _analyse_pcls_timing(
            pension_real=500000, pcls_fraction=0.25,
            real_return=0.03, retirement_age=67, life_expectancy=85,
        )
        assert result["late_pcls_amount"] > result["early_pcls_amount"]


class TestStatePensionDeferral:
    def test_returns_scenarios(self):
        result = _analyse_sp_deferral(
            state_pension_real=11500, deferral_rate=0.058,
            retirement_age=67, state_pension_age=67, life_expectancy=85,
        )
        assert "scenarios" in result
        assert len(result["scenarios"]) > 0
        assert "recommendation" in result

    def test_scenarios_have_break_even(self):
        result = _analyse_sp_deferral(
            state_pension_real=11500, deferral_rate=0.058,
            retirement_age=67, state_pension_age=67, life_expectancy=85,
        )
        for s in result["scenarios"]:
            assert "break_even_age" in s
            assert "defer_years" in s
            assert "enhanced_annual" in s
            assert s["enhanced_annual"] > 11500

    def test_uplift_correct(self):
        result = _analyse_sp_deferral(
            state_pension_real=10000, deferral_rate=0.058,
            retirement_age=67, state_pension_age=67, life_expectancy=85,
        )
        one_year = next(s for s in result["scenarios"] if s["defer_years"] == 1)
        assert one_year["enhanced_annual"] == pytest.approx(10580, abs=1)

    def test_short_life_expectancy_fewer_scenarios(self):
        result = _analyse_sp_deferral(
            state_pension_real=11500, deferral_rate=0.058,
            retirement_age=67, state_pension_age=67, life_expectancy=70,
        )
        # Only 3 years from SPA to death, so 5-year deferral excluded
        defer_years = [s["defer_years"] for s in result["scenarios"]]
        assert 5 not in defer_years


class TestEdgeCases:
    def test_zero_pension(self, assumptions):
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "No Pension", "age": 60, "retirement_age": 67},
            "income": {"primary_gross_annual": 30000},
            "expenses": {"housing": {"rent_monthly": 800}},
            "savings": {"emergency_fund": 5000, "pension_balance": 0},
            "debts": [],
            "goals": [],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        inv = analyse_investments(profile, assumptions, cashflow)
        result = model_withdrawal_sequence(profile, assumptions, inv)
        assert result["optimised_total_tax"] >= 0
        assert len(result["optimised_schedule"]) > 0

    def test_already_retired(self, assumptions):
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "Retiree", "age": 70, "retirement_age": 67},
            "income": {"primary_gross_annual": 0},
            "expenses": {"housing": {"rent_monthly": 700}},
            "savings": {
                "emergency_fund": 20000, "pension_balance": 200000,
                "isa_balance": 50000,
            },
            "debts": [],
            "goals": [],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        inv = analyse_investments(profile, assumptions, cashflow)
        result = model_withdrawal_sequence(profile, assumptions, inv)
        assert len(result["optimised_schedule"]) > 0
