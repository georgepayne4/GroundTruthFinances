"""Tests for engine/estate.py — estate & IHT modelling with gift strategies (v8.5)."""

from __future__ import annotations

import pytest

from engine.estate import (
    _build_iht_timeline,
    _calculate_available_rnrb,
    _calculate_iht_with_gifts,
    _calculate_taper_relief,
    _classify_gifts,
    analyse_estate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def iht_cfg():
    return {
        "nil_rate_band": 325000,
        "residence_nil_rate": 175000,
        "rate": 0.40,
        "charitable_rate": 0.36,
        "charitable_threshold_pct": 0.10,
        "spousal_exemption": True,
        "annual_gift_exemption": 3000,
        "small_gift_limit": 250,
        "pet_full_exemption_years": 7,
        "taper_relief": [
            {"min_years": 3, "relief_pct": 0.20},
            {"min_years": 4, "relief_pct": 0.40},
            {"min_years": 5, "relief_pct": 0.60},
            {"min_years": 6, "relief_pct": 0.80},
        ],
        "rnrb_taper_threshold": 2000000,
        "rnrb_taper_rate": 0.50,
    }


# ---------------------------------------------------------------------------
# Edge cases first
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_estate_no_iht(self, iht_cfg):
        result = _calculate_iht_with_gifts(0, 500000, 0, iht_cfg, False)
        assert result["iht_liability"] == 0

    def test_estate_at_nrb_boundary(self, iht_cfg):
        result = _calculate_iht_with_gifts(325000, 325000, 0, iht_cfg, False)
        assert result["iht_liability"] == 0

    def test_estate_one_pound_over(self, iht_cfg):
        result = _calculate_iht_with_gifts(325001, 325000, 0, iht_cfg, False)
        assert result["iht_liability"] == pytest.approx(0.40, abs=0.01)

    def test_pet_exactly_seven_years(self, iht_cfg):
        gifts = [{"amount": 50000, "years_ago": 7, "type": "pet", "description": "Gift"}]
        result = _classify_gifts(gifts, iht_cfg, 60, 85, None)
        assert result["total_pets_outstanding"] == 0
        assert result["total_exempt"] == 50000

    def test_pet_under_seven_years(self, iht_cfg):
        gifts = [{"amount": 50000, "years_ago": 5, "type": "pet", "description": "Gift"}]
        result = _classify_gifts(gifts, iht_cfg, 60, 85, None)
        assert result["total_pets_outstanding"] == 50000

    def test_spousal_exemption_overrides(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.loader import normalise_profile
        from engine.mortgage import analyse_mortgage

        profile = normalise_profile({
            "personal": {"name": "Spouse", "age": 60, "retirement_age": 67, "dependents": 2},
            "income": {"primary_gross_annual": 100000, "partner_gross_annual": 50000},
            "expenses": {"housing": {"mortgage_monthly": 1500}},
            "savings": {"emergency_fund": 50000, "pension_balance": 500000},
            "debts": [],
            "goals": [],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        debt = analyse_debt(profile, assumptions)
        inv = analyse_investments(profile, assumptions, cashflow)
        mort = analyse_mortgage(profile, assumptions, cashflow, debt)
        result = analyse_estate(profile, assumptions, inv, mort, cashflow)
        assert result["iht_liability"] == 0

    def test_no_estate_planning_backward_compat(self, sample_profile, assumptions):
        from engine.cashflow import analyse_cashflow
        from engine.debt import analyse_debt
        from engine.investments import analyse_investments
        from engine.mortgage import analyse_mortgage

        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        mort = analyse_mortgage(sample_profile, assumptions, cashflow, debt)
        result = analyse_estate(sample_profile, assumptions, inv, mort, cashflow)
        assert "projected_estate_value" in result
        assert "iht_timeline" in result
        assert "gift_analysis" in result
        assert "optimisation_suggestions" in result


# ---------------------------------------------------------------------------
# RNRB taper
# ---------------------------------------------------------------------------


class TestRNRBTaper:
    def test_full_rnrb_below_threshold(self, iht_cfg):
        result = _calculate_available_rnrb(500000, True, 1500000, iht_cfg)
        assert result == 175000

    def test_rnrb_taper_above_threshold(self, iht_cfg):
        # Estate 2.35M → 350k over threshold → 175k RNRB fully eliminated
        result = _calculate_available_rnrb(500000, True, 2350000, iht_cfg)
        assert result == 0

    def test_rnrb_partial_taper(self, iht_cfg):
        # Estate 2.1M → 100k over → 50k reduction → 125k RNRB
        result = _calculate_available_rnrb(500000, True, 2100000, iht_cfg)
        assert result == 125000

    def test_no_rnrb_no_property(self, iht_cfg):
        result = _calculate_available_rnrb(0, True, 500000, iht_cfg)
        assert result == 0

    def test_no_rnrb_no_descendants(self, iht_cfg):
        result = _calculate_available_rnrb(500000, False, 500000, iht_cfg)
        assert result == 0


# ---------------------------------------------------------------------------
# Taper relief
# ---------------------------------------------------------------------------


class TestTaperRelief:
    def test_under_3_years_no_relief(self, iht_cfg):
        assert _calculate_taper_relief(2, iht_cfg["taper_relief"]) == 0.0

    def test_3_to_4_years(self, iht_cfg):
        assert _calculate_taper_relief(3.5, iht_cfg["taper_relief"]) == 0.20

    def test_4_to_5_years(self, iht_cfg):
        assert _calculate_taper_relief(4.5, iht_cfg["taper_relief"]) == 0.40

    def test_5_to_6_years(self, iht_cfg):
        assert _calculate_taper_relief(5.5, iht_cfg["taper_relief"]) == 0.60

    def test_6_to_7_years(self, iht_cfg):
        assert _calculate_taper_relief(6.5, iht_cfg["taper_relief"]) == 0.80

    def test_no_bands_uses_defaults(self):
        assert _calculate_taper_relief(4.5, []) == 0.40


# ---------------------------------------------------------------------------
# Gift classification
# ---------------------------------------------------------------------------


class TestClassifyGifts:
    def test_annual_exemption(self, iht_cfg):
        gifts = [{"amount": 3000, "years_ago": 1, "type": "annual_exemption", "description": "Annual"}]
        result = _classify_gifts(gifts, iht_cfg, 60, 85, None)
        assert result["total_exempt"] == 3000
        assert result["annual_exemption_remaining"] == 0

    def test_small_gift_under_limit(self, iht_cfg):
        gifts = [{"amount": 200, "years_ago": 1, "type": "small_gift", "description": "Small"}]
        result = _classify_gifts(gifts, iht_cfg, 60, 85, None)
        assert result["total_exempt"] == 200

    def test_pet_classified(self, iht_cfg):
        gifts = [{"amount": 50000, "years_ago": 3, "type": "pet", "description": "PET"}]
        result = _classify_gifts(gifts, iht_cfg, 60, 85, None)
        assert result["total_pets_outstanding"] == 50000
        assert result["gifts"][0]["taper_relief_pct"] == 0.20

    def test_regular_income_exempt(self, iht_cfg):
        regular = {"annual_amount": 5000}
        cashflow = {"surplus": {"monthly": 500}}
        result = _classify_gifts([], iht_cfg, 60, 85, cashflow, regular)
        assert result["regular_income_gifts"]["exempt"] is True


# ---------------------------------------------------------------------------
# IHT with gifts
# ---------------------------------------------------------------------------


class TestIHTWithGifts:
    def test_pets_consume_nrb(self, iht_cfg):
        # Estate 600k, PET 200k, NRB 500k
        # PET uses 200k of NRB, leaving 300k for estate
        # Taxable: 600k - 300k = 300k, IHT = 120k
        result = _calculate_iht_with_gifts(600000, 500000, 200000, iht_cfg, False)
        assert result["nrb_used_by_pets"] == 200000
        assert result["nrb_for_estate"] == 300000
        assert result["iht_liability"] == pytest.approx(120000, abs=1)

    def test_pet_exceeds_nrb(self, iht_cfg):
        # PET 400k > NRB 325k → 75k taxable at 40%
        result = _calculate_iht_with_gifts(500000, 325000, 400000, iht_cfg, False)
        assert result["nrb_used_by_pets"] == 325000
        assert result["iht_on_pets"] == pytest.approx(30000, abs=1)

    def test_charitable_rate(self, iht_cfg):
        # With charitable intent, rate drops from 40% to 36%
        result_standard = _calculate_iht_with_gifts(800000, 500000, 0, iht_cfg, False)
        result_charity = _calculate_iht_with_gifts(800000, 500000, 0, iht_cfg, True)
        assert result_charity["effective_rate"] == 0.36
        assert result_charity["iht_liability"] < result_standard["iht_liability"]


# ---------------------------------------------------------------------------
# IHT timeline
# ---------------------------------------------------------------------------


class TestIHTTimeline:
    def test_timeline_length(self, iht_cfg):
        breakdown = {"investments": 100000, "liquid_savings": 50000, "property": 300000}
        gift_analysis = {"gifts": [], "total_pets_outstanding": 0}
        timeline = _build_iht_timeline(
            60, 85, breakdown, gift_analysis, iht_cfg, 325000, 175000,
            0.06, 0.03, 0.04, False,
        )
        assert len(timeline) == 26  # 60 to 85 inclusive

    def test_timeline_estate_grows(self, iht_cfg):
        breakdown = {"investments": 100000, "liquid_savings": 50000, "property": 300000}
        gift_analysis = {"gifts": [], "total_pets_outstanding": 0}
        timeline = _build_iht_timeline(
            60, 85, breakdown, gift_analysis, iht_cfg, 325000, 175000,
            0.06, 0.03, 0.04, False,
        )
        assert timeline[-1]["estate_value"] > timeline[0]["estate_value"]

    def test_timeline_no_iht_with_partner(self, iht_cfg):
        breakdown = {"investments": 1000000, "liquid_savings": 500000, "property": 500000}
        gift_analysis = {"gifts": [], "total_pets_outstanding": 0}
        timeline = _build_iht_timeline(
            60, 85, breakdown, gift_analysis, iht_cfg, 325000, 175000,
            0.06, 0.03, 0.04, True,
        )
        assert all(entry["iht_liability"] == 0 for entry in timeline)


# ---------------------------------------------------------------------------
# Optimisation suggestions
# ---------------------------------------------------------------------------


class TestOptimisationSuggestions:
    def test_suggests_annual_exemption(self, iht_cfg):
        from engine.estate import _generate_optimisation_suggestions
        gift_analysis = {"annual_exemption_remaining": 3000}
        suggestions = _generate_optimisation_suggestions(
            1000000, 200000, gift_analysis, iht_cfg, 500, {}, 20, 0.40,
        )
        strategies = [s["strategy"] for s in suggestions]
        assert "annual_gift_exemption" in strategies

    def test_suggests_pet_strategy(self, iht_cfg):
        from engine.estate import _generate_optimisation_suggestions
        gift_analysis = {"annual_exemption_remaining": 3000}
        suggestions = _generate_optimisation_suggestions(
            2000000, 600000, gift_analysis, iht_cfg, 500, {}, 20, 0.40,
        )
        strategies = [s["strategy"] for s in suggestions]
        assert "pet_7_year_rule" in strategies

    def test_bpr_flag(self, iht_cfg):
        from engine.estate import _generate_optimisation_suggestions
        gift_analysis = {"annual_exemption_remaining": 3000}
        suggestions = _generate_optimisation_suggestions(
            1000000, 200000, gift_analysis, iht_cfg, 500,
            {"has_business_property": True}, 20, 0.40,
        )
        strategies = [s["strategy"] for s in suggestions]
        assert "business_property_relief" in strategies

    def test_apr_flag(self, iht_cfg):
        from engine.estate import _generate_optimisation_suggestions
        gift_analysis = {"annual_exemption_remaining": 3000}
        suggestions = _generate_optimisation_suggestions(
            1000000, 200000, gift_analysis, iht_cfg, 500,
            {"has_agricultural_property": True}, 20, 0.40,
        )
        strategies = [s["strategy"] for s in suggestions]
        assert "agricultural_property_relief" in strategies

    def test_no_suggestions_when_no_liability(self, iht_cfg):
        from engine.estate import _generate_optimisation_suggestions
        gift_analysis = {"annual_exemption_remaining": 3000}
        suggestions = _generate_optimisation_suggestions(
            100000, 0, gift_analysis, iht_cfg, 500, {}, 20, 0.40,
        )
        assert len(suggestions) == 0


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    def test_estate_in_report(self, sample_profile, assumptions):
        from engine.pipeline import run_pipeline
        report, _, _ = run_pipeline(sample_profile, assumptions_override=assumptions)
        estate = report["estate"]
        assert "iht_timeline" in estate
        assert "gift_analysis" in estate
        assert "optimisation_suggestions" in estate
        assert "estimated_tax_savings" in estate

    def test_estate_insights_in_report(self, sample_profile, assumptions):
        from engine.pipeline import run_pipeline
        report, _, _ = run_pipeline(sample_profile, assumptions_override=assumptions)
        insights = report.get("advisor_insights", {})
        assert "estate_insights" in insights
