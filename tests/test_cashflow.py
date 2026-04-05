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


class TestSideIncomeTax:
    def test_side_income_taxed_at_marginal_rate(self, assumptions):
        """Side income for a higher-rate taxpayer should be taxed above 20%."""
        from engine.loader import _normalise_profile
        profile = _normalise_profile({
            "personal": {"age": 35, "employment_type": "employed"},
            "income": {
                "primary_gross_annual": 80000,
                "side_income_monthly": 500,  # £6,000/year
            },
            "expenses": {"housing": {"rent_monthly": 1200}},
            "savings": {
                "pension_personal_contribution_pct": 0.0,
                "pension_employer_contribution_pct": 0.0,
            },
            "debts": [],
            "goals": [],
        })
        result = analyse_cashflow(profile, assumptions)
        other_tax = result["deductions"]["other_income_tax_annual"]
        # £80k primary is well into higher rate band (40%)
        # So £6k side income should be taxed at ~40%, not flat 20%
        # At flat 20%: other_tax = 1200. At 40%: other_tax = 2400
        assert other_tax > 1200, f"Side income tax {other_tax} should be above flat 20% (1200)"

    def test_side_income_basic_rate_for_low_earner(self, assumptions):
        """Side income for a basic-rate taxpayer should be taxed at 20%."""
        from engine.loader import _normalise_profile
        profile = _normalise_profile({
            "personal": {"age": 25, "employment_type": "employed"},
            "income": {
                "primary_gross_annual": 30000,
                "side_income_monthly": 200,  # £2,400/year
            },
            "expenses": {"housing": {"rent_monthly": 800}},
            "savings": {
                "pension_personal_contribution_pct": 0.0,
                "pension_employer_contribution_pct": 0.0,
            },
            "debts": [],
            "goals": [],
        })
        result = analyse_cashflow(profile, assumptions)
        other_tax = result["deductions"]["other_income_tax_annual"]
        # £30k primary is entirely within basic band. Side income also basic rate.
        # £2400 * 0.20 = £480
        assert abs(other_tax - 480) < 1, f"Expected ~480, got {other_tax}"


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
