"""Tests for the bank CSV import module (v5.2-01)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from engine.import_csv import (
    BANK_FORMATS,
    ImportCsvError,
    Transaction,
    _assess_income_regularity_from_amounts,
    _classify_cadence,
    _detect_format,
    _is_known_subscription_merchant,
    _normalise_merchant,
    _parse_amount,
    _parse_date,
    _parse_payment_method,
    _score_match,
    aggregate_to_expenses,
    categorise_transactions,
    detect_committed_outflows,
    detect_income_transactions,
    detect_recurring_transactions,
    detect_subscriptions,
    import_bank_csv,
    load_category_rules,
    parse_csv,
    verify_income,
)
from engine.loader import merge_bank_data

# ---------------------------------------------------------------------------
# Sample CSV writers — keep tests self-contained, no fixture files
# ---------------------------------------------------------------------------

MONZO_CSV = """Date,Time,Type,Name,Emoji,Category,Amount,Currency,Local amount,Local currency,Notes and #tags,Address,Receipt,Description,Category split,Money Out,Money In
01/03/2026,08:30:00,Card payment,Tesco,🛒,Groceries,-45.20,GBP,-45.20,GBP,,,,,,-45.20,
03/03/2026,12:15:00,Card payment,Pret a Manger,☕,Eating out,-8.50,GBP,-8.50,GBP,,,,,,-8.50,
05/03/2026,09:00:00,Faster payment,SALARY ACME LTD,💰,Income,2500.00,GBP,2500.00,GBP,,,,,,,2500.00
10/03/2026,14:00:00,Direct debit,Octopus Energy,⚡,Bills,-95.00,GBP,-95.00,GBP,,,,,,-95.00,
15/03/2026,18:30:00,Card payment,Netflix,📺,Entertainment,-12.99,GBP,-12.99,GBP,,,,,,-12.99,
20/03/2026,10:00:00,Direct debit,Council Tax,🏛,Bills,-150.00,GBP,-150.00,GBP,,,,,,-150.00,
"""

LLOYDS_CSV = """Transaction Date,Transaction Type,Sort Code,Account Number,Transaction Description,Debit Amount,Credit Amount,Balance
01/03/2026,DEB,'30-00-00,12345678,SAINSBURYS GROCERIES,52.30,,1947.70
05/03/2026,FPI,'30-00-00,12345678,SALARY MARCH,,2500.00,4447.70
10/03/2026,DD,'30-00-00,12345678,BRITISH GAS,85.00,,4362.70
"""

NATIONWIDE_CSV = """Date,Transaction type,Description,Paid out,Paid in,Balance
01 Mar 2026,Visa,WAITROSE GROCERIES,£68.40,,£1900.00
05 Mar 2026,FP,EMPLOYER PAYROLL,,£2500.00,£4400.00
"""


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

class TestFormatDetection:
    def test_monzo_detected(self):
        headers = ["Date", "Time", "Type", "Name", "Emoji", "Category", "Amount", "Currency"]
        fmt = _detect_format(headers)
        assert fmt is not None
        assert fmt.name == "monzo"

    def test_lloyds_detected(self):
        headers = [
            "Transaction Date", "Transaction Type", "Sort Code", "Account Number",
            "Transaction Description", "Debit Amount", "Credit Amount", "Balance",
        ]
        fmt = _detect_format(headers)
        assert fmt is not None
        assert fmt.name == "lloyds"

    def test_nationwide_detected(self):
        headers = ["Date", "Transaction type", "Description", "Paid out", "Paid in", "Balance"]
        fmt = _detect_format(headers)
        assert fmt is not None
        assert fmt.name == "nationwide"

    def test_unknown_format_returns_none(self):
        headers = ["foo", "bar", "baz"]
        assert _detect_format(headers) is None

    def test_all_formats_have_unique_names(self):
        names = [f.name for f in BANK_FORMATS]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Date and amount parsing
# ---------------------------------------------------------------------------

class TestParsing:
    def test_parse_date_uk_slash(self):
        assert _parse_date("01/03/2026", ("%d/%m/%Y",)) == date(2026, 3, 1)

    def test_parse_date_iso(self):
        assert _parse_date("2026-03-01", ("%Y-%m-%d",)) == date(2026, 3, 1)

    def test_parse_date_text_month(self):
        assert _parse_date("01 Mar 2026", ("%d %b %Y",)) == date(2026, 3, 1)

    def test_parse_date_falls_through_formats(self):
        assert _parse_date("01/03/2026", ("%Y-%m-%d", "%d/%m/%Y")) == date(2026, 3, 1)

    def test_parse_date_empty_raises(self):
        with pytest.raises(ValueError):
            _parse_date("", ("%d/%m/%Y",))

    def test_parse_amount_basic(self):
        assert _parse_amount("12.50") == 12.50

    def test_parse_amount_with_pound(self):
        assert _parse_amount("£12.50") == 12.50

    def test_parse_amount_with_comma(self):
        assert _parse_amount("1,234.56") == 1234.56

    def test_parse_amount_negative(self):
        assert _parse_amount("-12.50") == -12.50

    def test_parse_amount_parentheses_negative(self):
        assert _parse_amount("(12.50)") == -12.50

    def test_parse_amount_dr_suffix(self):
        assert _parse_amount("12.50 DR") == -12.50

    def test_parse_amount_cr_suffix(self):
        assert _parse_amount("12.50 CR") == 12.50

    def test_parse_amount_empty(self):
        assert _parse_amount("") == 0.0
        assert _parse_amount("   ") == 0.0


# ---------------------------------------------------------------------------
# End-to-end CSV parsing
# ---------------------------------------------------------------------------

class TestParseCsv:
    def test_parse_monzo_csv(self, tmp_path: Path):
        f = tmp_path / "monzo.csv"
        f.write_text(MONZO_CSV, encoding="utf-8")
        txns = parse_csv(f)
        assert len(txns) == 6
        assert txns[0].bank == "monzo"
        assert txns[0].txn_date == date(2026, 3, 1)
        assert txns[0].description == "Tesco"
        assert txns[0].amount == -45.20
        # Salary credit
        salary = next(t for t in txns if "SALARY" in t.description)
        assert salary.amount == 2500.00

    def test_parse_lloyds_csv(self, tmp_path: Path):
        f = tmp_path / "lloyds.csv"
        f.write_text(LLOYDS_CSV, encoding="utf-8")
        txns = parse_csv(f)
        assert len(txns) == 3
        assert txns[0].bank == "lloyds"
        assert txns[0].amount == -52.30  # debit becomes negative
        assert txns[1].amount == 2500.00  # credit stays positive

    def test_parse_nationwide_csv(self, tmp_path: Path):
        f = tmp_path / "nationwide.csv"
        f.write_text(NATIONWIDE_CSV, encoding="utf-8")
        txns = parse_csv(f)
        assert len(txns) == 2
        assert txns[0].bank == "nationwide"
        assert txns[0].amount == -68.40
        assert txns[1].amount == 2500.00

    def test_parse_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ImportCsvError, match="not found"):
            parse_csv(tmp_path / "nope.csv")

    def test_parse_unknown_format_raises(self, tmp_path: Path):
        f = tmp_path / "weird.csv"
        f.write_text("foo,bar,baz\n1,2,3\n", encoding="utf-8")
        with pytest.raises(ImportCsvError, match="Unrecognised"):
            parse_csv(f)


# ---------------------------------------------------------------------------
# Categorisation
# ---------------------------------------------------------------------------

class TestCategorisation:
    def test_categorise_groceries(self):
        rules = {"living": {"groceries_monthly": ["tesco", "sainsbury"]}}
        txns = [
            Transaction(date(2026, 3, 1), "Tesco", -45.20, "monzo"),
            Transaction(date(2026, 3, 2), "Sainsbury's", -32.10, "monzo"),
        ]
        categorise_transactions(txns, rules)
        assert all(t.category == "living" for t in txns)
        assert all(t.sub_category == "groceries_monthly" for t in txns)

    def test_categorise_skips_inflows(self):
        rules = {"living": {"groceries_monthly": ["tesco"]}}
        txns = [Transaction(date(2026, 3, 1), "Tesco refund", 5.00, "monzo")]
        categorise_transactions(txns, rules)
        assert txns[0].category is None

    def test_categorise_first_match_wins(self):
        rules = {
            "living": {"groceries_monthly": ["tesco"]},
            "transport": {"fuel_monthly": ["tesco fuel"]},
        }
        # "tesco" matches before "tesco fuel" in iteration order
        txns = [Transaction(date(2026, 3, 1), "Tesco Fuel Watford", -50.00, "monzo")]
        categorise_transactions(txns, rules)
        # First rule wins — depends on dict iteration which is insertion-ordered
        assert txns[0].category == "living"

    def test_uncategorised_left_alone(self):
        rules = {"living": {"groceries_monthly": ["tesco"]}}
        txns = [Transaction(date(2026, 3, 1), "Random merchant", -10.00, "monzo")]
        categorise_transactions(txns, rules)
        assert txns[0].category is None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

class TestAggregation:
    def test_aggregate_basic(self):
        txns = [
            Transaction(date(2026, 3, 1), "Tesco", -50.00, "monzo",
                        category="living", sub_category="groceries_monthly"),
            Transaction(date(2026, 3, 15), "Tesco", -50.00, "monzo",
                        category="living", sub_category="groceries_monthly"),
        ]
        # Span ~2 weeks → infer 1 month
        result = aggregate_to_expenses(txns)
        assert result["living"]["groceries_monthly"] == 100.00

    def test_aggregate_normalises_to_monthly(self):
        # 3 months of data, £150 total → £50/mo
        txns = [
            Transaction(date(2026, 1, 1), "Tesco", -50.00, "monzo",
                        category="living", sub_category="groceries_monthly"),
            Transaction(date(2026, 4, 1), "Tesco", -100.00, "monzo",
                        category="living", sub_category="groceries_monthly"),
        ]
        result = aggregate_to_expenses(txns)
        # Span ~90 days → 3 months → 150/3 = 50
        assert result["living"]["groceries_monthly"] == 50.00

    def test_aggregate_uncategorised_to_misc(self):
        txns = [
            Transaction(date(2026, 3, 1), "Mystery merchant", -30.00, "monzo"),
        ]
        result = aggregate_to_expenses(txns, months=1)
        assert result["other"]["miscellaneous_monthly"] == 30.00

    def test_aggregate_skips_inflows(self):
        txns = [
            Transaction(date(2026, 3, 1), "Salary", 2500.00, "monzo"),
        ]
        result = aggregate_to_expenses(txns, months=1)
        assert result == {}

    def test_aggregate_explicit_months_override(self):
        txns = [
            Transaction(date(2026, 3, 1), "Tesco", -120.00, "monzo",
                        category="living", sub_category="groceries_monthly"),
        ]
        result = aggregate_to_expenses(txns, months=3)
        assert result["living"]["groceries_monthly"] == 40.00


# ---------------------------------------------------------------------------
# Category rules
# ---------------------------------------------------------------------------

class TestCategoryRules:
    def test_load_default_rules(self):
        rules = load_category_rules()
        assert "housing" in rules
        assert "living" in rules
        assert "groceries_monthly" in rules["living"]

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ImportCsvError, match="not found"):
            load_category_rules(tmp_path / "nope.yaml")


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_import_bank_csv_full_pipeline(self, tmp_path: Path):
        f = tmp_path / "monzo.csv"
        f.write_text(MONZO_CSV, encoding="utf-8")
        result = import_bank_csv(f)

        assert result["summary"]["transactions_parsed"] == 6
        assert result["summary"]["inflow_count"] == 1
        assert result["summary"]["outflow_count"] == 5
        assert result["summary"]["bank"] == "monzo"
        assert "average_confidence" in result["summary"]
        assert result["summary"]["average_confidence"] > 0

        # Tesco should land in living.groceries_monthly
        expenses = result["expenses"]
        assert "living" in expenses
        assert expenses["living"]["groceries_monthly"] >= 45.20

        # Octopus → utilities
        assert "housing" in expenses
        assert expenses["housing"]["utilities_monthly"] >= 95.00

        # Council tax
        assert expenses["housing"]["council_tax_monthly"] >= 150.00

        # Netflix → subscriptions
        assert expenses["living"]["subscriptions_monthly"] >= 12.99

        # v5.2-02: detection results
        assert "income_transactions" in result
        assert len(result["income_transactions"]) == 1
        assert "SALARY" in result["income_transactions"][0]["description"]
        assert "recurring_transactions" in result


# ---------------------------------------------------------------------------
# v5.2-02: Confidence scoring and detection helpers
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    def test_exact_match_high_confidence(self):
        rules = {"living": {"subscriptions_monthly": ["netflix"]}}
        txns = [Transaction(date(2026, 3, 1), "Netflix", -12.99, "monzo")]
        categorise_transactions(txns, rules)
        assert txns[0].confidence == 1.0

    def test_prefix_match_confidence(self):
        rules = {"living": {"groceries_monthly": ["sainsbury"]}}
        txns = [Transaction(date(2026, 3, 1), "Sainsburys London", -45.20, "monzo")]
        categorise_transactions(txns, rules)
        assert txns[0].confidence == 0.9

    def test_word_boundary_match_confidence(self):
        rules = {"living": {"groceries_monthly": ["tesco"]}}
        txns = [Transaction(date(2026, 3, 1), "Card payment Tesco Watford", -45.20, "monzo")]
        categorise_transactions(txns, rules)
        assert txns[0].confidence == 0.8

    def test_short_keyword_lower_confidence(self):
        rules = {"transport": {"public_transport_monthly": ["tfl"]}}
        txns = [Transaction(date(2026, 3, 1), "Card payment TfL Charge", -5.00, "monzo")]
        categorise_transactions(txns, rules)
        # 'tfl' is len 3 and not at the start → 0.5
        assert txns[0].confidence == 0.5

    def test_score_match_helper(self):
        assert _score_match("netflix", "netflix") == 1.0
        assert _score_match("Netflix", "netflix") == 1.0
        assert _score_match("Sainsburys", "sainsbury") == 0.9
        assert _score_match("Card Payment Tesco", "tesco") == 0.8
        assert _score_match("XYZ TfL XYZ", "tfl") == 0.5

    def test_uncategorised_has_no_confidence(self):
        rules = {"living": {"groceries_monthly": ["tesco"]}}
        txns = [Transaction(date(2026, 3, 1), "Random merchant", -10.00, "monzo")]
        categorise_transactions(txns, rules)
        assert txns[0].confidence is None


class TestIncomeDetection:
    def test_detects_salary_credit(self):
        txns = [
            Transaction(date(2026, 3, 5), "SALARY ACME LTD", 2500.00, "monzo"),
            Transaction(date(2026, 3, 1), "Tesco", -45.20, "monzo"),
        ]
        income = detect_income_transactions(txns)
        assert len(income) == 1
        assert income[0].description == "SALARY ACME LTD"

    def test_detects_payroll_keyword(self):
        txns = [Transaction(date(2026, 3, 5), "EMPLOYER PAYROLL", 3000.00, "monzo")]
        income = detect_income_transactions(txns)
        assert len(income) == 1

    def test_ignores_small_credits(self):
        txns = [Transaction(date(2026, 3, 5), "Salary refund", 50.00, "monzo")]
        income = detect_income_transactions(txns)
        assert income == []

    def test_ignores_outflows(self):
        txns = [Transaction(date(2026, 3, 5), "SALARY DEDUCTION", -500.00, "monzo")]
        income = detect_income_transactions(txns)
        assert income == []

    def test_ignores_non_salary_credits(self):
        txns = [Transaction(date(2026, 3, 5), "Birthday gift transfer", 1000.00, "monzo")]
        income = detect_income_transactions(txns)
        assert income == []

    def test_min_amount_threshold(self):
        txns = [Transaction(date(2026, 3, 5), "SALARY part-time", 400.00, "monzo")]
        # Default threshold is 500
        assert detect_income_transactions(txns) == []
        # Lower threshold catches it
        assert len(detect_income_transactions(txns, min_amount=300)) == 1


class TestRecurringDetection:
    def test_detects_monthly_subscription(self):
        txns = [
            Transaction(date(2026, 1, 15), "Netflix", -12.99, "monzo"),
            Transaction(date(2026, 2, 15), "Netflix", -12.99, "monzo"),
            Transaction(date(2026, 3, 15), "Netflix", -12.99, "monzo"),
        ]
        recurring = detect_recurring_transactions(txns)
        assert len(recurring) == 1
        assert recurring[0]["occurrences"] == 3
        assert recurring[0]["mean_amount"] == 12.99

    def test_ignores_single_occurrence(self):
        txns = [Transaction(date(2026, 3, 15), "Netflix", -12.99, "monzo")]
        recurring = detect_recurring_transactions(txns)
        assert recurring == []

    def test_filters_high_variance_amounts(self):
        # Amounts vary too much to be a fixed subscription
        txns = [
            Transaction(date(2026, 1, 15), "Tesco", -45.00, "monzo"),
            Transaction(date(2026, 2, 15), "Tesco", -90.00, "monzo"),
            Transaction(date(2026, 3, 15), "Tesco", -20.00, "monzo"),
        ]
        recurring = detect_recurring_transactions(txns)
        assert recurring == []  # variance > 10% of mean

    def test_normalises_descriptions(self):
        # Same merchant, slightly different descriptions (date suffixes)
        txns = [
            Transaction(date(2026, 1, 15), "SPOTIFY UK 0123 LONDON", -9.99, "monzo"),
            Transaction(date(2026, 2, 15), "SPOTIFY UK 4567 LONDON", -9.99, "monzo"),
        ]
        recurring = detect_recurring_transactions(txns)
        assert len(recurring) == 1
        assert recurring[0]["occurrences"] == 2

    def test_ignores_inflows(self):
        txns = [
            Transaction(date(2026, 1, 5), "Salary", 2500.00, "monzo"),
            Transaction(date(2026, 2, 5), "Salary", 2500.00, "monzo"),
        ]
        # Salary is inflow → not in recurring outflows
        recurring = detect_recurring_transactions(txns)
        assert recurring == []

    def test_normalise_merchant_strips_noise(self):
        assert _normalise_merchant("TESCO STORES 1234 LONDON 03MAR") == \
               _normalise_merchant("TESCO STORES 5678 LONDON 17MAR")


# ---------------------------------------------------------------------------
# v5.2-02: merge_bank_data
# ---------------------------------------------------------------------------

class TestMergeBankData:
    def _base_profile(self) -> dict:
        return {
            "personal": {"name": "Test", "age": 30, "retirement_age": 67,
                         "dependents": 0, "risk_profile": "moderate",
                         "employment_type": "employed"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {
                "housing": {"rent_monthly": 1200},
                "living": {"groceries_monthly": 250},
            },
            "savings": {
                "emergency_fund": 5000,
                "pension_balance": 10000,
                "pension_personal_contribution_pct": 0.05,
                "pension_employer_contribution_pct": 0.03,
            },
            "debts": [],
            "goals": [],
        }

    def _bank_result(self, expenses=None, income_txns=None, recurring=None):
        return {
            "expenses": expenses or {},
            "income_transactions": income_txns or [],
            "recurring_transactions": recurring or [],
            "summary": {"average_confidence": 0.85, "bank": "monzo"},
        }

    def test_merge_takes_max_by_default(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 400}})
        merged = merge_bank_data(profile, bank)
        # Bank value (400) > profile value (250) → bank wins
        assert merged["expenses"]["living"]["groceries_monthly"] == 400

    def test_merge_keeps_higher_profile_value(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 100}})
        merged = merge_bank_data(profile, bank)
        # Profile value (250) > bank value (100) → profile wins
        assert merged["expenses"]["living"]["groceries_monthly"] == 250

    def test_merge_override_replaces_value(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 100}})
        merged = merge_bank_data(profile, bank, override=True)
        assert merged["expenses"]["living"]["groceries_monthly"] == 100

    def test_merge_adds_new_subcategory(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"subscriptions_monthly": 25}})
        merged = merge_bank_data(profile, bank)
        assert merged["expenses"]["living"]["subscriptions_monthly"] == 25

    def test_merge_adds_new_category(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"transport": {"fuel_monthly": 80}})
        merged = merge_bank_data(profile, bank)
        assert merged["expenses"]["transport"]["fuel_monthly"] == 80

    def test_merge_renormalises_totals(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 500}})
        merged = merge_bank_data(profile, bank)
        # Totals should reflect new groceries figure
        assert merged["expenses"]["_total_monthly"] == 1200 + 500

    def test_merge_does_not_mutate_input(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        original_groceries = profile["expenses"]["living"]["groceries_monthly"]
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 999}})
        merge_bank_data(profile, bank)
        assert profile["expenses"]["living"]["groceries_monthly"] == original_groceries

    def test_merge_infers_income_when_missing(self):
        from engine.loader import normalise_profile
        base = self._base_profile()
        base["income"] = {}  # no salary specified
        profile = normalise_profile(base)
        bank = self._bank_result(income_txns=[
            {"date": "2026-03-05", "description": "SALARY ACME", "amount": 3000.00},
        ])
        merged = merge_bank_data(profile, bank)
        assert merged["income"]["primary_gross_annual"] == 36000.00
        assert merged["_bank_import"]["income_inferred"] is not None

    def test_merge_does_not_overwrite_existing_income(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(income_txns=[
            {"date": "2026-03-05", "description": "SALARY ACME", "amount": 5000.00},
        ])
        merged = merge_bank_data(profile, bank)
        # Profile already had 50000, bank doesn't override
        assert merged["income"]["primary_gross_annual"] == 50000
        assert merged["_bank_import"]["income_inferred"] is None

    def test_merge_attaches_bank_import_metadata(self):
        from engine.loader import normalise_profile
        profile = normalise_profile(self._base_profile())
        bank = self._bank_result(
            expenses={"living": {"groceries_monthly": 400}},
            recurring=[{"description": "Netflix", "monthly_estimate": 12.99}],
        )
        merged = merge_bank_data(profile, bank)
        assert "_bank_import" in merged
        bi = merged["_bank_import"]
        assert "summary" in bi
        assert "expense_fields_overridden" in bi or "expense_fields_supplemented" in bi
        assert len(bi["recurring_transactions"]) == 1


# ---------------------------------------------------------------------------
# v5.2-06: Subscription detection
# ---------------------------------------------------------------------------

def _monthly_txns(name: str, amount: float, months: int = 4) -> list[Transaction]:
    """Build N consecutive monthly outflow transactions for a merchant."""
    return [
        Transaction(date(2026, 1 + i, 15), name, -amount, "monzo")
        for i in range(months)
    ]


class TestClassifyCadence:
    def test_monthly_cadence_recognised(self):
        assert _classify_cadence(30) == "monthly"
        assert _classify_cadence(28) == "monthly"
        assert _classify_cadence(34) == "monthly"

    def test_annual_cadence_recognised(self):
        assert _classify_cadence(365) == "annual"
        assert _classify_cadence(355) == "annual"

    def test_weekly_not_classified(self):
        assert _classify_cadence(7) is None

    def test_quarterly_not_classified(self):
        assert _classify_cadence(90) is None

    def test_zero_returns_none(self):
        assert _classify_cadence(0) is None


class TestKnownSubscriptionMerchant:
    def test_netflix_match(self):
        assert _is_known_subscription_merchant("NETFLIX.COM 0123", "netflix com") is True

    def test_spotify_match(self):
        assert _is_known_subscription_merchant("SPOTIFY UK", "spotify uk") is True

    def test_supermarket_not_match(self):
        assert _is_known_subscription_merchant("TESCO STORES", "tesco stores") is False

    def test_council_tax_not_match(self):
        assert _is_known_subscription_merchant("Council Tax", "council tax") is False


class TestDetectSubscriptions:
    def test_known_monthly_subscription_detected(self):
        txns = _monthly_txns("Netflix", 12.99, months=4)
        subs = detect_subscriptions(txns)
        assert len(subs) == 1
        assert subs[0]["merchant_key"] == "netflix"
        assert subs[0]["frequency"] == "monthly"
        assert subs[0]["monthly_cost"] == 12.99
        assert subs[0]["known_merchant"] is True
        assert subs[0]["price_changed"] is False

    def test_groceries_not_classified_as_subscription(self):
        # Recurring monthly grocery shop at the same merchant — not a sub.
        txns = _monthly_txns("TESCO STORES", 200.00, months=4)
        subs = detect_subscriptions(txns)
        assert subs == []

    def test_price_increase_detected(self):
        txns = [
            Transaction(date(2026, 1, 15), "Netflix", -10.99, "monzo"),
            Transaction(date(2026, 2, 15), "Netflix", -10.99, "monzo"),
            Transaction(date(2026, 3, 15), "Netflix", -12.99, "monzo"),
            Transaction(date(2026, 4, 15), "Netflix", -12.99, "monzo"),
        ]
        subs = detect_subscriptions(txns)
        assert len(subs) == 1
        sub = subs[0]
        assert sub["price_changed"] is True
        assert sub["previous_amount"] == 10.99
        assert sub["current_amount"] == 12.99
        assert sub["monthly_cost"] == 12.99  # uses latest

    def test_annual_subscription_classified(self):
        # Two charges roughly 12 months apart for a known sub
        txns = [
            Transaction(date(2025, 3, 1), "Amazon Prime", -95.00, "monzo"),
            Transaction(date(2026, 3, 1), "Amazon Prime", -95.00, "monzo"),
        ]
        subs = detect_subscriptions(txns)
        assert len(subs) == 1
        assert subs[0]["frequency"] == "annual"
        # Annual cost spread monthly: 95/12
        assert subs[0]["monthly_cost"] == round(95 / 12, 2)

    def test_amount_above_range_excluded(self):
        # £600/month rent — way above subscription range, should not classify
        txns = _monthly_txns("Netflix", 600.00, months=4)
        subs = detect_subscriptions(txns)
        assert subs == []

    def test_subscription_category_overrides_unknown_merchant(self):
        # Unknown merchant but already categorised under subscriptions
        txns = []
        for i in range(4):
            t = Transaction(date(2026, 1 + i, 10), "ObscureSaaS Inc", -8.99, "monzo")
            t.category = "living"
            t.sub_category = "subscriptions_monthly"
            txns.append(t)
        subs = detect_subscriptions(txns)
        assert len(subs) == 1
        assert subs[0]["known_merchant"] is False

    def test_weekly_recurring_not_subscription(self):
        # Weekly outflow — too frequent to be a typical sub
        txns = [
            Transaction(date(2026, 1, 7), "Netflix", -12.99, "monzo"),
            Transaction(date(2026, 1, 14), "Netflix", -12.99, "monzo"),
            Transaction(date(2026, 1, 21), "Netflix", -12.99, "monzo"),
            Transaction(date(2026, 1, 28), "Netflix", -12.99, "monzo"),
        ]
        subs = detect_subscriptions(txns)
        assert subs == []

    def test_sorted_by_monthly_cost_descending(self):
        txns = (
            _monthly_txns("Spotify", 9.99, months=3)
            + _monthly_txns("Netflix", 17.99, months=3)
            + _monthly_txns("Disney", 8.99, months=3)
        )
        subs = detect_subscriptions(txns)
        costs = [s["monthly_cost"] for s in subs]
        assert costs == sorted(costs, reverse=True)
        assert subs[0]["merchant_key"] == "netflix"

    def test_inflows_ignored(self):
        txns = [
            Transaction(date(2026, 1, 15), "Netflix Refund", 12.99, "monzo"),
            Transaction(date(2026, 2, 15), "Netflix Refund", 12.99, "monzo"),
        ]
        subs = detect_subscriptions(txns)
        assert subs == []

    def test_import_bank_csv_includes_subscriptions(self, tmp_path):
        csv_path = tmp_path / "monzo.csv"
        csv_path.write_text(
            "Date,Time,Type,Name,Emoji,Category,Amount,Currency,Local amount,"
            "Local currency,Notes and #tags,Address,Receipt,Description,"
            "Category split,Money Out,Money In\n"
            "15/01/2026,08:30:00,Card payment,Netflix,📺,Entertainment,-12.99,"
            "GBP,-12.99,GBP,,,,,,-12.99,\n"
            "15/02/2026,08:30:00,Card payment,Netflix,📺,Entertainment,-12.99,"
            "GBP,-12.99,GBP,,,,,,-12.99,\n"
            "15/03/2026,08:30:00,Card payment,Netflix,📺,Entertainment,-12.99,"
            "GBP,-12.99,GBP,,,,,,-12.99,\n",
            encoding="utf-8",
        )
        result = import_bank_csv(csv_path)
        assert "subscriptions" in result
        assert result["summary"]["subscription_count"] >= 1
        assert result["summary"]["subscription_monthly_total"] >= 12.99


class TestSubscriptionInsight:
    def _profile_with_subs(self, subs):
        from engine.loader import normalise_profile
        from tests.test_import_csv import TestMergeBankData
        base = TestMergeBankData()._base_profile()
        profile = normalise_profile(base)
        profile["_bank_import"] = {
            "summary": {},
            "subscriptions": subs,
            "recurring_transactions": [],
            "expense_fields_overridden": [],
            "expense_fields_supplemented": [],
            "income_inferred": None,
        }
        return profile

    def test_no_subscriptions_returns_empty(self):
        from engine.insights import _subscription_insights
        profile = self._profile_with_subs([])
        cashflow = {"net_income": {"monthly": 3000}}
        assert _subscription_insights(profile, cashflow) == {}

    def test_no_bank_import_returns_empty(self):
        from engine.insights import _subscription_insights
        profile = {"_bank_import": {}}
        cashflow = {"net_income": {"monthly": 3000}}
        assert _subscription_insights(profile, cashflow) == {}

    def test_summary_totals(self):
        from engine.insights import _subscription_insights
        profile = self._profile_with_subs([
            {"name": "Netflix", "monthly_cost": 12.99, "frequency": "monthly", "price_changed": False},
            {"name": "Spotify", "monthly_cost": 9.99, "frequency": "monthly", "price_changed": False},
        ])
        cashflow = {"net_income": {"monthly": 3000}}
        result = _subscription_insights(profile, cashflow)
        assert result["applicable"] is True
        assert result["subscription_count"] == 2
        assert result["monthly_total"] == 22.98
        assert result["annual_total"] == round(22.98 * 12, 2)

    def test_price_change_message_included(self):
        from engine.insights import _subscription_insights
        profile = self._profile_with_subs([
            {
                "name": "Netflix", "monthly_cost": 12.99, "frequency": "monthly",
                "price_changed": True, "previous_amount": 10.99, "current_amount": 12.99,
            },
        ])
        cashflow = {"net_income": {"monthly": 3000}}
        result = _subscription_insights(profile, cashflow)
        assert result["price_changed_count"] == 1
        assert any("Netflix" in m and "10.99" in m for m in result["messages"])

    def test_high_pct_of_income_warning(self):
        from engine.insights import _subscription_insights
        profile = self._profile_with_subs([
            {"name": "BigSub", "monthly_cost": 200.0, "frequency": "monthly", "price_changed": False},
        ])
        cashflow = {"net_income": {"monthly": 3000}}
        result = _subscription_insights(profile, cashflow)
        # 200/3000 = 6.67% > 5% threshold
        assert any("net monthly income" in m for m in result["messages"])

    def test_pct_of_income_skipped_when_no_income(self):
        from engine.insights import _subscription_insights
        profile = self._profile_with_subs([
            {"name": "Netflix", "monthly_cost": 12.99, "frequency": "monthly", "price_changed": False},
        ])
        cashflow = {"net_income": {"monthly": 0}}
        result = _subscription_insights(profile, cashflow)
        assert result["pct_of_net_income"] is None


# ---------------------------------------------------------------------------
# v5.2-07: Payment method parsing and committed outflows
# ---------------------------------------------------------------------------

def _dd_txns(name: str, amount: float, months: int = 3) -> list[Transaction]:
    """Build monthly direct-debit outflow transactions."""
    return [
        Transaction(
            date(2026, 1 + i, 1), name, -amount, "monzo",
            payment_method="direct_debit",
        )
        for i in range(months)
    ]


def _so_txns(name: str, amount: float, months: int = 3) -> list[Transaction]:
    """Build monthly standing-order outflow transactions."""
    return [
        Transaction(
            date(2026, 1 + i, 1), name, -amount, "monzo",
            payment_method="standing_order",
        )
        for i in range(months)
    ]


class TestPaymentMethodParsing:
    def _monzo_fmt(self):
        return next(f for f in BANK_FORMATS if f.name == "monzo")

    def _lloyds_fmt(self):
        return next(f for f in BANK_FORMATS if f.name == "lloyds")

    def _natwest_fmt(self):
        return next(f for f in BANK_FORMATS if f.name == "natwest")

    def test_monzo_direct_debit(self):
        row = {"Type": "Direct debit"}
        assert _parse_payment_method(row, self._monzo_fmt()) == "direct_debit"

    def test_monzo_card_payment(self):
        row = {"Type": "Card payment"}
        assert _parse_payment_method(row, self._monzo_fmt()) == "card"

    def test_monzo_standing_order(self):
        row = {"Type": "Standing order"}
        assert _parse_payment_method(row, self._monzo_fmt()) == "standing_order"

    def test_monzo_unknown_type_returns_none(self):
        row = {"Type": "Pot transfer"}
        assert _parse_payment_method(row, self._monzo_fmt()) is None

    def test_lloyds_dd(self):
        row = {"Transaction Type": "DD"}
        assert _parse_payment_method(row, self._lloyds_fmt()) == "direct_debit"

    def test_lloyds_deb(self):
        row = {"Transaction Type": "DEB"}
        assert _parse_payment_method(row, self._lloyds_fmt()) == "card"

    def test_natwest_d_d(self):
        row = {"Type": "D/D"}
        assert _parse_payment_method(row, self._natwest_fmt()) == "direct_debit"

    def test_natwest_s_o(self):
        row = {"Type": "S/O"}
        assert _parse_payment_method(row, self._natwest_fmt()) == "standing_order"

    def test_no_type_field_returns_none(self):
        barclays = next(f for f in BANK_FORMATS if f.name == "barclays")
        row = {"anything": "value"}
        assert _parse_payment_method(row, barclays) is None

    def test_case_insensitive(self):
        row = {"Type": "DIRECT DEBIT"}
        assert _parse_payment_method(row, self._monzo_fmt()) == "direct_debit"

    def test_monzo_csv_parses_payment_method(self, tmp_path):
        csv_path = tmp_path / "monzo.csv"
        csv_path.write_text(
            "Date,Time,Type,Name,Emoji,Category,Amount,Currency,Local amount,"
            "Local currency,Notes and #tags,Address,Receipt,Description,"
            "Category split,Money Out,Money In\n"
            "01/03/2026,08:30:00,Direct debit,Octopus Energy,,Bills,-95.00,"
            "GBP,-95.00,GBP,,,,,,-95.00,\n",
            encoding="utf-8",
        )
        txns = parse_csv(csv_path)
        assert len(txns) == 1
        assert txns[0].payment_method == "direct_debit"


class TestDetectCommittedOutflows:
    def test_direct_debits_detected(self):
        txns = _dd_txns("British Gas", 85.00, months=3)
        committed = detect_committed_outflows(txns)
        assert len(committed) == 1
        assert committed[0]["payment_method"] == "direct_debit"
        assert committed[0]["monthly_amount"] == 85.00
        assert committed[0]["occurrences"] == 3

    def test_standing_orders_detected(self):
        txns = _so_txns("Landlord Rent", 1100.00, months=3)
        committed = detect_committed_outflows(txns)
        assert len(committed) == 1
        assert committed[0]["payment_method"] == "standing_order"

    def test_card_payments_excluded(self):
        txns = [
            Transaction(date(2026, 1, 15), "Tesco", -45.00, "monzo", payment_method="card"),
            Transaction(date(2026, 2, 15), "Tesco", -45.00, "monzo", payment_method="card"),
            Transaction(date(2026, 3, 15), "Tesco", -45.00, "monzo", payment_method="card"),
        ]
        committed = detect_committed_outflows(txns)
        assert committed == []

    def test_no_payment_method_excluded(self):
        txns = _monthly_txns("Some Service", 50.00, months=3)
        committed = detect_committed_outflows(txns)
        assert committed == []

    def test_single_occurrence_excluded(self):
        txns = _dd_txns("One-off DD", 200.00, months=1)
        committed = detect_committed_outflows(txns)
        assert committed == []

    def test_inflows_excluded(self):
        txns = [
            Transaction(date(2026, 1, 5), "Salary", 2500.00, "monzo", payment_method="transfer"),
            Transaction(date(2026, 2, 5), "Salary", 2500.00, "monzo", payment_method="transfer"),
        ]
        committed = detect_committed_outflows(txns)
        assert committed == []

    def test_mixed_dd_and_card_separates_correctly(self):
        txns = [
            *_dd_txns("Octopus Energy", 95.00, months=3),
            Transaction(date(2026, 1, 15), "Tesco", -45.00, "monzo", payment_method="card"),
            Transaction(date(2026, 2, 15), "Tesco", -45.00, "monzo", payment_method="card"),
        ]
        committed = detect_committed_outflows(txns)
        assert len(committed) == 1
        assert "octopus" in committed[0]["merchant_key"]

    def test_sorted_by_amount_descending(self):
        txns = (
            _dd_txns("Council Tax", 150.00, months=3)
            + _dd_txns("British Gas", 85.00, months=3)
            + _so_txns("Rent", 1100.00, months=3)
        )
        committed = detect_committed_outflows(txns)
        amounts = [c["monthly_amount"] for c in committed]
        assert amounts == sorted(amounts, reverse=True)
        assert committed[0]["monthly_amount"] == 1100.00

    def test_preserves_category_from_categorisation(self):
        txns = _dd_txns("British Gas", 85.00, months=3)
        for t in txns:
            t.category = "housing"
            t.sub_category = "utilities_monthly"
        committed = detect_committed_outflows(txns)
        assert committed[0]["category"] == "housing"
        assert committed[0]["sub_category"] == "utilities_monthly"

    def test_import_bank_csv_includes_committed_outflows(self, tmp_path):
        csv_path = tmp_path / "monzo.csv"
        csv_path.write_text(
            "Date,Time,Type,Name,Emoji,Category,Amount,Currency,Local amount,"
            "Local currency,Notes and #tags,Address,Receipt,Description,"
            "Category split,Money Out,Money In\n"
            "01/01/2026,08:00:00,Direct debit,British Gas,,Bills,-85.00,"
            "GBP,-85.00,GBP,,,,,,-85.00,\n"
            "01/02/2026,08:00:00,Direct debit,British Gas,,Bills,-85.00,"
            "GBP,-85.00,GBP,,,,,,-85.00,\n"
            "01/03/2026,08:00:00,Direct debit,British Gas,,Bills,-85.00,"
            "GBP,-85.00,GBP,,,,,,-85.00,\n",
            encoding="utf-8",
        )
        result = import_bank_csv(csv_path)
        assert "committed_outflows" in result
        assert result["summary"]["committed_outflow_count"] >= 1
        assert result["summary"]["committed_outflow_monthly_total"] >= 85.00


# ---------------------------------------------------------------------------
# v5.2-08: Income verification
# ---------------------------------------------------------------------------

def _salary_txns(amount: float = 2500.0, months: int = 3, desc: str = "SALARY ACME LTD") -> list[Transaction]:
    return [
        Transaction(date(2026, 1 + i, 5), desc, amount, "monzo")
        for i in range(months)
    ]


class TestIncomeRegularity:
    def test_regular_amounts(self):
        assert _assess_income_regularity_from_amounts([2500, 2500, 2500]) == "regular"

    def test_variable_amounts(self):
        assert _assess_income_regularity_from_amounts([2500, 3500, 1800]) == "variable"

    def test_insufficient_data(self):
        assert _assess_income_regularity_from_amounts([2500]) == "insufficient_data"

    def test_empty(self):
        assert _assess_income_regularity_from_amounts([]) == "insufficient_data"

    def test_within_5pct_tolerance(self):
        # 2500 * 1.04 = 2600, within 5%
        assert _assess_income_regularity_from_amounts([2500, 2600, 2550]) == "regular"

    def test_just_outside_5pct(self):
        # mean of [2000, 2500] = 2250; |2500-2250|/2250 = 11.1% → variable
        assert _assess_income_regularity_from_amounts([2000, 2500]) == "variable"


class TestVerifyIncome:
    def test_no_transactions_unverifiable(self):
        result = verify_income([], 50000)
        assert result["match_status"] == "unverifiable"
        assert result["observed_annual"] is None
        assert result["source_count"] == 0

    def test_match_reasonable_net_to_gross_ratio(self):
        # 3500 net/mo * 12 = 42000 net. For 60000 gross, ratio = 0.70 → match
        txns = _salary_txns(amount=3500.0, months=3)
        result = verify_income(txns, 60000)
        assert result["match_status"] == "match"
        assert result["observed_annual"] == 42000.0
        assert result["income_regularity"] == "regular"

    def test_discrepancy_low_observed(self):
        # 1500 net/mo * 12 = 18000. For 60000 gross, ratio = 0.30 → too low
        txns = _salary_txns(amount=1500.0, months=3)
        result = verify_income(txns, 60000)
        assert result["match_status"] == "discrepancy"
        assert any("low" in m for m in result["messages"])

    def test_discrepancy_high_observed(self):
        # 5000 net/mo * 12 = 60000. For 60000 gross, ratio = 1.0 → too high
        txns = _salary_txns(amount=5000.0, months=3)
        result = verify_income(txns, 60000)
        assert result["match_status"] == "discrepancy"
        assert any("exceed" in m for m in result["messages"])

    def test_no_declared_income(self):
        txns = _salary_txns(amount=3000.0, months=3)
        result = verify_income(txns, None)
        assert result["match_status"] == "unverifiable"
        assert result["observed_annual"] == 36000.0
        assert any("No declared income" in m for m in result["messages"])

    def test_multiple_sources_detected(self):
        txns = [
            *_salary_txns(amount=2500.0, months=3, desc="SALARY ACME"),
            *_salary_txns(amount=500.0, months=3, desc="FREELANCE WAGES CLIENT"),
        ]
        result = verify_income(txns, 50000)
        assert result["source_count"] == 2
        assert any("Multiple income sources" in m for m in result["messages"])

    def test_variable_income_flagged(self):
        txns = [
            Transaction(date(2026, 1, 5), "SALARY ACME WAGES", 2500.0, "monzo"),
            Transaction(date(2026, 2, 5), "SALARY ACME WAGES", 3500.0, "monzo"),
            Transaction(date(2026, 3, 5), "SALARY ACME WAGES", 1800.0, "monzo"),
        ]
        result = verify_income(txns, 40000)
        assert result["income_regularity"] == "variable"
        assert any("vary" in m for m in result["messages"])

    def test_accepts_serialised_dicts(self):
        dicts = [
            {"date": "2026-01-05", "description": "SALARY ACME LTD", "amount": 3000.0},
            {"date": "2026-02-05", "description": "SALARY ACME LTD", "amount": 3000.0},
        ]
        result = verify_income(dicts, 50000)
        assert result["match_status"] in ("match", "discrepancy")
        assert result["observed_annual"] == 36000.0

    def test_zero_declared_treated_as_missing(self):
        txns = _salary_txns(amount=3000.0, months=3)
        result = verify_income(txns, 0)
        assert result["match_status"] == "unverifiable"


class TestIncomeVerificationInsight:
    def test_no_bank_import_returns_empty(self):
        from engine.insights import _income_verification_insight
        assert _income_verification_insight({}) == {}

    def test_unverifiable_returns_empty(self):
        from engine.insights import _income_verification_insight
        profile = {"_bank_import": {"income_verification": {"match_status": "unverifiable"}}}
        assert _income_verification_insight(profile) == {}

    def test_match_returns_applicable(self):
        from engine.insights import _income_verification_insight
        profile = {
            "_bank_import": {
                "income_verification": {
                    "match_status": "match",
                    "observed_annual": 42000,
                    "declared_annual": 60000,
                    "income_regularity": "regular",
                    "source_count": 1,
                    "messages": ["Consistent."],
                },
            },
        }
        result = _income_verification_insight(profile)
        assert result["applicable"] is True
        assert result["match_status"] == "match"

    def test_discrepancy_surfaces(self):
        from engine.insights import _income_verification_insight
        profile = {
            "_bank_import": {
                "income_verification": {
                    "match_status": "discrepancy",
                    "observed_annual": 18000,
                    "declared_annual": 60000,
                    "income_regularity": "regular",
                    "source_count": 1,
                    "messages": ["Appears low."],
                },
            },
        }
        result = _income_verification_insight(profile)
        assert result["applicable"] is True
        assert result["match_status"] == "discrepancy"
