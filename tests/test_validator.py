"""Tests for engine/validator.py."""

from __future__ import annotations

from engine.validator import Severity, validate_profile


class TestValidatorRequiredSections:
    def test_missing_personal_is_error(self, assumptions):
        flags = validate_profile({"income": {"primary_gross_annual": 50000}}, assumptions)
        errors = [f for f in flags if f.severity == Severity.ERROR]
        fields = [e.field for e in errors]
        assert "personal" in fields

    def test_missing_income_is_error(self, assumptions):
        flags = validate_profile({"personal": {"age": 30}}, assumptions)
        errors = [f for f in flags if f.severity == Severity.ERROR]
        fields = [e.field for e in errors]
        assert "income" in fields

    def test_valid_profile_no_errors(self, sample_profile, assumptions):
        flags = validate_profile(sample_profile, assumptions)
        errors = [f for f in flags if f.severity == Severity.ERROR]
        assert len(errors) == 0


class TestValidatorPersonal:
    def test_missing_age(self, assumptions):
        profile = {
            "personal": {"name": "Test"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 1000},
        }
        flags = validate_profile(profile, assumptions)
        age_errors = [f for f in flags if "age" in f.field.lower() and f.severity == Severity.ERROR]
        assert len(age_errors) > 0

    def test_zero_income_is_error(self, assumptions):
        profile = {
            "personal": {"age": 30},
            "income": {"primary_gross_annual": 0},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 1000},
        }
        flags = validate_profile(profile, assumptions)
        income_errors = [f for f in flags if "income" in f.field.lower() and f.severity == Severity.ERROR]
        assert len(income_errors) > 0


class TestValidationHardening:
    """v5.1-09: Additional validation checks."""

    def test_debt_rate_as_percentage_is_error(self, assumptions):
        profile = {
            "personal": {"age": 30},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 5000},
            "debts": [{"balance": 5000, "interest_rate": 20, "minimum_payment_monthly": 100, "type": "credit_card"}],
        }
        flags = validate_profile(profile, assumptions)
        rate_errors = [f for f in flags if "interest_rate" in f.field and f.severity == Severity.ERROR]
        assert len(rate_errors) > 0
        assert "percentage" in rate_errors[0].message.lower() or "decimal" in rate_errors[0].message.lower()

    def test_lisa_over_contribution_is_error(self, assumptions):
        profile = {
            "personal": {"age": 28},
            "income": {"primary_gross_annual": 40000},
            "expenses": {"housing": {"rent_monthly": 800}},
            "savings": {
                "emergency_fund": 5000,
                "lisa_balance": 8000,
                "lisa_contributions_this_year": 5000,
                "pension_personal_contribution_pct": 0.05,
                "pension_employer_contribution_pct": 0.03,
            },
        }
        flags = validate_profile(profile, assumptions)
        lisa_errors = [f for f in flags if "lisa_contributions" in f.field and f.severity == Severity.ERROR]
        assert len(lisa_errors) > 0

    def test_lisa_property_over_limit(self, assumptions):
        profile = {
            "personal": {"age": 28},
            "income": {"primary_gross_annual": 60000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {
                "emergency_fund": 10000,
                "lisa_balance": 10000,
                "pension_personal_contribution_pct": 0.05,
                "pension_employer_contribution_pct": 0.03,
            },
            "mortgage": {"target_property_value": 500000},
        }
        flags = validate_profile(profile, assumptions)
        lisa_prop = [f for f in flags if "lisa_property" in f.field]
        assert len(lisa_prop) > 0

    def test_partner_no_salary_warned(self, assumptions):
        profile = {
            "personal": {"age": 30},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 5000},
            "partner": {"name": "Test Partner"},
        }
        flags = validate_profile(profile, assumptions)
        partner_flags = [f for f in flags if "partner.gross_salary" in f.field]
        assert len(partner_flags) > 0

    def test_pension_exceeds_annual_allowance(self, assumptions):
        profile = {
            "personal": {"age": 45},
            "income": {"primary_gross_annual": 150000},
            "expenses": {"housing": {"rent_monthly": 2000}},
            "savings": {
                "emergency_fund": 50000,
                "pension_personal_contribution_pct": 0.30,
                "pension_employer_contribution_pct": 0.15,
            },
        }
        flags = validate_profile(profile, assumptions)
        # 150000 * 0.45 = 67500 > 60000 annual allowance
        aa_flags = [f for f in flags if "pension_contributions" in f.field]
        assert len(aa_flags) > 0
