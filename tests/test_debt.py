"""Tests for engine/debt.py."""

from __future__ import annotations

import pytest

from engine.debt import _is_full_pay_card, analyse_debt
from engine.loader import _normalise_profile


class TestDebtAnalysis:
    def test_no_debts(self, minimal_profile, assumptions):
        result = analyse_debt(minimal_profile, assumptions)
        assert result["summary"]["total_balance"] == 0

    def test_with_debts(self, sample_profile, assumptions):
        result = analyse_debt(sample_profile, assumptions)
        assert result["summary"]["total_balance"] > 0
        assert result.get("recommended_strategy") is not None

    def test_avalanche_order_by_interest_rate(self, assumptions):
        """Avalanche should prioritise highest interest rate first."""
        profile = _normalise_profile({
            "personal": {"age": 30, "employment_type": "employed"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 5000},
            "debts": [
                {"name": "Low rate", "balance": 5000, "interest_rate": 0.05, "minimum_payment_monthly": 100, "type": "personal_loan"},
                {"name": "High rate", "balance": 3000, "interest_rate": 0.25, "minimum_payment_monthly": 80, "type": "credit_card"},
            ],
            "goals": [],
        })
        result = analyse_debt(profile, assumptions)
        if result.get("avalanche_order"):
            assert result["avalanche_order"][0] == "High rate"

    def test_student_loan_write_off(self, sample_profile, assumptions):
        result = analyse_debt(sample_profile, assumptions)
        for d in result.get("debts", []):
            if "student" in d.get("name", "").lower():
                woi = d.get("write_off_intelligence")
                if woi:
                    assert "will_be_written_off" in woi


# ---------------------------------------------------------------------------
# v5.2-03: Credit card model
# ---------------------------------------------------------------------------

@pytest.fixture
def full_pay_card_profile() -> dict:
    """Profile with one paid-in-full credit card and one revolver."""
    return _normalise_profile({
        "personal": {"age": 30, "employment_type": "employed",
                     "retirement_age": 67, "dependents": 0,
                     "risk_profile": "moderate"},
        "income": {"primary_gross_annual": 50000},
        "expenses": {"housing": {"rent_monthly": 1000}},
        "savings": {"emergency_fund": 5000, "pension_balance": 0,
                    "pension_personal_contribution_pct": 0.05,
                    "pension_employer_contribution_pct": 0.03},
        "debts": [
            {
                "name": "Amex Cashback",
                "type": "credit_card",
                "balance": 800,
                "interest_rate": 0.346,
                "minimum_payment_monthly": 0,
                "statement_balance": 800,
                "current_balance": 800,
                "credit_limit": 10000,
                "payment_behaviour": "full",
                "monthly_spend": 800,
            },
            {
                "name": "Revolver Card",
                "type": "credit_card",
                "balance": 3000,
                "interest_rate": 0.219,
                "minimum_payment_monthly": 90,
                "statement_balance": 3000,
                "current_balance": 3000,
                "credit_limit": 5000,
                "payment_behaviour": "minimum",
                "monthly_spend": 200,
            },
        ],
        "goals": [],
    })


class TestCreditCardModel:
    def test_is_full_pay_card_helper(self):
        assert _is_full_pay_card({"type": "credit_card", "payment_behaviour": "full"})
        assert not _is_full_pay_card({"type": "credit_card", "payment_behaviour": "minimum"})
        assert not _is_full_pay_card({"type": "credit_card"})  # default = minimum
        assert not _is_full_pay_card({"type": "personal_loan", "payment_behaviour": "full"})

    def test_full_pay_card_excluded_from_total_balance(self, full_pay_card_profile, assumptions):
        result = analyse_debt(full_pay_card_profile, assumptions)
        # Only the £3000 revolver counts
        assert result["summary"]["total_balance"] == 3000

    def test_full_pay_card_excluded_from_avalanche(self, full_pay_card_profile, assumptions):
        result = analyse_debt(full_pay_card_profile, assumptions)
        assert "Amex Cashback" not in result["avalanche_order"]
        assert "Revolver Card" in result["avalanche_order"]

    def test_full_pay_card_excluded_from_dti(self, full_pay_card_profile, assumptions):
        result = analyse_debt(full_pay_card_profile, assumptions)
        # Min payments only count revolver (£90), not the £0 from full-pay card
        assert result["summary"]["total_minimum_monthly"] == 90

    def test_full_pay_card_in_tracking(self, full_pay_card_profile, assumptions):
        result = analyse_debt(full_pay_card_profile, assumptions)
        tracking = result.get("credit_card_tracking", [])
        assert len(tracking) == 1
        card = tracking[0]
        assert card["name"] == "Amex Cashback"
        assert card["utilisation_pct"] == 8.0  # 800/10000
        assert card["utilisation_tier"] == "low"
        assert card["treated_as"] == "cash_flow_tool"

    def test_high_utilisation_tier(self, assumptions):
        profile = _normalise_profile({
            "personal": {"age": 30, "employment_type": "employed",
                         "retirement_age": 67, "dependents": 0,
                         "risk_profile": "moderate"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 5000, "pension_balance": 0,
                        "pension_personal_contribution_pct": 0.05,
                        "pension_employer_contribution_pct": 0.03},
            "debts": [{
                "name": "Maxed Card",
                "type": "credit_card",
                "balance": 4500,
                "interest_rate": 0.30,
                "minimum_payment_monthly": 0,
                "current_balance": 4500,
                "credit_limit": 5000,
                "payment_behaviour": "full",
            }],
            "goals": [],
        })
        result = analyse_debt(profile, assumptions)
        tracking = result["credit_card_tracking"]
        assert tracking[0]["utilisation_tier"] == "high"  # 90%

    def test_summary_full_pay_card_count(self, full_pay_card_profile, assumptions):
        result = analyse_debt(full_pay_card_profile, assumptions)
        assert result["summary"]["full_pay_card_count"] == 1

    def test_backward_compat_no_new_fields(self, sample_profile, assumptions):
        """Existing profiles without new fields must still work."""
        result = analyse_debt(sample_profile, assumptions)
        # Sample has the new fields now, but the credit card uses payment_behaviour=minimum
        # → still treated as a real debt
        assert any("Credit Card" in n for n in result["avalanche_order"])

    def test_loader_excludes_full_pay_from_debt_summary(self, full_pay_card_profile):
        summary = full_pay_card_profile["_debt_summary"]
        # Real debts: 1 (the revolver)
        assert summary["count"] == 1
        assert summary["total_balance"] == 3000
        assert summary["full_pay_card_count"] == 1

    def test_loader_subtracts_full_pay_from_net_worth(self, full_pay_card_profile):
        # Assets: 5000 emergency fund + 0 pension = 5000
        # Real debt: 3000 revolver
        # Full-pay committed: 800
        # Net worth: 5000 - 3000 - 800 = 1200
        assert full_pay_card_profile["_net_worth"] == 1200
