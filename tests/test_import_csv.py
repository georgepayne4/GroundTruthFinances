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
    _parse_amount,
    _parse_date,
    aggregate_to_expenses,
    categorise_transactions,
    import_bank_csv,
    load_category_rules,
    parse_csv,
)

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
