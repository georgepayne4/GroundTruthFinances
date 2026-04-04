"""Tests for engine/validator.py."""

from __future__ import annotations

import pytest

from engine.validator import validate_profile, Severity


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
