"""Tests for engine/investments.py."""

from __future__ import annotations

from engine.investments import _check_annual_allowance, analyse_investments

AA_CFG = {
    "standard": 60000,
    "taper_threshold": 260000,
    "taper_reduction_rate": 0.50,
    "minimum_allowance": 10000,
    "tax_charge_rate_basic": 0.20,
    "tax_charge_rate_higher": 0.40,
    "tax_charge_rate_additional": 0.45,
}


class TestPensionAnnualAllowance:
    def test_within_allowance(self):
        result = _check_annual_allowance(80000, 15000, AA_CFG)
        assert result["breached"] is False
        assert result["excess"] == 0
        assert result["effective_allowance"] == 60000

    def test_exceeds_allowance(self):
        result = _check_annual_allowance(80000, 65000, AA_CFG)
        assert result["breached"] is True
        assert result["excess"] == 5000
        assert result["estimated_tax_charge"] == 2000  # 5000 * 0.40

    def test_tapered_high_earner(self):
        # £300k income + £50k contributions -> adjusted = £350k
        # Over taper by 90k, reduction = 45000, effective AA = 15000
        result = _check_annual_allowance(300000, 50000, AA_CFG)
        assert result["tapered"] is True
        assert result["effective_allowance"] == 15000
        assert result["breached"] is True
        assert result["excess"] == 35000

    def test_minimum_allowance_floor(self):
        # Very high earner — taper can't reduce below 10000
        result = _check_annual_allowance(500000, 5000, AA_CFG)
        assert result["effective_allowance"] == 10000
        assert result["breached"] is False

    def test_capped_at_earnings(self):
        # Low earner: AA capped at 100% of earnings
        result = _check_annual_allowance(8000, 9000, AA_CFG)
        assert result["effective_allowance"] == 8000
        assert result["breached"] is True
        assert result["excess"] == 1000


class TestInvestmentAnalysis:
    def test_returns_pension_analysis(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        cashflow = analyse_cashflow(sample_profile, assumptions)
        result = analyse_investments(sample_profile, assumptions, cashflow)
        assert "pension_analysis" in result
        assert result["pension_analysis"]["current_balance"] >= 0

    def test_aa_check_included(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        cashflow = analyse_cashflow(sample_profile, assumptions)
        result = analyse_investments(sample_profile, assumptions, cashflow)
        assert "pension_annual_allowance" in result
        aa = result["pension_annual_allowance"]
        assert "breached" in aa
        assert "effective_allowance" in aa


class TestMonteCarloIntegration:
    def test_mc_summary_present_when_configured(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        assumptions["monte_carlo"] = {
            "num_simulations": 200, "percentiles": [10, 50, 90], "random_seed": 42,
        }
        cashflow = analyse_cashflow(sample_profile, assumptions)
        result = analyse_investments(sample_profile, assumptions, cashflow)
        assert "monte_carlo_summary" in result
        assert result["monte_carlo_summary"]["num_simulations"] == 200
        assert "terminal_real" in result["monte_carlo_summary"]

    def test_mc_absent_when_not_configured(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        assumptions.pop("monte_carlo", None)
        cashflow = analyse_cashflow(sample_profile, assumptions)
        result = analyse_investments(sample_profile, assumptions, cashflow)
        assert "monte_carlo_summary" not in result

    def test_pension_mc_fields_present(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        assumptions["monte_carlo"] = {
            "num_simulations": 200, "percentiles": [10, 50, 90], "random_seed": 42,
        }
        cashflow = analyse_cashflow(sample_profile, assumptions)
        result = analyse_investments(sample_profile, assumptions, cashflow)
        mc = result["pension_analysis"].get("monte_carlo")
        assert mc is not None
        assert "narrative" in mc
        assert "probability_of_target_pct" in mc
        assert "pension_pot_percentiles" in mc

    def test_backward_compatibility_without_mc(self, minimal_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        assumptions.pop("monte_carlo", None)
        cashflow = analyse_cashflow(minimal_profile, assumptions)
        result = analyse_investments(minimal_profile, assumptions, cashflow)
        assert "pension_analysis" in result
        assert "monte_carlo" not in result.get("pension_analysis", {})
        assert "monte_carlo_summary" not in result
