"""Tests for engine/tax.py — income tax, NI, CGT, dividend tax."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from engine.tax import (
    calculate_income_tax,
    calculate_marriage_allowance,
    calculate_national_insurance,
    calculate_tax_on_pension_withdrawal,
    calculate_capital_gains_tax,
    calculate_dividend_tax,
)

TAX_CFG = {
    "personal_allowance": 12570,
    "basic_rate": 0.20,
    "basic_threshold": 50270,
    "higher_rate": 0.40,
    "higher_threshold": 125140,
    "additional_rate": 0.45,
    "national_insurance_rate": 0.08,
}


@pytest.fixture
def tax_cfg():
    return dict(TAX_CFG)


@pytest.fixture
def cgt_cfg():
    return {
        "annual_exemption": 3000,
        "basic_rate": 0.10,
        "higher_rate": 0.20,
        "basic_rate_property": 0.18,
        "higher_rate_property": 0.24,
    }


@pytest.fixture
def div_cfg():
    return {
        "allowance": 500,
        "basic_rate": 0.0875,
        "higher_rate": 0.3375,
        "additional_rate": 0.3935,
    }


# -----------------------------------------------------------------------
# Income Tax
# -----------------------------------------------------------------------

class TestIncomeTax:
    def test_zero_income(self, tax_cfg):
        assert calculate_income_tax(0, tax_cfg) == 0.0

    def test_negative_income(self, tax_cfg):
        assert calculate_income_tax(-1000, tax_cfg) == 0.0

    def test_below_personal_allowance(self, tax_cfg):
        assert calculate_income_tax(10000, tax_cfg) == 0.0

    def test_exactly_personal_allowance(self, tax_cfg):
        assert calculate_income_tax(12570, tax_cfg) == 0.0

    def test_basic_rate_only(self, tax_cfg):
        # £30,000 gross: taxable = 30000 - 12570 = 17430
        # Tax = 17430 * 0.20 = 3486
        assert calculate_income_tax(30000, tax_cfg) == 3486.0

    def test_at_basic_threshold(self, tax_cfg):
        # £50,270: taxable = 50270 - 12570 = 37700
        # Tax = 37700 * 0.20 = 7540
        assert calculate_income_tax(50270, tax_cfg) == 7540.0

    def test_higher_rate(self, tax_cfg):
        # £80,000: taxable = 80000 - 12570 = 67430
        # Basic band = 50270 - 12570 = 37700 -> 37700 * 0.20 = 7540
        # Higher band = 67430 - 37700 = 29730 -> 29730 * 0.40 = 11892
        # Total = 19432
        assert calculate_income_tax(80000, tax_cfg) == 19432.0

    def test_personal_allowance_taper(self, tax_cfg):
        # £125,140: PA reduced to 0 (125140 - 100000 = 25140, reduction = 12570)
        # Effective PA = 0
        # Taxable = 125140
        # Basic: 50270 * 0.20 = 10054
        # Higher: (125140 - 50270) * 0.40 = 29948
        # Total = 40002
        result = calculate_income_tax(125140, tax_cfg)
        assert result == 40002.0

    def test_additional_rate(self, tax_cfg):
        # £200,000: PA = 0 (fully tapered)
        # Basic: 50270 * 0.20 = 10054
        # Higher band: 125140 - 50270 = 74870 -> 74870 * 0.40 = 29948
        # Additional: 200000 - 125140 = 74860 -> 74860 * 0.45 = 33687
        # Total = 73689
        assert calculate_income_tax(200000, tax_cfg) == 73689.0

    @given(income=st.floats(min_value=0, max_value=1_000_000, allow_nan=False))
    def test_tax_never_exceeds_income(self, income):
        tax = calculate_income_tax(income, TAX_CFG)
        assert tax >= 0
        assert tax <= income

    @given(income=st.floats(min_value=0, max_value=1_000_000, allow_nan=False))
    def test_tax_is_monotonically_increasing(self, income):
        tax_lower = calculate_income_tax(income, TAX_CFG)
        tax_higher = calculate_income_tax(income + 1000, TAX_CFG)
        assert tax_higher >= tax_lower


# -----------------------------------------------------------------------
# National Insurance
# -----------------------------------------------------------------------

class TestNationalInsurance:
    def test_zero_income(self, tax_cfg):
        assert calculate_national_insurance(0, tax_cfg) == 0.0

    def test_below_threshold(self, tax_cfg):
        assert calculate_national_insurance(10000, tax_cfg) == 0.0

    def test_employed_ni(self, tax_cfg):
        # £50,000: NI = (50000 - 12570) * 0.08 = 2994.40
        assert calculate_national_insurance(50000, tax_cfg) == 2994.40

    def test_self_employed_ni(self, tax_cfg):
        # Self-employed with £50,000 income
        tax_cfg["self_employment"] = {
            "class4_main_rate": 0.09,
            "class4_additional_rate": 0.02,
            "class2_weekly_rate": 3.45,
        }
        result = calculate_national_insurance(50000, tax_cfg, self_employed=True)
        # Class 4: (50000 - 12570) * 0.09 = 3368.70
        # Class 2: 3.45 * 52 = 179.40
        # Total = 3548.10
        assert result == 3548.10

    @given(income=st.floats(min_value=0, max_value=500_000, allow_nan=False))
    def test_ni_never_negative(self, income):
        assert calculate_national_insurance(income, TAX_CFG) >= 0


# -----------------------------------------------------------------------
# Pension Withdrawal Tax
# -----------------------------------------------------------------------

class TestPensionWithdrawalTax:
    def test_zero_drawdown(self, tax_cfg):
        result = calculate_tax_on_pension_withdrawal(0, 0, tax_cfg)
        assert result["income_tax"] == 0
        assert result["net_income"] == 0

    def test_with_state_pension(self, tax_cfg):
        result = calculate_tax_on_pension_withdrawal(20000, 11502, tax_cfg)
        assert result["tax_free_drawdown"] == 5000  # 25% of 20000
        assert result["taxable_income"] == 26502     # 75% of 20000 + 11502
        assert result["income_tax"] >= 0
        assert result["net_income"] > 0


# -----------------------------------------------------------------------
# Capital Gains Tax
# -----------------------------------------------------------------------

class TestCapitalGainsTax:
    def test_within_exemption(self, cgt_cfg, tax_cfg):
        result = calculate_capital_gains_tax(2000, 40000, cgt_cfg, tax_cfg)
        assert result["taxable_gain"] == 0
        assert result["tax"] == 0

    def test_basic_rate_taxpayer(self, cgt_cfg, tax_cfg):
        # £10,000 gain, £30,000 income -> taxable gain = 7000
        # All within basic band remaining (50270 - 30000 = 20270)
        # Tax = 7000 * 0.10 = 700
        result = calculate_capital_gains_tax(10000, 30000, cgt_cfg, tax_cfg)
        assert result["taxable_gain"] == 7000
        assert result["tax"] == 700.0

    def test_property_rates_higher(self, cgt_cfg, tax_cfg):
        result_std = calculate_capital_gains_tax(10000, 30000, cgt_cfg, tax_cfg, is_property=False)
        result_prop = calculate_capital_gains_tax(10000, 30000, cgt_cfg, tax_cfg, is_property=True)
        assert result_prop["tax"] > result_std["tax"]


# -----------------------------------------------------------------------
# Dividend Tax
# -----------------------------------------------------------------------

class TestDividendTax:
    def test_within_allowance(self, div_cfg, tax_cfg):
        result = calculate_dividend_tax(400, 40000, div_cfg, tax_cfg)
        assert result["taxable_dividends"] == 0
        assert result["tax"] == 0

    def test_basic_rate_dividend(self, div_cfg, tax_cfg):
        result = calculate_dividend_tax(5000, 30000, div_cfg, tax_cfg)
        assert result["taxable_dividends"] == 4500
        assert result["tax"] > 0


# -----------------------------------------------------------------------
# Marriage Allowance
# -----------------------------------------------------------------------

class TestMarriageAllowance:
    def test_eligible_couple(self, tax_cfg):
        # One earns £10k (below PA), other earns £30k (basic rate)
        result = calculate_marriage_allowance(10000, 30000, tax_cfg)
        assert result["eligible"] is True
        assert result["annual_tax_saving"] == 252  # 1260 * 0.20
        assert result["transfer_amount"] == 1260

    def test_eligible_reversed(self, tax_cfg):
        # Works when roles are swapped
        result = calculate_marriage_allowance(30000, 10000, tax_cfg)
        assert result["eligible"] is True
        assert result["annual_tax_saving"] == 252

    def test_ineligible_both_earning(self, tax_cfg):
        # Both above PA — not eligible
        result = calculate_marriage_allowance(30000, 40000, tax_cfg)
        assert result["eligible"] is False

    def test_ineligible_higher_rate(self, tax_cfg):
        # Recipient is higher rate — not eligible
        result = calculate_marriage_allowance(10000, 60000, tax_cfg)
        assert result["eligible"] is False

    def test_ineligible_both_below_pa(self, tax_cfg):
        # Both below PA — neither qualifies as recipient
        result = calculate_marriage_allowance(5000, 8000, tax_cfg)
        assert result["eligible"] is False
