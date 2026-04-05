"""Tests for engine/cashflow.py."""

from __future__ import annotations

from engine.cashflow import _salary_sacrifice_comparison, analyse_cashflow


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


SS_TAX_CFG = {
    "personal_allowance": 12570,
    "basic_rate": 0.20,
    "basic_threshold": 50270,
    "higher_rate": 0.40,
    "higher_threshold": 125140,
    "additional_rate": 0.45,
    "national_insurance_rate": 0.08,
    "employer_national_insurance_rate": 0.15,
    "employer_ni_threshold": 5000,
}


class TestSalarySacrifice:
    """v5.1-11: Salary sacrifice modelling."""

    def test_comparison_shows_ni_savings(self):
        # ��50k salary, 5% personal contribution = £2,500
        result = _salary_sacrifice_comparison(50000, 2500, 1500, SS_TAX_CFG, "personal")
        assert result["employee_ni_saving_annual"] == 200.0  # 2500 * 0.08
        assert result["employer_ni_saving_annual"] == 375.0  # 2500 * 0.15
        assert result["combined_ni_saving_annual"] == 575.0

    def test_comparison_employer_passthrough(self):
        result = _salary_sacrifice_comparison(50000, 2500, 1500, SS_TAX_CFG, "personal")
        passthrough = result["if_employer_passes_ni_saving"]
        # 2500 personal + 1500 employer + 375 employer NI saving
        assert passthrough["total_pension_with_passthrough"] == 4375.0

    def test_salary_sacrifice_mode_reduces_ni(self, assumptions):
        from engine.loader import _normalise_profile
        base = {
            "personal": {"age": 30, "employment_type": "employed"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 800}},
            "savings": {
                "pension_personal_contribution_pct": 0.05,
                "pension_employer_contribution_pct": 0.03,
            },
            "debts": [],
            "goals": [],
        }
        profile_personal = _normalise_profile(dict(base))
        result_personal = analyse_cashflow(profile_personal, assumptions)

        base_ss = dict(base)
        base_ss["savings"] = dict(base["savings"])
        base_ss["savings"]["pension_contribution_method"] = "salary_sacrifice"
        profile_ss = _normalise_profile(base_ss)
        result_ss = analyse_cashflow(profile_ss, assumptions)

        # Salary sacrifice should have lower NI (higher take-home)
        ni_personal = result_personal["deductions"]["national_insurance_annual"]
        ni_ss = result_ss["deductions"]["national_insurance_annual"]
        assert ni_ss < ni_personal, f"SS NI {ni_ss} should be less than personal {ni_personal}"

        # Net income should be higher under salary sacrifice
        net_personal = result_personal["net_income"]["annual"]
        net_ss = result_ss["net_income"]["annual"]
        assert net_ss > net_personal

    def test_salary_sacrifice_ni_saving_amount(self, assumptions):
        """Employee NI saving should equal contribution * NI rate."""
        from engine.loader import _normalise_profile
        base = {
            "personal": {"age": 30, "employment_type": "employed"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 800}},
            "savings": {
                "pension_personal_contribution_pct": 0.05,
                "pension_employer_contribution_pct": 0.03,
            },
            "debts": [],
            "goals": [],
        }
        profile_personal = _normalise_profile(dict(base))
        result_personal = analyse_cashflow(profile_personal, assumptions)

        base_ss = dict(base)
        base_ss["savings"] = dict(base["savings"])
        base_ss["savings"]["pension_contribution_method"] = "salary_sacrifice"
        profile_ss = _normalise_profile(base_ss)
        result_ss = analyse_cashflow(profile_ss, assumptions)

        ni_diff = (
            result_personal["deductions"]["national_insurance_annual"]
            - result_ss["deductions"]["national_insurance_annual"]
        )
        # Contribution = 50000 * 0.05 = 2500. NI rate = 0.08. Expected saving = 200
        assert abs(ni_diff - 200) < 1

    def test_comparison_included_in_result(self, sample_profile, assumptions):
        result = analyse_cashflow(sample_profile, assumptions)
        # sample_profile has pension contributions, so comparison should exist
        assert "salary_sacrifice_comparison" in result
        ss = result["salary_sacrifice_comparison"]
        assert ss["current_method"] == "personal"
        assert ss["employee_ni_saving_annual"] > 0

    def test_no_comparison_for_self_employed(self, self_employed_profile, assumptions):
        result = analyse_cashflow(self_employed_profile, assumptions)
        # Salary sacrifice is only for employed — not available for self-employed
        assert "salary_sacrifice_comparison" not in result


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
