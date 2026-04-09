"""Tests for engine/loader.py — multi-account aggregation (v5.2-04) and core normalisation."""

from __future__ import annotations

from engine.loader import _aggregate_accounts, normalise_profile


def _base_profile(**overrides) -> dict:
    base = {
        "personal": {
            "name": "Test", "age": 30, "retirement_age": 67,
            "dependents": 0, "risk_profile": "moderate",
            "employment_type": "employed",
        },
        "income": {"primary_gross_annual": 50000},
        "expenses": {"housing": {"rent_monthly": 1000}},
        "savings": {
            "emergency_fund": 0,
            "general_savings": 0,
            "isa_balance": 0,
            "lisa_balance": 0,
            "pension_balance": 0,
            "other_investments": 0,
            "pension_personal_contribution_pct": 0.05,
            "pension_employer_contribution_pct": 0.03,
        },
        "debts": [],
        "goals": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _aggregate_accounts unit tests
# ---------------------------------------------------------------------------

class TestAggregateAccounts:
    def test_no_accounts_returns_empty(self):
        assert _aggregate_accounts({"accounts": []}) == {}
        assert _aggregate_accounts({}) == {}

    def test_default_type_mapping(self):
        accounts = [
            {"name": "Monzo", "type": "current", "balance": 1500},
            {"name": "Chase ISA", "type": "isa", "balance": 6000},
            {"name": "SIPP", "type": "pension", "balance": 30000},
        ]
        totals = _aggregate_accounts({"accounts": accounts})
        assert totals["general_savings"] == 1500
        assert totals["isa_balance"] == 6000
        assert totals["pension_balance"] == 30000

    def test_explicit_maps_to_overrides_type(self):
        accounts = [
            {"name": "Chase Savings", "type": "savings", "balance": 5000, "maps_to": "emergency_fund"},
        ]
        totals = _aggregate_accounts({"accounts": accounts})
        assert totals["emergency_fund"] == 5000
        assert "general_savings" not in totals

    def test_multiple_accounts_same_field_summed(self):
        accounts = [
            {"name": "Monzo Current", "type": "current", "balance": 1000},
            {"name": "Joint Current", "type": "current", "balance": 500},
        ]
        totals = _aggregate_accounts({"accounts": accounts})
        assert totals["general_savings"] == 1500

    def test_unknown_type_falls_back(self):
        accounts = [{"name": "Unknown", "type": "exotic", "balance": 100}]
        totals = _aggregate_accounts({"accounts": accounts})
        assert totals["general_savings"] == 100

    def test_zero_balance_skipped(self):
        accounts = [
            {"name": "Empty", "type": "current", "balance": 0},
            {"name": "Real", "type": "current", "balance": 200},
        ]
        totals = _aggregate_accounts({"accounts": accounts})
        assert totals["general_savings"] == 200

    def test_lisa_type_routed(self):
        accounts = [{"name": "LISA", "type": "lisa", "balance": 12000}]
        totals = _aggregate_accounts({"accounts": accounts})
        assert totals["lisa_balance"] == 12000

    def test_stocks_and_shares_isa_routed(self):
        accounts = [{"name": "T212", "type": "stocks_and_shares_isa", "balance": 8000}]
        totals = _aggregate_accounts({"accounts": accounts})
        assert totals["isa_balance"] == 8000


# ---------------------------------------------------------------------------
# normalise_profile integration with accounts
# ---------------------------------------------------------------------------

class TestNormaliseProfileWithAccounts:
    def test_accounts_replace_savings_fields(self):
        profile = _base_profile(accounts=[
            {"name": "Chase EF", "type": "easy_access", "balance": 6000, "maps_to": "emergency_fund"},
            {"name": "T212 ISA", "type": "stocks_and_shares_isa", "balance": 9000},
        ])
        normalised = normalise_profile(profile)
        assert normalised["savings"]["emergency_fund"] == 6000
        assert normalised["savings"]["isa_balance"] == 9000

    def test_accounts_override_existing_savings_value(self):
        profile = _base_profile()
        profile["savings"]["isa_balance"] = 1234  # stale direct value
        profile["accounts"] = [
            {"name": "Real ISA", "type": "isa", "balance": 9999},
        ]
        normalised = normalise_profile(profile)
        assert normalised["savings"]["isa_balance"] == 9999
        assert "isa_balance" in normalised["savings"]["_account_overridden_fields"]

    def test_no_accounts_keeps_direct_savings(self):
        profile = _base_profile()
        profile["savings"]["emergency_fund"] = 5000
        profile["savings"]["isa_balance"] = 7000
        normalised = normalise_profile(profile)
        assert normalised["savings"]["emergency_fund"] == 5000
        assert normalised["savings"]["isa_balance"] == 7000
        assert "_account_aggregated_fields" not in normalised["savings"]

    def test_unmapped_savings_fields_untouched(self):
        profile = _base_profile()
        profile["savings"]["pension_balance"] = 50000  # no pension account
        profile["accounts"] = [
            {"name": "ISA", "type": "isa", "balance": 6000},
        ]
        normalised = normalise_profile(profile)
        assert normalised["savings"]["pension_balance"] == 50000  # untouched
        assert normalised["savings"]["isa_balance"] == 6000

    def test_total_assets_reflects_account_aggregation(self):
        profile = _base_profile(accounts=[
            {"name": "Current", "type": "current", "balance": 1000},
            {"name": "ISA", "type": "isa", "balance": 5000},
            {"name": "Pension", "type": "pension", "balance": 20000},
        ])
        normalised = normalise_profile(profile)
        # 1000 (general) + 5000 (isa) + 0 (ef/lisa) + 20000 (pension) + 0 (other)
        assert normalised["savings"]["_total_assets"] == 26000

    def test_aggregated_fields_recorded(self):
        profile = _base_profile(accounts=[
            {"name": "Current", "type": "current", "balance": 100},
            {"name": "ISA", "type": "isa", "balance": 200},
        ])
        normalised = normalise_profile(profile)
        agg = normalised["savings"]["_account_aggregated_fields"]
        assert "general_savings" in agg
        assert "isa_balance" in agg


# ---------------------------------------------------------------------------
# Validator integration
# ---------------------------------------------------------------------------

class TestAccountValidation:
    def test_negative_balance_is_error(self, assumptions):
        from engine.validator import Severity, validate_profile
        profile = normalise_profile(_base_profile(accounts=[
            {"name": "Bad", "type": "current", "balance": -50},
        ]))
        flags = validate_profile(profile, assumptions)
        errors = [f for f in flags if f.field.startswith("accounts[")]
        assert any(f.severity == Severity.ERROR for f in errors)

    def test_unknown_type_warning(self, assumptions):
        from engine.validator import Severity, validate_profile
        profile = normalise_profile(_base_profile(accounts=[
            {"name": "Crypto pot", "type": "shitcoin", "balance": 100},
        ]))
        flags = validate_profile(profile, assumptions)
        warnings = [
            f for f in flags
            if f.field.startswith("accounts[") and f.severity == Severity.WARNING
        ]
        assert len(warnings) >= 1

    def test_unknown_type_with_maps_to_no_warning(self, assumptions):
        from engine.validator import Severity, validate_profile
        profile = normalise_profile(_base_profile(accounts=[
            {"name": "Custom", "type": "shitcoin", "balance": 100, "maps_to": "other_investments"},
        ]))
        flags = validate_profile(profile, assumptions)
        type_warnings = [
            f for f in flags
            if "type" in f.field and f.severity == Severity.WARNING
        ]
        assert len(type_warnings) == 0

    def test_missing_name_warning(self, assumptions):
        from engine.validator import Severity, validate_profile
        profile = normalise_profile(_base_profile(accounts=[
            {"type": "current", "balance": 100},
        ]))
        flags = validate_profile(profile, assumptions)
        name_flags = [f for f in flags if f.field == "accounts[0].name"]
        assert any(f.severity == Severity.WARNING for f in name_flags)

    def test_override_emits_info(self, assumptions):
        from engine.validator import Severity, validate_profile
        profile = _base_profile()
        profile["savings"]["isa_balance"] = 1234
        profile["accounts"] = [{"name": "Real ISA", "type": "isa", "balance": 9999}]
        normalised = normalise_profile(profile)
        flags = validate_profile(normalised, assumptions)
        info_flags = [
            f for f in flags
            if f.field == "savings" and f.severity == Severity.INFO
        ]
        assert any("Account aggregation overrode" in f.message for f in info_flags)

    def test_accounts_not_list_is_error(self, assumptions):
        from engine.validator import Severity, validate_profile
        profile = normalise_profile(_base_profile())
        profile["accounts"] = "not a list"
        flags = validate_profile(profile, assumptions)
        assert any(f.field == "accounts" and f.severity == Severity.ERROR for f in flags)

    def test_no_accounts_no_validation_noise(self, assumptions, sample_profile):
        from engine.validator import validate_profile
        # sample_profile now has accounts that match savings exactly,
        # so override INFO should NOT fire
        flags = validate_profile(sample_profile, assumptions)
        override_flags = [
            f for f in flags
            if f.field == "savings" and "overrode" in f.message
        ]
        assert len(override_flags) == 0
