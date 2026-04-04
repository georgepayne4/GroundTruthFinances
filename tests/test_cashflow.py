"""Tests for engine/cashflow.py."""

from __future__ import annotations

import pytest

from engine.cashflow import analyse_cashflow


class TestCashflowBasic:
    def test_returns_required_keys(self, sample_profile, assumptions):
        result = analyse_cashflow(sample_profile, assumptions)
        assert "income" in result
        assert "deductions" in result
        assert "net_income" in result
        assert "expenses" in result
        assert "surplus" in result
        assert "savings_rate" in result

    def test_net_income_is_positive(self, sample_profile, assumptions):
        result = analyse_cashflow(sample_profile, assumptions)
        assert result["net_income"]["annual"] > 0
        assert result["net_income"]["monthly"] > 0

    def test_surplus_equals_net_minus_outgoings(self, sample_profile, assumptions):
        result = analyse_cashflow(sample_profile, assumptions)
        net = result["net_income"]["monthly"]
        outgoings = result["total_outgoings_monthly"]
        surplus = result["surplus"]["monthly"]
        assert abs(surplus - (net - outgoings)) < 0.01

    def test_annual_is_monthly_times_twelve(self, sample_profile, assumptions):
        result = analyse_cashflow(sample_profile, assumptions)
        assert abs(result["surplus"]["annual"] - result["surplus"]["monthly"] * 12) < 0.10
        assert abs(result["net_income"]["annual"] - result["net_income"]["monthly"] * 12) < 0.10


class TestCashflowSelfEmployed:
    def test_business_expenses_reduce_taxable(self, self_employed_profile, assumptions):
        result = analyse_cashflow(self_employed_profile, assumptions)
        assert result.get("self_employment") is not None
        se = result["self_employment"]
        assert se["taxable_profit"] == 70000  # 80000 - 10000
        assert se["business_expenses_deducted"] == 10000

    def test_quarterly_tax_estimate(self, self_employed_profile, assumptions):
        result = analyse_cashflow(self_employed_profile, assumptions)
        se = result["self_employment"]
        assert se["quarterly_tax_payment"] > 0


class TestCashflowHighEarner:
    def test_higher_deductions(self, high_earner_profile, assumptions):
        result = analyse_cashflow(high_earner_profile, assumptions)
        deductions = result["deductions"]
        assert deductions["income_tax_annual"] > 20000
        assert deductions["pension_personal_annual"] > 0

    def test_bonus_scenarios_use_progressive_tax(self, high_earner_profile, assumptions):
        result = analyse_cashflow(high_earner_profile, assumptions)
        scenarios = result.get("bonus_scenarios")
        if scenarios:
            expected = scenarios.get("expected", {})
            assert expected["gross"] == 30000
            assert expected["tax"] > 0
            assert expected["net"] == expected["gross"] - expected["tax"]


class TestCashflowPartner:
    def test_partner_section(self, sample_profile, assumptions):
        # Add partner to sample profile
        profile = dict(sample_profile)
        profile["partner"] = {
            "name": "Test Partner",
            "gross_salary": 45000,
            "pension_contribution_pct": 0.05,
            "employer_pension_pct": 0.03,
        }
        result = analyse_cashflow(profile, assumptions)
        assert "partner" in result
        assert "household" in result
        assert result["partner"]["gross_salary"] == 45000
        assert result["household"]["combined_gross_annual"] > result["income"]["primary_gross_annual"]
