"""Tests for the bank CSV import module (v5.2-01)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from engine.import_csv import (
    BANK_FORMATS,
    ImportCsvError,
    Transaction,
    _detect_format,
    _normalise_merchant,
    _parse_amount,
    _parse_date,
    _score_match,
    aggregate_to_expenses,
    categorise_transactions,
    detect_income_transactions,
    detect_recurring_transactions,
    import_bank_csv,
    load_category_rules,
    parse_csv,
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
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 400}})
        merged = merge_bank_data(profile, bank)
        # Bank value (400) > profile value (250) → bank wins
        assert merged["expenses"]["living"]["groceries_monthly"] == 400

    def test_merge_keeps_higher_profile_value(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 100}})
        merged = merge_bank_data(profile, bank)
        # Profile value (250) > bank value (100) → profile wins
        assert merged["expenses"]["living"]["groceries_monthly"] == 250

    def test_merge_override_replaces_value(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 100}})
        merged = merge_bank_data(profile, bank, override=True)
        assert merged["expenses"]["living"]["groceries_monthly"] == 100

    def test_merge_adds_new_subcategory(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"subscriptions_monthly": 25}})
        merged = merge_bank_data(profile, bank)
        assert merged["expenses"]["living"]["subscriptions_monthly"] == 25

    def test_merge_adds_new_category(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"transport": {"fuel_monthly": 80}})
        merged = merge_bank_data(profile, bank)
        assert merged["expenses"]["transport"]["fuel_monthly"] == 80

    def test_merge_renormalises_totals(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 500}})
        merged = merge_bank_data(profile, bank)
        # Totals should reflect new groceries figure
        assert merged["expenses"]["_total_monthly"] == 1200 + 500

    def test_merge_does_not_mutate_input(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        original_groceries = profile["expenses"]["living"]["groceries_monthly"]
        bank = self._bank_result(expenses={"living": {"groceries_monthly": 999}})
        merge_bank_data(profile, bank)
        assert profile["expenses"]["living"]["groceries_monthly"] == original_groceries

    def test_merge_infers_income_when_missing(self):
        from engine.loader import _normalise_profile
        base = self._base_profile()
        base["income"] = {}  # no salary specified
        profile = _normalise_profile(base)
        bank = self._bank_result(income_txns=[
            {"date": "2026-03-05", "description": "SALARY ACME", "amount": 3000.00},
        ])
        merged = merge_bank_data(profile, bank)
        assert merged["income"]["primary_gross_annual"] == 36000.00
        assert merged["_bank_import"]["income_inferred"] is not None

    def test_merge_does_not_overwrite_existing_income(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
        bank = self._bank_result(income_txns=[
            {"date": "2026-03-05", "description": "SALARY ACME", "amount": 5000.00},
        ])
        merged = merge_bank_data(profile, bank)
        # Profile already had 50000, bank doesn't override
        assert merged["income"]["primary_gross_annual"] == 50000
        assert merged["_bank_import"]["income_inferred"] is None

    def test_merge_attaches_bank_import_metadata(self):
        from engine.loader import _normalise_profile
        profile = _normalise_profile(self._base_profile())
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
