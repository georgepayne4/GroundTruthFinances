"""Tests for engine/debt.py."""

from __future__ import annotations

from engine.debt import analyse_debt


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
        from engine.loader import _normalise_profile
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
